"""Train the competition five-label RAD-DINO raster baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import DataLoader
from transformers import AutoImageProcessor

from medagentx.labels.constants import CHEXPERT_COMPETITION_LABELS
from medagentx.splits.competition import COMPETITION_SPLIT_POLICY_VERSION
from medagentx.vision.data import (
    StudyBatchCollator,
    StudyDataset,
    LightCxrAugment,
    build_study_training_records,
    raster_to_pil_rgb,
)
from medagentx.vision.metrics import compute_masked_metrics
from medagentx.vision.model import RadDinoStudyClassifier
from medagentx.vision.trainer import (
    TrainingConfig,
    collect_predictions,
    load_finetuned_checkpoint,
    prediction_table,
    train_with_validation,
)


DEFAULT_MANIFEST_ROOT = Path("v2/artifacts/chexpert_competition_v1/manifests")
DEFAULT_SPLIT_ROOT = Path("v2/artifacts/chexpert_competition_v1/splits")
DEFAULT_IMAGE_ROOT = Path("v2/artifacts/chexpert_competition_v1/PNG_train")
DEFAULT_OUTPUT_ROOT = Path(
    "v2/artifacts/chexpert_competition_v1/vision/raddino_baseline_v1"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Train a five-label study-level RAD-DINO baseline from the "
            "CheXpert competition PNG manifest."
        )
    )
    parser.add_argument("--manifest-root", type=Path, default=DEFAULT_MANIFEST_ROOT)
    parser.add_argument("--split-root", type=Path, default=DEFAULT_SPLIT_ROOT)
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--model-name", default="microsoft/rad-dino")
    parser.add_argument(
        "--pooling-mode",
        choices=("max", "mean", "mean_max"),
        default="max",
        help="Study-level view pooling; max matches the official baseline protocol.",
    )
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--early-stopping-patience", type=int, default=5)
    parser.add_argument("--backbone-lr", type=float, default=1e-5)
    parser.add_argument("--head-lr", type=float, default=1e-3)
    parser.add_argument("--trainable-last-blocks", type=int, default=4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
    )
    parser.add_argument("--warmup-ratio", type=float, default=0.05)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--max-train-studies", type=int, default=None)
    parser.add_argument("--max-dev-studies", type=int, default=None)
    parser.add_argument(
        "--progress-every",
        type=int,
        default=500,
        help="Print train/validation batch progress every N batches; 0 disables it.",
    )
    parser.add_argument(
        "--no-mixed-precision",
        action="store_true",
        help="Disable CUDA mixed precision.",
    )
    return parser


def _loader(
    records: list,
    *,
    image_root: Path,
    processor: object,
    batch_size: int,
    num_workers: int,
    train: bool,
) -> DataLoader:
    dataset = StudyDataset(
        records,
        image_root=image_root,
        image_loader=raster_to_pil_rgb,
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
    args = build_parser().parse_args(argv)
    for name in (
        "batch_size",
        "gradient_accumulation_steps",
        "epochs",
        "early_stopping_patience",
        "trainable_last_blocks",
    ):
        if getattr(args, name) <= 0:
            raise ValueError(f"{name.replace('_', '-')} must be > 0")
    if args.num_workers < 0:
        raise ValueError("num-workers must be >= 0")
    if args.progress_every < 0:
        raise ValueError("progress-every must be >= 0")
    if args.backbone_lr <= 0 or args.head_lr <= 0:
        raise ValueError("learning rates must be > 0")
    if args.weight_decay < 0 or args.max_grad_norm < 0:
        raise ValueError("weight-decay and max-grad-norm must be >= 0")
    if not 0 <= args.warmup_ratio < 1:
        raise ValueError("warmup-ratio must satisfy 0 <= warmup-ratio < 1")

    manifest_root: Path = args.manifest_root
    split_root: Path = args.split_root
    paths = {
        "view_splits": split_root / "view_splits.csv",
        "study_labels": manifest_root / "study_labels.csv",
    }
    for path in (*paths.values(), args.image_root):
        if not path.exists():
            raise FileNotFoundError(f"Required competition artifact missing: {path}")

    views = pd.read_csv(paths["view_splits"], dtype=str)
    labels = pd.read_csv(paths["study_labels"], dtype=str)
    train_records = build_study_training_records(
        views,
        labels,
        split="train",
        label_names=CHEXPERT_COMPETITION_LABELS,
        target_prefix="target",
        mask_prefix="mask",
        path_column="image_path_relative",
    )
    dev_records = build_study_training_records(
        views,
        labels,
        split="dev",
        label_names=CHEXPERT_COMPETITION_LABELS,
        target_prefix="target",
        mask_prefix="mask",
        path_column="image_path_relative",
    )
    if args.max_train_studies is not None:
        if args.max_train_studies <= 0:
            raise ValueError("max-train-studies must be > 0")
        train_records = train_records[: args.max_train_studies]
    if args.max_dev_studies is not None:
        if args.max_dev_studies <= 0:
            raise ValueError("max-dev-studies must be > 0")
        dev_records = dev_records[: args.max_dev_studies]
    if not train_records or not dev_records:
        raise ValueError("Training and development splits must both be non-empty")

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")
    print(
        f"[CompetitionVision] studies train={len(train_records)} "
        f"dev={len(dev_records)} device={device}"
    )
    processor = AutoImageProcessor.from_pretrained(args.model_name)
    train_loader = _loader(
        train_records,
        image_root=args.image_root,
        processor=processor,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        train=True,
    )
    dev_loader = _loader(
        dev_records,
        image_root=args.image_root,
        processor=processor,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        train=False,
    )
    model = RadDinoStudyClassifier.from_pretrained(
        args.model_name,
        label_names=CHEXPERT_COMPETITION_LABELS,
        trainable_last_blocks=args.trainable_last_blocks,
        pooling_mode=args.pooling_mode,
    )
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
        loss_name="bce",
        selection_metric="macro_auroc",
        warmup_ratio=args.warmup_ratio,
        max_grad_norm=args.max_grad_norm,
        label_names=CHEXPERT_COMPETITION_LABELS,
        label_policy_version="chexpert_ignore_uncertain_v1",
        split_policy_version=COMPETITION_SPLIT_POLICY_VERSION,
        image_source="png_train",
        progress_every=args.progress_every,
    )

    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "run_config.json").write_text(
        json.dumps(
            {
                "manifest_root": str(manifest_root),
                "split_root": str(split_root),
                "image_root": str(args.image_root),
                "output_root": str(args.output_root),
                "label_names": list(CHEXPERT_COMPETITION_LABELS),
                "pooling_mode": args.pooling_mode,
                "training_config": config.__dict__,
            },
            indent=2,
            sort_keys=True,
        )
    )
    result = train_with_validation(
        model,
        train_loader,
        dev_loader,
        output_root=args.output_root,
        device=device,
        config=config,
    )
    best_model, checkpoint = load_finetuned_checkpoint(
        result["checkpoint_path"],
        device=device,
    )
    predictions = collect_predictions(
        best_model,
        dev_loader,
        device=device,
        mixed_precision=config.mixed_precision,
        config=config,
    )
    thresholds = checkpoint["thresholds"]
    prediction_table(
        predictions,
        thresholds,
        split="dev",
        label_names=CHEXPERT_COMPETITION_LABELS,
    ).to_csv(args.output_root / "dev_study_predictions.csv", index=False)
    metrics = compute_masked_metrics(
        predictions["targets"],
        predictions["probabilities"],
        predictions["masks"],
        thresholds,
        label_names=CHEXPERT_COMPETITION_LABELS,
    )
    (args.output_root / "dev_metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True)
    )
    print(
        f"[CompetitionVision] best_epoch={result['best_epoch']} "
        f"best_dev_macro_auroc={result['best_score']}"
    )
    print(f"[CompetitionVision] checkpoint -> {result['checkpoint_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
