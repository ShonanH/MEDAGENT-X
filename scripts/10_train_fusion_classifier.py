#!/usr/bin/env python3
"""
Train study-level multi-label fusion classifier on frozen embeddings.
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
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.fusion.constants import (
    DEFAULT_MODEL_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_LABEL_TABLE,
    DEFAULT_SPLIT_METADATA,
    DEFAULT_TEST_PREDICTIONS,
    DEFAULT_THRESHOLDS_PATH,
    DEFAULT_TRAINING_METRICS,
    DISEASE_LABELS,
    FUSION_MODEL_VERSION,
    snake_label,
)
from src.medagentx.fusion.features import (
    aggregate_study_features,
    concat_image_features,
    feature_dim_for_mode,
    load_feature_manifests,
    merge_label_and_feature_tables,
)
from src.medagentx.fusion.metrics import (
    compute_pos_weight,
    masked_bce_with_logits_loss,
    multilabel_metrics,
    tune_thresholds_on_validation,
)
from src.medagentx.fusion.model import FusionMLP
from src.medagentx.fusion.splits import assert_patient_level_integrity, build_patient_split_table


class StudyFeatureDataset(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray, mask: np.ndarray):
        self.X = torch.from_numpy(X.astype(np.float32))
        self.y = torch.from_numpy(y.astype(np.float32))
        self.mask = torch.from_numpy(mask.astype(np.float32))

    def __len__(self):
        return self.X.shape[0]

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx], self.mask[idx]


def _progress(message: str) -> None:
    print(f"[fusion-train] {message}", flush=True)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-label-table", type=Path, default=DEFAULT_REPORT_LABEL_TABLE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--feature-mode", choices=["fusion", "convnext_only", "raddino_only"], default="fusion")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--limit-studies", type=int, default=None)
    return parser.parse_args()


def summarize_split(name: str, df: pd.DataFrame, y: np.ndarray, mask: np.ndarray) -> None:
    if df.empty:
        _progress(f"{name}: 0 studies")
        return

    labeled = int(mask.sum())
    positives = int((y * mask).sum())
    _progress(
        f"{name}: {len(df)} studies, {df['deid_patient_id'].nunique()} patients, "
        f"{labeled} supervised cells, {positives} positive cells"
    )


def build_study_training_table(
    label_df: pd.DataFrame,
    feature_df: pd.DataFrame,
    feature_mode: str,
) -> pd.DataFrame:
    merged = merge_label_and_feature_tables(label_df, feature_df)
    study_groups = list(merged.groupby("study_key", sort=False))

    study_rows = []
    for study_key, group in tqdm(study_groups, desc="Loading study features", unit="study"):
        image_features = []
        for _, row in group.iterrows():
            image_features.append(
                concat_image_features(
                    row["convnext_feature_path"],
                    row["raddino_feature_path"],
                    feature_mode=feature_mode,
                )
            )

        x_study = aggregate_study_features(image_features)
        first = group.iloc[0]

        out = {
            "study_key": study_key,
            "deid_patient_id": first["deid_patient_id"],
            "image_count": len(group),
            "feature_vector_json": json.dumps(x_study.astype(float).tolist()),
        }

        for label in DISEASE_LABELS:
            slug = snake_label(label)
            value = first.get(f"weak_value_{slug}")
            status = first.get(f"weak_status_{slug}")
            out[f"weak_value_{slug}"] = value
            out[f"weak_status_{slug}"] = status

        study_rows.append(out)

    return pd.DataFrame(study_rows)


def arrays_from_study_table(study_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    X = np.stack(
        [np.asarray(json.loads(v), dtype=np.float32) for v in study_df["feature_vector_json"]],
        axis=0,
    )

    y = []
    mask = []

    for _, row in study_df.iterrows():
        y_row = []
        m_row = []
        for label in DISEASE_LABELS:
            slug = snake_label(label)
            value = row.get(f"weak_value_{slug}")
            if value is None or (isinstance(value, float) and np.isnan(value)) or value == "":
                y_row.append(0.0)
                m_row.append(0.0)
            else:
                y_row.append(float(value))
                m_row.append(1.0)
        y.append(y_row)
        mask.append(m_row)

    return X, np.asarray(y, dtype=np.float32), np.asarray(mask, dtype=np.float32)


def train_one_epoch(model, loader, optimizer, device, pos_weight):
    model.train()
    total_loss = 0.0
    n = 0

    for X, y, mask in loader:
        X = X.to(device)
        y = y.to(device)
        mask = mask.to(device)

        logits = model(X)
        loss = masked_bce_with_logits_loss(logits, y, mask, pos_weight=pos_weight)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * X.size(0)
        n += X.size(0)

    return total_loss / max(n, 1)


@torch.no_grad()
def predict_probs(model, loader, device) -> np.ndarray:
    model.eval()
    outputs = []
    for X, _, _ in loader:
        logits = model(X.to(device))
        probs = torch.sigmoid(logits).cpu().numpy()
        outputs.append(probs)
    return np.concatenate(outputs, axis=0)


def main():
    started = time.time()
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    input_dim = feature_dim_for_mode(args.feature_mode)

    _progress("Starting fusion classifier training.")
    _progress(f"Feature mode: {args.feature_mode} (input_dim={input_dim})")
    _progress(f"Device: {args.device}")
    _progress(f"Output dir: {args.output_dir}")

    _progress(f"Loading weak labels from {args.report_label_table}")
    label_df = pd.read_csv(args.report_label_table, dtype=str)
    _progress(f"Loaded {len(label_df)} image-level label rows across {label_df['study_key'].nunique()} studies")

    _progress("Loading ConvNeXt and RAD-DINO feature manifests")
    feature_df = load_feature_manifests()
    ready_count = int(feature_df["feature_ready"].sum())
    _progress(f"Feature manifest rows: {len(feature_df)} ({ready_count} feature-ready)")

    _progress("Building study-level feature vectors from frozen embeddings")
    study_df = build_study_training_table(label_df, feature_df, feature_mode=args.feature_mode)
    _progress(f"Built {len(study_df)} study-level training rows")

    if args.limit_studies:
        study_df = study_df.head(args.limit_studies).copy()
        _progress(f"Limiting to first {len(study_df)} studies for this run")

    _progress("Creating patient-level train/validation/test splits")
    split_table = build_patient_split_table(study_df)
    split_table.to_csv(args.output_dir / DEFAULT_SPLIT_METADATA.name, index=False)
    _progress(f"Saved split metadata to {args.output_dir / DEFAULT_SPLIT_METADATA.name}")

    study_df = study_df.merge(split_table, on="deid_patient_id", how="left")
    assert_patient_level_integrity(study_df)

    train_df = study_df[study_df["split"] == "train"].reset_index(drop=True)
    val_df = study_df[study_df["split"] == "validation"].reset_index(drop=True)
    test_df = study_df[study_df["split"] == "test"].reset_index(drop=True)

    X_train, y_train, m_train = arrays_from_study_table(train_df)
    X_val, y_val, m_val = arrays_from_study_table(val_df)
    X_test, y_test, m_test = arrays_from_study_table(test_df)

    summarize_split("Train split", train_df, y_train, m_train)
    summarize_split("Validation split", val_df, y_val, m_val)
    summarize_split("Test split", test_df, y_test, m_test)

    pos_weight = torch.tensor(compute_pos_weight(y_train, m_train), device=args.device)

    train_loader = DataLoader(StudyFeatureDataset(X_train, y_train, m_train), batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(StudyFeatureDataset(X_val, y_val, m_val), batch_size=args.batch_size, shuffle=False)
    test_loader = DataLoader(StudyFeatureDataset(X_test, y_test, m_test), batch_size=args.batch_size, shuffle=False)

    model = FusionMLP(
        input_dim=input_dim,
        num_labels=len(DISEASE_LABELS),
    ).to(args.device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    param_count = sum(p.numel() for p in model.parameters())

    _progress(
        f"Training FusionMLP for {args.epochs} epochs "
        f"(batch_size={args.batch_size}, lr={args.lr}, params={param_count:,})"
    )

    metrics_rows = []
    best_val_f1 = -1.0
    best_state = None
    best_epoch = 0

    for epoch in range(1, args.epochs + 1):
        epoch_started = time.time()
        train_loss = train_one_epoch(model, train_loader, optimizer, args.device, pos_weight)
        val_probs = predict_probs(model, val_loader, args.device)
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

    _progress("Running final validation threshold tuning and test evaluation")
    val_probs = predict_probs(model, val_loader, args.device)
    thresholds, _ = tune_thresholds_on_validation(y_val, val_probs, m_val)
    test_probs = predict_probs(model, test_loader, args.device)
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
        },
        model_path,
    )

    with thresholds_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "model_version": FUSION_MODEL_VERSION,
                "feature_mode": args.feature_mode,
                "thresholds": {snake_label(label): float(thresholds[i]) for i, label in enumerate(DISEASE_LABELS)},
            },
            f,
            indent=2,
        )

    pd.DataFrame(metrics_rows).to_csv(metrics_path, index=False)

    test_rows = []
    for i, row in test_df.iterrows():
        out = {"study_key": row["study_key"], "deid_patient_id": row["deid_patient_id"]}
        for j, label in enumerate(DISEASE_LABELS):
            slug = snake_label(label)
            out[f"fusion_prob_{slug}"] = float(test_probs[i, j])
            out[f"fusion_pred_{slug}"] = int(test_probs[i, j] >= thresholds[j])
            out[f"fusion_threshold_{slug}"] = float(thresholds[j])
        test_rows.append(out)

    pd.DataFrame(test_rows).to_csv(test_preds_path, index=False)

    _progress("Training complete.")
    _progress(f"Saved model: {model_path}")
    _progress(f"Saved thresholds: {thresholds_path}")
    _progress(f"Saved metrics: {metrics_path}")
    _progress(f"Saved test predictions: {test_preds_path}")
    _progress(f"Test macro F1: {test_metrics['macro_f1']:.4f}")
    _progress(f"Test micro F1: {test_metrics['micro_f1']:.4f}")
    _progress(f"Total runtime: {time.time() - started:.1f}s")
    _progress("Next step: python scripts/12_run_fusion_inference.py")


if __name__ == "__main__":
    main()
