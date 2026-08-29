"""Inference-time retrieval helpers for the label-fusion pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from medagentx.reasoning.constants import FUSION_RETRIEVAL_TOP_K
from medagentx.retrieval.constants import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_RETRIEVAL_SUBDIR,
)
from medagentx.retrieval.index import (
    RetrievedStudy,
    get_chroma_collection,
    query_similar_studies,
)
from medagentx.vision.inference_output import VisionStudyOutput


def default_retrieval_chroma_dir(cohort_root: str | Path) -> Path:
    """Return the default persisted Chroma directory for one cohort."""
    return Path(cohort_root) / DEFAULT_RETRIEVAL_SUBDIR / "chroma"


def open_retrieval_collection(
    vector_db_dir: str | Path,
    *,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> Any:
    """Open the offline train-study retrieval collection."""
    return get_chroma_collection(
        vector_db_dir,
        collection_name=collection_name,
    )


def retrieve_similar_reports(
    collection: Any,
    study_output: VisionStudyOutput,
    *,
    top_k: int = FUSION_RETRIEVAL_TOP_K,
) -> list[RetrievedStudy]:
    """Query similar train studies for one vision study output."""
    return query_similar_studies(
        collection,
        study_output.query_embedding(),
        query_study_key=study_output.study_key,
        query_patient_id=study_output.deid_patient_id,
        top_k=top_k,
    )
