"""Masked RAD-DINO fine-tuning, validation, and checkpoint selection."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.constants import CHEXPERT_TRAINING_POLICY_VERSION
from medagentx.labels.schema import snake_label
from medagentx.splits.constants import SPLIT_POLICY_VERSION
from medagentx.vision.constants import (
    DEFAULT_BACKBONE_LR,
    DEFAULT_BATCH_SIZE,
    DEFAULT_EARLY_STOPPING_PATIENCE,
    DEFAULT_EPOCHS,
    DEFAULT_GRADIENT_ACCUMULATION_STEPS,
    DEFAULT_HEAD_LR,
    DEFAULT_MODEL_NAME,
    DEFAULT_NUM_WORKERS,
    DEFAULT_SEED,
    DEFAULT_WEIGHT_DECAY,
    VISION_BACKEND_ID,
)
from medagentx.vision.metrics import (
    compute_masked_metrics,
    tune_validation_thresholds,
)


@dataclass(frozen=True)
class TrainingConfig:
    """Locked defaults plus explicit runtime training parameters."""

    model_name: str = DEFAULT_MODEL_NAME
    epochs: int = DEFAULT_EPOCHS
    gradient_accumulation_steps: int = DEFAULT_GRADIENT_ACCUMULATION_STEPS
    backbone_lr: float = DEFAULT_BACKBONE_LR
    head_lr: float = DEFAULT_HEAD_LR
    weight_decay: float = DEFAULT_WEIGHT_DECAY
    early_stopping_patience: int = DEFAULT_EARLY_STOPPING_PATIENCE
    seed: int = DEFAULT_SEED
    mixed_precision: bool = True
    batch_size: int = DEFAULT_BATCH_SIZE
    num_workers: int = DEFAULT_NUM_WORKERS


def set_reproducible_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def masked_binary_cross_entropy(
    logits: torch.Tensor,
    targets: torch.Tensor,
    masks: torch.Tensor,
) -> tuple[torch.Tensor, int]:
    """Average BCE over U-mask supervised disease cells only."""
    if logits.shape != targets.shape or logits.shape != masks.shape:
        raise ValueError("logits, targets, and masks must have identical shapes")
    loss_cells = F.binary_cross_entropy_with_logits(
        logits,
        targets,
        reduction="none",
    )
    supervised = int(masks.sum().item())
    denominator = masks.sum().clamp_min(1.0)
    return (loss_cells * masks).sum() / denominator, supervised


def build_optimizer(
    model: Any,
    *,
    backbone_lr: float,
    head_lr: float,
    weight_decay: float,
) -> torch.optim.Optimizer:
    """Create AdamW with locked differential backbone/head learning rates."""
    backbone_parameters = list(model.trainable_backbone_parameters())
    head_parameters = list(model.classifier.parameters())
    if not backbone_parameters:
        raise ValueError("No trainable RAD-DINO backbone parameters")
    return torch.optim.AdamW(
        [
            {"params": backbone_parameters, "lr": backbone_lr},
            {"params": head_parameters, "lr": head_lr},
        ],
        weight_decay=weight_decay,
    )


def _move_batch(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    output = dict(batch)
    for key in ("pixel_values", "study_indices", "targets", "masks"):
        if key in output:
            output[key] = output[key].to(device, non_blocking=True)
    return output


def train_one_epoch(
    model: Any,
    loader: Any,
    optimizer: torch.optim.Optimizer,
    *,
    device: torch.device,
    gradient_accumulation_steps: int,
    mixed_precision: bool,
) -> float:
    """Train one epoch and return supervised-cell-weighted masked BCE."""
    if gradient_accumulation_steps <= 0:
        raise ValueError("gradient_accumulation_steps must be > 0")

    model.train()
    optimizer.zero_grad(set_to_none=True)
    use_amp = bool(mixed_precision and device.type == "cuda")
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)
    loss_sum = 0.0
    supervised_sum = 0

    for step, raw_batch in enumerate(loader):
        batch = _move_batch(raw_batch, device)
        with torch.autocast(
            device_type=device.type,
            dtype=torch.float16,
            enabled=use_amp,
        ):
            output = model(
                batch["pixel_values"],
                batch["study_indices"],
                batch["num_studies"],
            )
            loss, supervised = masked_binary_cross_entropy(
                output["logits"],
                batch["targets"],
                batch["masks"],
            )
            scaled_loss = loss / gradient_accumulation_steps

        scaler.scale(scaled_loss).backward()
        should_step = (
            (step + 1) % gradient_accumulation_steps == 0
            or step + 1 == len(loader)
        )
        if should_step:
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)

        loss_sum += float(loss.detach().item()) * supervised
        supervised_sum += supervised

    return loss_sum / max(supervised_sum, 1)


@torch.no_grad()
def collect_predictions(
    model: Any,
    loader: Any,
    *,
    device: torch.device,
    mixed_precision: bool,
) -> dict[str, Any]:
    """Collect study-level probabilities, masks, metadata, and masked loss."""
    model.eval()
    use_amp = bool(mixed_precision and device.type == "cuda")
    probabilities: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    masks: list[np.ndarray] = []
    study_keys: list[str] = []
    patient_ids: list[str] = []
    view_counts: list[int] = []
    dicom_paths: list[tuple[str, ...]] = []
    loss_sum = 0.0
    supervised_sum = 0

    for raw_batch in loader:
        batch = _move_batch(raw_batch, device)
        with torch.autocast(
            device_type=device.type,
            dtype=torch.float16,
            enabled=use_amp,
        ):
            output = model(
                batch["pixel_values"],
                batch["study_indices"],
                batch["num_studies"],
            )
            loss, supervised = masked_binary_cross_entropy(
                output["logits"],
                batch["targets"],
                batch["masks"],
            )

        probabilities.append(
            torch.sigmoid(output["logits"]).detach().cpu().float().numpy()
        )
        targets.append(batch["targets"].detach().cpu().float().numpy())
        masks.append(batch["masks"].detach().cpu().float().numpy())
        study_keys.extend(raw_batch["study_keys"])
        patient_ids.extend(raw_batch["patient_ids"])
        view_counts.extend(raw_batch["view_counts"])
        dicom_paths.extend(raw_batch["dicom_paths"])
        loss_sum += float(loss.detach().item()) * supervised
        supervised_sum += supervised

    return {
        "probabilities": np.concatenate(probabilities, axis=0),
        "targets": np.concatenate(targets, axis=0),
        "masks": np.concatenate(masks, axis=0),
        "study_keys": study_keys,
        "patient_ids": patient_ids,
        "view_counts": view_counts,
        "dicom_paths": dicom_paths,
        "masked_bce": loss_sum / max(supervised_sum, 1),
    }


@torch.no_grad()
def collect_inference_predictions(
    model: Any,
    loader: Any,
    *,
    device: torch.device,
    mixed_precision: bool,
) -> dict[str, Any]:
    """Collect image-only study probabilities for online/backend use."""
    model.eval()
    use_amp = bool(mixed_precision and device.type == "cuda")
    probabilities: list[np.ndarray] = []
    study_keys: list[str] = []
    patient_ids: list[str] = []
    splits: list[str] = []
    view_counts: list[int] = []
    dicom_paths: list[tuple[str, ...]] = []

    for raw_batch in loader:
        batch = _move_batch(raw_batch, device)
        with torch.autocast(
            device_type=device.type,
            dtype=torch.float16,
            enabled=use_amp,
        ):
            output = model(
                batch["pixel_values"],
                batch["study_indices"],
                batch["num_studies"],
            )
        probabilities.append(
            torch.sigmoid(output["logits"]).detach().cpu().float().numpy()
        )
        study_keys.extend(raw_batch["study_keys"])
        patient_ids.extend(raw_batch["patient_ids"])
        splits.extend(raw_batch["splits"])
        view_counts.extend(raw_batch["view_counts"])
        dicom_paths.extend(raw_batch["dicom_paths"])

    return {
        "probabilities": np.concatenate(probabilities, axis=0),
        "study_keys": study_keys,
        "patient_ids": patient_ids,
        "splits": splits,
        "view_counts": view_counts,
        "dicom_paths": dicom_paths,
    }


def prediction_table(
    predictions: dict[str, Any],
    thresholds: dict[str, float],
    *,
    split: str,
) -> pd.DataFrame:
    """Flatten study predictions into the permanent vision output contract."""
    rows: list[dict[str, Any]] = []
    probabilities = predictions["probabilities"]
    for index, study_key in enumerate(predictions["study_keys"]):
        row: dict[str, Any] = {
            "study_key": study_key,
            "deid_patient_id": predictions["patient_ids"][index],
            "split": split,
            "view_count": predictions["view_counts"][index],
            "dicom_paths": "|".join(predictions["dicom_paths"][index]),
            "vision_backend_id": VISION_BACKEND_ID,
        }
        for label_index, label in enumerate(DISEASE_LABELS):
            slug = snake_label(label)
            probability = float(probabilities[index, label_index])
            threshold = float(thresholds[label])
            row[f"probability_{slug}"] = probability
            row[f"threshold_{slug}"] = threshold
            row[f"status_{slug}"] = (
                "present" if probability >= threshold else "absent"
            )
        rows.append(row)
    return pd.DataFrame(rows)


def inference_prediction_table(
    predictions: dict[str, Any],
    thresholds: dict[str, float],
) -> pd.DataFrame:
    """Flatten image-only backend predictions into the permanent contract."""
    rows: list[dict[str, Any]] = []
    probabilities = predictions["probabilities"]
    for index, study_key in enumerate(predictions["study_keys"]):
        row: dict[str, Any] = {
            "study_key": study_key,
            "deid_patient_id": predictions["patient_ids"][index],
            "split": predictions["splits"][index],
            "view_count": predictions["view_counts"][index],
            "dicom_paths": "|".join(predictions["dicom_paths"][index]),
            "vision_backend_id": VISION_BACKEND_ID,
        }
        for label_index, label in enumerate(DISEASE_LABELS):
            slug = snake_label(label)
            probability = float(probabilities[index, label_index])
            threshold = float(thresholds[label])
            row[f"probability_{slug}"] = probability
            row[f"threshold_{slug}"] = threshold
            row[f"status_{slug}"] = (
                "present" if probability >= threshold else "absent"
            )
        rows.append(row)
    return pd.DataFrame(rows)


def train_with_validation(
    model: Any,
    train_loader: Any,
    val_loader: Any,
    *,
    output_root: str | Path,
    device: torch.device,
    config: TrainingConfig,
) -> dict[str, Any]:
    """Train RAD-DINO and select the checkpoint by masked val macro AUROC."""
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    set_reproducible_seed(config.seed)
    model.to(device)
    optimizer = build_optimizer(
        model,
        backbone_lr=config.backbone_lr,
        head_lr=config.head_lr,
        weight_decay=config.weight_decay,
    )

    best_score = float("-inf")
    best_epoch = 0
    epochs_without_improvement = 0
    history: list[dict[str, Any]] = []
    checkpoint_path = output / "best_checkpoint.pt"
    thresholds_path = output / "thresholds.json"
    metrics_path = output / "val_metrics.json"

    for epoch in range(1, config.epochs + 1):
        train_loss = train_one_epoch(
            model,
            train_loader,
            optimizer,
            device=device,
            gradient_accumulation_steps=config.gradient_accumulation_steps,
            mixed_precision=config.mixed_precision,
        )
        val_predictions = collect_predictions(
            model,
            val_loader,
            device=device,
            mixed_precision=config.mixed_precision,
        )
        thresholds = tune_validation_thresholds(
            val_predictions["targets"],
            val_predictions["probabilities"],
            val_predictions["masks"],
        )
        val_metrics = compute_masked_metrics(
            val_predictions["targets"],
            val_predictions["probabilities"],
            val_predictions["masks"],
            thresholds,
        )
        val_metrics["masked_bce"] = val_predictions["masked_bce"]
        val_metrics["epoch"] = epoch
        val_metrics["train_masked_bce"] = train_loss

        macro_auroc = val_metrics["macro_auroc"]
        macro_f1 = val_metrics["macro_f1"]
        if macro_auroc is not None:
            score = float(macro_auroc)
            selection_metric = "macro_auroc"
        else:
            score = float(macro_f1 or 0.0)
            selection_metric = "macro_f1_fallback"
        history.append(dict(val_metrics))
        print(
            f"[Vision] epoch={epoch} train_bce={train_loss:.5f} "
            f"val_bce={val_predictions['masked_bce']:.5f} "
            f"macro_auroc={macro_auroc} macro_f1={macro_f1}"
        )

        if score > best_score:
            best_score = score
            best_epoch = epoch
            epochs_without_improvement = 0
            checkpoint = {
                "model_state_dict": model.state_dict(),
                "model_name": config.model_name,
                "vision_backend_id": VISION_BACKEND_ID,
                "disease_labels": list(DISEASE_LABELS),
                "trainable_last_blocks": model.trainable_last_blocks,
                "hidden_size": model.hidden_size,
                "thresholds": thresholds,
                "epoch": epoch,
                "selection_metric": selection_metric,
                "selection_score": score,
                "val_metrics": val_metrics,
                "training_config": asdict(config),
                "label_policy_version": CHEXPERT_TRAINING_POLICY_VERSION,
                "split_policy_version": SPLIT_POLICY_VERSION,
            }
            temporary = checkpoint_path.with_suffix(".tmp")
            torch.save(checkpoint, temporary)
            temporary.replace(checkpoint_path)
            thresholds_path.write_text(
                json.dumps(thresholds, indent=2, sort_keys=True)
            )
            metrics_path.write_text(
                json.dumps(val_metrics, indent=2, sort_keys=True)
            )
        else:
            epochs_without_improvement += 1

        pd.DataFrame(history).to_csv(
            output / "training_history.csv",
            index=False,
        )
        if epochs_without_improvement >= config.early_stopping_patience:
            print(
                f"[Vision] Early stopping after epoch {epoch}; "
                f"best epoch was {best_epoch}."
            )
            break

    return {
        "checkpoint_path": checkpoint_path,
        "thresholds_path": thresholds_path,
        "metrics_path": metrics_path,
        "history_path": output / "training_history.csv",
        "best_epoch": best_epoch,
        "best_score": best_score,
    }


def load_finetuned_checkpoint(
    checkpoint_path: str | Path,
    *,
    device: torch.device,
) -> tuple[Any, dict[str, Any]]:
    """Recreate the RAD-DINO backend and restore a v2 checkpoint."""
    from medagentx.vision.model import RadDinoStudyClassifier

    checkpoint = torch.load(
        checkpoint_path,
        map_location="cpu",
    )
    if checkpoint.get("disease_labels") != list(DISEASE_LABELS):
        raise ValueError("Checkpoint disease label order is incompatible")

    model = RadDinoStudyClassifier.from_pretrained(
        checkpoint["model_name"],
        trainable_last_blocks=int(checkpoint["trainable_last_blocks"]),
    )
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.to(device)
    model.eval()
    return model, checkpoint
