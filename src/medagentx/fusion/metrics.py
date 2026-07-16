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


def tune_thresholds_on_validation(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    mask: np.ndarray,
    thresholds: np.ndarray | None = None,
) -> tuple[np.ndarray, list[float]]:
    if thresholds is None:
        thresholds = np.linspace(0.05, 0.95, 19)

    best_thresholds = []
    best_f1s = []

    for j in range(y_true.shape[1]):
        best_t = 0.5
        best_f1 = -1.0

        valid = mask[:, j] > 0
        if valid.sum() == 0:
            best_thresholds.append(0.5)
            best_f1s.append(float("nan"))
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
            f1 = 2 * precision * recall / (precision + recall + 1e-8)

            if f1 > best_f1:
                best_f1 = f1
                best_t = float(t)

        best_thresholds.append(best_t)
        best_f1s.append(best_f1)

    return np.asarray(best_thresholds, dtype=np.float32), best_f1s


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