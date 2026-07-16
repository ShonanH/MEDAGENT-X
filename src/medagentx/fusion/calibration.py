from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from src.medagentx.fusion.constants import DISEASE_LABELS, snake_label


DEFAULT_PRESENT_THRESHOLD = 0.60
DEFAULT_ABSENT_THRESHOLD = 0.20

# Labels that are broad, noisy, or clinically rare on CXR reports.
BROAD_OR_NOISY_LABELS = {
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Lung Opacity",
    "Enlarged Cardiomediastinum",
}

RARE_OR_HIGH_COST_FP_LABELS = {
    "Fracture",
    "Lung Lesion",
    "Pneumonia",
    "Pleural Other",
}

# Labels where weak DenseNet/fusion agreement can still support a present call.
RECALL_LENIENT_LABELS = {
    "Edema",
    "Pneumothorax",
    "Pleural Effusion",
    "Fracture",
    "Pneumonia",
    "Pleural Other",
    "Lung Lesion",
}

MODERATE_RECALL_LABELS = {
    "Atelectasis",
    "Consolidation",
    "Cardiomegaly",
    "Enlarged Cardiomediastinum",
}

STRICT_PRESENT_LABELS = {
    "Lung Opacity",
}

# Fusion is often overconfident on broad labels; down-weight it in the blend.
DENSENET_HEAVY_BLEND_LABELS = BROAD_OR_NOISY_LABELS | MODERATE_RECALL_LABELS

LUNG_OPACITY_MIN_DENSENET = 0.82
LUNG_OPACITY_MIN_ENSEMBLE = 0.92
LUNG_OPACITY_MAX_FUSION_GAP = 0.12

# Conservative floors applied after validation tuning.
LABEL_PRESENT_THRESHOLD_FLOORS: dict[str, float] = {
    "Atelectasis": 0.65,
    "Cardiomegaly": 0.70,
    "Consolidation": 0.65,
    "Edema": 0.60,
    "Pleural Effusion": 0.60,
    "Pneumonia": 0.75,
    "Pneumothorax": 0.65,
    "Fracture": 0.80,
    "Lung Lesion": 0.80,
    "Lung Opacity": 0.92,
    "Enlarged Cardiomediastinum": 0.70,
    "Pleural Other": 0.75,
}

DEFAULT_DENSENET_PRESENT_THRESHOLDS: dict[str, float] = {
    label: 0.70 if label in BROAD_OR_NOISY_LABELS else 0.65
    for label in DISEASE_LABELS
}
for label in RARE_OR_HIGH_COST_FP_LABELS:
    DEFAULT_DENSENET_PRESENT_THRESHOLDS[label] = 0.75


def apply_threshold_floor(label: str, threshold: float) -> float:
    floor = LABEL_PRESENT_THRESHOLD_FLOORS.get(label, DEFAULT_PRESENT_THRESHOLD)
    return float(max(threshold, floor))


def prob_to_status(
    probability: float | None,
    present_threshold: float = DEFAULT_PRESENT_THRESHOLD,
    absent_threshold: float = DEFAULT_ABSENT_THRESHOLD,
) -> str:
    if probability is None:
        return "unavailable"

    if probability >= present_threshold:
        return "present"

    if probability <= absent_threshold:
        return "absent"

    return "uncertain"


def f_beta_score(precision: float, recall: float, beta: float = 0.5) -> float:
    beta_sq = beta * beta
    denom = beta_sq * precision + recall + 1e-8
    return (1.0 + beta_sq) * precision * recall / denom


def tune_thresholds_precision_favored(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    mask: np.ndarray,
    label_names: list[str],
    thresholds: np.ndarray | None = None,
    beta: float = 0.5,
    min_precision: float = 0.35,
) -> tuple[np.ndarray, list[float]]:
    if thresholds is None:
        thresholds = np.linspace(0.10, 0.95, 35)

    best_thresholds: list[float] = []
    best_scores: list[float] = []

    for j, label in enumerate(label_names):
        best_t = apply_threshold_floor(label, DEFAULT_PRESENT_THRESHOLD)
        best_score = -1.0

        valid = mask[:, j] > 0
        if valid.sum() == 0:
            best_thresholds.append(best_t)
            best_scores.append(float("nan"))
            continue

        yt = y_true[valid, j]
        yp = y_prob[valid, j]

        for t in thresholds:
            pred = (yp >= t).astype(np.int32)
            tp = ((pred == 1) & (yt == 1)).sum()
            fp = ((pred == 1) & (yt == 0)).sum()
            fn = ((pred == 0) & (yt == 1)).sum()

            precision = tp / (tp + fp + 1e-8)
            recall = tp / (tp + fn + 1e-8)

            if fp > 0 and precision < min_precision:
                continue

            score = f_beta_score(float(precision), float(recall), beta=beta)
            if score > best_score:
                best_score = score
                best_t = float(t)

        best_thresholds.append(apply_threshold_floor(label, best_t))
        best_scores.append(best_score)

    return np.asarray(best_thresholds, dtype=np.float32), best_scores


