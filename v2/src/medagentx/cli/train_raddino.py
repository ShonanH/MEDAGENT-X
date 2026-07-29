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
)
from medagentx.vision.data import (
    LightCxrAugment,
    StudyBatchCollator,
    StudyDataset,
    build_study_training_records,
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


def build_parser() -> argparse.ArgumentParser:
    """Build the RAD-DINO training command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Fine-tune the last two RAD-DINO transformer blocks plus a "
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
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
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
        "--weight-decay", type=float, default=DEFAULT_WEIGHT_DECAY
    )
    parser.add_argument(
        "--num-workers", type=int, default=DEFAULT_NUM_WORKERS
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
) -> DataLoader:
    dataset = StudyDataset(records, dicom_root=dicom_root)
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
    if args.num_workers < 0:
        raise ValueError("num-workers must be >= 0")
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
    train_loader = _loader(
        train_records,
        dicom_root=dicom_root,
        processor=processor,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        train=True,
    )
    val_loader = _loader(
        val_records,
        dicom_root=dicom_root,
        processor=processor,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        train=False,
    )
    test_loader = _loader(
        test_records,
        dicom_root=dicom_root,
        processor=processor,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        train=False,
    )

    model = RadDinoStudyClassifier.from_pretrained(args.model_name)
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
    )
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "run_config.json").write_text(
        json.dumps(
            {
                "view_splits_csv": str(view_splits_csv),
                "study_labels_csv": str(study_labels_csv),
                "dicom_root": str(dicom_root),
                "output_root": str(output_root),
                "device": str(device),
                "train_studies": len(train_records),
                "val_studies": len(val_records),
                "test_studies": len(test_records),
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
    )
    test_predictions = collect_predictions(
        best_model,
        test_loader,
        device=device,
        mixed_precision=config.mixed_precision,
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
    test_metrics["masked_bce"] = test_predictions["masked_bce"]
    (output_root / "test_metrics.json").write_text(
        json.dumps(test_metrics, indent=2, sort_keys=True)
    )
    print(
        f"[Vision] best_epoch={result['best_epoch']} "
        f"best_val_macro_auroc={result['best_score']}"
    )
    print(
        f"[Vision] test macro_auroc={test_metrics['macro_auroc']} "
        f"macro_f1={test_metrics['macro_f1']}"
    )
    print(f"[Vision] checkpoint -> {result['checkpoint_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
