"""Short no-evaluation throughput gate for GPU-resident RAD-DINO inputs."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd
import torch
from transformers import AutoImageProcessor

from medagentx.vision.constants import (
    DEFAULT_BACKBONE_LR,
    DEFAULT_HEAD_LR,
    DEFAULT_MODEL_NAME,
    DEFAULT_WEIGHT_DECAY,
)
from medagentx.vision.data import build_study_training_records
from medagentx.vision.gpu_data import GpuResidentStudyLoader
from medagentx.vision.model import RadDinoStudyClassifier
from medagentx.vision.model_ready_cache import ModelReadyImageCache
from medagentx.vision.trainer import TrainingConfig, build_optimizer, compute_training_loss


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure GPU-resident RAD-DINO input throughput without val/test."
    )
    parser.add_argument("--cohort-root", type=Path, required=True)
    parser.add_argument("--model-ready-cache-root", type=Path, required=True)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--trainable-last-blocks", type=int, default=1)
    parser.add_argument("--backbone-lr", type=float, default=DEFAULT_BACKBONE_LR)
    parser.add_argument("--head-lr", type=float, default=DEFAULT_HEAD_LR)
    parser.add_argument("--weight-decay", type=float, default=DEFAULT_WEIGHT_DECAY)
    parser.add_argument("--progress-every-steps", type=int, default=25)
    args = parser.parse_args(argv)
    if args.batch_size <= 0 or args.steps <= 0 or args.progress_every_steps <= 0:
        raise ValueError("batch-size, steps, and progress-every-steps must be > 0")

    device = torch.device("cuda")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the GPU-resident throughput gate")
    processor = AutoImageProcessor.from_pretrained(args.model_name)
    processor_config = {"model_name": args.model_name, "config": processor.to_dict()}
    views_csv = args.cohort_root / "splits" / "view_splits.csv"
    labels_csv = args.cohort_root / "study_label_table.csv"
    dicom_root = args.cohort_root / "dicom_train"
    records = build_study_training_records(
        pd.read_csv(views_csv, dtype=str),
        pd.read_csv(labels_csv, dtype=str),
        split="train",
    )
    cache = ModelReadyImageCache(args.model_ready_cache_root)
    cache.validate_training_inputs(
        cohort_root=args.cohort_root,
        dicom_root=dicom_root,
        view_splits_csv=views_csv,
        required_paths=[path for record in records for path in record.dicom_paths],
        image_processor_config=processor_config,
    )
    pixels = cache.preload_to_device(device)
    loader = GpuResidentStudyLoader(
        records,
        path_to_index=cache.path_to_index,
        cached_pixels=pixels,
        batch_size=args.batch_size,
        train=True,
        image_mean=processor_config["config"]["image_mean"],
        image_std=processor_config["config"]["image_std"],
    )
    model = RadDinoStudyClassifier.from_pretrained(
        args.model_name, trainable_last_blocks=args.trainable_last_blocks
    ).to(device)
    optimizer = build_optimizer(
        model,
        backbone_lr=args.backbone_lr,
        head_lr=args.head_lr,
        weight_decay=args.weight_decay,
    )
    config = TrainingConfig(loss_name="asymmetric")
    scaler = torch.amp.GradScaler("cuda")
    print(
        "[Vision throughput] ready "
        f"steps={args.steps} batch_size={args.batch_size} "
        f"resident_gib={pixels.numel() / (1024**3):.2f}",
        flush=True,
    )
    iterator = iter(loader)
    interval_start = time.perf_counter()
    total_start = interval_start
    views_seen = 0
    studies_seen = 0
    for step in range(1, args.steps + 1):
        try:
            batch = next(iterator)
        except StopIteration:
            iterator = iter(loader)
            batch = next(iterator)
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            output = model(
                batch["pixel_values"], batch["study_indices"], batch["num_studies"]
            )
            loss, _ = compute_training_loss(
                output["logits"], batch["targets"], batch["masks"], config
            )
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)
        views_seen += int(batch["pixel_values"].shape[0])
        studies_seen += int(batch["num_studies"])
        if step % args.progress_every_steps == 0 or step == args.steps:
            torch.cuda.synchronize(device)
            interval = time.perf_counter() - interval_start
            total = time.perf_counter() - total_start
            print(
                "[Vision throughput] "
                f"step={step}/{args.steps} interval_s={interval:.2f} "
                f"studies_per_s={studies_seen / total:.2f} "
                f"views_per_s={views_seen / total:.2f} "
                f"gpu_mem_gib={torch.cuda.max_memory_allocated(device) / (1024**3):.2f}",
                flush=True,
            )
            interval_start = time.perf_counter()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
