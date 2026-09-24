from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from medagentx.evaluation.chexpert_competition import (
    build_competition_ground_truth,
    build_competition_validation_ground_truth,
    build_competition_view_manifest,
    competition_study_key,
)
from medagentx.labels.constants import CHEXPERT_COMPETITION_LABELS
from medagentx.labels.statuses import LabelStatus


def _expert_row(study: str, value: int = 0) -> dict[str, object]:
    return {
        "Study": study,
        **{label: value for label in CHEXPERT_COMPETITION_LABELS},
    }


def test_competition_study_key_normalizes_study_and_view_paths() -> None:
    assert competition_study_key(
        "CheXpert-v1.0/test/patient64741/study1",
        field_name="Study",
    ) == "patient64741/study1"
    assert competition_study_key(
        "CheXpert-v1.0/valid/patient64541/study1/view1_frontal.jpg",
        field_name="Path",
        source_split="val",
    ) == "patient64541/study1"
    assert competition_study_key(
        "CheXpert-v1.0/test/patient64741/study1/view1_frontal.jpg",
        field_name="Path",
    ) == "patient64741/study1"


def test_view_manifest_preserves_multiple_views_per_study(tmp_path: Path) -> None:
    paths = [
        "patient64741/study1/view1_frontal.jpg",
        "patient64741/study1/view2_lateral.jpg",
        "patient64742/study1/view1_frontal.jpg",
    ]
    for relative in paths:
        image = tmp_path / relative
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"test")
    test_labels = pd.DataFrame(
        {"Path": [f"CheXpert-v1.0/test/{path}" for path in paths]}
    )

    manifest = build_competition_view_manifest(
        test_labels,
        image_root=tmp_path,
    )

    assert len(manifest) == 3
    assert manifest["study_key"].nunique() == 2
    assert manifest["study_key"].tolist()[:2] == [
        "patient64741/study1",
        "patient64741/study1",
    ]
    assert manifest["dicom_path"].tolist() == paths


def test_view_manifest_requires_downloaded_images(tmp_path: Path) -> None:
    test_labels = pd.DataFrame(
        {
            "Path": [
                "CheXpert-v1.0/test/patient64741/study1/view1_frontal.jpg"
            ]
        }
    )

    with pytest.raises(FileNotFoundError, match="Competition test image missing"):
        build_competition_view_manifest(test_labels, image_root=tmp_path)


def test_ground_truth_uses_only_requested_studies_and_five_labels() -> None:
    first = _expert_row("CheXpert-v1.0/test/patient64741/study1")
    first["Edema"] = 1
    second = _expert_row("CheXpert-v1.0/test/patient64742/study1", value=1)
    frame = pd.DataFrame([first, second])

    records = build_competition_ground_truth(
        frame,
        study_keys=["patient64741/study1"],
    )

    assert len(records) == 5
    assert {record.label for record in records} == set(
        CHEXPERT_COMPETITION_LABELS
    )
    statuses = {record.label: record.ground_truth_status for record in records}
    assert statuses["Edema"] is LabelStatus.PRESENT
    assert statuses["Atelectasis"] is LabelStatus.ABSENT
    assert all(
        record.ground_truth_source == "chexpert_expert_majority_vote"
        for record in records
    )


def test_ground_truth_rejects_nonbinary_expert_labels() -> None:
    row = _expert_row("CheXpert-v1.0/test/patient64741/study1")
    row["Atelectasis"] = -1

    with pytest.raises(ValueError, match="Expert label must be binary"):
        build_competition_ground_truth(
            pd.DataFrame([row]),
            study_keys=["patient64741/study1"],
        )


def test_validation_ground_truth_collapses_consistent_views() -> None:
    paths = [
        "CheXpert-v1.0/valid/patient64541/study1/view1_frontal.jpg",
        "CheXpert-v1.0/valid/patient64541/study1/view2_lateral.jpg",
    ]
    rows = []
    for path in paths:
        row = {"Path": path}
        row.update({label: 0 for label in CHEXPERT_COMPETITION_LABELS})
        row["Edema"] = 1
        rows.append(row)

    records = build_competition_validation_ground_truth(
        pd.DataFrame(rows),
        study_keys=["patient64541/study1"],
    )

    assert len(records) == 5
    statuses = {record.label: record.ground_truth_status for record in records}
    assert statuses["Edema"] is LabelStatus.PRESENT
    assert statuses["Atelectasis"] is LabelStatus.ABSENT
