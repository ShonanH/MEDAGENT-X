"""Extract fine-tuned RAD-DINO study embeddings for retrieval."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import torch
from torch.utils.data import DataLoader

from medagentx.retrieval.constants import DEFAULT_PROGRESS_EVERY_BATCHES
from medagentx.vision.data import (
    InferenceStudyDataset,
    StudyBatchCollator,
    StudyInferenceRecord,
)
from medagentx.vision.gpu_data import GpuResidentStudyLoader
from medagentx.vision.model_ready_cache import ModelReadyImageCache
from medagentx.vision.trainer import load_finetuned_checkpoint
from medagentx.vision.processor import load_training_image_processor


def _move_batch(batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
    output = dict(batch)
    for key in ("pixel_values", "study_indices"):
        if key in output:
            output[key] = output[key].to(device, non_blocking=True)
    return output


def _log_progress(
    *,
    batch_index: int,
    total_batches: int,
    studies_done: int,
    total_studies: int,
    elapsed_s: float,
) -> None:
    rate = studies_done / elapsed_s if elapsed_s > 0 else 0.0
    remaining = max(total_studies - studies_done, 0)
    eta_s = remaining / rate if rate > 0 else 0.0
    print(
        f"[Retrieval] embedded batch {batch_index}/{total_batches} "
        f"studies={studies_done}/{total_studies} "
        f"elapsed={elapsed_s:.0f}s eta={eta_s:.0f}s"
    )


@torch.no_grad()
def collect_study_embeddings(
    model: Any,
    loader: DataLoader,
    *,
    device: torch.device,
    mixed_precision: bool,
    progress_every: int = DEFAULT_PROGRESS_EVERY_BATCHES,
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

    total_batches = len(loader)
    total_studies = len(loader.dataset)
    if progress_every <= 0:
        raise ValueError("progress_every must be > 0")

    print(
        f"[Retrieval] starting embedding loop "
        f"batches={total_batches} studies={total_studies} device={device}"
    )
    started = time.perf_counter()

    for batch_index, raw_batch in enumerate(loader, start=1):
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

        if (
            batch_index == 1
            or batch_index % progress_every == 0
            or batch_index == total_batches
        ):
            _log_progress(
                batch_index=batch_index,
                total_batches=total_batches,
                studies_done=len(study_keys),
                total_studies=total_studies,
                elapsed_s=time.perf_counter() - started,
            )

    if not embeddings:
        raise ValueError("loader produced no study embeddings")

    elapsed_s = time.perf_counter() - started
    print(
        f"[Retrieval] embedding loop complete "
        f"studies={len(study_keys)} elapsed={elapsed_s:.1f}s"
    )

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
    print(
        f"[Retrieval] loading checkpoint {checkpoint_path} onto {resolved_device}"
    )
    started = time.perf_counter()
    model, checkpoint = load_finetuned_checkpoint(
        checkpoint_path,
        device=resolved_device,
    )
    processor = load_training_image_processor(checkpoint_path, checkpoint)
    print(
        f"[Retrieval] checkpoint ready model={checkpoint['model_name']} "
        f"elapsed={time.perf_counter() - started:.1f}s"
    )
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
    progress_every: int = DEFAULT_PROGRESS_EVERY_BATCHES,
    model_ready_cache_root: str | Path | None = None,
    cohort_root: str | Path | None = None,
    view_splits_csv: str | Path | None = None,
    gpu_cache_preload_chunk_size: int = 64,
) -> dict[str, Any]:
    """End-to-end helper: load checkpoint and embed the provided studies."""
    resolved_device = torch.device(device)
    model, checkpoint, processor = load_embedding_model(
        checkpoint_path,
        device=resolved_device,
    )
    input_cache: dict[str, Any]
    if model_ready_cache_root is None:
        loader = build_study_embedding_loader(
            records,
            dicom_root=dicom_root,
            processor=processor,
            batch_size=batch_size,
            num_workers=num_workers,
            device=resolved_device,
        )
        input_cache = {"mode": "raw_dicom"}
    else:
        if resolved_device.type != "cuda":
            raise ValueError("model-ready cache embedding requires CUDA")
        if cohort_root is None or view_splits_csv is None:
            raise ValueError(
                "cohort_root and view_splits_csv are required with "
                "model_ready_cache_root"
            )
        if gpu_cache_preload_chunk_size <= 0:
            raise ValueError("gpu_cache_preload_chunk_size must be > 0")
        cache = ModelReadyImageCache(model_ready_cache_root)
        image_processor_config = {
            "model_name": checkpoint["model_name"],
            "config": processor.to_dict(),
        }
        cache.validate_training_inputs(
            cohort_root=cohort_root,
            dicom_root=dicom_root,
            view_splits_csv=view_splits_csv,
            required_paths=(
                path for record in records for path in record.dicom_paths
            ),
            image_processor_config=image_processor_config,
        )
        cached_pixels = cache.preload_to_device(
            resolved_device,
            chunk_size=gpu_cache_preload_chunk_size,
        )
        config_values = image_processor_config["config"]
        loader = GpuResidentStudyLoader(
            records,
            path_to_index=cache.path_to_index,
            cached_pixels=cached_pixels,
            batch_size=batch_size,
            train=False,
            image_mean=config_values["image_mean"],
            image_std=config_values["image_std"],
        )
        input_cache = {
            "mode": "gpu_resident_model_ready",
            "root": str(Path(model_ready_cache_root)),
            "cache_id": cache.cache_id,
            "view_count": int(cache.manifest["view_count"]),
        }
        print(
            "[Retrieval] model-ready cache preloaded to GPU "
            f"views={len(cached_pixels)} resident_gib="
            f"{cached_pixels.numel() / (1024**3):.2f}",
            flush=True,
        )
    payload = collect_study_embeddings(
        model,
        loader,
        device=resolved_device,
        mixed_precision=mixed_precision,
        progress_every=progress_every,
    )
    payload["checkpoint"] = checkpoint
    payload["input_cache"] = input_cache
    return payload
