"""
Redivis REST query client for CheXpert Plus.

HTTP execution lives here. SQL definitions live in redivis_queries.py.
"""

from __future__ import annotations

import os
import re
import time
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from medagentx.helpers.redivis_queries import (
    CHEXPERT_LABEL_COLUMNS,
    METADATA_EXPORT_COLUMNS,
    REDIVIS_CHEXPERT_LABELS_TABLE_REFERENCE,
    REDIVIS_EXPORTS,
    REDIVIS_TABLE_REFERENCE,
    SELECTED_REDIVIS_COLUMNS,
    build_filtered_chexpert_labels_sql,
    build_filtered_redivis_sql,
    build_image_labels_for_dicom_paths_query,
    build_image_labels_for_paths_query,
    build_train_split_query,
    get_export,
    list_exports,
    normalize_text,
)

REDIVIS_API_BASE_URL = "https://redivis.com/api/v1"


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


def sql_quote(value: str) -> str:
    from medagentx.helpers.redivis_queries import sql_quote as _sql_quote

    return _sql_quote(value)


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


def run_redivis_export(
    export_name: str,
    output_csv: str | Path | None = None,
    max_results: int | None = None,
    **query_kwargs: Any,
) -> pd.DataFrame:
    spec = get_export(export_name)
    query = spec.build_query(**query_kwargs)
    limit = max_results if max_results is not None else spec.default_max_results
    df = run_redivis_query(query, max_results=limit)

    if output_csv is not None:
        out_path = Path(output_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)

    return df


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


def fetch_image_labels_for_paths(
    path_to_images: list[str],
    batch_size: int = 250,
    *,
    path_column: str = "path_to_image",
) -> pd.DataFrame:
    """
    Fetch per-image label columns from df_chexpert_plus_240401.

    The chexpert_labels Redivis table is a file index, not per-image labels.
    """
    paths = [normalize_text(path) for path in path_to_images if normalize_text(path)]
    if not paths:
        from medagentx.helpers.redivis_queries import IMAGE_LABEL_EXPORT_COLUMNS

        empty_cols = (
            IMAGE_LABEL_EXPORT_COLUMNS
            if path_column == "path_to_image"
            else ["path_to_dcm", *CHEXPERT_LABEL_COLUMNS]
        )
        return pd.DataFrame(columns=empty_cols)

    builder = (
        build_image_labels_for_paths_query
        if path_column == "path_to_image"
        else build_image_labels_for_dicom_paths_query
    )

    frames: list[pd.DataFrame] = []
    for start in range(0, len(paths), batch_size):
        batch = paths[start : start + batch_size]
        query = builder(batch)
        frames.append(run_redivis_query(query, max_results=len(batch)))

    combined = pd.concat(frames, ignore_index=True)
    join_col = path_column if path_column in combined.columns else "path_to_image"
    if join_col not in combined.columns:
        return combined

    combined["_join_key"] = combined[join_col].map(normalize_text)
    combined = combined[combined["_join_key"].ne("")].copy()
    return combined.drop_duplicates(subset=["_join_key"], keep="last").drop(columns=["_join_key"])


# Backward-compatible alias
fetch_chexpert_labels_for_paths = fetch_image_labels_for_paths


def merge_redivis_row_tables(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat([existing, incoming], ignore_index=True)
    if "path_to_dcm" not in combined.columns:
        return combined.drop_duplicates()

    combined["_join_key"] = combined["path_to_dcm"].map(normalize_text)
    combined = combined[combined["_join_key"].ne("")].copy()
    combined = combined.drop_duplicates(subset=["_join_key"], keep="last")
    return combined.drop(columns=["_join_key"])


__all__ = [
    "CHEXPERT_LABEL_COLUMNS",
    "METADATA_EXPORT_COLUMNS",
    "REDIVIS_CHEXPERT_LABELS_TABLE_REFERENCE",
    "REDIVIS_EXPORTS",
    "REDIVIS_TABLE_REFERENCE",
    "SELECTED_REDIVIS_COLUMNS",
    "build_filtered_chexpert_labels_sql",
    "build_filtered_redivis_sql",
    "build_train_split_query",
    "fetch_chexpert_labels_for_paths",
    "fetch_image_labels_for_paths",
    "list_exports",
    "merge_redivis_row_tables",
    "normalize_text",
    "require_redivis_token",
    "run_redivis_export",
    "run_redivis_query",
    "sql_quote",
]
