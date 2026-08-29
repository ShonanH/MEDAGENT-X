"""Canonical CheXpert label parsing and policy package."""

from __future__ import annotations

import sys
from pathlib import Path

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.labels.aggregate import (
    aggregate_label_statuses,
    aggregate_study_statuses,
)
from medagentx.labels.builder import build_study_label_bundle
from medagentx.labels.constants import (
    ALL_CHEXPERT_LABELS,
    CHEXPERT_TRAINING_POLICY_VERSION,
    DISEASE_LABELS,
    NON_DISEASE_LABELS,
)
from medagentx.labels.parse import parse_chexpert_raw_value
from medagentx.labels.schema import (
    LabelRecord,
    StudyLabelBundle,
    label_column_names,
    label_record_to_columns,
    snake_label,
    study_bundle_to_row,
)
from medagentx.labels.statuses import LabelStatus
from medagentx.labels.training import (
    apply_no_finding_training_rule,
    build_label_record,
    build_training_records,
    training_target_for_status,
)

__all__ = [
    "ALL_CHEXPERT_LABELS",
    "CHEXPERT_TRAINING_POLICY_VERSION",
    "DISEASE_LABELS",
    "LabelRecord",
    "LabelStatus",
    "NON_DISEASE_LABELS",
    "StudyLabelBundle",
    "aggregate_label_statuses",
    "aggregate_study_statuses",
    "apply_no_finding_training_rule",
    "build_label_record",
    "build_study_label_bundle",
    "build_training_records",
    "label_column_names",
    "label_record_to_columns",
    "parse_chexpert_raw_value",
    "snake_label",
    "study_bundle_to_row",
    "training_target_for_status",
]