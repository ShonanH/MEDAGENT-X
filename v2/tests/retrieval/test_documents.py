"""Tests for study-level retrieval document construction."""

from __future__ import annotations

import pandas as pd
import pytest

from medagentx.retrieval.documents import (
    build_retrieval_document,
    build_study_report_table,
    truncate_document,
)


def test_build_retrieval_document_joins_findings_and_impression() -> None:
    document = build_retrieval_document(
        section_findings="Bilateral opacities.",
        section_impression="Pneumonia.",
    )
    assert "Findings: Bilateral opacities." in document
    assert "Impression: Pneumonia." in document


def test_build_study_report_table_collapses_views_to_one_row() -> None:
    eligible = pd.DataFrame(
        [
            {
                "study_key": "patient1/study1",
                "deid_patient_id": "patient1",
                "section_findings": "",
                "section_impression": "",
            },
            {
                "study_key": "patient1/study1",
                "deid_patient_id": "patient1",
                "section_findings": "Small effusion.",
                "section_impression": "Effusion.",
            },
        ]
    )
    table = build_study_report_table(eligible)
    assert len(table) == 1
    assert table.iloc[0]["section_findings"] == "Small effusion."
    assert table.iloc[0]["section_impression"] == "Effusion."
    assert "Findings: Small effusion." in table.iloc[0]["retrieval_document"]


def test_build_study_report_table_rejects_conflicting_patient_ids() -> None:
    eligible = pd.DataFrame(
        [
            {
                "study_key": "patient1/study1",
                "deid_patient_id": "patient1",
                "section_findings": "A",
                "section_impression": "B",
            },
            {
                "study_key": "patient1/study1",
                "deid_patient_id": "patient2",
                "section_findings": "A",
                "section_impression": "B",
            },
        ]
    )
    with pytest.raises(ValueError, match="multiple patient IDs"):
        build_study_report_table(eligible)


def test_truncate_document_preserves_prefix() -> None:
    text = "x" * 20
    assert truncate_document(text, max_chars=10) == "x" * 10
