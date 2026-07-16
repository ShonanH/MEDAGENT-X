#!/usr/bin/env python3
"""
Train image/study-level multi-label fusion classifier on frozen embeddings.

Tier 1-3 training stack:
  - judge-aligned labels (--label-mode judge)
  - DenseNet probability stacking (--include-densenet-probs)
  - image-level or study-level rows (--training-level image|study)
  - focal loss (--loss focal) with label smoothing
  - early stopping on judge-aligned validation macro F1
  - post-hoc temperature scaling on validation logits
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.fusion.constants import (
    DEFAULT_DENSENET_PREDICTIONS,
    DEFAULT_MODEL_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_LABEL_TABLE,
    DEFAULT_SPLIT_METADATA,
    DEFAULT_TEST_PREDICTIONS,
    DEFAULT_THRESHOLDS_PATH,
    DEFAULT_TRAINING_METRICS,
    DENSENET_PROB_DIM,
    DISEASE_LABELS,
    FUSION_MODEL_VERSION,
    snake_label,
)
from src.medagentx.fusion.features import feature_dim_for_mode, load_feature_manifests
from src.medagentx.fusion.labels import LABEL_MODE_JUDGE, LABEL_MODE_WEAK
from src.medagentx.fusion.metrics import (
    compute_pos_weight,
    fit_temperature_scaling,
    logits_from_model,
    masked_bce_with_logits_loss,
    masked_focal_bce_with_logits_loss,
    multilabel_metrics,
    predict_probs,
    tune_thresholds_on_validation,
)
from src.medagentx.fusion.model import FusionMLP
from src.medagentx.fusion.splits import assert_patient_level_integrity, build_patient_split_table
from src.medagentx.fusion.training_data import (
    FusionFeatureDataset,
    arrays_from_training_table,
    build_image_training_table,
    build_study_training_table,
)


def _progress(message: str) -> None:
    print(f"[fusion-train] {message}", flush=True)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-label-table", type=Path, default=DEFAULT_REPORT_LABEL_TABLE)
    parser.add_argument("--densenet-csv", type=Path, default=DEFAULT_DENSENET_PREDICTIONS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--feature-mode", choices=["fusion", "convnext_only", "raddino_only"], default="fusion")
    parser.add_argument("--label-mode", choices=[LABEL_MODE_WEAK, LABEL_MODE_JUDGE], default=LABEL_MODE_JUDGE)
    parser.add_argument("--training-level", choices=["image", "study"], default="image")
    parser.add_argument("--study-pool", choices=["attention", "mean"], default="attention")
    parser.add_argument("--include-densenet-probs", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--loss", choices=["bce", "focal"], default="focal")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=8e-4)
    parser.add_argument("--hidden-dim", type=int, default=512)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--limit-studies", type=int, default=None)
    return parser.parse_args()


def summarize_split(name: str, df: pd.DataFrame, y: np.ndarray, mask: np.ndarray) -> None:
    if df.empty:
        _progress(f"{name}: 0 rows")
        return
    labeled = int(mask.sum())
    positives = int((y * mask).sum())
    _progress(
        f"{name}: {len(df)} rows, {df['deid_patient_id'].nunique()} patients, "
        f"{labeled} supervised cells, {positives} positive cells"
    )


def train_one_epoch(
    model,
    loader,
    optimizer,
    device,
    pos_weight,
    loss_name: str,
):
    model.train()
    total_loss = 0.0
    n = 0
    uses_densenet = model.densenet_dim > 0

    for batch in loader:
        if uses_densenet:
            X, densenet_probs, y, mask = batch
            densenet_probs = densenet_probs.to(device)
        else:
            X, y, mask = batch
            densenet_probs = None

        X = X.to(device)
        y = y.to(device)
        mask = mask.to(device)
        logits = model(X, densenet_probs=densenet_probs)

        if loss_name == "focal":
            loss = masked_focal_bce_with_logits_loss(logits, y, mask, pos_weight=pos_weight)
        else:
            loss = masked_bce_with_logits_loss(
                logits,
                y,
                mask,
                pos_weight=pos_weight,
                label_smoothing_present=0.05,
                label_smoothing_absent=0.02,
            )

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * X.size(0)
        n += X.size(0)

    return total_loss / max(n, 1)


def make_loader(table_df, batch_size, shuffle, include_densenet_probs):
    X, y, mask, densenet_probs = arrays_from_training_table(
        table_df,
        include_densenet_probs=include_densenet_probs,
    )
    dataset = FusionFeatureDataset(X, y, mask, densenet_probs=densenet_probs)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle), X, y, mask, densenet_probs


def main():
    started = time.time()
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    embedding_dim = feature_dim_for_mode(args.feature_mode)
    densenet_dim = DENSENET_PROB_DIM if args.include_densenet_probs else 0
    input_dim = embedding_dim

    _progress("Starting fusion classifier training (v2 stacked).")
    _progress(
        f"label_mode={args.label_mode}, training_level={args.training_level}, "
        f"feature_mode={args.feature_mode}, include_densenet_probs={args.include_densenet_probs}, loss={args.loss}"
    )
    _progress(f"Device: {args.device}")
    _progress(f"Output dir: {args.output_dir}")

    label_df = pd.read_csv(args.report_label_table, dtype=str)
    feature_df = load_feature_manifests()
    image_table = build_image_training_table(
        label_df=label_df,
        feature_df=feature_df,
        feature_mode=args.feature_mode,
        densenet_csv=args.densenet_csv if args.include_densenet_probs else None,
        label_mode=args.label_mode,
    )

    if args.training_level == "study":
        training_table = build_study_training_table(image_table, pool_mode=args.study_pool)
    else:
        training_table = image_table

    if args.limit_studies:
        keep_studies = training_table["study_key"].drop_duplicates().head(args.limit_studies)
        training_table = training_table[training_table["study_key"].isin(keep_studies)].copy()
        _progress(f"Limiting to first {len(keep_studies)} studies")

    split_table = build_patient_split_table(training_table)
    split_table.to_csv(args.output_dir / DEFAULT_SPLIT_METADATA.name, index=False)
    training_table = training_table.merge(split_table, on="deid_patient_id", how="left")
    assert_patient_level_integrity(training_table)

    train_df = training_table[training_table["split"] == "train"].reset_index(drop=True)
    val_df = training_table[training_table["split"] == "validation"].reset_index(drop=True)
    test_df = training_table[training_table["split"] == "test"].reset_index(drop=True)

    train_loader, X_train, y_train, m_train, _ = make_loader(
        train_df, args.batch_size, True, args.include_densenet_probs
    )
    val_loader, X_val, y_val, m_val, _ = make_loader(
        val_df, args.batch_size, False, args.include_densenet_probs
    )
    test_loader, X_test, y_test, m_test, _ = make_loader(
        test_df, args.batch_size, False, args.include_densenet_probs
    )

    summarize_split("Train split", train_df, y_train, m_train)
    summarize_split("Validation split", val_df, y_val, m_val)
    summarize_split("Test split", test_df, y_test, m_test)

    pos_weight = torch.tensor(compute_pos_weight(y_train, m_train), device=args.device)
    model = FusionMLP(
        input_dim=input_dim,
        num_labels=len(DISEASE_LABELS),
        hidden_dim=args.hidden_dim,
        dropout=args.dropout,
        densenet_dim=densenet_dim,
        per_label_heads=True,
    ).to(args.device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    param_count = sum(p.numel() for p in model.parameters())

    _progress(
        f"Training FusionMLP v2 for {args.epochs} epochs "
        f"(batch_size={args.batch_size}, lr={args.lr}, params={param_count:,})"
    )

    metrics_rows = []
    best_val_f1 = -1.0
    best_state = None
    best_epoch = 0
    uses_densenet = model.densenet_dim > 0

    for epoch in range(1, args.epochs + 1):
        epoch_started = time.time()
        train_loss = train_one_epoch(
            model,
            train_loader,
            optimizer,
            args.device,
            pos_weight,
            loss_name=args.loss,
        )
        val_probs = predict_probs(
            model,
            val_loader,
            args.device,
            uses_densenet=uses_densenet,
        )
        thresholds, _ = tune_thresholds_on_validation(y_val, val_probs, m_val)
        val_metrics = multilabel_metrics(y_val, val_probs, m_val, thresholds, DISEASE_LABELS)

        metrics_rows.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "val_macro_f1": val_metrics["macro_f1"],
                "val_micro_f1": val_metrics["micro_f1"],
            }
        )

        improved = val_metrics["macro_f1"] > best_val_f1
        if improved:
            best_val_f1 = val_metrics["macro_f1"]
            best_epoch = epoch
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

        marker = " *best*" if improved else ""
        _progress(
            f"Epoch {epoch:02d}/{args.epochs:02d} | "
            f"train_loss={train_loss:.4f} | "
            f"val_macro_f1={val_metrics['macro_f1']:.4f} | "
            f"val_micro_f1={val_metrics['micro_f1']:.4f} | "
            f"elapsed={time.time() - epoch_started:.1f}s{marker}"
        )

    if best_state is not None:
        model.load_state_dict(best_state)
        _progress(f"Restored best checkpoint from epoch {best_epoch} (val_macro_f1={best_val_f1:.4f})")
    else:
        _progress("No validation improvement recorded; using final epoch weights")

    _progress("Fitting temperature scaling on validation logits")
    val_logits = logits_from_model(model, val_loader, args.device, uses_densenet=uses_densenet)
    temperature = fit_temperature_scaling(val_logits, y_val, m_val, device=torch.device(args.device))

    val_probs = predict_probs(
        model,
        val_loader,
        args.device,
        temperature=temperature,
        uses_densenet=uses_densenet,
    )
    thresholds, _ = tune_thresholds_on_validation(y_val, val_probs, m_val)
    test_probs = predict_probs(
        model,
        test_loader,
        args.device,
        temperature=temperature,
        uses_densenet=uses_densenet,
    )
    test_metrics = multilabel_metrics(y_test, test_probs, m_test, thresholds, DISEASE_LABELS)

    model_path = args.output_dir / DEFAULT_MODEL_PATH.name
    thresholds_path = args.output_dir / DEFAULT_THRESHOLDS_PATH.name
    metrics_path = args.output_dir / DEFAULT_TRAINING_METRICS.name
    test_preds_path = args.output_dir / DEFAULT_TEST_PREDICTIONS.name

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "feature_mode": args.feature_mode,
            "input_dim": input_dim,
            "num_labels": len(DISEASE_LABELS),
            "labels": DISEASE_LABELS,
            "model_version": FUSION_MODEL_VERSION,
            "densenet_dim": densenet_dim,
            "per_label_heads": True,
            "label_mode": args.label_mode,
            "training_level": args.training_level,
            "temperature": float(temperature),
            "loss": args.loss,
        },
        model_path,
    )

    with thresholds_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "model_version": FUSION_MODEL_VERSION,
                "feature_mode": args.feature_mode,
                "label_mode": args.label_mode,
                "training_level": args.training_level,
                "temperature": float(temperature),
                "thresholds": {snake_label(label): float(thresholds[i]) for i, label in enumerate(DISEASE_LABELS)},
            },
            f,
            indent=2,
        )

    pd.DataFrame(metrics_rows).to_csv(metrics_path, index=False)

    test_rows = []
    for idx, row in test_df.reset_index(drop=True).iterrows():
        out = {
            "study_key": row["study_key"],
            "dicom_path": row.get("dicom_path", ""),
            "deid_patient_id": row["deid_patient_id"],
        }
        for j, label in enumerate(DISEASE_LABELS):
            slug = snake_label(label)
            out[f"fusion_prob_{slug}"] = float(test_probs[idx, j])
            out[f"fusion_pred_{slug}"] = int(test_probs[idx, j] >= thresholds[j])
            out[f"fusion_threshold_{slug}"] = float(thresholds[j])
        test_rows.append(out)

    pd.DataFrame(test_rows).to_csv(test_preds_path, index=False)

    _progress("Training complete.")
    _progress(f"Saved model: {model_path}")
    _progress(f"Saved thresholds: {thresholds_path}")
    _progress(f"Saved metrics: {metrics_path}")
    _progress(f"Saved test predictions: {test_preds_path}")
    _progress(f"Validation temperature: {temperature:.4f}")
    _progress(f"Test macro F1 ({args.label_mode} labels): {test_metrics['macro_f1']:.4f}")
    _progress(f"Test micro F1 ({args.label_mode} labels): {test_metrics['micro_f1']:.4f}")
    _progress(f"Total runtime: {time.time() - started:.1f}s")
    _progress("Next steps:")
    _progress("  python scripts/12_run_fusion_inference.py")
    _progress("  python scripts/13_build_ensemble_classifier_predictions.py")
    _progress("  python scripts/14_tune_ensemble_thresholds.py --label-mode judge")
    _progress("  python scripts/16_fit_ensemble_calibrator.py --label-mode judge")


if __name__ == "__main__":
    main()
