"""
Redivis REST query client for CheXpert Plus metadata rows.

Uses POST /queries and GET /queries/{id}/rows (CSV), avoiding Redivis Python
file helpers that can fail on NRP with Arrow stream / timeout errors.
"""

from __future__ import annotations

import os
import re
import time
from io import StringIO
from typing import Any

import pandas as pd
import requests

REDIVIS_API_BASE_URL = "https://redivis.com/api/v1"
REDIVIS_TABLE_REFERENCE = "aimi.chexpert_plus:5yyj:v1_0.df_chexpert_plus_240401:bavj"

IDENTIFIER_COLUMNS = [
    "path_to_image",
    "path_to_dcm",
    "deid_patient_id",
    "patient_report_date_order",
    "section_accession_number",
]

DEMOGRAPHIC_COLUMNS = [
    "age",
    "sex",
    "race",
    "ethnicity",
]

REPORT_COLUMNS = [
    "report",
    "section_narrative",
    "section_clinical_history",
    "section_history",
    "section_comparison",
    "section_technique",
    "section_procedure_comments",
    "section_findings",
    "section_impression",
    "section_end_of_impression",
    "section_summary",
]

SELECTED_REDIVIS_COLUMNS = IDENTIFIER_COLUMNS + DEMOGRAPHIC_COLUMNS + REPORT_COLUMNS


def require_redivis_token() -> str:
    token = os.getenv("REDIVIS_ACCESS_TOKEN") or os.getenv("REDIVIS_API_TOKEN")
    if not token:
        raise RuntimeError(
            "Missing Redivis token. Set REDIVIS_ACCESS_TOKEN or REDIVIS_API_TOKEN."
        )
    return token


def redivis_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""

    normalized = str(value).strip().lower()
    normalized = normalized.replace("\\", "/")
    normalized = re.sub(r"/+", "/", normalized)
    return normalized


def sql_quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def build_train_split_query(row_limit: int) -> str:
    selected_sql = ",\n        ".join(f"`{column}`" for column in SELECTED_REDIVIS_COLUMNS)
    return f"""
    SELECT
        {selected_sql}
    FROM `{REDIVIS_TABLE_REFERENCE}`
    WHERE path_to_dcm IS NOT NULL
      AND split = 'train'
    LIMIT {int(row_limit)}
    """


def build_filtered_redivis_sql(local_dicom_paths: list[str]) -> str:
    selected_sql = ",\n        ".join(f"`{column}`" for column in SELECTED_REDIVIS_COLUMNS)

    like_clauses = [
        f"LOWER(`path_to_dcm`) LIKE {sql_quote('%' + normalize_text(dicom_path))}"
        for dicom_path in local_dicom_paths
        if normalize_text(dicom_path)
    ]

    if not like_clauses:
        raise RuntimeError("No local DICOM paths were available for the Redivis query.")

    where_sql = "\n        OR ".join(like_clauses)

    return f"""
    SELECT
        {selected_sql}
    FROM `{REDIVIS_TABLE_REFERENCE}`
    WHERE
        {where_sql}
    """


def post_redivis_query(headers: dict[str, str], query: str) -> dict[str, Any]:
    response = requests.post(
        f"{REDIVIS_API_BASE_URL}/queries",
        headers=headers,
        json={
            "query": query,
            "timeoutMs": 60000,
        },
        timeout=120,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Redivis query POST failed with HTTP {response.status_code}\n"
            f"Response: {response.text[:4000]}"
        )

    return response.json()


def get_query_id(query_payload: dict[str, Any]) -> str:
    for key in ["id", "queryId", "referenceId"]:
        value = query_payload.get(key)
        if value:
            return str(value)

    uri = str(query_payload.get("uri", ""))
    match = re.search(r"/queries/([^/]+)", uri)
    if match:
        return match.group(1)

    raise RuntimeError(f"Could not determine query id from Redivis response: {query_payload}")


def wait_for_query_completion(
    headers: dict[str, str],
    query_id: str,
    timeout_seconds: int = 600,
) -> None:
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        response = requests.get(
            f"{REDIVIS_API_BASE_URL}/queries/{query_id}",
            headers=headers,
            timeout=120,
        )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Redivis query GET failed with HTTP {response.status_code}\n"
                f"Response: {response.text[:4000]}"
            )

        payload = response.json()
        status = str(payload.get("status", "")).lower()

        if status in {"completed", "succeeded", "success"}:
            return

        if status in {"failed", "error", "cancelled", "canceled"}:
            raise RuntimeError(f"Redivis query failed: {payload}")

        time.sleep(5)

    raise TimeoutError(f"Timed out waiting for Redivis query {query_id}.")


def download_query_rows_csv(
    headers: dict[str, str],
    query_id: str,
    max_results: int,
) -> pd.DataFrame:
    response = requests.get(
        f"{REDIVIS_API_BASE_URL}/queries/{query_id}/rows",
        headers=headers,
        params={
            "format": "csv",
            "maxResults": max_results,
        },
        timeout=300,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Redivis query rows download failed with HTTP {response.status_code}\n"
            f"URL: {response.url}\n"
            f"Response: {response.text[:4000]}"
        )

    return pd.read_csv(StringIO(response.text), dtype=str)


def run_redivis_query(query: str, max_results: int) -> pd.DataFrame:
    token = require_redivis_token()
    headers = redivis_headers(token)

    query_payload = post_redivis_query(headers=headers, query=query)
    query_id = get_query_id(query_payload)

    status = str(query_payload.get("status", "")).lower()
    if status not in {"completed", "succeeded", "success"}:
        wait_for_query_completion(headers=headers, query_id=query_id)

    return download_query_rows_csv(
        headers=headers,
        query_id=query_id,
        max_results=max_results,
    )


def limit_unique_patients(df: pd.DataFrame, patient_limit: int | None) -> pd.DataFrame:
    if patient_limit is None or patient_limit <= 0:
        return df

    if "deid_patient_id" not in df.columns:
        raise ValueError("deid_patient_id column required for patient limiting")

    keep_patients: list[str] = []
    rows = []

    for _, row in df.iterrows():
        patient_id = str(row.get("deid_patient_id", "")).strip()
        if not patient_id:
            continue

        if patient_id not in keep_patients:
            if len(keep_patients) >= patient_limit:
                continue
            keep_patients.append(patient_id)

        if patient_id in keep_patients:
            rows.append(row)

    return pd.DataFrame(rows)


def merge_redivis_row_tables(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat([existing, incoming], ignore_index=True)
    if "path_to_dcm" not in combined.columns:
        return combined.drop_duplicates()

    combined["_join_key"] = combined["path_to_dcm"].map(normalize_text)
    combined = combined[combined["_join_key"].ne("")].copy()
    combined = combined.drop_duplicates(subset=["_join_key"], keep="last")
    return combined.drop(columns=["_join_key"])
