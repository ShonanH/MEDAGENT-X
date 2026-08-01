"""Masked multi-label losses for RAD-DINO study classification."""

from __future__ import annotations

import torch
import torch.nn.functional as F


def validate_loss_inputs(
    logits: torch.Tensor,
    targets: torch.Tensor,
    masks: torch.Tensor,
) -> None:
    """Validate shared loss tensor shape requirements."""
    if logits.shape != targets.shape or logits.shape != masks.shape:
        raise ValueError("logits, targets, and masks must have identical shapes")
    if logits.ndim != 2:
        raise ValueError("loss tensors must have shape [studies, labels]")


def masked_binary_cross_entropy(
    logits: torch.Tensor,
    targets: torch.Tensor,
    masks: torch.Tensor,
) -> tuple[torch.Tensor, int]:
    """Average BCE over supervised disease cells only."""
    validate_loss_inputs(logits, targets, masks)
    loss_cells = F.binary_cross_entropy_with_logits(
        logits,
        targets,
        reduction="none",
    )
    supervised = int(masks.sum().item())
    denominator = masks.sum().clamp_min(1.0)
    return (loss_cells * masks).sum() / denominator, supervised


def masked_asymmetric_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    masks: torch.Tensor,
    *,
    gamma_neg: float = 4.0,
    gamma_pos: float = 1.0,
    clip: float = 0.05,
    eps: float = 1e-8,
) -> tuple[torch.Tensor, int]:
    """Average Asymmetric Loss over supervised disease cells only.

    This is the multi-label ASL variant: negatives receive stronger focal
    down-weighting than positives, which is useful for sparse positive labels.
    """
    validate_loss_inputs(logits, targets, masks)
    if gamma_neg < 0 or gamma_pos < 0:
        raise ValueError("gamma_neg and gamma_pos must be >= 0")
    if clip < 0:
        raise ValueError("clip must be >= 0")
    if eps <= 0:
        raise ValueError("eps must be > 0")

    probabilities = torch.sigmoid(logits)
    pos_probs = probabilities
    neg_probs = 1.0 - probabilities
    if clip > 0:
        neg_probs = torch.clamp(neg_probs + clip, max=1.0)

    log_pos = torch.log(pos_probs.clamp(min=eps))
    log_neg = torch.log(neg_probs.clamp(min=eps))
    pos_loss = targets * log_pos
    neg_loss = (1.0 - targets) * log_neg
    loss_cells = pos_loss + neg_loss

    if gamma_neg > 0 or gamma_pos > 0:
        pt = pos_probs * targets + neg_probs * (1.0 - targets)
        gamma = gamma_pos * targets + gamma_neg * (1.0 - targets)
        loss_cells = loss_cells * torch.pow(1.0 - pt, gamma)

    supervised = int(masks.sum().item())
    denominator = masks.sum().clamp_min(1.0)
    return -(loss_cells * masks).sum() / denominator, supervised


def masked_multilabel_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    masks: torch.Tensor,
    *,
    loss_name: str,
    gamma_neg: float = 4.0,
    gamma_pos: float = 1.0,
    clip: float = 0.05,
) -> tuple[torch.Tensor, int]:
    """Dispatch a named masked multi-label loss."""
    normalized = loss_name.strip().lower()
    if normalized in {"bce", "masked_bce"}:
        return masked_binary_cross_entropy(logits, targets, masks)
    if normalized in {"asymmetric", "asl", "asymmetric_loss"}:
        return masked_asymmetric_loss(
            logits,
            targets,
            masks,
            gamma_neg=gamma_neg,
            gamma_pos=gamma_pos,
            clip=clip,
        )
    raise ValueError(f"Unsupported loss_name: {loss_name!r}")
