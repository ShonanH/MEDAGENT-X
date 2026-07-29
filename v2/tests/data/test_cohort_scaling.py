"""Contract tests for the vectorized label gate and join-key resolution."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from medagentx.data.cohort import (
    DROP_REASON_MISSING_LABELS,
    apply_label_gated_cohort,
    limit_to_whole_studies,
    load_findings_for_cohort,
)
from medagentx.data.paths import (
    path_to_image_join_keys,
    path_to_image_key_from_row,
)
from medagentx.labels.constants import ALL_CHEXPERT_LABELS
from medagentx.labels.study_table import build_study_label_table


def _view_row(patient: int, study: int, view: str) -> dict[str, str]:
    stem = f"patient{patient:05d}/study{study}/{view}"
    return {
        "deid_patient_id": f"patient{patient:05d}",
        "study_key": f"patient{patient:05d}/study{study}",
        "dicom_path": f"{stem}.dcm",
        "path_to_dcm": f"train/{stem}.dcm",
        "path_to_image": f"{stem}.jpg",
        "file_id": f"file-{stem}",
    }


def _findings_line(path_to_image: str, *, positive: str) -> str:
    record: dict[str, object] = {"path_to_image": path_to_image}
    for label in ALL_CHEXPERT_LABELS:
        record[label] = 1 if label == positive else 0
    return json.dumps(record)


def test_vectorized_join_keys_match_per_row_resolution() -> None:
    frame = pd.DataFrame(
        [
            _view_row(1, 1, "view1"),
            {
                "deid_patient_id": "patient00002",
                "study_key": "patient00002/study1",
                "dicom_path": "patient00002/study1/view1.dcm",
                "path_to_dcm": "train/patient00002/study1/view1.dcm",
                "path_to_image": "",
                "file_id": "file-2",
            },
            {
                "deid_patient_id": "patient00003",
                "study_key": "patient00003/study1",
                "dicom_path": "patient00003/study1/view1.dcm",
                "path_to_dcm": None,
                "path_to_image": None,
                "file_id": "file-3",
            },
        ]
    )

    vectorized = path_to_image_join_keys(frame).tolist()
    per_row = [path_to_image_key_from_row(row) for _, row in frame.iterrows()]

    assert vectorized == per_row
    assert vectorized[0] == "patient00001/study1/view1.jpg"
    # Fallback columns are normalized but not prefix-stripped, matching the
    # per-row resolver that the cohort gate has always used.
    assert vectorized[1] == "train/patient00002/study1/view1.jpg"
    assert vectorized[2] == "patient00003/study1/view1.jpg"


def test_gate_keeps_labeled_studies_and_drops_unlabeled(tmp_path: Path) -> None:
    rows = pd.DataFrame(
        [
            _view_row(1, 1, "frontal"),
            _view_row(1, 1, "lateral"),
            _view_row(2, 1, "frontal"),
        ]
    )
    findings = tmp_path / "findings_fixed.json"
    findings.write_text(
        "\n".join(
            [
                _findings_line(
                    "patient00001/study1/frontal.jpg",
                    positive="Cardiomegaly",
                ),
                _findings_line(
                    "patient00001/study1/lateral.jpg",
                    positive="Cardiomegaly",
                ),
            ]
        ),
        encoding="utf-8",
    )

    index = load_findings_for_cohort(findings, rows)
    kept, dropped = apply_label_gated_cohort(rows, index)

    assert sorted(kept["study_key"].unique()) == ["patient00001/study1"]
    assert len(kept) == 2
    assert dropped.iloc[0]["study_key"] == "patient00002/study1"
    assert dropped.iloc[0]["reason"] == DROP_REASON_MISSING_LABELS

    labels = build_study_label_table(kept, index)
    assert len(labels) == 1
    assert labels.iloc[0]["view_count"] == 2
    assert labels.iloc[0]["training_target_cardiomegaly"] == 1.0


def test_row_limit_keeps_whole_studies_in_order() -> None:
    rows = pd.DataFrame(
        [
            _view_row(1, 1, "frontal"),
            _view_row(1, 1, "lateral"),
            _view_row(2, 1, "frontal"),
            _view_row(3, 1, "frontal"),
        ]
    )

    kept, dropped = limit_to_whole_studies(rows, max_rows=3)

    assert kept["study_key"].tolist() == [
        "patient00001/study1",
        "patient00001/study1",
        "patient00002/study1",
    ]
    assert dropped["study_key"].tolist() == ["patient00003/study1"]


def test_gate_scales_linearly_on_a_large_pool(tmp_path: Path) -> None:
    view_rows: list[dict[str, str]] = []
    findings_lines: list[str] = []
    for patient in range(4000):
        view_rows.append(_view_row(patient, 1, "frontal"))
        findings_lines.append(
            _findings_line(
                f"patient{patient:05d}/study1/frontal.jpg",
                positive="Lung Opacity",
            )
        )
    rows = pd.DataFrame(view_rows)
    findings = tmp_path / "findings_fixed.json"
    findings.write_text("\n".join(findings_lines), encoding="utf-8")

    index = load_findings_for_cohort(findings, rows)
    kept, dropped = apply_label_gated_cohort(rows, index)

    assert len(kept) == len(rows)
    assert dropped.empty
