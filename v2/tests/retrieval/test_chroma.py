"""Integration tests for the Chroma retrieval index."""

from __future__ import annotations

import numpy as np

from medagentx.retrieval.index import (
    IndexedStudy,
    query_similar_studies,
    write_chroma_index,
)


def test_write_and_query_chroma_index(tmp_path) -> None:
    records = [
        IndexedStudy(
            study_key="patient1/study1",
            deid_patient_id="patient1",
            document="Findings: opacity.",
            embedding=(1.0, 0.0, 0.0),
        ),
        IndexedStudy(
            study_key="patient2/study1",
            deid_patient_id="patient2",
            document="Findings: effusion.",
            embedding=(0.9, 0.1, 0.0),
        ),
        IndexedStudy(
            study_key="patient3/study1",
            deid_patient_id="patient3",
            document="Findings: clear lungs.",
            embedding=(0.0, 1.0, 0.0),
        ),
    ]
    collection = write_chroma_index(
        tmp_path / "chroma",
        records,
        rebuild=True,
    )
    assert collection.count() == 3

    hits = query_similar_studies(
        collection,
        query_embedding=[0.95, 0.05, 0.0],
        query_study_key="patient9/study9",
        query_patient_id="patient9",
        top_k=2,
    )
    assert len(hits) == 2
    assert hits[0].study_key == "patient2/study1"
    assert hits[1].study_key == "patient1/study1"


def test_query_excludes_same_patient_even_when_closest(tmp_path) -> None:
    records = [
        IndexedStudy(
            study_key="patient1/study1",
            deid_patient_id="patient1",
            document="Findings: A.",
            embedding=tuple(np.random.rand(8).tolist()),
        ),
        IndexedStudy(
            study_key="patient1/study2",
            deid_patient_id="patient1",
            document="Findings: B.",
            embedding=tuple(np.random.rand(8).tolist()),
        ),
        IndexedStudy(
            study_key="patient2/study1",
            deid_patient_id="patient2",
            document="Findings: C.",
            embedding=tuple(np.random.rand(8).tolist()),
        ),
    ]
    collection = write_chroma_index(tmp_path / "chroma", records, rebuild=True)
    query_vector = list(records[1].embedding)
    hits = query_similar_studies(
        collection,
        query_embedding=query_vector,
        query_study_key="patient1/study2",
        query_patient_id="patient1",
        top_k=2,
    )
    assert all(hit.deid_patient_id != "patient1" for hit in hits)
    assert hits[0].study_key == "patient2/study1"
