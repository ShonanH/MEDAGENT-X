from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TypedDict

import chromadb
import pandas as pd
import requests
from langgraph.graph import END, START, StateGraph


DEFAULT_VECTOR_DB_DIR = Path("outputs/chexpert_plus/vector_db/chroma")
DEFAULT_COLLECTION_NAME = "chexpert_plus_cases"
DEFAULT_QUALITY_EVIDENCE_CSV = Path("outputs/chexpert_plus/quality_evidence_manifest.csv")
DEFAULT_QUALITY_GATE_CSV = Path("outputs/chexpert_plus/quality_gate_decisions.csv")
DEFAULT_OUTPUT_CSV = Path("outputs/chexpert_plus/retrieval_results.csv")

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_EMBED_MODEL = "nomic-embed-text"

QUALITY_EVIDENCE_EXCLUDED_COLUMNS = {
    "manifest_row_index",
    "local_dicom_path",
    "workflow_a_feature_ready",
    "convnext_feature_path",
    "raddino_feature_path",
    "validation_status",
    "validation_preview_path",
    "validation_metadata_path",
    "validation_intensity_mean",
    "validation_intensity_mean_outlier_z",
    "validation_intensity_std",
    "validation_intensity_std_outlier_z",
    "validation_contrast_proxy",
    "validation_contrast_proxy_outlier_z",
    "validation_noise_proxy",
    "validation_noise_proxy_outlier_z",
    "validation_blur_proxy",
    "validation_blur_proxy_outlier_z",
    "validation_sharpness_proxy",
    "validation_sharpness_proxy_outlier_z",
    "validation_edge_density",
    "validation_edge_density_outlier_z",
    "validation_entropy",
    "validation_entropy_outlier_z",
    "convnext_vector_source",
    "convnext_vector_valid",
    "convnext_vector_dim",
    "convnext_embedding_nan_count",
    "convnext_embedding_inf_count",
    "raddino_vector_source",
    "raddino_vector_valid",
    "raddino_vector_dim",
    "raddino_embedding_nan_count",
    "raddino_embedding_inf_count",
    "raddino_patch_token_count",
    "raddino_patch_dim",
    "raddino_patch_mean",
    "raddino_patch_std",
    "raddino_patch_variability",
    "convnext_embedding_norm_outlier_z",
    "convnext_embedding_mean_outlier_z",
    "convnext_embedding_std_outlier_z",
    "raddino_embedding_norm_outlier_z",
    "raddino_embedding_mean_outlier_z",
    "raddino_embedding_std_outlier_z",
    "raddino_patch_variability_outlier_z",
    "convnext_embedding_outlier_distance",
    "convnext_embedding_outlier_z",
    "raddino_embedding_outlier_distance",
    "raddino_embedding_outlier_z",
    "evidence_complete",
    "max_handcrafted_quality_outlier_z",
    "max_deep_feature_outlier_z",
    "max_quality_evidence_z",
    "evidence_notes"
}

QUALITY_GATE_COLUMNS_TO_PREFIX = [
    "technical_explanation",
]


class RetrievalAgentState(TypedDict):
    study_key: str
    dicom_path: str
    top_k: int
    output_csv: str
    retrieved_cases: list[dict[str, Any]]
    route_next: str


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""

    normalized = str(value).strip().lower()
    normalized = normalized.replace("\\", "/")
    normalized = re.sub(r"/+", "/", normalized)
    return normalized


def parse_patient_id(value: Any) -> str:
    normalized = normalize_text(value)
    match = re.search(r"(patient\d+)", normalized)
    return match.group(1) if match else ""


def chroma_document_id(dicom_path: str) -> str:
    return f"chexpert_plus::{normalize_text(dicom_path)}"


def make_case_key(study_key: Any, dicom_path: Any) -> tuple[str, str]:
    return normalize_text(study_key), normalize_text(dicom_path)


def load_quality_gate_decision(
    dicom_path: str,
    study_key: str,
    quality_gate_csv: Path = DEFAULT_QUALITY_GATE_CSV,
) -> dict[str, Any]:
    if not quality_gate_csv.exists():
        return {}

    gate_df = pd.read_csv(quality_gate_csv, dtype=str)

    matched = gate_df[
        gate_df["dicom_path"].map(normalize_text).eq(normalize_text(dicom_path))
        & gate_df["study_key"].map(normalize_text).eq(normalize_text(study_key))
    ]

    if matched.empty:
        return {}

    return matched.iloc[0].to_dict()


