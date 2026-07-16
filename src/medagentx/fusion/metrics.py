from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn

from src.medagentx.fusion.calibration import tune_thresholds_precision_favored
from src.medagentx.fusion.constants import DISEASE_LABELS


def masked_bce_with_logits_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    mask: torch.Tensor,
    pos_weight: torch.Tensor | None = None,
    label_smoothing_present: float = 0.0,
    label_smoothing_absent: float = 0.0,
) -> torch.Tensor:
    smoothed_targets = targets.clone()
    if label_smoothing_present > 0:
        smoothed_targets = torch.where(
            (mask > 0) & (targets > 0.5),
            torch.full_like(targets, 1.0 - label_smoothing_present),
            smoothed_targets,
        )
    if label_smoothing_absent > 0:
        smoothed_targets = torch.where(
            (mask > 0) & (targets <= 0.5),
            torch.full_like(targets, label_smoothing_absent),
            smoothed_targets,
        )

    criterion = nn.BCEWithLogitsLoss(reduction="none", pos_weight=pos_weight)
    loss = criterion(logits, smoothed_targets)
    loss = loss * mask
    denom = mask.sum().clamp_min(1.0)
    return loss.sum() / denom


def masked_focal_bce_with_logits_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    mask: torch.Tensor,
    pos_weight: torch.Tensor | None = None,
    gamma: float = 2.0,
    label_smoothing_present: float = 0.05,
    label_smoothing_absent: float = 0.02,
) -> torch.Tensor:
    smoothed_targets = targets.clone()
    if label_smoothing_present > 0:
        smoothed_targets = torch.where(
            (mask > 0) & (targets > 0.5),
            torch.full_like(targets, 1.0 - label_smoothing_present),
            smoothed_targets,
        )
    if label_smoothing_absent > 0:
        smoothed_targets = torch.where(
            (mask > 0) & (targets <= 0.5),
            torch.full_like(targets, label_smoothing_absent),
            smoothed_targets,
        )

    bce = nn.functional.binary_cross_entropy_with_logits(
        logits,
        smoothed_targets,
        reduction="none",
        pos_weight=pos_weight,
    )
    probs = torch.sigmoid(logits)
    pt = torch.where(smoothed_targets > 0.5, probs, 1.0 - probs)
    focal_factor = (1.0 - pt).clamp_min(1e-6).pow(gamma)
    loss = bce * focal_factor * mask
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
            weights.append(float(min(neg / pos, 20.0)))
    return np.asarray(weights, dtype=np.float32)


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


@torch.no_grad()
def predict_probs(
    model: torch.nn.Module,
    loader: torch.utils.data.DataLoader,
    device: torch.device,
    temperature: float = 1.0,
    uses_densenet: bool = False,
) -> np.ndarray:
    model.eval()
    outputs = []
    for batch in loader:
        if uses_densenet:
            X, densenet_probs, _, _ = batch
            densenet_probs = densenet_probs.to(device)
        else:
            X, _, _ = batch
            densenet_probs = None

        X = X.to(device)
        logits = model(X, densenet_probs=densenet_probs)
        probs = torch.sigmoid(logits / max(temperature, 1e-3)).cpu().numpy()
        outputs.append(probs)
    return np.concatenate(outputs, axis=0)


def fit_temperature_scaling(
    logits: np.ndarray,
    y_true: np.ndarray,
    mask: np.ndarray,
    max_iter: int = 200,
    device: torch.device | None = None,
) -> float:
    if device is None:
        device = torch.device("cpu")

    valid = mask > 0
    if valid.sum() < 8:
        return 1.0

    logits_t = torch.from_numpy(logits[valid].astype(np.float32)).to(device)
    targets_t = torch.from_numpy(y_true[valid].astype(np.float32)).to(device)
    temperature = nn.Parameter(torch.ones(1, device=device))

    optimizer = torch.optim.LBFGS([temperature], lr=0.1, max_iter=max_iter)

    def closure():
        optimizer.zero_grad()
        scaled = logits_t / temperature.clamp_min(1e-3)
        loss = nn.functional.binary_cross_entropy_with_logits(scaled, targets_t)
        loss.backward()
        return loss

    try:
        optimizer.step(closure)
        return float(temperature.detach().clamp_min(1e-3).item())
    except Exception:
        return 1.0


def logits_from_model(
    model: torch.nn.Module,
    loader: torch.utils.data.DataLoader,
    device: torch.device,
    uses_densenet: bool = False,
) -> np.ndarray:
    model.eval()
    outputs = []
    with torch.no_grad():
        for batch in loader:
            if uses_densenet:
                X, densenet_probs, _, _ = batch
                densenet_probs = densenet_probs.to(device)
            else:
                X, _, _ = batch
                densenet_probs = None
            X = X.to(device)
            logits = model(X, densenet_probs=densenet_probs).cpu().numpy()
            outputs.append(logits)
    return np.concatenate(outputs, axis=0)
