"""Contract tests for deterministic label-enriched cohort selection."""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from medagentx.data.balanced_select import select_enriched_cohort
from medagentx.data.dicoms import (
    download_eligible_dicoms,
    reuse_existing_dicoms,
)
from medagentx.data.redivis_client import RedivisClient, RedivisDownloadResult
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import label_column_names
from medagentx.splits.assign import assign_patient_split
from medagentx.splits.constants import ALL_SPLITS, SPLIT_SEED


def _patients_for_split(split: str, count: int) -> list[str]:
    patients: list[str] = []
    index = 0
    while len(patients) < count:
        patient_id = f"patient_{split}_{index:05d}"
        if assign_patient_split(patient_id, seed=SPLIT_SEED) == split:
            patients.append(patient_id)
        index += 1
    return patients


def _study_label_row(
    patient_id: str,
    *,
    positive: bool,
    supervised: bool = True,
    study_index: int = 1,
    positive_labels: frozenset[str] | None = None,
) -> dict[str, object]:
    study_key = f"{patient_id}/study{study_index}"
    row: dict[str, object] = {
        "study_key": study_key,
        "deid_patient_id": patient_id,
    }
    for label in DISEASE_LABELS:
        columns = label_column_names(label)
        is_positive = (
            positive if positive_labels is None else label in positive_labels
        )
        row[columns["training_mask"]] = int(supervised)
        row[columns["training_target"]] = (
            float(is_positive) if supervised else None
        )
    return row


def _eligible_row(patient_id: str, *, study_index: int = 1) -> dict[str, str]:
    study_key = f"{patient_id}/study{study_index}"
    return {
        "deid_patient_id": patient_id,
        "study_key": study_key,
        "dicom_path": f"{study_key}/view1.dcm",
        "file_id": f"file-{patient_id}-{study_index}",
    }


def test_selection_meets_small_targets_and_is_deterministic() -> None:
    patients: list[tuple[str, bool]] = []
    for split in ALL_SPLITS:
        positive, background = _patients_for_split(split, 2)
        patients.extend(((positive, True), (background, False)))

    eligible = pd.DataFrame([_eligible_row(patient) for patient, _ in patients])
    labels = pd.DataFrame(
        [
            _study_label_row(patient, positive=positive)
            for patient, positive in patients
        ]
    )
    targets = {split: 1 for split in ALL_SPLITS}

    first = select_enriched_cohort(
        eligible,
        labels,
        positive_targets=targets,
        negative_ratio=1,
        patient_cap=30,
    )
    second = select_enriched_cohort(
        eligible,
        labels,
        positive_targets=targets,
        negative_ratio=1,
        patient_cap=30,
    )

    assert first.patient_selection.equals(second.patient_selection)
    assert len(first.patient_selection) == 6
    assert set(first.patient_selection["selection_reason"]) == {
        "positive_enrichment",
        "background",
    }
    assert first.label_audit["target_met"].all()
    assert (
        first.patient_selection.groupby("deid_patient_id")["split"].nunique()
        == 1
    ).all()


def test_unavailable_labels_are_audited_without_crashing() -> None:
    patient = _patients_for_split("train", 1)[0]
    eligible = pd.DataFrame([_eligible_row(patient)])
    labels = pd.DataFrame(
        [_study_label_row(patient, positive=True, supervised=True)]
    )

    result = select_enriched_cohort(
        eligible,
        labels,
        positive_targets={split: 2 for split in ALL_SPLITS},
        negative_ratio=0,
        patient_cap=20,
    )

    val_rows = result.label_audit[result.label_audit["split"] == "val"]
    assert (val_rows["positive_shortage"] == 2).all()
    assert (
        val_rows["positive_shortage_reason"]
        == "insufficient_available_positives"
    ).all()
    assert not val_rows["target_met"].any()
    assert len(result.patient_selection) == 1


def test_selection_never_exceeds_patient_cap() -> None:
    patients: list[str] = []
    for split in ALL_SPLITS:
        patients.extend(_patients_for_split(split, 6))
    eligible = pd.DataFrame([_eligible_row(patient) for patient in patients])
    labels = pd.DataFrame(
        [_study_label_row(patient, positive=True) for patient in patients]
    )

    result = select_enriched_cohort(
        eligible,
        labels,
        positive_targets={split: 10 for split in ALL_SPLITS},
        negative_ratio=0,
        patient_cap=10,
    )

    assert len(result.patient_selection) <= 10
    assert (result.label_audit["positive_shortage"] > 0).any()


