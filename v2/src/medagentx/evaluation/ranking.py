"""Threshold-independent ranking metrics for continuous label scores."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from medagentx.evaluation.constants import RANKING_METRIC_VERSION
from medagentx.evaluation.ground_truth import GroundTruthRecord
from medagentx.labels.statuses import LabelStatus


@dataclass(frozen=True)
class RankingCell:
    """One study-label score and its binary-evaluation disposition."""

    study_key: str
    label: str
    ground_truth_status: LabelStatus
    ground_truth_binary: int | None
    prediction_score: float
    included: bool
    exclusion_reason: str | None


@dataclass(frozen=True)
class LabelRankingMetrics:
    """AUROC and average precision for one label."""

    label: str
    total: int
    evaluated: int
    positive: int
    negative: int
    excluded_uncertain: int
    excluded_unmentioned: int
    auroc: float | None
    average_precision: float | None


@dataclass(frozen=True)
class RankingResult:
    """Per-label and macro ranking metrics for one prediction run."""

    cells: tuple[RankingCell, ...]
    per_label_metrics: tuple[LabelRankingMetrics, ...]
    macro_auroc: float | None
    macro_average_precision: float | None
    requested_label_count: int
    scored_label_count: int
    ranking_metric_version: str = RANKING_METRIC_VERSION


def _binary_target(status: LabelStatus) -> tuple[int | None, str | None]:
    if status is LabelStatus.PRESENT:
        return 1, None
    if status is LabelStatus.ABSENT:
        return 0, None
    if status is LabelStatus.UNCERTAIN:
        return None, "ground_truth_uncertain"
    if status is LabelStatus.UNMENTIONED:
        return None, "ground_truth_unmentioned"
    raise ValueError(f"Unsupported ground-truth status: {status!r}")


def _auroc_and_average_precision(
    y_true: np.ndarray,
    y_score: np.ndarray,
) -> tuple[float, float]:
    """Compute binary ranking metrics, treating tied scores as equal ranks."""
    order = np.argsort(-y_score, kind="stable")
    sorted_true = y_true[order]
    sorted_scores = y_score[order]
    distinct_ends = np.r_[
        np.flatnonzero(np.diff(sorted_scores)) + 1,
        len(sorted_scores),
    ]
    cumulative_tp = np.cumsum(sorted_true)[distinct_ends - 1]
    cumulative_fp = distinct_ends - cumulative_tp

    positive = int(y_true.sum())
    negative = int(len(y_true) - positive)
    tpr = cumulative_tp / positive
    fpr = cumulative_fp / negative
    tpr_points = np.r_[0.0, tpr]
    fpr_points = np.r_[0.0, fpr]
    auroc = float(
        np.sum(
            np.diff(fpr_points)
            * (tpr_points[:-1] + tpr_points[1:])
            / 2.0
        )
    )

    recall_increments = np.diff(np.r_[0.0, tpr])
    precision = cumulative_tp / distinct_ends
    average_precision = float(np.sum(recall_increments * precision))
    return auroc, average_precision


def compute_ranking_metrics(
    *,
    ground_truth_records: Sequence[GroundTruthRecord],
    predicted_scores: Mapping[tuple[str, str], float],
    labels: Sequence[str],
    require_two_classes_per_label: bool = False,
) -> RankingResult:
    """Compute AUROC/AP after masking non-binary ground-truth statuses."""
    if not ground_truth_records:
        raise ValueError("ground_truth_records must not be empty")
    if not labels:
        raise ValueError("labels must not be empty")

    requested_labels = tuple(labels)
    if len(set(requested_labels)) != len(requested_labels):
        raise ValueError("labels must not contain duplicates")
    requested_set = set(requested_labels)

    records_by_label: dict[str, list[GroundTruthRecord]] = {
        label: [] for label in requested_labels
    }
    seen_keys: set[tuple[str, str]] = set()
    cells: list[RankingCell] = []

    for record in ground_truth_records:
        if record.label not in requested_set:
            continue
        key = (record.study_key, record.label)
        if key in seen_keys:
            raise ValueError(f"Duplicate ground-truth ranking key: {key!r}")
        seen_keys.add(key)
        records_by_label[record.label].append(record)

        if key not in predicted_scores:
            raise ValueError(f"Missing prediction score for {key!r}")
        score = float(predicted_scores[key])
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            raise ValueError(
                f"Prediction score for {key!r} must be finite and in [0, 1], "
                f"got {predicted_scores[key]!r}"
            )

        target, exclusion_reason = _binary_target(record.ground_truth_status)
        cells.append(
            RankingCell(
                study_key=record.study_key,
                label=record.label,
                ground_truth_status=record.ground_truth_status,
                ground_truth_binary=target,
                prediction_score=score,
                included=target is not None,
                exclusion_reason=exclusion_reason,
            )
        )

    missing_labels = [
        label for label, records in records_by_label.items() if not records
    ]
    if missing_labels:
        raise ValueError(f"No ground-truth records for labels: {missing_labels}")

    metrics: list[LabelRankingMetrics] = []
    for label in requested_labels:
        label_cells = [cell for cell in cells if cell.label == label]
        included = [cell for cell in label_cells if cell.included]
        y_true = np.asarray(
            [cell.ground_truth_binary for cell in included], dtype=np.int64
        )
        y_score = np.asarray(
            [cell.prediction_score for cell in included], dtype=np.float64
        )
        positive = int(y_true.sum()) if len(y_true) else 0
        negative = int(len(y_true) - positive)

        if positive and negative:
            auroc, average_precision = _auroc_and_average_precision(
                y_true,
                y_score,
            )
        else:
            auroc = None
            average_precision = None
            if require_two_classes_per_label:
                raise ValueError(
                    f"Label {label!r} requires both positive and negative "
                    f"ground truth for AUROC; positive={positive}, negative={negative}"
                )

        metrics.append(
            LabelRankingMetrics(
                label=label,
                total=len(label_cells),
                evaluated=len(included),
                positive=positive,
                negative=negative,
                excluded_uncertain=sum(
                    cell.ground_truth_status is LabelStatus.UNCERTAIN
                    for cell in label_cells
                ),
                excluded_unmentioned=sum(
                    cell.ground_truth_status is LabelStatus.UNMENTIONED
                    for cell in label_cells
                ),
                auroc=auroc,
                average_precision=average_precision,
            )
        )

    aurocs = [item.auroc for item in metrics if item.auroc is not None]
    average_precisions = [
        item.average_precision
        for item in metrics
        if item.average_precision is not None
    ]
    return RankingResult(
        cells=tuple(cells),
        per_label_metrics=tuple(metrics),
        macro_auroc=float(np.mean(aurocs)) if aurocs else None,
        macro_average_precision=(
            float(np.mean(average_precisions)) if average_precisions else None
        ),
        requested_label_count=len(requested_labels),
        scored_label_count=len(aurocs),
    )
