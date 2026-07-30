"""Extract fine-tuned RAD-DINO study embeddings for retrieval."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch
from torch.utils.data import DataLoader
from transformers import AutoImageProcessor

from medagentx.vision.data import (
    InferenceStudyDataset,
    StudyBatchCollator,
    StudyInferenceRecord,
)
from medagentx.vision.trainer import load_finetuned_checkpoint


def _move_batch(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    output = dict(batch)
    for key in ("pixel_values", "study_indices"):
        if key in output:
            output[key] = output[key].to(device, non_blocking=True)
    return output


@torch.no_grad()
def collect_study_embeddings(
    model: Any,
    loader: DataLoader,
    *,
    device: torch.device,
    mixed_precision: bool,
) -> dict[str, Any]:
    """Collect mean-pooled study embeddings for every batch in ``loader``."""
    model.eval()
    use_amp = bool(mixed_precision and device.type == "cuda")
    embeddings: list[np.ndarray] = []
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
        embeddings.append(
            output["study_embeddings"].detach().cpu().float().numpy()
        )
        study_keys.extend(raw_batch["study_keys"])
        patient_ids.extend(raw_batch["patient_ids"])
        splits.extend(raw_batch["splits"])
        view_counts.extend(raw_batch["view_counts"])
        dicom_paths.extend(raw_batch["dicom_paths"])

    if not embeddings:
        raise ValueError("loader produced no study embeddings")

    return {
        "embeddings": np.concatenate(embeddings, axis=0),
        "study_keys": study_keys,
        "patient_ids": patient_ids,
        "splits": splits,
        "view_counts": view_counts,
        "dicom_paths": dicom_paths,
    }


def build_study_embedding_loader(
    records: Sequence[StudyInferenceRecord],
    *,
    dicom_root: str | Path,
    processor: Any,
    batch_size: int,
    num_workers: int,
    device: torch.device,
) -> DataLoader:
    """Create the image-only loader used for offline embedding extraction."""
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    if num_workers < 0:
        raise ValueError("num_workers must be >= 0")

    dataset = InferenceStudyDataset(records, dicom_root=dicom_root)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=device.type == "cuda",
        persistent_workers=num_workers > 0,
        collate_fn=StudyBatchCollator(processor),
    )


def load_embedding_model(
    checkpoint_path: str | Path,
    *,
    device: str | torch.device,
) -> tuple[Any, dict[str, Any], Any]:
    """Load the fine-tuned RAD-DINO classifier and its image processor."""
    resolved_device = torch.device(device)
    model, checkpoint = load_finetuned_checkpoint(
        checkpoint_path,
        device=resolved_device,
    )
    processor = AutoImageProcessor.from_pretrained(checkpoint["model_name"])
    return model, checkpoint, processor


def extract_study_embeddings(
    records: Sequence[StudyInferenceRecord],
    *,
    checkpoint_path: str | Path,
    dicom_root: str | Path,
    device: str | torch.device,
    batch_size: int,
    num_workers: int,
    mixed_precision: bool = True,
) -> dict[str, Any]:
    """End-to-end helper: load checkpoint and embed the provided studies."""
    resolved_device = torch.device(device)
    model, checkpoint, processor = load_embedding_model(
        checkpoint_path,
        device=resolved_device,
    )
    loader = build_study_embedding_loader(
        records,
        dicom_root=dicom_root,
        processor=processor,
        batch_size=batch_size,
        num_workers=num_workers,
        device=resolved_device,
    )
    payload = collect_study_embeddings(
        model,
        loader,
        device=resolved_device,
        mixed_precision=mixed_precision,
    )
    payload["checkpoint"] = checkpoint
    return payload
