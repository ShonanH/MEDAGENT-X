from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn


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


def no_finding_penalty_loss(
    logits: torch.Tensor,
    no_finding_mask: torch.Tensor,
    threshold: float = 0.5,
    weight: float = 1.0,
) -> torch.Tensor:
    """Penalize high disease probabilities when study-level No Finding is present."""
    if no_finding_mask.sum() == 0:
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
    no_finding_penalty_weight: float = 1.0,
    no_finding_prob_threshold: float = 0.5,
) -> torch.Tensor:
    loss = masked_bce_with_logits_loss(logits, targets, mask, pos_weight=pos_weight)
    if no_finding_mask is not None and no_finding_mask.sum() > 0:
        loss = loss + no_finding_penalty_loss(
            logits,
            no_finding_mask,
            threshold=no_finding_prob_threshold,
            weight=no_finding_penalty_weight,
        )
    return loss


def compute_pos_weight(y_train: np.ndarray, mask_train: np.ndarray) -> np.ndarray:
    weights = []
    for j in range(y_train.shape[1]):
        m = mask_train[:, j] > 0
        pos = (y_train[m, j] > 0.5).sum()
        neg = (y_train[m, j] <= 0.5).sum()
        if pos == 0:
            weights.append(1.0)
        else:
            weights.append(float(neg / pos))
    return np.asarray(weights, dtype=np.float32)


from medagentx.fusion.calibration import tune_thresholds_precision_favored
from medagentx.fusion.constants import DISEASE_LABELS


def tune_thresholds_on_validation(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    mask: np.ndarray,
    thresholds: np.ndarray | None = None,
) -> tuple[np.ndarray, list[float]]:
    return tune_thresholds_precision_favored(
        y_true,
        y_prob,
        mask,
        DISEASE_LABELS,
        thresholds=thresholds,
        beta=0.5,
        min_precision=0.35,
    )


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