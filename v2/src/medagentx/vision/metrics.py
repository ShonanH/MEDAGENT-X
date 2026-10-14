"""Masked multilabel metrics and validation-only threshold selection."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from medagentx.labels.constants import DISEASE_LABELS
from medagentx.vision.constants import (
    THRESHOLD_MAX,
    THRESHOLD_MIN,
    THRESHOLD_STEP,
)


def _binary_f1(targets: np.ndarray, predictions: np.ndarray) -> float:
    tp = int(np.sum((targets == 1) & (predictions == 1)))
    fp = int(np.sum((targets == 0) & (predictions == 1)))
    fn = int(np.sum((targets == 1) & (predictions == 0)))
    denominator = 2 * tp + fp + fn
    return float(2 * tp / denominator) if denominator else 0.0


def tune_validation_thresholds(
    targets: np.ndarray,
    probabilities: np.ndarray,
    masks: np.ndarray,
    *,
    label_names: Sequence[str] = DISEASE_LABELS,
    threshold_min: float = THRESHOLD_MIN,
    threshold_max: float = THRESHOLD_MAX,
    threshold_step: float = THRESHOLD_STEP,
) -> dict[str, float]:
    """Tune one disease threshold on masked validation F1 only."""
    _validate_shapes(targets, probabilities, masks)
    grid = np.arange(
        threshold_min,
        threshold_max + threshold_step / 2.0,
        threshold_step,
    )
    label_names = tuple(label_names)
    if len(label_names) != targets.shape[1]:
        raise ValueError("label_names length must match metric array columns")
    output: dict[str, float] = {}

    for index, label in enumerate(label_names):
        valid = masks[:, index] == 1
        if not np.any(valid):
            output[label] = 0.5
            continue
        y_true = targets[valid, index].astype(int)
        y_prob = probabilities[valid, index]
        if len(np.unique(y_true)) < 2:
            output[label] = 0.5
            continue
        best_threshold = 0.5
        best_f1 = -1.0
        for threshold in grid:
            f1 = _binary_f1(y_true, (y_prob >= threshold).astype(int))
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = float(threshold)
        output[label] = round(best_threshold, 4)
    return output


def compute_masked_metrics(
    targets: np.ndarray,
    probabilities: np.ndarray,
    masks: np.ndarray,
    thresholds: dict[str, float] | None = None,
    *,
    label_names: Sequence[str] = DISEASE_LABELS,
) -> dict[str, float | int | None]:
    """Compute per-label and macro AUROC/AP/F1 on supervised cells."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    _validate_shapes(targets, probabilities, masks)
    label_names = tuple(label_names)
    if len(label_names) != targets.shape[1]:
        raise ValueError("label_names length must match metric array columns")
    thresholds = thresholds or {label: 0.5 for label in label_names}

    output: dict[str, float | int | None] = {}
    aurocs: list[float] = []
    average_precisions: list[float] = []
    f1s: list[float] = []

    for index, label in enumerate(label_names):
        valid = masks[:, index] == 1
        y_true = targets[valid, index].astype(int)
        y_prob = probabilities[valid, index]
        output[f"{label}/supervised"] = int(valid.sum())
        output[f"{label}/positive"] = int(y_true.sum())

        threshold = float(thresholds.get(label, 0.5))
        output[f"{label}/threshold"] = threshold
        if not len(y_true):
            output[f"{label}/auroc"] = None
            output[f"{label}/average_precision"] = None
            output[f"{label}/f1"] = None
            continue

        if int(y_true.sum()) == 0:
            output[f"{label}/f1"] = None
        else:
            f1 = _binary_f1(y_true, (y_prob >= threshold).astype(int))
            output[f"{label}/f1"] = f1
            f1s.append(f1)

        if len(np.unique(y_true)) < 2:
            output[f"{label}/auroc"] = None
            output[f"{label}/average_precision"] = None
            continue

        auroc = float(roc_auc_score(y_true, y_prob))
        average_precision = float(average_precision_score(y_true, y_prob))
        output[f"{label}/auroc"] = auroc
        output[f"{label}/average_precision"] = average_precision
        aurocs.append(auroc)
        average_precisions.append(average_precision)

    output["macro_auroc"] = float(np.mean(aurocs)) if aurocs else None
    output["macro_average_precision"] = (
        float(np.mean(average_precisions)) if average_precisions else None
    )
    output["macro_f1"] = float(np.mean(f1s)) if f1s else None
    output["scored_labels_auroc"] = len(aurocs)
    return output


def _validate_shapes(
    targets: np.ndarray,
    probabilities: np.ndarray,
    masks: np.ndarray,
) -> None:
    if targets.shape != probabilities.shape or targets.shape != masks.shape:
        raise ValueError(
            "targets, probabilities, and masks must have identical shapes"
        )
    if targets.ndim != 2:
        raise ValueError(
            f"Expected arrays shaped [studies, labels], got {targets.shape}"
        )