def load_threshold_json(path: str | Path, prefix: str = "") -> dict[str, float]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    thresholds = payload.get("thresholds", payload)

    output: dict[str, float] = {}
    for label in DISEASE_LABELS:
        slug = snake_label(label)
        key = f"{prefix}{slug}" if prefix else slug
        if key in thresholds:
            output[label] = apply_threshold_floor(label, float(thresholds[key]))
        elif slug in thresholds:
            output[label] = apply_threshold_floor(label, float(thresholds[slug]))
    return output


def default_densenet_thresholds() -> dict[str, float]:
    return {
        label: apply_threshold_floor(label, DEFAULT_DENSENET_PRESENT_THRESHOLDS[label])
        for label in DISEASE_LABELS
    }


def ensemble_prob_blend(
    label: str,
    d_prob: float | None,
    f_prob: float | None,
    fusion_weight: float = 0.5,
) -> float | None:
    if d_prob is None and f_prob is None:
        return None
    if d_prob is None:
        return float(f_prob)
    if f_prob is None:
        return float(d_prob)

    if label in STRICT_PRESENT_LABELS:
        return float(min(d_prob, f_prob))

    if label in DENSENET_HEAVY_BLEND_LABELS:
        return float(0.65 * d_prob + 0.35 * f_prob)

    return float((1.0 - fusion_weight) * d_prob + fusion_weight * f_prob)


def agreement_field(
    d_prob: float | None,
    f_prob: float | None,
    d_threshold: float,
    f_threshold: float,
) -> str:
    if d_prob is None and f_prob is None:
        return "insufficient_evidence"
    if d_prob is None or f_prob is None:
        return "insufficient_evidence"

    d_present = d_prob >= d_threshold
    f_present = f_prob >= f_threshold
    d_absent = d_prob <= DEFAULT_ABSENT_THRESHOLD
    f_absent = f_prob <= DEFAULT_ABSENT_THRESHOLD

    if d_present and f_present:
        return "strong_present"
    if d_absent and f_absent:
        return "strong_absent"
    if d_present and not f_present and not f_absent:
        return "weak_present"
    if f_present and not d_present and not d_absent:
        return "weak_present"
    if d_absent and not f_absent and not f_present:
        return "weak_absent"
    if f_absent and not d_present and not d_present:
        return "weak_absent"
    if (d_present and f_absent) or (f_present and d_absent):
        return "conflict"
    return "insufficient_evidence"


def ensemble_present_status(
    label: str,
    d_prob: float | None,
    f_prob: float | None,
    e_prob: float | None,
    d_threshold: float,
    f_threshold: float,
    e_threshold: float,
    require_agreement: bool = True,
) -> str:
    if e_prob is None:
        return "unavailable"

    if e_prob <= DEFAULT_ABSENT_THRESHOLD:
        return "absent"

    agreement = agreement_field(d_prob, f_prob, d_threshold, f_threshold)

    if label in STRICT_PRESENT_LABELS:
        if agreement == "strong_absent":
            return "absent"
        if (
            agreement == "strong_present"
            and e_prob >= LUNG_OPACITY_MIN_ENSEMBLE
            and d_prob is not None
            and f_prob is not None
            and d_prob >= LUNG_OPACITY_MIN_DENSENET
            and (f_prob - d_prob) <= LUNG_OPACITY_MAX_FUSION_GAP
        ):
            return "present"
        return "uncertain"

    if label in RECALL_LENIENT_LABELS:
        if agreement == "strong_absent" and e_prob <= DEFAULT_ABSENT_THRESHOLD:
            return "absent"
        if agreement in {"weak_present", "strong_present"} and e_prob >= e_threshold:
            return "present"
        return "uncertain"

    if label in MODERATE_RECALL_LABELS:
        if agreement == "strong_absent" and e_prob <= DEFAULT_ABSENT_THRESHOLD:
            return "absent"
        if agreement in {"weak_present", "strong_present"} and e_prob >= e_threshold:
            return "present"
        return "uncertain"

    if label in RARE_OR_HIGH_COST_FP_LABELS:
        if agreement == "strong_present" and e_prob >= e_threshold:
            return "present"
        if agreement == "strong_absent":
            return "absent"
        return "uncertain"

    if require_agreement:
        if agreement == "strong_present" and e_prob >= e_threshold:
            return "present"
        if agreement == "strong_absent":
            return "absent"
        return "uncertain"

    if e_prob >= e_threshold:
        return "present"
    return "uncertain"


def thresholds_to_json_payload(
    thresholds: dict[str, float],
    model_version: str,
    feature_mode: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model_version": model_version,
        "thresholds": {snake_label(label): float(value) for label, value in thresholds.items()},
    }
    if feature_mode:
        payload["feature_mode"] = feature_mode
    return payload
