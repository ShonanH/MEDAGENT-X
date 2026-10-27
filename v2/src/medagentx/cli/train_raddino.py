"""Fine-tune RAD-DINO for study-level CheXpert disease classification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import DataLoader
from transformers import AutoImageProcessor

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
    TRAINABLE_LAST_BLOCKS,
)
from medagentx.vision.cache import CachedImageLoader, RadDinoImageCache
from medagentx.vision.data import (
    LightCxrAugment,
    StudyBatchCollator,
    StudyDataset,
    build_study_training_records,
)
from medagentx.vision.gpu_data import GpuResidentStudyLoader
from medagentx.vision.metrics import compute_masked_metrics
from medagentx.vision.model import RadDinoStudyClassifier
from medagentx.vision.model_ready_cache import ModelReadyImageCache
from medagentx.vision.trainer import (
    TrainingConfig,
    collect_predictions,
    load_finetuned_checkpoint,
    prediction_table,
    train_with_validation,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the RAD-DINO training command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Fine-tune configurable RAD-DINO transformer blocks plus a "
            "12-disease study-level head using masked CheXpert supervision."
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
    parser.add_argument(
        "--image-cache-root",
        type=Path,
        default=None,
        help=(
            "Validated immutable RAD-DINO cache root. When omitted, retain "
            "the existing raw-DICOM input path."
        ),
    )
    parser.add_argument(
        "--model-ready-cache-root",
        type=Path,
        default=None,
        help=(
            "Validated compact fixed-shape cache. Its full uint8 view tensor "
            "is preloaded to CUDA once; it cannot be combined with "
            "--image-cache-root."
        ),
    )
    parser.add_argument(
        "--gpu-cache-preload-chunk-size",
        type=int,
        default=64,
        help="Views copied to GPU in each model-ready-cache preload chunk.",
    )
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument(
        "--pooling-mode",
        choices=("mean", "mean_max"),
        default="mean_max",
        help="Study-level view pooling mode for the classifier head.",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--gradient-accumulation-steps",
        type=int,
        default=DEFAULT_GRADIENT_ACCUMULATION_STEPS,
    )
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument(
        "--early-stopping-patience",
        type=int,
        default=DEFAULT_EARLY_STOPPING_PATIENCE,
    )
    parser.add_argument(
        "--backbone-lr", type=float, default=DEFAULT_BACKBONE_LR
    )
    parser.add_argument("--head-lr", type=float, default=DEFAULT_HEAD_LR)
    parser.add_argument(
        "--trainable-last-blocks",
        type=int,
        default=TRAINABLE_LAST_BLOCKS,
        help=(
            "Number of final RAD-DINO transformer blocks to fine-tune. "
            f"Default preserves the locked baseline: {TRAINABLE_LAST_BLOCKS}."
        ),
    )
    parser.add_argument(
        "--weight-decay", type=float, default=DEFAULT_WEIGHT_DECAY
    )
    parser.add_argument(
        "--loss-name",
        choices=("bce", "asymmetric"),
        default="asymmetric",
        help="Masked multi-label loss. Use asymmetric for recall-focused retraining.",
    )
    parser.add_argument("--asl-gamma-neg", type=float, default=4.0)
    parser.add_argument("--asl-gamma-pos", type=float, default=1.0)
    parser.add_argument("--asl-clip", type=float, default=0.05)
    parser.add_argument(
        "--selection-metric",
        choices=("macro_f1", "macro_average_precision", "macro_auroc"),
        default="macro_f1",
        help="Validation metric used to select best checkpoint.",
    )
    parser.add_argument("--warmup-ratio", type=float, default=0.05)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument(
        "--num-workers", type=int, default=DEFAULT_NUM_WORKERS
    )
    parser.add_argument(
        "--progress-every-batches",
        type=int,
        default=25,
        help="Emit input/throughput diagnostics every N training batches.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--max-train-studies",
        type=int,
        default=None,
        help="Development-only cap for a runtime smoke test.",
    )
    parser.add_argument(
        "--max-val-studies",
        type=int,
        default=None,
        help="Development-only cap for a runtime smoke test.",
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
    parser.add_argument(
        "--no-mixed-precision",
        action="store_true",
        help="Disable fp16 mixed precision.",
    )
    return parser


def _loader(
    records: list,
    *,
    dicom_root: Path,
    processor: object,
    batch_size: int,
    num_workers: int,
    train: bool,
    image_cache_root: Path | None = None,
) -> DataLoader:
    image_loader = (
        CachedImageLoader(dicom_root=dicom_root, cache_root=image_cache_root)
        if image_cache_root is not None
        else None
    )
    dataset = StudyDataset(
        records,
        dicom_root=dicom_root,
        **({"image_loader": image_loader} if image_loader is not None else {}),
    )
    collator = StudyBatchCollator(
        processor,
        augment=LightCxrAugment() if train else None,
    )
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=train,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
        persistent_workers=num_workers > 0,
        collate_fn=collator,
    )


def main(argv: list[str] | None = None) -> int:
    """Train, select on validation AUROC, and evaluate once on test."""
    args = build_parser().parse_args(argv)
    if args.batch_size <= 0:
        raise ValueError("batch-size must be > 0")
    if args.gpu_cache_preload_chunk_size <= 0:
        raise ValueError("gpu-cache-preload-chunk-size must be > 0")
    if args.image_cache_root is not None and args.model_ready_cache_root is not None:
        raise ValueError(
            "Use exactly one of --image-cache-root and --model-ready-cache-root"
        )
    if args.gradient_accumulation_steps <= 0:
        raise ValueError("gradient-accumulation-steps must be > 0")
    if args.epochs <= 0:
        raise ValueError("epochs must be > 0")
    if args.early_stopping_patience <= 0:
        raise ValueError("early-stopping-patience must be > 0")
    if args.backbone_lr <= 0 or args.head_lr <= 0:
        raise ValueError("learning rates must be > 0")
    if args.trainable_last_blocks <= 0:
        raise ValueError("trainable-last-blocks must be > 0")
    if args.weight_decay < 0:
        raise ValueError("weight-decay must be >= 0")
    if args.asl_gamma_neg < 0 or args.asl_gamma_pos < 0:
        raise ValueError("ASL gamma values must be >= 0")
    if args.asl_clip < 0:
        raise ValueError("asl-clip must be >= 0")
    if not 0 <= args.warmup_ratio < 1:
        raise ValueError("warmup-ratio must satisfy 0 <= warmup-ratio < 1")
    if args.max_grad_norm < 0:
        raise ValueError("max-grad-norm must be >= 0")
    if args.num_workers < 0:
        raise ValueError("num-workers must be >= 0")
    if args.progress_every_batches <= 0:
        raise ValueError("progress-every-batches must be > 0")
    for name in (
        "max_train_studies",
        "max_val_studies",
        "max_test_studies",
    ):
        value = getattr(args, name)
        if value is not None and value <= 0:
            raise ValueError(f"{name.replace('_', '-')} must be > 0")

    cohort_root: Path = args.cohort_root
    view_splits_csv = args.view_splits_csv or (
        cohort_root / "splits" / "view_splits.csv"
    )
    study_labels_csv = args.study_labels_csv or (
        cohort_root / "study_label_table.csv"
    )
    dicom_root = args.dicom_root or (cohort_root / "dicom_train")
    output_root = args.output_root or (
        cohort_root / "vision" / "raddino_finetuned_v1"
    )
    for path in (view_splits_csv, study_labels_csv):
        if not path.exists():
            raise FileNotFoundError(f"Required training artifact missing: {path}")
    if not dicom_root.exists():
        raise FileNotFoundError(f"DICOM root missing: {dicom_root}")

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")

    views = pd.read_csv(view_splits_csv, dtype=str)
    labels = pd.read_csv(study_labels_csv, dtype=str)
    train_records = build_study_training_records(
        views, labels, split="train"
    )
    val_records = build_study_training_records(views, labels, split="val")
    test_records = build_study_training_records(views, labels, split="test")
    if args.max_train_studies is not None:
        train_records = train_records[: args.max_train_studies]
    if args.max_val_studies is not None:
        val_records = val_records[: args.max_val_studies]
    if args.max_test_studies is not None:
        test_records = test_records[: args.max_test_studies]
    if not train_records or not val_records or not test_records:
        raise ValueError("Development study limits must leave every split non-empty")
    print(
        f"[Vision] studies train={len(train_records)} "
        f"val={len(val_records)} test={len(test_records)}"
    )
    print(f"[Vision] model={args.model_name} device={device}")

    processor = AutoImageProcessor.from_pretrained(args.model_name)
    image_processor_config = {
        "model_name": args.model_name,
        "config": processor.to_dict(),
    }
    image_cache: RadDinoImageCache | ModelReadyImageCache | None = None
    cache_mode = "raw_dicom"
    if args.image_cache_root is not None:
        image_cache = RadDinoImageCache(args.image_cache_root)
        cache_mode = "lossless_cached"
    elif args.model_ready_cache_root is not None:
        if device.type != "cuda":
            raise ValueError("--model-ready-cache-root requires --device cuda")
        image_cache = ModelReadyImageCache(args.model_ready_cache_root)
        cache_mode = "gpu_resident_model_ready"
    if image_cache is not None:
        required_paths = [
            path
            for records in (train_records, val_records, test_records)
            for record in records
            for path in record.dicom_paths
        ]
        image_cache.validate_training_inputs(
            cohort_root=cohort_root,
            dicom_root=dicom_root,
            view_splits_csv=view_splits_csv,
            required_paths=required_paths,
            image_processor_config=image_processor_config,
        )
        for split_name, records in (
            ("train", train_records),
            ("val", val_records),
            ("test", test_records),
        ):
            print(
                f"[Vision] cache planned split={split_name} "
                f"studies={len(records)} "
                f"images={sum(len(record.dicom_paths) for record in records)}"
            )
        print(
            f"[Vision] cache_mode={cache_mode} cache_id={image_cache.cache_id}"
        )
    if isinstance(image_cache, ModelReadyImageCache):
        config_values = image_processor_config["config"]
        cached_pixels = image_cache.preload_to_device(
            device, chunk_size=args.gpu_cache_preload_chunk_size
        )
        loader_kwargs = {
            "path_to_index": image_cache.path_to_index,
            "cached_pixels": cached_pixels,
            "batch_size": args.batch_size,
            "image_mean": config_values["image_mean"],
            "image_std": config_values["image_std"],
        }
        train_loader = GpuResidentStudyLoader(
            train_records, train=True, **loader_kwargs
        )
        val_loader = GpuResidentStudyLoader(
            val_records, train=False, **loader_kwargs
        )
        test_loader = GpuResidentStudyLoader(
            test_records, train=False, **loader_kwargs
        )
        print(
            "[Vision] model-ready cache preloaded to GPU "
            f"views={len(cached_pixels)} resident_gib="
            f"{cached_pixels.numel() / (1024**3):.2f}",
            flush=True,
        )
    else:
        train_loader = _loader(
            train_records,
            dicom_root=dicom_root,
            processor=processor,
            batch_size=args.batch_size,
            num_workers=args.num_workers,
            train=True,
            image_cache_root=args.image_cache_root,
        )
        val_loader = _loader(
            val_records,
            dicom_root=dicom_root,
            processor=processor,
            batch_size=args.batch_size,
            num_workers=args.num_workers,
            train=False,
            image_cache_root=args.image_cache_root,
        )
        test_loader = _loader(
            test_records,
            dicom_root=dicom_root,
            processor=processor,
            batch_size=args.batch_size,
            num_workers=args.num_workers,
            train=False,
            image_cache_root=args.image_cache_root,
        )

    model = RadDinoStudyClassifier.from_pretrained(
        args.model_name,
        trainable_last_blocks=args.trainable_last_blocks,
        pooling_mode=args.pooling_mode,
    )
    print(f"[Vision] freeze summary: {model.freeze_summary}")
    config = TrainingConfig(
        model_name=args.model_name,
        epochs=args.epochs,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        backbone_lr=args.backbone_lr,
        head_lr=args.head_lr,
        weight_decay=args.weight_decay,
        early_stopping_patience=args.early_stopping_patience,
        seed=args.seed,
        mixed_precision=not args.no_mixed_precision,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        loss_name=args.loss_name,
        asl_gamma_neg=args.asl_gamma_neg,
        asl_gamma_pos=args.asl_gamma_pos,
        asl_clip=args.asl_clip,
        selection_metric=args.selection_metric,
        warmup_ratio=args.warmup_ratio,
        max_grad_norm=args.max_grad_norm,
        progress_every_batches=args.progress_every_batches,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "run_config.json").write_text(
        json.dumps(
            {
                "view_splits_csv": str(view_splits_csv),
                "study_labels_csv": str(study_labels_csv),
                "dicom_root": str(dicom_root),
                "image_cache_root": (
                    str(args.image_cache_root) if args.image_cache_root else None
                ),
                "model_ready_cache_root": (
                    str(args.model_ready_cache_root)
                    if args.model_ready_cache_root
                    else None
                ),
                "cache_mode": cache_mode,
                "cache_manifest_id": image_cache.cache_id if image_cache else None,
                "image_processor": image_processor_config,
                "output_root": str(output_root),
                "device": str(device),
                "train_studies": len(train_records),
                "val_studies": len(val_records),
                "test_studies": len(test_records),
                "pooling_mode": args.pooling_mode,
                "trainable_last_blocks": args.trainable_last_blocks,
                "training_config": config.__dict__,
            },
            indent=2,
            sort_keys=True,
        )
    )
    result = train_with_validation(
        model,
        train_loader,
        val_loader,
        output_root=output_root,
        device=device,
        config=config,
    )

    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    best_model, checkpoint = load_finetuned_checkpoint(
        result["checkpoint_path"],
        device=device,
    )
    thresholds = checkpoint["thresholds"]
    val_predictions = collect_predictions(
        best_model,
        val_loader,
        device=device,
        mixed_precision=config.mixed_precision,
        config=config,
    )
    test_predictions = collect_predictions(
        best_model,
        test_loader,
        device=device,
        mixed_precision=config.mixed_precision,
        config=config,
    )
    prediction_table(val_predictions, thresholds, split="val").to_csv(
        output_root / "val_study_predictions.csv",
        index=False,
    )
    prediction_table(test_predictions, thresholds, split="test").to_csv(
        output_root / "test_study_predictions.csv",
        index=False,
    )
    test_metrics = compute_masked_metrics(
        test_predictions["targets"],
        test_predictions["probabilities"],
        test_predictions["masks"],
        thresholds,
    )
    test_metrics["masked_loss"] = test_predictions["masked_loss"]
    test_metrics["loss_name"] = config.loss_name
    (output_root / "test_metrics.json").write_text(
        json.dumps(test_metrics, indent=2, sort_keys=True)
    )
    if image_cache is not None:
        completed_epochs = int(result["epochs_completed"])
        split_records = {
            "train": train_records,
            "val": val_records,
            "test": test_records,
        }
        split_passes = {
            "train": completed_epochs,
            # One validation pass per epoch plus best-checkpoint evaluation.
            "val": completed_epochs + 1,
            "test": 1,
        }
        cache_usage = {
            split: {
                "studies_per_pass": len(records),
                "views_per_pass": sum(
                    len(record.dicom_paths) for record in records
                ),
                "passes": split_passes[split],
                "studies_read": len(records) * split_passes[split],
                "views_read": sum(
                    len(record.dicom_paths) for record in records
                )
                * split_passes[split],
            }
            for split, records in split_records.items()
        }
        (output_root / "cache_usage.json").write_text(
            json.dumps(cache_usage, indent=2, sort_keys=True) + "\n"
        )
        for split, usage in cache_usage.items():
            print(
                f"[Vision] cache actual split={split} "
                f"studies_read={usage['studies_read']} "
                f"views_read={usage['views_read']}"
            )
    print(
        f"[Vision] best_epoch={result['best_epoch']} "
        f"best_val_{config.selection_metric}={result['best_score']}"
    )
    print(
        f"[Vision] test macro_auroc={test_metrics['macro_auroc']} "
        f"macro_f1={test_metrics['macro_f1']}"
    )
    print(f"[Vision] checkpoint -> {result['checkpoint_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
