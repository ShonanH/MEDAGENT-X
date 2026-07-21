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

from medagentx._bootstrap import ensure_src_on_path

ensure_src_on_path()

from medagentx.fusion.constants import (
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
from medagentx.fusion.features import (
    aggregate_study_features,
    concat_image_features,
    feature_dim_for_mode,
    load_feature_manifests,
    merge_label_and_feature_tables,
)
from medagentx.fusion.calibration import (
    TRAINING_DEFAULT_PRESENT_THRESHOLD,
    apply_deployment_thresholds,
)
from medagentx.fusion.metrics import (
    compute_pos_weight,
    fusion_training_loss,
    multilabel_metrics,
    multilabel_ranking_metrics,
    tune_thresholds_on_validation,
    tune_thresholds_precision_favored,
)
from medagentx.fusion.model import FusionMLP
from medagentx.fusion.splits import assert_patient_level_integrity, build_patient_split_table


class StudyFeatureDataset(Dataset):
    def __init__(self, X: np.ndarray, y: np.ndarray, mask: np.ndarray, no_finding_mask: np.ndarray):
        self.X = torch.from_numpy(X.astype(np.float32))
        self.y = torch.from_numpy(y.astype(np.float32))
        self.mask = torch.from_numpy(mask.astype(np.float32))
        self.no_finding_mask = torch.from_numpy(no_finding_mask.astype(np.float32))

    def __len__(self):
        return self.X.shape[0]

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx], self.mask[idx], self.no_finding_mask[idx]


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
    parser.add_argument(
        "--no-finding-penalty-weight",
        type=float,
        default=0.0,
        help="Auxiliary loss weight when No Finding=1 but disease heads are high (default: off).",
    )
    parser.add_argument(
        "--no-finding-negative-weight",
        type=float,
        default=0.35,
        help="Downweight explicit negative labels on No Finding studies in BCE (0-1].",
    )
    parser.add_argument(
        "--pos-weight-boost",
        type=float,
        default=2.0,
        help="Multiplier for per-label pos_weight to improve recall on rare positives.",
    )
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

        no_finding_slug = snake_label("No Finding")
        out[f"weak_value_{no_finding_slug}"] = first.get(f"weak_value_{no_finding_slug}")
        out[f"weak_status_{no_finding_slug}"] = first.get(f"weak_status_{no_finding_slug}")

        study_rows.append(out)

    return pd.DataFrame(study_rows)


