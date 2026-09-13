"""Masked RAD-DINO fine-tuning, validation, and checkpoint selection."""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

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
from medagentx.vision.losses import masked_multilabel_loss
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
    loss_name: str = "bce"
    asl_gamma_neg: float = 4.0
    asl_gamma_pos: float = 1.0
    asl_clip: float = 0.05
    selection_metric: str = "macro_f1"
    warmup_ratio: float = 0.05
    max_grad_norm: float = 1.0
    label_names: tuple[str, ...] = DISEASE_LABELS
    label_policy_version: str = CHEXPERT_TRAINING_POLICY_VERSION
    split_policy_version: str = SPLIT_POLICY_VERSION
    image_source: str = "dicom"


def set_reproducible_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def compute_training_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    masks: torch.Tensor,
    config: TrainingConfig,
) -> tuple[torch.Tensor, int]:
    """Compute the configured masked multi-label loss."""
    return masked_multilabel_loss(
        logits,
        targets,
        masks,
        loss_name=config.loss_name,
        gamma_neg=config.asl_gamma_neg,
        gamma_pos=config.asl_gamma_pos,
        clip=config.asl_clip,
    )


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


def build_lr_scheduler(
    optimizer: torch.optim.Optimizer,
    *,
    total_optimizer_steps: int,
    warmup_ratio: float,
) -> torch.optim.lr_scheduler.LambdaLR:
    """Create warmup + cosine decay scheduler over optimizer steps."""
    if total_optimizer_steps <= 0:
        raise ValueError("total_optimizer_steps must be > 0")
    if not 0.0 <= warmup_ratio < 1.0:
        raise ValueError("warmup_ratio must satisfy 0 <= warmup_ratio < 1")
    warmup_steps = int(total_optimizer_steps * warmup_ratio)

    def lr_lambda(step: int) -> float:
        if warmup_steps > 0 and step < warmup_steps:
            return float(step + 1) / float(warmup_steps)
        decay_steps = max(total_optimizer_steps - warmup_steps, 1)
        progress = min(max(step - warmup_steps, 0), decay_steps) / decay_steps
        return 0.5 * (1.0 + math.cos(math.pi * progress))

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


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
    config: TrainingConfig,
    scheduler: torch.optim.lr_scheduler.LRScheduler | None = None,
) -> float:
    """Train one epoch and return supervised-cell-weighted masked loss."""
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
            loss, supervised = compute_training_loss(
                output["logits"],
                batch["targets"],
                batch["masks"],
                config,
            )
            scaled_loss = loss / gradient_accumulation_steps

        scaler.scale(scaled_loss).backward()
        should_step = (
            (step + 1) % gradient_accumulation_steps == 0
            or step + 1 == len(loader)
        )
        if should_step:
            if config.max_grad_norm > 0:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(
                    model.parameters(),
                    config.max_grad_norm,
                )
            scaler.step(optimizer)
            scaler.update()
            if scheduler is not None:
                scheduler.step()
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
    config: TrainingConfig,
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
            loss, supervised = compute_training_loss(
                output["logits"],
                batch["targets"],
                batch["masks"],
                config,
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
        "masked_loss": loss_sum / max(supervised_sum, 1),
        "loss_name": config.loss_name,
    }


