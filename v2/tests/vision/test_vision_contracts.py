"""Dependency-light contracts for the RAD-DINO vision data flow."""

from __future__ import annotations

import numpy as np
import pandas as pd

from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label
from medagentx.vision.data import (
    build_study_inference_records,
    build_study_training_records,
)
from medagentx.vision.metrics import tune_validation_thresholds


def _study_label_row(study_key: str) -> dict[str, object]:
    row: dict[str, object] = {"study_key": study_key}
    for index, label in enumerate(DISEASE_LABELS):
        slug = snake_label(label)
        row[f"training_target_{slug}"] = 1.0 if index == 0 else ""
        row[f"training_mask_{slug}"] = 1 if index == 0 else 0
    return row


def test_training_records_pool_quality_views_by_study() -> None:
    views = pd.DataFrame(
        [
            {
                "study_key": "patient1/study1",
                "deid_patient_id": "patient1",
                "dicom_path": "patient1/study1/frontal.dcm",
                "split": "train",
            },
            {
                "study_key": "patient1/study1",
                "deid_patient_id": "patient1",
                "dicom_path": "patient1/study1/lateral.dcm",
                "split": "train",
            },
        ]
    )
    labels = pd.DataFrame([_study_label_row("patient1/study1")])

    records = build_study_training_records(views, labels, split="train")

    assert len(records) == 1
    assert records[0].dicom_paths == (
        "patient1/study1/frontal.dcm",
        "patient1/study1/lateral.dcm",
    )
    assert len(records[0].targets) == 12
    assert len(records[0].masks) == 12
    assert records[0].targets[0] == 1.0
    assert records[0].masks[0] == 1.0


def test_inference_records_require_no_labels() -> None:
    views = pd.DataFrame(
        [
            {
                "study_key": "patient2/study1",
                "deid_patient_id": "patient2",
                "dicom_path": "patient2/study1/frontal.dcm",
                "split": "test",
            }
        ]
    )

    records = build_study_inference_records(views, split="test")

    assert len(records) == 1
    assert records[0].study_key == "patient2/study1"
    assert records[0].split == "test"


def test_thresholds_are_tuned_only_on_supervised_cells() -> None:
    targets = np.zeros((4, 12), dtype=float)
    probabilities = np.zeros((4, 12), dtype=float)
    masks = np.zeros((4, 12), dtype=float)
    targets[:, 0] = [0, 0, 1, 1]
    probabilities[:, 0] = [0.1, 0.2, 0.7, 0.8]
    masks[:, 0] = 1

    thresholds = tune_validation_thresholds(targets, probabilities, masks)

    assert 0.2 <= thresholds[DISEASE_LABELS[0]] <= 0.7
    assert thresholds[DISEASE_LABELS[1]] == 0.5