def load_quality_evidence_lookup(
    quality_evidence_csv: Path = DEFAULT_QUALITY_EVIDENCE_CSV,
) -> dict[tuple[str, str], dict[str, Any]]:
    if not quality_evidence_csv.exists():
        raise FileNotFoundError(f"Missing quality evidence CSV: {quality_evidence_csv}")

    evidence_df = pd.read_csv(quality_evidence_csv, dtype=str)

    required_columns = {"study_key", "dicom_path"}
    missing_columns = sorted(required_columns - set(evidence_df.columns))
    if missing_columns:
        raise RuntimeError(
            f"Quality evidence CSV is missing required columns: {missing_columns}"
        )

    lookup: dict[tuple[str, str], dict[str, Any]] = {}

    evidence_columns = [
        column for column in evidence_df.columns
        if column not in QUALITY_EVIDENCE_EXCLUDED_COLUMNS
    ]

    for _, row in evidence_df.iterrows():
        key = make_case_key(row["study_key"], row["dicom_path"])
        lookup[key] = {
            column: row.get(column, "")
            for column in evidence_columns
            if column not in {"study_key", "dicom_path"}
        }

    return lookup


def load_quality_gate_lookup(
    quality_gate_csv: Path = DEFAULT_QUALITY_GATE_CSV,
) -> dict[tuple[str, str], dict[str, Any]]:
    if not quality_gate_csv.exists():
        return {}

    gate_df = pd.read_csv(quality_gate_csv, dtype=str)

    required_columns = {"study_key", "dicom_path"}
    missing_columns = sorted(required_columns - set(gate_df.columns))
    if missing_columns:
        raise RuntimeError(
            f"Quality gate CSV is missing required columns: {missing_columns}"
        )

    lookup: dict[tuple[str, str], dict[str, Any]] = {}

    for _, row in gate_df.iterrows():
        key = make_case_key(row["study_key"], row["dicom_path"])
        lookup[key] = {
            column: row.get(column, "")
            for column in QUALITY_GATE_COLUMNS_TO_PREFIX
            if column in gate_df.columns
        }

    return lookup


