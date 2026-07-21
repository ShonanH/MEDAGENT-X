from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from medagentx.fusion.calibration import (
    TRAINING_DEFAULT_PRESENT_THRESHOLD,
    tune_thresholds_precision_favored,
)
from medagentx.fusion.constants import DISEASE_LABELS


def masked_bce_with_logits_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    mask: torch.Tensor,
    pos_weight: torch.Tensor | None = None,
) -> torch.Tensor:
    criterion = nn.BCEWithLogitsLoss(reduction="none", pos_weight=pos_weight)
    loss = criterion(logits, targets)
    loss = loss * mask
    denom = mask.sum().clamp_min(1.0)
    return loss.sum() / denom


def apply_no_finding_negative_downweight(
    mask: torch.Tensor,
    targets: torch.Tensor,
    no_finding_mask: torch.Tensor | None,
    weight: float,
) -> torch.Tensor:
    """Reduce loss contribution from explicit negatives on No Finding studies."""
    if no_finding_mask is None or weight >= 1.0:
        return mask

    nf = no_finding_mask.unsqueeze(1)
    negative = targets < 0.5
    downweight = (nf > 0) & negative
    scale = torch.ones_like(mask)
    scale = torch.where(downweight, torch.full_like(mask, weight), scale)
    return mask * scale


def no_finding_penalty_loss(
    logits: torch.Tensor,
    no_finding_mask: torch.Tensor,
    threshold: float = 0.5,
    weight: float = 1.0,
) -> torch.Tensor:
    """Penalize high disease probabilities when study-level No Finding is present."""
    if no_finding_mask.sum() == 0 or weight <= 0:
        return logits.new_tensor(0.0)

    probs = torch.sigmoid(logits)
    max_prob = probs.max(dim=1).values
    penalty = torch.relu(max_prob - threshold) * no_finding_mask
    return weight * penalty.sum() / no_finding_mask.sum().clamp_min(1.0)


def fusion_training_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    mask: torch.Tensor,
    no_finding_mask: torch.Tensor | None = None,
    pos_weight: torch.Tensor | None = None,
    no_finding_penalty_weight: float = 0.0,
    no_finding_prob_threshold: float = 0.5,
    no_finding_negative_weight: float = 0.35,
) -> torch.Tensor:
    effective_mask = apply_no_finding_negative_downweight(
        mask,
        targets,
        no_finding_mask,
        weight=no_finding_negative_weight,
    )
    loss = masked_bce_with_logits_loss(logits, targets, effective_mask, pos_weight=pos_weight)
    if no_finding_mask is not None and no_finding_penalty_weight > 0 and no_finding_mask.sum() > 0:
        loss = loss + no_finding_penalty_loss(
            logits,
            no_finding_mask,
            threshold=no_finding_prob_threshold,
            weight=no_finding_penalty_weight,
        )
    return loss


def compute_pos_weight(
    y_train: np.ndarray,
    mask_train: np.ndarray,
    *,
    boost: float = 2.0,
    max_weight: float = 30.0,
) -> np.ndarray:
    weights = []
    for j in range(y_train.shape[1]):
        m = mask_train[:, j] > 0
        pos = (y_train[m, j] > 0.5).sum()
        neg = (y_train[m, j] <= 0.5).sum()
        if pos == 0:
            weights.append(1.0)
        else:
            ratio = float(neg / pos) * boost
            weights.append(min(ratio, max_weight))
    return np.asarray(weights, dtype=np.float32)


def tune_thresholds_on_validation(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    mask: np.ndarray,
    thresholds: np.ndarray | None = None,
    *,
    apply_floors: bool = False,
    min_precision: float = 0.15,
    beta: float = 1.0,
) -> tuple[np.ndarray, list[float]]:
    return tune_thresholds_precision_favored(
        y_true,
        y_prob,
        mask,
        DISEASE_LABELS,
        thresholds=thresholds,
        beta=beta,
        min_precision=min_precision,
        apply_floors=apply_floors,
        default_threshold=TRAINING_DEFAULT_PRESENT_THRESHOLD,
    )


def _safe_auroc(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    try:
        from sklearn.metrics import roc_auc_score

        return float(roc_auc_score(y_true, y_prob))
    except Exception:
        return float("nan")


def _safe_average_precision(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    try:
        from sklearn.metrics import average_precision_score

        return float(average_precision_score(y_true, y_prob))
    except Exception:
        return float("nan")


def multilabel_ranking_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    mask: np.ndarray,
    label_names: list[str],
) -> dict:
    rows = []
    auroc_scores = []
    ap_scores = []

    for j, label in enumerate(label_names):
        valid = mask[:, j] > 0
        if valid.sum() == 0:
            rows.append({"label": label, "auroc": float("nan"), "avg_precision": float("nan")})
            continue

        yt = y_true[valid, j]
        yp = y_prob[valid, j]

        if len(np.unique(yt)) < 2:
            rows.append({"label": label, "auroc": float("nan"), "avg_precision": float("nan")})
            continue

        auroc = _safe_auroc(yt, yp)
        ap = _safe_average_precision(yt, yp)
        rows.append({"label": label, "auroc": auroc, "avg_precision": ap})
        auroc_scores.append(auroc)
        ap_scores.append(ap)

    return {
        "per_label": rows,
        "macro_auroc": float(np.nanmean(auroc_scores)) if auroc_scores else float("nan"),
        "macro_avg_precision": float(np.nanmean(ap_scores)) if ap_scores else float("nan"),
    }


def multilabel_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    mask: np.ndarray,
    thresholds: np.ndarray,
    label_names: list[str],
) -> dict:
    rows = []
    present_preds = []
    present_true = []

    for j, label in enumerate(label_names):
        valid = mask[:, j] > 0
        if valid.sum() == 0:
            rows.append(
                {
                    "label": label,
                    "support_present": 0,
                    "support_total": 0,
                    "precision": float("nan"),
                    "recall": float("nan"),
                    "f1": float("nan"),
                    "threshold": float(thresholds[j]),
                }
            )
            continue

        yt = y_true[valid, j]
        yp = (y_prob[valid, j] >= thresholds[j]).astype(np.int32)

        tp = ((yp == 1) & (yt == 1)).sum()
        fp = ((yp == 1) & (yt == 0)).sum()
        fn = ((yp == 0) & (yt == 1)).sum()

        precision = tp / (tp + fp + 1e-8)
        recall = tp / (tp + fn + 1e-8)
        f1 = 2 * precision * recall / (precision + recall + 1e-8)

        rows.append(
            {
                "label": label,
                "support_present": int((yt == 1).sum()),
                "support_total": int(valid.sum()),
                "precision": float(precision),
                "recall": float(recall),
                "f1": float(f1),
                "threshold": float(thresholds[j]),
            }
        )

        present_preds.extend(yp.tolist())
        present_true.extend(yt.astype(np.int32).tolist())

    macro_f1 = float(np.nanmean([row["f1"] for row in rows]))

    tp = sum(int(p == 1 and t == 1) for p, t in zip(present_preds, present_true))
    fp = sum(int(p == 1 and t == 0) for p, t in zip(present_preds, present_true))
    fn = sum(int(p == 0 and t == 1) for p, t in zip(present_preds, present_true))

    micro_precision = tp / (tp + fp + 1e-8)
    micro_recall = tp / (tp + fn + 1e-8)
    micro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall + 1e-8)

    return {
        "per_label": rows,
        "macro_f1": macro_f1,
        "micro_precision": float(micro_precision),
        "micro_recall": float(micro_recall),
        "micro_f1": float(micro_f1),
    }
