"""Chroma-backed study retrieval index build and query helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import chromadb
import numpy as np
import pandas as pd

from medagentx.retrieval.constants import (
    CHROMA_DISTANCE_SPACE,
    DEFAULT_COLLECTION_NAME,
    DEFAULT_TOP_K,
    EMBEDDING_BACKEND_ID,
    EXCLUDE_SAME_PATIENT,
    EXCLUDE_SAME_STUDY,
    INDEX_METADATA_COLUMNS,
    QUERY_CANDIDATE_MIN_EXTRA,
    QUERY_CANDIDATE_MULTIPLIER,
    RETRIEVAL_INDEX_ID,
    RETRIEVAL_POLICY_VERSION,
)


def normalize_study_key(value: Any) -> str:
    """Normalize study keys for stable comparisons."""
    return str(value).strip().lower()


def normalize_patient_id(value: Any) -> str:
    """Normalize patient IDs for stable comparisons."""
    return str(value).strip().lower()


def chroma_document_id(study_key: str) -> str:
    """Return the stable Chroma id for one study-level index row."""
    normalized = normalize_study_key(study_key)
    if not normalized:
        raise ValueError("study_key must be non-empty")
    return f"medagentx::{normalized}"


def query_candidate_count(top_k: int) -> int:
    """Oversample before exclusion filters shrink the result list."""
    if top_k <= 0:
        raise ValueError("top_k must be > 0")
    return max(top_k * QUERY_CANDIDATE_MULTIPLIER, top_k + QUERY_CANDIDATE_MIN_EXTRA)


def clean_metadata_value(value: Any) -> str:
    """Coerce metadata values into Chroma-safe strings."""
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    return str(value).strip()


@dataclass(frozen=True)
class IndexedStudy:
    """One study row written to the retrieval index."""

    study_key: str
    deid_patient_id: str
    document: str
    embedding: tuple[float, ...]


@dataclass(frozen=True)
class RetrievedStudy:
    """One filtered retrieval hit returned to Label Fusion."""

    study_key: str
    deid_patient_id: str
    document: str
    distance: float
    similarity: float


def build_index_records(
    *,
    embeddings: np.ndarray,
    study_keys: Sequence[str],
    patient_ids: Sequence[str],
    documents: Mapping[str, str],
) -> list[IndexedStudy]:
    """Zip embedding rows with study metadata and report payloads."""
    if embeddings.ndim != 2:
        raise ValueError("embeddings must be a 2D array")
    if len(study_keys) != embeddings.shape[0]:
        raise ValueError("study_keys length must match embeddings rows")
    if len(patient_ids) != embeddings.shape[0]:
        raise ValueError("patient_ids length must match embeddings rows")

    records: list[IndexedStudy] = []
    for index, study_key in enumerate(study_keys):
        key = str(study_key).strip()
        if key not in documents:
            raise ValueError(f"Missing retrieval document for study_key={key!r}")
        document = documents[key].strip()
        if not document:
            raise ValueError(f"Empty retrieval document for study_key={key!r}")
        records.append(
            IndexedStudy(
                study_key=key,
                deid_patient_id=str(patient_ids[index]).strip(),
                document=document,
                embedding=tuple(float(value) for value in embeddings[index].tolist()),
            )
        )
    return records


def filter_retrieved_studies(
    candidates: Sequence[RetrievedStudy],
    *,
    query_study_key: str,
    query_patient_id: str,
    top_k: int,
    exclude_same_study: bool = EXCLUDE_SAME_STUDY,
    exclude_same_patient: bool = EXCLUDE_SAME_PATIENT,
) -> list[RetrievedStudy]:
    """Apply the locked exclusion rules and keep the closest ``top_k`` hits."""
    if top_k <= 0:
        raise ValueError("top_k must be > 0")

    current_study = normalize_study_key(query_study_key)
    current_patient = normalize_patient_id(query_patient_id)
    filtered: list[RetrievedStudy] = []

    for candidate in sorted(candidates, key=lambda row: row.distance):
        if exclude_same_study and normalize_study_key(candidate.study_key) == current_study:
            continue
        if (
            exclude_same_patient
            and current_patient
            and normalize_patient_id(candidate.deid_patient_id) == current_patient
        ):
            continue
        filtered.append(candidate)
        if len(filtered) >= top_k:
            break
    return filtered


def _flatten_chroma_results(results: dict[str, Any]) -> list[RetrievedStudy]:
    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    flattened: list[RetrievedStudy] = []
    for _id, document, metadata, distance in zip(
        ids, documents, metadatas, distances
    ):
        metadata = metadata or {}
        distance_value = float(distance)
        flattened.append(
            RetrievedStudy(
                study_key=str(metadata.get("study_key", "")).strip(),
                deid_patient_id=str(metadata.get("deid_patient_id", "")).strip(),
                document=document or "",
                distance=distance_value,
                similarity=1.0 - distance_value,
            )
        )
    return flattened


def get_chroma_collection(
    vector_db_dir: str | Path,
    *,
    collection_name: str = DEFAULT_COLLECTION_NAME,
):
    """Open an existing persistent Chroma collection."""
    client = chromadb.PersistentClient(path=str(vector_db_dir))
    return client.get_collection(collection_name)


def write_chroma_index(
    vector_db_dir: str | Path,
    records: Sequence[IndexedStudy],
    *,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    rebuild: bool = False,
) -> Any:
    """Persist study embeddings and report payloads to Chroma."""
    if not records:
        raise ValueError("records must be non-empty")

    root = Path(vector_db_dir)
    root.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(root))

    if rebuild:
        try:
            client.delete_collection(collection_name)
            print(f"[Retrieval] deleted existing Chroma collection {collection_name!r}")
        except Exception:
            pass

    print(
        f"[Retrieval] opening Chroma collection {collection_name!r} at {root}"
    )
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={
            "description": "MEDAGENT-X v2 train-study image retrieval index",
            "embedding_backend_id": EMBEDDING_BACKEND_ID,
            "retrieval_policy_version": RETRIEVAL_POLICY_VERSION,
            "retrieval_index_id": RETRIEVAL_INDEX_ID,
            "hnsw:space": CHROMA_DISTANCE_SPACE,
        },
    )

    ids = [chroma_document_id(record.study_key) for record in records]
    documents = [record.document for record in records]
    embeddings = [list(record.embedding) for record in records]
    metadatas = [
        {
            column: clean_metadata_value(getattr(record, column))
            for column in INDEX_METADATA_COLUMNS
        }
        for record in records
    ]

    print(
        f"[Retrieval] writing {len(records)} study embeddings to Chroma "
        f"(space={CHROMA_DISTANCE_SPACE})"
    )
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    print(f"[Retrieval] Chroma write complete count={collection.count()}")
    return collection


def query_similar_studies(
    collection: Any,
    query_embedding: Sequence[float],
    *,
    query_study_key: str,
    query_patient_id: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedStudy]:
    """Return the closest train studies after exclusion filtering."""
    candidate_count = query_candidate_count(top_k)
    raw_results = collection.query(
        query_embeddings=[list(query_embedding)],
        n_results=candidate_count,
        include=["documents", "metadatas", "distances"],
    )
    candidates = _flatten_chroma_results(raw_results)
    return filter_retrieved_studies(
        candidates,
        query_study_key=query_study_key,
        query_patient_id=query_patient_id,
        top_k=top_k,
    )


def write_index_manifest(
    output_path: str | Path,
    *,
    records: Sequence[IndexedStudy],
    build_config: Mapping[str, Any],
) -> Path:
    """Persist an auditable CSV manifest for the indexed studies."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "study_key": record.study_key,
            "deid_patient_id": record.deid_patient_id,
            "chroma_document_id": chroma_document_id(record.study_key),
            "document_chars": len(record.document),
            "embedding_dim": len(record.embedding),
        }
        for record in records
    ]
    pd.DataFrame(rows).to_csv(path, index=False)

    summary_path = path.with_name("build_summary.json")
    summary = {
        "retrieval_policy_version": RETRIEVAL_POLICY_VERSION,
        "retrieval_index_id": RETRIEVAL_INDEX_ID,
        "indexed_studies": len(records),
        **dict(build_config),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return path
