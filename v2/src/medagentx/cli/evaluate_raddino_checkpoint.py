"""Evaluate one selected RAD-DINO checkpoint on the held-out test split.

This command intentionally has no training or threshold-tuning path.  It
restores the thresholds saved with the validation-selected checkpoint and
applies them once to the test split.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import torch

from medagentx.labels.constants import CHEXPERT_TRAINING_POLICY_VERSION
from medagentx.splits.constants import SPLIT_POLICY_VERSION
from medagentx.vision.cache import sha256_file
from medagentx.vision.constants import DEFAULT_BATCH_SIZE
from medagentx.vision.data import build_study_training_records
from medagentx.vision.gpu_data import GpuResidentStudyLoader
from medagentx.vision.metrics import compute_masked_metrics
from medagentx.vision.model_ready_cache import ModelReadyImageCache
from medagentx.vision.processor import load_training_image_processor
from medagentx.vision.trainer import (
    TrainingConfig,
    collect_predictions,
    load_finetuned_checkpoint,
    prediction_table,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the held-out checkpoint-evaluation parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate one validation-selected RAD-DINO checkpoint on the "
            "held-out test split without retraining or threshold tuning."
        )
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path("v2/artifacts/cohort"),
    )
    parser.add_argument("--view-splits-csv", type=Path, default=None)
    parser.add_argument("--study-labels-csv", type=Path, default=None)
    parser.add_argument("--dicom-root", type=Path, default=None)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--model-ready-cache-root", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--gpu-cache-preload-chunk-size",
        type=int,
        default=64,
        help="Views copied to GPU in each model-ready-cache preload chunk.",
    )
    parser.add_argument(
        "--max-test-studies",
        type=int,
        default=None,
        help="Development-only cap for a runtime smoke test.",
    )
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
    )
    parser.add_argument("--no-mixed-precision", action="store_true")
    return parser


def _training_config_from_checkpoint(
    checkpoint: dict[str, object],
) -> TrainingConfig:
    values = checkpoint.get("training_config")
    if not isinstance(values, dict):
        raise ValueError("Checkpoint is missing its training configuration")
    try:
        return TrainingConfig(**values)
    except TypeError as error:
        raise ValueError("Checkpoint training configuration is incompatible") from error


def _validate_checkpoint_contract(checkpoint: dict[str, object]) -> None:
    if checkpoint.get("label_policy_version") != CHEXPERT_TRAINING_POLICY_VERSION:
        raise ValueError("Checkpoint label policy is incompatible")
    if checkpoint.get("split_policy_version") != SPLIT_POLICY_VERSION:
        raise ValueError("Checkpoint split policy is incompatible")
    thresholds = checkpoint.get("thresholds")
    if not isinstance(thresholds, dict) or not thresholds:
        raise ValueError("Checkpoint is missing validation-tuned thresholds")


def _refuse_existing_test_outputs(output_root: Path) -> None:
    existing = [
        name
        for name in (
            "run_config.json",
            "test_metrics.json",
            "test_study_predictions.csv",
        )
        if (output_root / name).exists()
    ]
    if existing:
        raise FileExistsError(
            "Refusing to repeat held-out test evaluation in an existing output "
            f"directory: {output_root} ({', '.join(existing)})"
        )


def main(argv: list[str] | None = None) -> int:
    """Score the test split once using the checkpoint's saved thresholds."""
    args = build_parser().parse_args(argv)
    if args.batch_size <= 0:
        raise ValueError("batch-size must be > 0")
    if args.gpu_cache_preload_chunk_size <= 0:
        raise ValueError("gpu-cache-preload-chunk-size must be > 0")
    if args.max_test_studies is not None and args.max_test_studies <= 0:
        raise ValueError("max-test-studies must be > 0")

    cohort_root: Path = args.cohort_root
    view_splits_csv = args.view_splits_csv or (
        cohort_root / "splits" / "view_splits.csv"
    )
    study_labels_csv = args.study_labels_csv or (
        cohort_root / "study_label_table.csv"
    )
    dicom_root = args.dicom_root or (cohort_root / "dicom_train")
    for path in (view_splits_csv, study_labels_csv, args.checkpoint):
        if not path.is_file():
            raise FileNotFoundError(f"Required evaluation artifact missing: {path}")
    if not dicom_root.is_dir():
        raise FileNotFoundError(f"DICOM root missing: {dicom_root}")
    _refuse_existing_test_outputs(args.output_root)

    device = torch.device(args.device)
    if device.type != "cuda":
        raise ValueError("--model-ready-cache-root requires --device cuda")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")

    model, checkpoint = load_finetuned_checkpoint(args.checkpoint, device=device)
    _validate_checkpoint_contract(checkpoint)
    config = _training_config_from_checkpoint(checkpoint)
    model_name = str(checkpoint["model_name"])
    processor = load_training_image_processor(args.checkpoint, checkpoint)
    image_processor_config = {
        "model_name": model_name,
        "config": processor.to_dict(),
    }

    views = pd.read_csv(view_splits_csv, dtype=str)
    labels = pd.read_csv(study_labels_csv, dtype=str)
    test_records = build_study_training_records(views, labels, split="test")
    if args.max_test_studies is not None:
        test_records = test_records[: args.max_test_studies]
    if not test_records:
        raise ValueError("Test-study limit must leave the test split non-empty")

    image_cache = ModelReadyImageCache(args.model_ready_cache_root)
    image_cache.validate_training_inputs(
        cohort_root=cohort_root,
        dicom_root=dicom_root,
        view_splits_csv=view_splits_csv,
        required_paths=(
            path for record in test_records for path in record.dicom_paths
        ),
        image_processor_config=image_processor_config,
    )
    cached_pixels = image_cache.preload_to_device(
        device, chunk_size=args.gpu_cache_preload_chunk_size
    )
    test_loader = GpuResidentStudyLoader(
        test_records,
        path_to_index=image_cache.path_to_index,
        cached_pixels=cached_pixels,
        batch_size=args.batch_size,
        train=False,
        image_mean=image_processor_config["config"]["image_mean"],
        image_std=image_processor_config["config"]["image_std"],
    )
    print(
        "[Vision] model-ready cache preloaded to GPU "
        f"views={len(cached_pixels)} resident_gib="
        f"{cached_pixels.numel() / (1024**3):.2f}",
        flush=True,
    )

    thresholds = checkpoint["thresholds"]
    assert isinstance(thresholds, dict)
    predictions = collect_predictions(
        model,
        test_loader,
        device=device,
        mixed_precision=config.mixed_precision and not args.no_mixed_precision,
        config=config,
    )
    metrics = compute_masked_metrics(
        predictions["targets"],
        predictions["probabilities"],
        predictions["masks"],
        thresholds,
    )
    metrics["masked_loss"] = predictions["masked_loss"]
    metrics["loss_name"] = config.loss_name
    metrics["checkpoint_selection_metric"] = checkpoint["selection_metric"]
    metrics["checkpoint_selection_score"] = checkpoint["selection_score"]

    args.output_root.mkdir(parents=True, exist_ok=True)
    prediction_table(predictions, thresholds, split="test").to_csv(
        args.output_root / "test_study_predictions.csv", index=False
    )
    (args.output_root / "test_metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n"
    )
    run_config = {
        "evaluation_type": "one_time_held_out_test",
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": sha256_file(args.checkpoint),
        "checkpoint_epoch": checkpoint["epoch"],
        "checkpoint_selection_metric": checkpoint["selection_metric"],
        "checkpoint_selection_score": checkpoint["selection_score"],
        "checkpoint_thresholds": thresholds,
        "view_splits_csv": str(view_splits_csv),
        "study_labels_csv": str(study_labels_csv),
        "dicom_root": str(dicom_root),
        "model_ready_cache_root": str(args.model_ready_cache_root),
        "cache_manifest_id": image_cache.cache_id,
        "image_processor": image_processor_config,
        "device": str(device),
        "test_studies": len(test_records),
        "test_views": sum(len(record.dicom_paths) for record in test_records),
        "training_config": asdict(config),
    }
    (args.output_root / "run_config.json").write_text(
        json.dumps(run_config, indent=2, sort_keys=True) + "\n"
    )
    cache_usage = {
        "test": {
            "studies_per_pass": len(test_records),
            "views_per_pass": sum(
                len(record.dicom_paths) for record in test_records
            ),
            "passes": 1,
            "studies_read": len(test_records),
            "views_read": sum(len(record.dicom_paths) for record in test_records),
        }
    }
    (args.output_root / "cache_usage.json").write_text(
        json.dumps(cache_usage, indent=2, sort_keys=True) + "\n"
    )
    print(
        "[Vision] cache actual split=test "
        f"studies_read={cache_usage['test']['studies_read']} "
        f"views_read={cache_usage['test']['views_read']}"
    )
    print(
        f"[Vision] test macro_auroc={metrics['macro_auroc']} "
        f"macro_f1={metrics['macro_f1']}"
    )
    print(f"[Vision] test metrics -> {args.output_root / 'test_metrics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