def arrays_from_study_table(
    study_df: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    X = np.stack(
        [np.asarray(json.loads(v), dtype=np.float32) for v in study_df["feature_vector_json"]],
        axis=0,
    )

    y = []
    mask = []
    no_finding_mask = []
    no_finding_slug = snake_label("No Finding")

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

        no_finding_value = row.get(f"weak_value_{no_finding_slug}")
        no_finding_status = str(row.get(f"weak_status_{no_finding_slug}", "")).strip().lower()
        is_no_finding = (
            no_finding_status == "present"
            or (no_finding_value is not None and float(no_finding_value) >= 0.5)
        )
        no_finding_mask.append(1.0 if is_no_finding else 0.0)

    return (
        X,
        np.asarray(y, dtype=np.float32),
        np.asarray(mask, dtype=np.float32),
        np.asarray(no_finding_mask, dtype=np.float32),
    )


def train_one_epoch(
    model,
    loader,
    optimizer,
    device,
    pos_weight,
    no_finding_penalty_weight,
    no_finding_negative_weight,
):
    model.train()
    total_loss = 0.0
    n = 0

    for X, y, mask, no_finding_mask in loader:
        X = X.to(device)
        y = y.to(device)
        mask = mask.to(device)
        no_finding_mask = no_finding_mask.to(device)

        logits = model(X)
        loss = fusion_training_loss(
            logits,
            y,
            mask,
            no_finding_mask=no_finding_mask,
            pos_weight=pos_weight,
            no_finding_penalty_weight=no_finding_penalty_weight,
            no_finding_negative_weight=no_finding_negative_weight,
        )

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
    for X, _, _, _ in loader:
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

    X_train, y_train, m_train, nf_train = arrays_from_study_table(train_df)
    X_val, y_val, m_val, nf_val = arrays_from_study_table(val_df)
    X_test, y_test, m_test, nf_test = arrays_from_study_table(test_df)

    summarize_split("Train split", train_df, y_train, m_train)
    summarize_split("Validation split", val_df, y_val, m_val)
    summarize_split("Test split", test_df, y_test, m_test)
    _progress(f"No Finding present studies (train): {int(nf_train.sum())}")

    pos_weight = torch.tensor(
        compute_pos_weight(y_train, m_train, boost=args.pos_weight_boost),
        device=args.device,
    )

    train_loader = DataLoader(
        StudyFeatureDataset(X_train, y_train, m_train, nf_train),
        batch_size=args.batch_size,
        shuffle=True,
    )
    val_loader = DataLoader(
        StudyFeatureDataset(X_val, y_val, m_val, nf_val),
        batch_size=args.batch_size,
        shuffle=False,
    )
    test_loader = DataLoader(
        StudyFeatureDataset(X_test, y_test, m_test, nf_test),
        batch_size=args.batch_size,
        shuffle=False,
    )

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
    best_val_score = -1.0
    best_state = None
    best_epoch = 0

    for epoch in range(1, args.epochs + 1):
        epoch_started = time.time()
        train_loss = train_one_epoch(
            model,
            train_loader,
            optimizer,
            args.device,
            pos_weight,
            args.no_finding_penalty_weight,
            args.no_finding_negative_weight,
        )
        val_probs = predict_probs(model, val_loader, args.device)
        val_thresholds, _ = tune_thresholds_precision_favored(
            y_val,
            val_probs,
            m_val,
            DISEASE_LABELS,
            beta=1.0,
            min_precision=0.15,
            apply_floors=False,
            default_threshold=TRAINING_DEFAULT_PRESENT_THRESHOLD,
        )
        val_metrics = multilabel_metrics(y_val, val_probs, m_val, val_thresholds, DISEASE_LABELS)
        val_ranking = multilabel_ranking_metrics(y_val, val_probs, m_val, DISEASE_LABELS)

        metrics_rows.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "val_macro_f1": val_metrics["macro_f1"],
                "val_micro_f1": val_metrics["micro_f1"],
                "val_macro_auroc": val_ranking["macro_auroc"],
                "val_macro_avg_precision": val_ranking["macro_avg_precision"],
            }
        )

        val_score = val_ranking["macro_avg_precision"]
        if np.isnan(val_score):
            val_score = val_metrics["macro_f1"]

        improved = val_score > best_val_score
        if improved:
            best_val_score = val_score
            best_epoch = epoch
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

        marker = " *best*" if improved else ""
        _progress(
            f"Epoch {epoch:02d}/{args.epochs:02d} | "
            f"train_loss={train_loss:.4f} | "
            f"val_macro_f1={val_metrics['macro_f1']:.4f} | "
            f"val_macro_ap={val_ranking['macro_avg_precision']:.4f} | "
            f"val_macro_auroc={val_ranking['macro_auroc']:.4f} | "
            f"elapsed={time.time() - epoch_started:.1f}s{marker}"
        )

    if best_state is not None:
        model.load_state_dict(best_state)
        _progress(
            f"Restored best checkpoint from epoch {best_epoch} "
            f"(val_macro_ap={best_val_score:.4f})"
        )
    else:
        _progress("No validation improvement recorded; using final epoch weights")

    _progress("Running final validation threshold tuning and test evaluation")
    val_probs = predict_probs(model, val_loader, args.device)
    tuned_thresholds, _ = tune_thresholds_on_validation(y_val, val_probs, m_val)
    deploy_thresholds = apply_deployment_thresholds(tuned_thresholds, DISEASE_LABELS)
    test_probs = predict_probs(model, test_loader, args.device)
    test_metrics_tuned = multilabel_metrics(y_test, test_probs, m_test, tuned_thresholds, DISEASE_LABELS)
    test_metrics_deploy = multilabel_metrics(y_test, test_probs, m_test, deploy_thresholds, DISEASE_LABELS)
    test_ranking = multilabel_ranking_metrics(y_test, test_probs, m_test, DISEASE_LABELS)

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
                "thresholds": {
                    snake_label(label): float(deploy_thresholds[i])
                    for i, label in enumerate(DISEASE_LABELS)
                },
                "tuned_thresholds": {
                    snake_label(label): float(tuned_thresholds[i])
                    for i, label in enumerate(DISEASE_LABELS)
                },
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
            out[f"fusion_pred_{slug}"] = int(test_probs[i, j] >= deploy_thresholds[j])
            out[f"fusion_pred_tuned_{slug}"] = int(test_probs[i, j] >= tuned_thresholds[j])
            out[f"fusion_threshold_{slug}"] = float(deploy_thresholds[j])
            out[f"fusion_threshold_tuned_{slug}"] = float(tuned_thresholds[j])
        test_rows.append(out)

    pd.DataFrame(test_rows).to_csv(test_preds_path, index=False)

    _progress("Training complete.")
    _progress(f"Saved model: {model_path}")
    _progress(f"Saved thresholds: {thresholds_path}")
    _progress(f"Saved metrics: {metrics_path}")
    _progress(f"Saved test predictions: {test_preds_path}")
    _progress(f"Test macro F1 (tuned thresholds): {test_metrics_tuned['macro_f1']:.4f}")
    _progress(f"Test micro F1 (tuned thresholds): {test_metrics_tuned['micro_f1']:.4f}")
    _progress(f"Test macro F1 (deployment thresholds): {test_metrics_deploy['macro_f1']:.4f}")
    _progress(f"Test micro F1 (deployment thresholds): {test_metrics_deploy['micro_f1']:.4f}")
    _progress(f"Test macro AUROC: {test_ranking['macro_auroc']:.4f}")
    _progress(f"Test macro AP: {test_ranking['macro_avg_precision']:.4f}")
    _progress(f"Total runtime: {time.time() - started:.1f}s")
    _progress("Next step: python -m medagentx.cli.14_run_fusion_inference")


if __name__ == "__main__":
    main()