def prefix_case_fields(
    prefix: str,
    study_key: Any,
    dicom_path: Any,
    evidence_lookup: dict[tuple[str, str], dict[str, Any]],
    gate_lookup: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    key = make_case_key(study_key, dicom_path)

    prefixed: dict[str, Any] = {}

    evidence_fields = evidence_lookup.get(key, {})
    gate_fields = gate_lookup.get(key, {})

    for column, value in evidence_fields.items():
        prefixed[f"{prefix}_{column}"] = "" if pd.isna(value) else value

    for column, value in gate_fields.items():
        prefixed[f"{prefix}_{column}"] = "" if pd.isna(value) else value

    return prefixed


def get_chroma_collection(
    vector_db_dir: Path = DEFAULT_VECTOR_DB_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
):
    client = chromadb.PersistentClient(path=str(vector_db_dir))
    return client.get_collection(collection_name)


def get_current_case_from_chroma(collection: Any, dicom_path: str) -> tuple[str, dict[str, Any]]:
    document_id = chroma_document_id(dicom_path)

    result = collection.get(
        ids=[document_id],
        include=["documents", "metadatas"],
    )

    if not result.get("ids"):
        raise RuntimeError(
            "Current case was not found in the Chroma vector DB. "
            "This can happen if the case failed the Quality Gate or was not indexed. "
            f"Missing document id: {document_id}"
        )

    document = result["documents"][0] or ""
    metadata = result["metadatas"][0] or {}

    if not document.strip():
        raise RuntimeError(f"Current case has an empty retrieval document: {document_id}")

    return document, metadata


def embed_text_with_ollama(
    text: str,
    model: str = DEFAULT_OLLAMA_EMBED_MODEL,
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL,
) -> list[float]:
    response = requests.post(
        f"{ollama_base_url}/api/embed",
        json={
            "model": model,
            "input": text,
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
    embeddings = payload.get("embeddings")

    if not isinstance(embeddings, list) or not embeddings:
        raise RuntimeError("Ollama did not return an embedding.")

    return embeddings[0]


def query_similar_cases(
    collection: Any,
    query_embedding: list[float],
    n_results: int,
) -> dict[str, Any]:
    return collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )


def flatten_chroma_query_results(results: dict[str, Any]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for result_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
        flattened.append(
            {
                "id": result_id,
                "document": document or "",
                "metadata": metadata or {},
                "distance": distance,
            }
        )

    return flattened


def filter_retrieved_cases(
    candidates: list[dict[str, Any]],
    current_study_key: str,
    current_patient_id: str,
    top_k: int,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []

    current_study_key_norm = normalize_text(current_study_key)
    current_patient_id_norm = normalize_text(current_patient_id)

    for candidate in candidates:
        metadata = candidate["metadata"]

        candidate_study_key = normalize_text(metadata.get("study_key", ""))
        candidate_patient_id = normalize_text(metadata.get("patient_id", ""))

        if candidate_study_key and candidate_study_key == current_study_key_norm:
            continue

        if (
            current_patient_id_norm
            and candidate_patient_id
            and candidate_patient_id == current_patient_id_norm
        ):
            continue

        filtered.append(candidate)

        if len(filtered) >= top_k:
            break

    return filtered


def build_output_rows(
    query_study_key: str,
    query_dicom_path: str,
    query_metadata: dict[str, Any],
    retrieved_cases: list[dict[str, Any]],
    evidence_lookup: dict[tuple[str, str], dict[str, Any]],
    gate_lookup: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    query_metric_fields = prefix_case_fields(
        prefix="query",
        study_key=query_study_key,
        dicom_path=query_dicom_path,
        evidence_lookup=evidence_lookup,
        gate_lookup=gate_lookup,
    )

    for case in retrieved_cases:
        metadata = case["metadata"]

        retrieved_study_key = metadata.get("study_key", "")
        retrieved_dicom_path = metadata.get("dicom_path", "")

        retrieved_metric_fields = prefix_case_fields(
            prefix="retrieved",
            study_key=retrieved_study_key,
            dicom_path=retrieved_dicom_path,
            evidence_lookup=evidence_lookup,
            gate_lookup=gate_lookup,
        )

        row = {
            "query_study_key": query_study_key,
            "query_dicom_path": query_dicom_path,
            "query_age": query_metadata.get("age", ""),
            "query_sex": query_metadata.get("sex", ""),
            "query_race": query_metadata.get("race", ""),
            "query_ethnicity": query_metadata.get("ethnicity", ""),
            **query_metric_fields,
            "retrieval_distance": case["distance"],
            "retrieved_study_key": retrieved_study_key,
            "retrieved_dicom_path": retrieved_dicom_path,
            "retrieved_path_to_dcm": metadata.get("path_to_dcm", ""),
            "retrieved_path_to_image": metadata.get("path_to_image", ""),
            "retrieved_age": metadata.get("age", ""),
            "retrieved_sex": metadata.get("sex", ""),
            "retrieved_race": metadata.get("race", ""),
            "retrieved_ethnicity": metadata.get("ethnicity", ""),
            **retrieved_metric_fields,
            "retrieved_document": case["document"],
            "retrieved_metadata_json": json.dumps(metadata, sort_keys=True),
        }

        rows.append(row)

    rows.sort(key=lambda row: row["retrieval_distance"])

    return rows


def retrieval_agent_node(state: RetrievalAgentState) -> RetrievalAgentState:
    study_key = state["study_key"]
    dicom_path = state["dicom_path"]
    top_k = int(state["top_k"])
    output_csv = Path(state["output_csv"])

    quality_gate_row = load_quality_gate_decision(
        dicom_path=dicom_path,
        study_key=study_key,
    )

    if quality_gate_row.get("quality_gate_decision") == "fail":
        return {
            **state,
            "retrieved_cases": [],
            "route_next": "stop_unreliable",
        }

    evidence_lookup = load_quality_evidence_lookup()
    gate_lookup = load_quality_gate_lookup()

    collection = get_chroma_collection()

    current_document, current_metadata = get_current_case_from_chroma(
        collection=collection,
        dicom_path=dicom_path,
    )

    current_patient_id = (
        current_metadata.get("patient_id")
        or parse_patient_id(dicom_path)
        or parse_patient_id(study_key)
    )

    query_embedding = embed_text_with_ollama(current_document)

    candidate_count = max(top_k * 8, top_k + 20)

    raw_results = query_similar_cases(
        collection=collection,
        query_embedding=query_embedding,
        n_results=candidate_count,
    )

    candidates = flatten_chroma_query_results(raw_results)

    retrieved_cases = filter_retrieved_cases(
        candidates=candidates,
        current_study_key=study_key,
        current_patient_id=current_patient_id,
        top_k=top_k,
    )

    output_rows = build_output_rows(
        query_study_key=study_key,
        query_dicom_path=dicom_path,
        query_metadata=current_metadata,
        retrieved_cases=retrieved_cases,
        evidence_lookup=evidence_lookup,
        gate_lookup=gate_lookup,
    )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(output_rows).to_csv(output_csv, index=False)

    return {
        **state,
        "retrieved_cases": output_rows,
        "route_next": "disease_reasoning_agent",
    }


def build_retrieval_graph():
    graph = StateGraph(RetrievalAgentState)

    graph.add_node("retrieval_agent", retrieval_agent_node)
    graph.add_edge(START, "retrieval_agent")
    graph.add_edge("retrieval_agent", END)

    return graph.compile()


def run_retrieval_agent(
    study_key: str,
    dicom_path: str,
    top_k: int = 5,
    output_csv: str = str(DEFAULT_OUTPUT_CSV),
) -> RetrievalAgentState:
    graph = build_retrieval_graph()

    return graph.invoke(
        {
            "study_key": study_key,
            "dicom_path": dicom_path,
            "top_k": top_k,
            "output_csv": output_csv,
            "retrieved_cases": [],
            "route_next": "",
        }
    )