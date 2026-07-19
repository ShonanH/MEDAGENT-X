from __future__ import annotations

from medagentx.paths import CHEXPERT_OUTPUT_DIR, DATA_DIR, FUSION_OUTPUT_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR, SRC_ROOT, VECTOR_DB_DIR

import argparse
import json
import os
import re
import time
from io import StringIO
from pathlib import Path
from typing import Any

import chromadb
import pandas as pd
import requests


REDIVIS_API_BASE_URL = "https://redivis.com/api/v1"
REDIVIS_TABLE_REFERENCE = "aimi.chexpert_plus:5yyj:v1_0.df_chexpert_plus_240401:bavj"

DEFAULT_QUALITY_EVIDENCE_CSV = Path(str(CHEXPERT_OUTPUT_DIR / "quality_evidence_manifest.csv"))
DEFAULT_QUALITY_GATE_CSV = Path(str(CHEXPERT_OUTPUT_DIR / "quality_gate_decisions.csv"))
DEFAULT_VECTOR_DB_DIR = Path(str(VECTOR_DB_DIR))
DEFAULT_BUILD_SUMMARY_JSON = VECTOR_DB_DIR.parent / "chroma_build_summary.json"

DEFAULT_COLLECTION_NAME = "chexpert_plus_cases"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_EMBED_MODEL = "nomic-embed-text"

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
    token = os.getenv("REDIVIS_ACCESS_TOKEN")
    if not token:
        raise RuntimeError(
            "Missing REDIVIS_ACCESS_TOKEN. Set it before running:\n"
            "export REDIVIS_ACCESS_TOKEN='your_redivis_api_token'"
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


def parse_case_identifiers_from_path(path_value: Any) -> dict[str, str]:
    normalized = normalize_text(path_value)

    patient_match = re.search(r"(patient\d+)", normalized)
    study_match = re.search(r"(study\d+)", normalized)
    view_match = re.search(r"(view[^/]+?)(?:\.dcm)?$", normalized)

    patient_id = patient_match.group(1) if patient_match else ""
    study_id = study_match.group(1) if study_match else ""
    view_stem = view_match.group(1).replace(".dcm", "") if view_match else ""
    view_filename = f"{view_stem}.dcm" if view_stem else ""

    study_key = f"{patient_id}/{study_id}" if patient_id and study_id else ""
    dicom_path = f"{study_key}/{view_filename}" if study_key and view_filename else ""

    return {
        "patient_id": patient_id,
        "study_id": study_id,
        "study_key": study_key,
        "view_stem": view_stem,
        "dicom_path": dicom_path,
    }


def load_indexable_local_cases(
    quality_evidence_csv: Path,
    quality_gate_csv: Path,
    include_failed_quality_gate: bool,
) -> pd.DataFrame:
    if not quality_evidence_csv.exists():
        raise FileNotFoundError(f"Missing quality evidence CSV: {quality_evidence_csv}")

    evidence_df = pd.read_csv(quality_evidence_csv, dtype=str)

    required_columns = {"study_key", "dicom_path"}
    missing_columns = sorted(required_columns - set(evidence_df.columns))
    if missing_columns:
        raise RuntimeError(
            f"Quality evidence CSV is missing required columns: {missing_columns}"
        )

    local_df = evidence_df[["study_key", "dicom_path"]].drop_duplicates().copy()

    if quality_gate_csv.exists():
        gate_df = pd.read_csv(quality_gate_csv, dtype=str)

        gate_columns = [
            column for column in [
                "study_key",
                "dicom_path",
                "quality_gate_decision",
                "route_next",
            ]
            if column in gate_df.columns
        ]

        if {"study_key", "dicom_path"}.issubset(gate_columns):
            local_df = local_df.merge(
                gate_df[gate_columns].drop_duplicates(),
                on=["study_key", "dicom_path"],
                how="left",
                validate="one_to_one",
            )

            if not include_failed_quality_gate and "quality_gate_decision" in local_df.columns:
                local_df = local_df[
                    local_df["quality_gate_decision"].fillna("").ne("fail")
                ].copy()
    else:
        print(f"WARNING: quality gate CSV not found: {quality_gate_csv}")

    local_df["local_join_key"] = local_df["dicom_path"].map(normalize_text)
    local_df = local_df[local_df["local_join_key"].ne("")].copy()

    return local_df


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

        print(f"Redivis query status: {status or 'unknown'}")
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


def build_case_document(row: pd.Series) -> str:
    parts: list[str] = []

    def add(label: str, column: str) -> None:
        value = row.get(column, "")
        if pd.isna(value) or str(value).strip() == "":
            return
        parts.append(f"{label}: {str(value).strip()}")

    add("Age", "age")
    add("Sex", "sex")
    add("Race", "race")
    add("Ethnicity", "ethnicity")

    add("Clinical history", "section_clinical_history")
    add("History", "section_history")
    add("Comparison", "section_comparison")
    add("Technique", "section_technique")
    add("Procedure comments", "section_procedure_comments")
    add("Findings", "section_findings")
    add("Impression", "section_impression")
    add("End of impression", "section_end_of_impression")
    add("Summary", "section_summary")
    add("Narrative", "section_narrative")
    add("Full report", "report")

    return "\n".join(parts)


def clean_metadata_value(value: Any) -> str | int | float | bool:
    if pd.isna(value):
        return ""
    return str(value)


def build_chroma_records(redivis_df: pd.DataFrame, max_document_chars: int) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []

    seen_ids: set[str] = set()

    for _, row in redivis_df.iterrows():
        path_to_dcm = row.get("path_to_dcm", "")
        identifiers = parse_case_identifiers_from_path(path_to_dcm)

        dicom_path = identifiers["dicom_path"]
        study_key = identifiers["study_key"]
        patient_id = identifiers["patient_id"]

        if not dicom_path:
            continue

        document_id = f"chexpert_plus::{dicom_path}"
        if document_id in seen_ids:
            continue

        document = build_case_document(row).strip()
        if not document:
            continue

        if len(document) > max_document_chars:
            document = document[:max_document_chars]

        metadata = {
            "dicom_path": dicom_path,
            "study_key": study_key,
            "patient_id": patient_id,
            "study_id": identifiers["study_id"],
            "view_stem": identifiers["view_stem"],
            "path_to_dcm": clean_metadata_value(row.get("path_to_dcm", "")),
            "path_to_image": clean_metadata_value(row.get("path_to_image", "")),
            "deid_patient_id": clean_metadata_value(row.get("deid_patient_id", "")),
            "patient_report_date_order": clean_metadata_value(row.get("patient_report_date_order", "")),
            "section_accession_number": clean_metadata_value(row.get("section_accession_number", "")),
            "age": clean_metadata_value(row.get("age", "")),
            "sex": clean_metadata_value(row.get("sex", "")),
            "race": clean_metadata_value(row.get("race", "")),
            "ethnicity": clean_metadata_value(row.get("ethnicity", "")),
        }

        ids.append(document_id)
        documents.append(document)
        metadatas.append(metadata)
        seen_ids.add(document_id)

    return ids, documents, metadatas


def check_ollama_available(ollama_base_url: str) -> None:
    response = requests.get(f"{ollama_base_url}/api/tags", timeout=30)

    if response.status_code >= 400:
        raise RuntimeError(
            f"Ollama is not responding correctly at {ollama_base_url}.\n"
            f"HTTP {response.status_code}: {response.text[:1000]}"
        )


def embed_documents_with_ollama(
    documents: list[str],
    model: str,
    ollama_base_url: str,
    batch_size: int,
) -> list[list[float]]:
    embeddings: list[list[float]] = []

    for start in range(0, len(documents), batch_size):
        batch = documents[start:start + batch_size]

        response = requests.post(
            f"{ollama_base_url}/api/embed",
            json={
                "model": model,
                "input": batch,
                "truncate": True,
                "keep_alive": "10m",
            },
            timeout=600,
        )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Ollama embedding request failed with HTTP {response.status_code}\n"
                f"Response: {response.text[:4000]}"
            )

        payload = response.json()
        batch_embeddings = payload.get("embeddings")

        if not isinstance(batch_embeddings, list) or len(batch_embeddings) != len(batch):
            raise RuntimeError(
                "Unexpected Ollama embedding response. Expected one embedding per input document."
            )

        embeddings.extend(batch_embeddings)
        print(f"Embedded {len(embeddings)} / {len(documents)} documents")

    return embeddings


