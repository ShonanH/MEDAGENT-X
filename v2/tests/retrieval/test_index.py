"""Tests for retrieval index helpers and exclusion rules."""

from __future__ import annotations

import numpy as np
import pytest

from medagentx.retrieval.index import (
    RetrievedStudy,
    build_index_records,
    chroma_document_id,
    filter_retrieved_studies,
    query_candidate_count,
)


def test_chroma_document_id_is_stable() -> None:
    assert chroma_document_id("Patient1/Study2") == chroma_document_id(
        "patient1/study2"
    )


def test_query_candidate_count_oversamples_before_filtering() -> None:
    assert query_candidate_count(5) == 40
    assert query_candidate_count(1) == 21


def test_filter_retrieved_studies_excludes_self_and_same_patient() -> None:
    candidates = [
        RetrievedStudy(
            study_key="patient1/study1",
            deid_patient_id="patient1",
            document="self",
            distance=0.01,
            similarity=0.99,
        ),
        RetrievedStudy(
            study_key="patient1/study2",
            deid_patient_id="patient1",
            document="same patient",
            distance=0.02,
            similarity=0.98,
        ),
        RetrievedStudy(
            study_key="patient2/study1",
            deid_patient_id="patient2",
            document="other patient",
            distance=0.03,
            similarity=0.97,
        ),
    ]
    filtered = filter_retrieved_studies(
        candidates,
        query_study_key="patient1/study1",
        query_patient_id="patient1",
        top_k=5,
    )
    assert len(filtered) == 1
    assert filtered[0].study_key == "patient2/study1"


def test_build_index_records_requires_documents_for_every_study() -> None:
    embeddings = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)
    with pytest.raises(ValueError, match="Missing retrieval document"):
        build_index_records(
            embeddings=embeddings,
            study_keys=["patient1/study1", "patient2/study1"],
            patient_ids=["patient1", "patient2"],
            documents={"patient1/study1": "Findings: effusion."},
        )