def test_studies_per_patient_respect_the_cap() -> None:
    patients = _patients_for_split("train", 3)
    studies_available = 6
    eligible = pd.DataFrame(
        [
            _eligible_row(patient, study_index=index)
            for patient in patients
            for index in range(1, studies_available + 1)
        ]
    )
    labels = pd.DataFrame(
        [
            _study_label_row(patient, positive=True, study_index=index)
            for patient in patients
            for index in range(1, studies_available + 1)
        ]
    )

    result = select_enriched_cohort(
        eligible,
        labels,
        positive_targets={split: 10 for split in ALL_SPLITS},
        negative_ratio=0,
        patient_cap=20,
        max_studies_per_patient=2,
    )
    repeat = select_enriched_cohort(
        eligible,
        labels,
        positive_targets={split: 10 for split in ALL_SPLITS},
        negative_ratio=0,
        patient_cap=20,
        max_studies_per_patient=2,
    )

    assert result.patient_selection["selected_study_count"].max() == 2
    assert len(result.study_selection) == len(patients) * 2
    assert result.eligible_rows["study_key"].nunique() == len(patients) * 2
    assert not result.study_selection["study_key"].duplicated().any()
    assert result.study_selection.equals(repeat.study_selection)
    assert set(result.study_selection["deid_patient_id"]) == set(
        result.patient_selection["deid_patient_id"]
    )


def test_capped_selection_prefers_studies_that_close_deficits() -> None:
    patient = _patients_for_split("train", 1)[0]
    target_label = DISEASE_LABELS[-1]
    eligible = pd.DataFrame(
        [
            _eligible_row(patient, study_index=index)
            for index in range(1, 4)
        ]
    )
    labels = pd.DataFrame(
        [
            _study_label_row(patient, positive=False, study_index=1),
            _study_label_row(
                patient,
                positive=False,
                study_index=2,
                positive_labels=frozenset({target_label}),
            ),
            _study_label_row(patient, positive=False, study_index=3),
        ]
    )

    result = select_enriched_cohort(
        eligible,
        labels,
        positive_targets={split: 1 for split in ALL_SPLITS},
        negative_ratio=0,
        patient_cap=20,
        max_studies_per_patient=1,
    )

    assert result.study_selection["study_key"].tolist() == [
        f"{patient}/study2"
    ]
    train_rows = result.label_audit[result.label_audit["split"] == "train"]
    assert (
        train_rows.loc[
            train_rows["label"] == target_label, "positive_shortage"
        ]
        == 0
    ).all()


def test_selection_rejects_misaligned_study_labels() -> None:
    patient = _patients_for_split("train", 1)[0]
    eligible = pd.DataFrame([_eligible_row(patient)])
    labels = pd.DataFrame(
        [_study_label_row("different_patient", positive=True)]
    )

    try:
        select_enriched_cohort(
            eligible,
            labels,
            positive_targets={split: 1 for split in ALL_SPLITS},
            negative_ratio=0,
            patient_cap=20,
        )
    except ValueError as exc:
        assert "same study_keys" in str(exc)
    else:
        raise AssertionError("misaligned study labels must be rejected")


def test_matching_dicoms_are_reused_without_network(
    tmp_path: Path,
) -> None:
    source = tmp_path / "old"
    destination = tmp_path / "new"
    patient = "patient1"
    eligible = pd.DataFrame([_eligible_row(patient)])
    relative = Path(str(eligible.iloc[0]["dicom_path"]))
    source_file = source / relative
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"dicom-bytes")

    status = reuse_existing_dicoms(eligible, source, destination)

    assert status.iloc[0]["status"] in {"reused_hardlink", "reused_copy"}
    assert (destination / relative).read_bytes() == b"dicom-bytes"


def test_parallel_downloads_keep_input_row_order(tmp_path: Path) -> None:
    eligible = pd.DataFrame(
        [_eligible_row(f"patient{index:03d}") for index in range(40)]
    )

    class _StubClient(RedivisClient):
        def download_raw_file(
            self,
            file_id: str,
            output_path: object,
            *,
            overwrite: bool = False,
            resume: bool = True,
        ) -> RedivisDownloadResult:
            # Reverse-order sleeps force out-of-order completion.
            index = int(file_id.split("patient", 1)[1].split("-", 1)[0])
            time.sleep(0.002 * (40 - index))
            return RedivisDownloadResult(
                file_id=file_id,
                output_path=str(output_path),
                status="downloaded",
                bytes_written=11,
            )

    client = _StubClient(api_token="test-token")
    serial = download_eligible_dicoms(
        client,
        eligible,
        tmp_path / "serial",
        max_workers=1,
        progress_every=0,
    )
    parallel = download_eligible_dicoms(
        client,
        eligible,
        tmp_path / "parallel",
        max_workers=8,
        progress_every=0,
    )

    assert parallel["file_id"].tolist() == eligible["file_id"].tolist()
    assert parallel["dicom_path"].tolist() == serial["dicom_path"].tolist()
    assert (parallel["status"] == "downloaded").all()
