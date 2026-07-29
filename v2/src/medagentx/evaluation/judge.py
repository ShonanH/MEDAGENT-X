"""Offline Judge orchestration: match predictions to frozen GT and score."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.evaluation.constants import JUDGE_METRIC_VERSION
from medagentx.evaluation.ground_truth import GroundTruthRecord
from medagentx.evaluation.matching import LabelMatch, compare_statuses
from medagentx.evaluation.metrics import (
    AggregateMetrics,
    LabelMetrics,
    compute_aggregate_metrics,
    compute_label_metrics,
)
from medagentx.labels.statuses import LabelStatus


@dataclass(frozen=True)
class JudgeResult:
    """Complete offline Judge output for one evaluation run."""

    matches: tuple[LabelMatch, ...]
    per_label_metrics: tuple[LabelMetrics, ...]
    aggregate_metrics: AggregateMetrics
    judge_metric_version: str = JUDGE_METRIC_VERSION


def _prediction_key(study_key: str, label: str) -> tuple[str, str]:
    return (study_key, label)


def run_judge(
    *,
    ground_truth_records: Sequence[GroundTruthRecord],
    predicted_statuses: Mapping[tuple[str, str], LabelStatus],
) -> JudgeResult:
    """Compare frozen GT rows to predicted statuses and compute metrics.

    Inputs:
      - ground_truth_records: frozen offline GT table rows
      - predicted_statuses: mapping of (study_key, label) -> LabelStatus

    Locked behavior:
      - Does not parse reports
      - Uses matching.py rules
      - Uses metrics.py aggregates
      - Requires an exact prediction for every GT row
    """
    if not ground_truth_records:
        raise ValueError("ground_truth_records must not be empty")

    matches: list[LabelMatch] = []
    seen_keys: set[tuple[str, str]] = set()

    for record in ground_truth_records:
        if not isinstance(record, GroundTruthRecord):
            raise ValueError(
                f"All GT rows must be GroundTruthRecord, got {record!r}"
            )

        key = _prediction_key(record.study_key, record.label)
        if key in seen_keys:
            raise ValueError(
                f"Duplicate ground-truth row for study_key={record.study_key!r}, "
                f"label={record.label!r}"
            )
        seen_keys.add(key)

        if key not in predicted_statuses:
            raise ValueError(
                f"Missing prediction for study_key={record.study_key!r}, "
                f"label={record.label!r}"
            )

        predicted = predicted_statuses[key]
        if not isinstance(predicted, LabelStatus):
            raise ValueError(
                f"predicted_statuses[{key!r}] must be LabelStatus, got {predicted!r}"
            )

        matches.append(
            compare_statuses(
                study_key=record.study_key,
                label=record.label,
                ground_truth_status=record.ground_truth_status,
                predicted_status=predicted,
            )
        )

    by_label: dict[str, list[LabelMatch]] = {}
    for match in matches:
        by_label.setdefault(match.label, []).append(match)

    per_label_metrics = tuple(
        compute_label_metrics(by_label[label]) for label in sorted(by_label)
    )
    aggregate_metrics = compute_aggregate_metrics(per_label_metrics)

    return JudgeResult(
        matches=tuple(matches),
        per_label_metrics=per_label_metrics,
        aggregate_metrics=aggregate_metrics,
    )
