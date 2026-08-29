"""Constrained per-label threshold tuning for vision predictions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label


THRESHOLD_POLICY_VERSION = "vision_threshold_policy_v2"


@dataclass(frozen=True)
class ThresholdTuningConstraints:
    """Guardrails that prevent validation F1 tuning from overcalling disease."""

    max_threshold_drop: float = 0.10
    min_precision_drop: float = 0.02
    max_positive_rate_multiplier: float = 1.25
    strict_sanity_f1_drop_allowed: float = 0.0
    min_label_f1_gain: float = 0.01
    threshold_min: float = 0.01
    threshold_max: float = 0.99
    grid_steps: int = 197


@dataclass(frozen=True)
class BinaryMetrics:
    """Binary precision/recall/F1 plus positive prediction rate."""

    tp: int
    tn: int
    fp: int
    fn: int
    precision: float | None
    recall: float | None
    f1: float | None
    positive_rate: float
    scoreable_cells: int


@dataclass(frozen=True)
class ThresholdCandidate:
    """One candidate threshold and its scored behavior."""

    label: str
    threshold: float
    judge_metrics: BinaryMetrics
    strict_metrics: BinaryMetrics


@dataclass(frozen=True)
class ThresholdTuningResult:
    """Accepted or rejected threshold decision for one label."""

    label: str
    current_threshold: float
    selected_threshold: float
    proposed_threshold: float
    accepted: bool
    reject_reason: str
    current_judge_metrics: BinaryMetrics
    proposed_judge_metrics: BinaryMetrics
    selected_judge_metrics: BinaryMetrics
    current_strict_metrics: BinaryMetrics
    proposed_strict_metrics: BinaryMetrics
    selected_strict_metrics: BinaryMetrics


def _safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None
    return 2.0 * precision * recall / (precision + recall)


def _status_values(values: Iterable[Any]) -> np.ndarray:
    return np.asarray([str(value).strip().lower() for value in values], dtype=object)


def _score_predictions(
    ground_truth_statuses: Sequence[Any],
    predicted_present: Sequence[bool],
    *,
    treat_uncertain_unmentioned_as_absent: bool,
) -> BinaryMetrics:
    gt = _status_values(ground_truth_statuses)
    pred = np.asarray(predicted_present, dtype=bool)
    if len(gt) != len(pred):
        raise ValueError("ground_truth_statuses and predicted_present length mismatch")

    positive_gt = gt == "present"
    if treat_uncertain_unmentioned_as_absent:
        negative_gt = np.isin(gt, ["absent", "uncertain", "unmentioned"])
    else:
        negative_gt = gt == "absent"
    scoreable = positive_gt | negative_gt

    tp = int(np.sum(positive_gt & pred))
    fn = int(np.sum(positive_gt & ~pred))
    fp = int(np.sum(negative_gt & pred))
    tn = int(np.sum(negative_gt & ~pred))

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    return BinaryMetrics(
        tp=tp,
        tn=tn,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=_f1(precision, recall),
        positive_rate=float(np.mean(pred)) if len(pred) else 0.0,
        scoreable_cells=int(np.sum(scoreable)),
    )


def _candidate_thresholds(
    probabilities: np.ndarray,
    constraints: ThresholdTuningConstraints,
) -> list[float]:
    grid = np.linspace(
        constraints.threshold_min,
        constraints.threshold_max,
        constraints.grid_steps,
    )
    values = np.concatenate([grid, probabilities])
    values = values[
        (values >= constraints.threshold_min) & (values <= constraints.threshold_max)
    ]
    return sorted(float(value) for value in np.unique(np.round(values, 6)))


def _score_candidate(
    *,
    label: str,
    threshold: float,
    probabilities: np.ndarray,
    ground_truth_statuses: np.ndarray,
) -> ThresholdCandidate:
    predicted_present = probabilities >= threshold
    return ThresholdCandidate(
        label=label,
        threshold=float(threshold),
        judge_metrics=_score_predictions(
            ground_truth_statuses,
            predicted_present,
            treat_uncertain_unmentioned_as_absent=False,
        ),
        strict_metrics=_score_predictions(
            ground_truth_statuses,
            predicted_present,
            treat_uncertain_unmentioned_as_absent=True,
        ),
    )


def _metric_value(value: float | None) -> float:
    return -1.0 if value is None else float(value)


def _best_candidate(
    candidates: Sequence[ThresholdCandidate],
    *,
    current_threshold: float,
) -> ThresholdCandidate:
    if not candidates:
        raise ValueError("candidates must not be empty")
    return max(
        candidates,
        key=lambda item: (
            _metric_value(item.judge_metrics.f1),
            _metric_value(item.judge_metrics.precision),
            -abs(item.threshold - current_threshold),
        ),
    )


def _best_accepted_candidate(
    candidates: Sequence[ThresholdCandidate],
    *,
    current: ThresholdCandidate,
    constraints: ThresholdTuningConstraints,
) -> ThresholdCandidate | None:
    accepted = [
        candidate
        for candidate in candidates
        if _rejection_reason(
            current=current,
            proposed=candidate,
            constraints=constraints,
        )
        == ""
    ]
    if not accepted:
        return None
    return _best_candidate(accepted, current_threshold=current.threshold)


def _rejection_reason(
    *,
    current: ThresholdCandidate,
    proposed: ThresholdCandidate,
    constraints: ThresholdTuningConstraints,
) -> str:
    current_f1 = _metric_value(current.judge_metrics.f1)
    proposed_f1 = _metric_value(proposed.judge_metrics.f1)
    if proposed_f1 - current_f1 < constraints.min_label_f1_gain:
        return "f1_gain_below_min"

    threshold_drop = current.threshold - proposed.threshold
    if threshold_drop > constraints.max_threshold_drop:
        return "threshold_drop_too_large"

    current_precision = _metric_value(current.judge_metrics.precision)
    proposed_precision = _metric_value(proposed.judge_metrics.precision)
    if current_precision - proposed_precision > constraints.min_precision_drop:
        return "precision_drop_too_large"

    current_rate = current.judge_metrics.positive_rate
    proposed_rate = proposed.judge_metrics.positive_rate
    allowed_rate = max(current_rate * constraints.max_positive_rate_multiplier, 1e-12)
    if proposed_rate > allowed_rate:
        return "positive_rate_too_high"

    current_strict_f1 = _metric_value(current.strict_metrics.f1)
    proposed_strict_f1 = _metric_value(proposed.strict_metrics.f1)
    strict_drop = current_strict_f1 - proposed_strict_f1
    if strict_drop > constraints.strict_sanity_f1_drop_allowed:
        return "strict_sanity_f1_drop"

    return ""


def tune_label_threshold(
    *,
    label: str,
    probabilities: Sequence[float],
    ground_truth_statuses: Sequence[Any],
    current_threshold: float,
    constraints: ThresholdTuningConstraints,
) -> ThresholdTuningResult:
    """Tune one label threshold with conservative guardrails."""
    probs = np.asarray(probabilities, dtype=float)
    gt = _status_values(ground_truth_statuses)
    if len(probs) != len(gt):
        raise ValueError("probabilities and ground_truth_statuses length mismatch")
    if len(probs) == 0:
        raise ValueError("probabilities must not be empty")

    current = _score_candidate(
        label=label,
        threshold=float(current_threshold),
        probabilities=probs,
        ground_truth_statuses=gt,
    )
    candidates = [
        _score_candidate(
            label=label,
            threshold=threshold,
            probabilities=probs,
            ground_truth_statuses=gt,
        )
        for threshold in _candidate_thresholds(probs, constraints)
    ]
    proposed = _best_candidate(candidates, current_threshold=float(current_threshold))
    accepted_candidate = _best_accepted_candidate(
        candidates,
        current=current,
        constraints=constraints,
    )
    if accepted_candidate is None:
        accepted = False
        selected = current
        reject_reason = _rejection_reason(
            current=current,
            proposed=proposed,
            constraints=constraints,
        )
    else:
        accepted = True
        selected = accepted_candidate
        reject_reason = ""

    return ThresholdTuningResult(
        label=label,
        current_threshold=current.threshold,
        selected_threshold=selected.threshold,
        proposed_threshold=proposed.threshold,
        accepted=accepted,
        reject_reason=reject_reason,
        current_judge_metrics=current.judge_metrics,
        proposed_judge_metrics=proposed.judge_metrics,
        selected_judge_metrics=selected.judge_metrics,
        current_strict_metrics=current.strict_metrics,
        proposed_strict_metrics=proposed.strict_metrics,
        selected_strict_metrics=selected.strict_metrics,
    )


def tune_thresholds_from_frames(
    *,
    vision_predictions: pd.DataFrame,
    study_labels: pd.DataFrame,
    labels: Sequence[str] = DISEASE_LABELS,
    constraints: ThresholdTuningConstraints = ThresholdTuningConstraints(),
) -> tuple[ThresholdTuningResult, ...]:
    """Tune all label thresholds from vision predictions and study labels."""
    if vision_predictions.empty:
        raise ValueError("vision_predictions must not be empty")
    if study_labels.empty:
        raise ValueError("study_labels must not be empty")
    if "study_key" not in vision_predictions or "study_key" not in study_labels:
        raise ValueError("Both frames must contain study_key")

    joined = vision_predictions.merge(
        study_labels,
        on="study_key",
        how="left",
        suffixes=("", "_gt"),
    )
    if joined["study_key"].isna().any():
        raise ValueError("Merged threshold tuning frame contains missing study_key")

    results: list[ThresholdTuningResult] = []
    for label in labels:
        slug = snake_label(label)
        probability_col = f"probability_{slug}"
        threshold_col = f"threshold_{slug}"
        status_col = f"status_{slug}_gt"
        missing = [
            col
            for col in (probability_col, threshold_col, status_col)
            if col not in joined
        ]
        if missing:
            raise ValueError(f"Missing required columns for {label}: {missing}")

        thresholds = joined[threshold_col].dropna().astype(float).unique()
        if len(thresholds) != 1:
            raise ValueError(
                f"Expected one current threshold for {label}, got {sorted(thresholds)}"
            )
        results.append(
            tune_label_threshold(
                label=label,
                probabilities=joined[probability_col].astype(float),
                ground_truth_statuses=joined[status_col],
                current_threshold=float(thresholds[0]),
                constraints=constraints,
            )
        )
    return tuple(results)


def _metrics_columns(prefix: str, metrics: BinaryMetrics) -> dict[str, Any]:
    return {
        f"{prefix}_tp": metrics.tp,
        f"{prefix}_tn": metrics.tn,
        f"{prefix}_fp": metrics.fp,
        f"{prefix}_fn": metrics.fn,
        f"{prefix}_precision": metrics.precision,
        f"{prefix}_recall": metrics.recall,
        f"{prefix}_f1": metrics.f1,
        f"{prefix}_positive_rate": metrics.positive_rate,
        f"{prefix}_scoreable_cells": metrics.scoreable_cells,
    }


def threshold_tuning_report_frame(
    results: Sequence[ThresholdTuningResult],
) -> pd.DataFrame:
    """Serialize threshold decisions to a compact report table."""
    rows: list[dict[str, Any]] = []
    for result in results:
        current_f1 = _metric_value(result.current_judge_metrics.f1)
        proposed_f1 = _metric_value(result.proposed_judge_metrics.f1)
        selected_f1 = _metric_value(result.selected_judge_metrics.f1)
        row: dict[str, Any] = {
            "label": result.label,
            "current_threshold": result.current_threshold,
            "proposed_threshold": result.proposed_threshold,
            "selected_threshold": result.selected_threshold,
            "accepted": result.accepted,
            "reject_reason": result.reject_reason,
            "proposed_f1_gain": proposed_f1 - current_f1,
            "selected_f1_gain": selected_f1 - current_f1,
        }
        row.update(_metrics_columns("current_judge", result.current_judge_metrics))
        row.update(_metrics_columns("proposed_judge", result.proposed_judge_metrics))
        row.update(_metrics_columns("selected_judge", result.selected_judge_metrics))
        row.update(_metrics_columns("current_strict", result.current_strict_metrics))
        row.update(_metrics_columns("proposed_strict", result.proposed_strict_metrics))
        row.update(_metrics_columns("selected_strict", result.selected_strict_metrics))
        rows.append(row)
    return pd.DataFrame(rows)


def threshold_policy_payload(
    *,
    results: Sequence[ThresholdTuningResult],
    constraints: ThresholdTuningConstraints,
    split: str,
) -> dict[str, Any]:
    """Build the JSON threshold policy artifact."""
    selected_thresholds = {
        result.label: result.selected_threshold for result in results
    }
    accepted_labels = [result.label for result in results if result.accepted]
    return {
        "threshold_policy_version": THRESHOLD_POLICY_VERSION,
        "source_split": split,
        "constraints": constraints.__dict__,
        "selected_thresholds": selected_thresholds,
        "accepted_labels": accepted_labels,
        "rejected_labels": {
            result.label: result.reject_reason
            for result in results
            if not result.accepted
        },
    }
