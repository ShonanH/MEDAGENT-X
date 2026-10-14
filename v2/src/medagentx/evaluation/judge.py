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
    StatusConfusionCount,
    UncertainStatusMetrics,
    compute_aggregate_metrics,
    compute_label_metrics,
    compute_status_confusion_counts,
    compute_uncertain_status_metrics,
)
from medagentx.evaluation.ranking import RankingResult, compute_ranking_metrics
from medagentx.labels.statuses import LabelStatus


@dataclass(frozen=True)
class JudgeResult:
    """Complete offline Judge output for one evaluation run."""

    matches: tuple[LabelMatch, ...]
    per_label_metrics: tuple[LabelMetrics, ...]
    uncertain_status_metrics: tuple[UncertainStatusMetrics, ...]
    status_confusion_counts: tuple[StatusConfusionCount, ...]
    aggregate_metrics: AggregateMetrics
    ranking_result: RankingResult | None = None
    judge_metric_version: str = JUDGE_METRIC_VERSION


def _prediction_key(study_key: str, label: str) -> tuple[str, str]:
    return (study_key, label)


def run_judge(
    *,
    ground_truth_records: Sequence[GroundTruthRecord],
    predicted_statuses: Mapping[tuple[str, str], LabelStatus],
    predicted_scores: Mapping[tuple[str, str], float] | None = None,
    ranking_labels: Sequence[str] | None = None,
    require_two_classes_per_ranking_label: bool = False,
) -> JudgeResult:
    """Compare frozen GT rows to predicted statuses and compute metrics.

    Inputs:
      - ground_truth_records: frozen offline GT table rows
      - predicted_statuses: mapping of (study_key, label) -> LabelStatus
      - predicted_scores: optional continuous scores for ranking metrics
      - ranking_labels: labels included in AUROC/AP when scores are provided

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
    uncertain_status_metrics = tuple(
        compute_uncertain_status_metrics(by_label[label])
        for label in sorted(by_label)
    )
    status_confusion_counts = tuple(
        count
        for label in sorted(by_label)
        for count in compute_status_confusion_counts(by_label[label])
    )
    aggregate_metrics = compute_aggregate_metrics(per_label_metrics)
    ranking_result = None
    if predicted_scores is not None:
        selected_labels = (
            ranking_labels if ranking_labels is not None else tuple(sorted(by_label))
        )
        ranking_result = compute_ranking_metrics(
            ground_truth_records=ground_truth_records,
            predicted_scores=predicted_scores,
            labels=selected_labels,
            require_two_classes_per_label=require_two_classes_per_ranking_label,
        )

    return JudgeResult(
        matches=tuple(matches),
        per_label_metrics=per_label_metrics,
        uncertain_status_metrics=uncertain_status_metrics,
        status_confusion_counts=status_confusion_counts,
        aggregate_metrics=aggregate_metrics,
        ranking_result=ranking_result,
    )