def score_for_selection(
    val_metrics: dict[str, Any],
    *,
    selection_metric: str,
) -> tuple[float, str]:
    """Return the checkpoint-selection score and metric name."""
    metric = selection_metric.strip().lower()
    if metric == "macro_f1":
        return float(val_metrics.get("macro_f1") or 0.0), "macro_f1"
    if metric == "macro_average_precision":
        return (
            float(val_metrics.get("macro_average_precision") or 0.0),
            "macro_average_precision",
        )
    if metric == "macro_auroc":
        return float(val_metrics.get("macro_auroc") or 0.0), "macro_auroc"
    raise ValueError(
        "selection_metric must be one of: macro_f1, "
        "macro_average_precision, macro_auroc"
    )


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
    study_embeddings: list[np.ndarray] = []
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
        study_embeddings.append(
            output["study_embeddings"].detach().cpu().float().numpy()
        )
        study_keys.extend(raw_batch["study_keys"])
        patient_ids.extend(raw_batch["patient_ids"])
        splits.extend(raw_batch["splits"])
        view_counts.extend(raw_batch["view_counts"])
        dicom_paths.extend(raw_batch["dicom_paths"])

    return {
        "probabilities": np.concatenate(probabilities, axis=0),
        "study_embeddings": np.concatenate(study_embeddings, axis=0),
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
    label_names: tuple[str, ...] = DISEASE_LABELS,
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
        for label_index, label in enumerate(label_names):
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
    *,
    label_names: tuple[str, ...] = DISEASE_LABELS,
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
        for label_index, label in enumerate(label_names):
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
    optimizer_steps_per_epoch = math.ceil(
        len(train_loader) / config.gradient_accumulation_steps
    )
    scheduler = build_lr_scheduler(
        optimizer,
        total_optimizer_steps=max(optimizer_steps_per_epoch * config.epochs, 1),
        warmup_ratio=config.warmup_ratio,
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
            config=config,
            scheduler=scheduler,
        )
        val_predictions = collect_predictions(
            model,
            val_loader,
            device=device,
            mixed_precision=config.mixed_precision,
            config=config,
        )
        thresholds = tune_validation_thresholds(
            val_predictions["targets"],
            val_predictions["probabilities"],
            val_predictions["masks"],
            label_names=config.label_names,
        )
        val_metrics = compute_masked_metrics(
            val_predictions["targets"],
            val_predictions["probabilities"],
            val_predictions["masks"],
            thresholds,
            label_names=config.label_names,
        )
        val_metrics["masked_loss"] = val_predictions["masked_loss"]
        val_metrics["loss_name"] = config.loss_name
        val_metrics["epoch"] = epoch
        val_metrics["train_masked_loss"] = train_loss

        score, selection_metric = score_for_selection(
            val_metrics,
            selection_metric=config.selection_metric,
        )
        macro_auroc = val_metrics["macro_auroc"]
        macro_f1 = val_metrics["macro_f1"]
        history.append(dict(val_metrics))
        print(
            f"[Vision] epoch={epoch} train_loss={train_loss:.5f} "
            f"val_loss={val_predictions['masked_loss']:.5f} "
            f"macro_auroc={macro_auroc} macro_f1={macro_f1} "
            f"selection={selection_metric}:{score}"
        )

        if score > best_score:
            best_score = score
            best_epoch = epoch
            epochs_without_improvement = 0
            checkpoint = {
                "model_state_dict": model.state_dict(),
                "model_name": config.model_name,
                "vision_backend_id": VISION_BACKEND_ID,
                "disease_labels": list(config.label_names),
                "label_names": list(config.label_names),
                "trainable_last_blocks": model.trainable_last_blocks,
                "hidden_size": model.hidden_size,
                "pooling_mode": getattr(model, "pooling_mode", "mean"),
                "thresholds": thresholds,
                "epoch": epoch,
                "selection_metric": selection_metric,
                "selection_score": score,
                "val_metrics": val_metrics,
                "training_config": asdict(config),
                "label_policy_version": config.label_policy_version,
                "split_policy_version": config.split_policy_version,
                "image_source": config.image_source,
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
    label_names = tuple(
        checkpoint.get("label_names", checkpoint.get("disease_labels", DISEASE_LABELS))
    )
    if not label_names:
        raise ValueError("Checkpoint label inventory is empty")

    model = RadDinoStudyClassifier.from_pretrained(
        checkpoint["model_name"],
        trainable_last_blocks=int(checkpoint["trainable_last_blocks"]),
        pooling_mode=str(checkpoint.get("pooling_mode", "mean")),
        label_names=label_names,
    )
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.to(device)
    model.eval()
    return model, checkpoint
