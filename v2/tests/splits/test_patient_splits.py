"""Contract tests for patient-level split assignment."""

from __future__ import annotations

import pandas as pd

from medagentx.splits.assign import assign_patient_split
from medagentx.splits.build import (
    build_patient_split_table,
    build_study_split_table,
    build_view_split_table,
    summarize_splits,
)
from medagentx.splits.constants import ALL_SPLITS, SPLIT_SEED


def test_assign_patient_split_is_deterministic() -> None:
    first = assign_patient_split("patient00001", seed=SPLIT_SEED)
    second = assign_patient_split("patient00001", seed=SPLIT_SEED)
    assert first == second
    assert first in ALL_SPLITS


def test_all_views_of_a_patient_share_one_split() -> None:
    eligible = pd.DataFrame(
        [
            {
                "deid_patient_id": "patient1",
                "study_key": "patient1/study1",
                "dicom_path": "patient1/study1/frontal.dcm",
            },
            {
                "deid_patient_id": "patient1",
                "study_key": "patient1/study1",
                "dicom_path": "patient1/study1/lateral.dcm",
            },
            {
                "deid_patient_id": "patient1",
                "study_key": "patient1/study2",
                "dicom_path": "patient1/study2/frontal.dcm",
            },
            {
                "deid_patient_id": "patient2",
                "study_key": "patient2/study1",
                "dicom_path": "patient2/study1/frontal.dcm",
            },
        ]
    )

    patient_splits = build_patient_split_table(eligible)
    study_splits = build_study_split_table(eligible, patient_splits)
    view_splits = build_view_split_table(eligible, patient_splits)

    patient1_split = patient_splits.loc[
        patient_splits["deid_patient_id"] == "patient1", "split"
    ].iloc[0]
    assert set(
        study_splits.loc[
            study_splits["deid_patient_id"] == "patient1", "split"
        ].tolist()
    ) == {patient1_split}
    assert set(
        view_splits.loc[
            view_splits["deid_patient_id"] == "patient1", "split"
        ].tolist()
    ) == {patient1_split}

    summary = summarize_splits(patient_splits, study_splits, view_splits)
    assert summary["patients"] == 2
    assert summary["studies"] == 3
    assert summary["views"] == 4
