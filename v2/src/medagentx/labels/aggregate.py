"""Study-level aggregation of canonical labels across DICOM views."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Mapping, Sequence

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.labels.constants import ALL_CHEXPERT_LABELS
from medagentx.labels.statuses import LabelStatus

# Locked priority: present > uncertain > absent > unmentioned
_STATUS_PRIORITY: dict[LabelStatus, int] = {
    LabelStatus.PRESENT: 3,
    LabelStatus.UNCERTAIN: 2,
    LabelStatus.ABSENT: 1,
    LabelStatus.UNMENTIONED: 0,
}


def _validate_view_statuses(
    view_statuses: Mapping[str, LabelStatus],
    view_index: int,
) -> None:
    """Validate one view's complete canonical label map."""
    expected = set(ALL_CHEXPERT_LABELS)
    actual = set(view_statuses)

    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)

    if missing or unexpected:
        raise ValueError(
            f"view_statuses[{view_index}] must contain exactly the 14 "
            "CheXpert labels; "
            f"missing={missing}, unexpected={unexpected}"
        )

    for label, status in view_statuses.items():
        if not isinstance(status, LabelStatus):
            raise ValueError(
                f"view_statuses[{view_index}][{label!r}] must be a "
                f"LabelStatus, got {status!r}"
            )


def aggregate_label_statuses(
    statuses: Sequence[LabelStatus],
) -> tuple[LabelStatus, bool]:
    """Aggregate one label across views and report disagreement."""
    if not statuses:
        raise ValueError("statuses must contain at least one LabelStatus")

    for status in statuses:
        if not isinstance(status, LabelStatus):
            raise ValueError(
                f"All statuses must be LabelStatus, got {status!r}"
            )

    unique = set(statuses)
    study_status = max(
        statuses,
        key=lambda status: _STATUS_PRIORITY[status],
    )
    conflict = len(unique) > 1
    return study_status, conflict


def aggregate_study_statuses(
    view_status_maps: Sequence[Mapping[str, LabelStatus]],
) -> tuple[dict[str, LabelStatus], dict[str, bool]]:
    """Aggregate complete per-view maps into one study-level result."""
    if not view_status_maps:
        raise ValueError("view_status_maps must contain at least one view")

    for index, view_statuses in enumerate(view_status_maps):
        _validate_view_statuses(view_statuses, index)

    study_statuses: dict[str, LabelStatus] = {}
    conflicts: dict[str, bool] = {}

    for label in ALL_CHEXPERT_LABELS:
        view_statuses = [view[label] for view in view_status_maps]
        study_status, conflict = aggregate_label_statuses(view_statuses)
        study_statuses[label] = study_status
        conflicts[label] = conflict

    return study_statuses, conflicts
