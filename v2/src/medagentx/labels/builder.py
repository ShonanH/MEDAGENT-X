"""Offline builder that wires parse, aggregate, training, and schema."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.labels.aggregate import aggregate_study_statuses
from medagentx.labels.constants import (
    ALL_CHEXPERT_LABELS,
    CHEXPERT_TRAINING_POLICY_VERSION,
)
from medagentx.labels.parse import parse_chexpert_raw_value
from medagentx.labels.schema import StudyLabelBundle
from medagentx.labels.statuses import LabelStatus
from medagentx.labels.training import build_training_records


def _validate_raw_map(
    raw_map: Mapping[str, Any],
    view_index: int,
) -> None:
    """Require one raw value for each canonical CheXpert label."""
    expected = set(ALL_CHEXPERT_LABELS)
    actual = set(raw_map)

    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)

    if missing or unexpected:
        raise ValueError(
            f"view_raw_maps[{view_index}] must contain exactly the 14 "
            "CheXpert labels; "
            f"missing={missing}, unexpected={unexpected}"
        )


def _parse_view_raw_map(
    raw_map: Mapping[str, Any],
    view_index: int,
) -> dict[str, LabelStatus]:
    """Strictly parse all raw labels for one DICOM view."""
    _validate_raw_map(raw_map, view_index)

    return {
        label: parse_chexpert_raw_value(raw_map[label])
        for label in ALL_CHEXPERT_LABELS
    }


def _study_raw_value_for_label(
    view_raw_maps: Sequence[Mapping[str, Any]],
    view_status_maps: Sequence[Mapping[str, LabelStatus]],
    label: str,
    study_status: LabelStatus,
) -> Any:
    """Keep the first raw value supporting the aggregated study status."""
    for raw_map, status_map in zip(view_raw_maps, view_status_maps):
        if status_map[label] is study_status:
            return raw_map[label]

    raise ValueError(
        f"No view raw value found for label={label!r} with "
        f"study_status={study_status.value!r}"
    )


def build_study_label_bundle(
    *,
    study_key: str,
    deid_patient_id: str,
    dicom_path: str,
    view_raw_maps: Sequence[Mapping[str, Any]],
) -> StudyLabelBundle:
    """Build one study-level label bundle from one or more view maps.

    The pipeline strictly parses each view, aggregates labels using
    present > uncertain > absent > unmentioned, records conflicts,
    applies U-mask and No Finding rules, and preserves the policy version.
    """
    if not isinstance(study_key, str) or not study_key.strip():
        raise ValueError("study_key must be a non-empty string")
    if not isinstance(deid_patient_id, str) or not deid_patient_id.strip():
        raise ValueError("deid_patient_id must be a non-empty string")
    if not isinstance(dicom_path, str) or not dicom_path.strip():
        raise ValueError("dicom_path must be a non-empty string")
    if not view_raw_maps:
        raise ValueError("view_raw_maps must contain at least one view")

    view_status_maps = [
        _parse_view_raw_map(raw_map, index)
        for index, raw_map in enumerate(view_raw_maps)
    ]

    study_statuses, conflicts = aggregate_study_statuses(view_status_maps)

    study_raw_values = {
        label: _study_raw_value_for_label(
            view_raw_maps=view_raw_maps,
            view_status_maps=view_status_maps,
            label=label,
            study_status=study_statuses[label],
        )
        for label in ALL_CHEXPERT_LABELS
    }

    records, no_finding_contradiction = build_training_records(
        raw_values=study_raw_values,
        statuses=study_statuses,
        conflicts=conflicts,
    )

    return StudyLabelBundle(
        study_key=study_key,
        dicom_path=dicom_path,
        deid_patient_id=deid_patient_id,
        labels=records,
        policy_version=CHEXPERT_TRAINING_POLICY_VERSION,
        no_finding_contradiction=no_finding_contradiction,
    )