def write_chroma_collection(
    vector_db_dir: Path,
    collection_name: str,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict[str, Any]],
    embeddings: list[list[float]],
    rebuild: bool,
) -> None:
    vector_db_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(vector_db_dir))

    if rebuild:
        try:
            client.delete_collection(collection_name)
            print(f"Deleted existing Chroma collection: {collection_name}")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={
            "description": "CheXpert Plus clinical case/report retrieval index",
            "embedding_model": DEFAULT_OLLAMA_EMBED_MODEL,
            "source_table": REDIVIS_TABLE_REFERENCE,
            "hnsw:space": "cosine",
        },
    )

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )

    print(f"Chroma collection count: {collection.count()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a Chroma vector DB from Redivis CheXpert Plus rows without writing a merged CSV."
    )
    parser.add_argument("--quality-evidence-csv", type=Path, default=DEFAULT_QUALITY_EVIDENCE_CSV)
    parser.add_argument("--quality-gate-csv", type=Path, default=DEFAULT_QUALITY_GATE_CSV)
    parser.add_argument("--vector-db-dir", type=Path, default=DEFAULT_VECTOR_DB_DIR)
    parser.add_argument("--build-summary-json", type=Path, default=DEFAULT_BUILD_SUMMARY_JSON)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--ollama-base-url", default=DEFAULT_OLLAMA_BASE_URL)
    parser.add_argument("--embedding-model", default=DEFAULT_OLLAMA_EMBED_MODEL)
    parser.add_argument("--embedding-batch-size", type=int, default=16)
    parser.add_argument("--max-document-chars", type=int, default=12000)
    parser.add_argument("--include-failed-quality-gate", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    local_cases = load_indexable_local_cases(
        quality_evidence_csv=args.quality_evidence_csv,
        quality_gate_csv=args.quality_gate_csv,
        include_failed_quality_gate=args.include_failed_quality_gate,
    )

    local_dicom_paths = sorted(set(local_cases["dicom_path"].dropna().astype(str)))

    print(f"Local indexable DICOM paths: {len(local_dicom_paths)}")
    print("Checking Ollama...")
    check_ollama_available(args.ollama_base_url)

    token = require_redivis_token()
    headers = redivis_headers(token)

    query = build_filtered_redivis_sql(local_dicom_paths)

    print("Posting filtered Redivis query...")
    query_payload = post_redivis_query(headers=headers, query=query)
    query_id = get_query_id(query_payload)

    status = str(query_payload.get("status", "")).lower()
    if status not in {"completed", "succeeded", "success"}:
        wait_for_query_completion(headers=headers, query_id=query_id)

    print(f"Downloading Redivis query rows for query {query_id}...")
    redivis_df = download_query_rows_csv(
        headers=headers,
        query_id=query_id,
        max_results=max(5000, len(local_dicom_paths) * 5),
    )

    print(f"Redivis rows returned: {len(redivis_df)}")

    ids, documents, metadatas = build_chroma_records(
        redivis_df=redivis_df,
        max_document_chars=args.max_document_chars,
    )

    if not ids:
        raise RuntimeError("No valid Chroma records were created from the Redivis query rows.")

    print(f"Chroma records prepared: {len(ids)}")
    print(f"Embedding model: {args.embedding_model}")

    embeddings = embed_documents_with_ollama(
        documents=documents,
        model=args.embedding_model,
        ollama_base_url=args.ollama_base_url,
        batch_size=args.embedding_batch_size,
    )

    write_chroma_collection(
        vector_db_dir=args.vector_db_dir,
        collection_name=args.collection_name,
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
        rebuild=args.rebuild,
    )

    args.build_summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "source_table": REDIVIS_TABLE_REFERENCE,
        "collection_name": args.collection_name,
        "vector_db_dir": str(args.vector_db_dir),
        "embedding_model": args.embedding_model,
        "local_indexable_dicom_paths": len(local_dicom_paths),
        "redivis_rows_returned": len(redivis_df),
        "chroma_records_added": len(ids),
        "included_failed_quality_gate_cases": args.include_failed_quality_gate,
    }

    args.build_summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("Vector DB build complete.")
    print(f"Vector DB directory: {args.vector_db_dir}")
    print(f"Collection name: {args.collection_name}")
    print(f"Build summary: {args.build_summary_json}")


if __name__ == "__main__":
    main()