#!/usr/bin/env python3
"""
Train study-level multi-label fusion classifier on frozen embeddings.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset

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


def build_study_training_table(
    label_df: pd.DataFrame,
    feature_df: pd.DataFrame,
    feature_mode: str,
) -> pd.DataFrame:
    merged = label_df.merge(feature_df, on=["study_key", "dicom_path"], how="inner")
    merged = merged[merged["feature_ready"]].copy()

    study_rows = []

    for study_key, group in merged.groupby("study_key", sort=False):
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
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    label_df = pd.read_csv(args.report_label_table, dtype=str)
    feature_df = load_feature_manifests()
    study_df = build_study_training_table(label_df, feature_df, feature_mode=args.feature_mode)

    if args.limit_studies:
        study_df = study_df.head(args.limit_studies).copy()

    split_table = build_patient_split_table(study_df)
    split_table.to_csv(args.output_dir / DEFAULT_SPLIT_METADATA.name, index=False)

    study_df = study_df.merge(split_table, on="deid_patient_id", how="left")
    assert_patient_level_integrity(study_df)

    X, y, mask = arrays_from_study_table(study_df)

    train_df = study_df[study_df["split"] == "train"].reset_index(drop=True)
    val_df = study_df[study_df["split"] == "validation"].reset_index(drop=True)
    test_df = study_df[study_df["split"] == "test"].reset_index(drop=True)

    X_train, y_train, m_train = arrays_from_study_table(train_df)
    X_val, y_val, m_val = arrays_from_study_table(val_df)
    X_test, y_test, m_test = arrays_from_study_table(test_df)

    pos_weight = torch.tensor(compute_pos_weight(y_train, m_train), device=args.device)

    train_loader = DataLoader(StudyFeatureDataset(X_train, y_train, m_train), batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(StudyFeatureDataset(X_val, y_val, m_val), batch_size=args.batch_size, shuffle=False)
    test_loader = DataLoader(StudyFeatureDataset(X_test, y_test, m_test), batch_size=args.batch_size, shuffle=False)

    model = FusionMLP(
        input_dim=feature_dim_for_mode(args.feature_mode),
        num_labels=len(DISEASE_LABELS),
    ).to(args.device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)

    metrics_rows = []
    best_val_f1 = -1.0
    best_state = None

    for epoch in range(1, args.epochs + 1):
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

        if val_metrics["macro_f1"] > best_val_f1:
            best_val_f1 = val_metrics["macro_f1"]
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

        print(
            f"epoch={epoch} train_loss={train_loss:.4f} "
            f"val_macro_f1={val_metrics['macro_f1']:.4f}"
        )

    if best_state is not None:
        model.load_state_dict(best_state)

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
            "input_dim": feature_dim_for_mode(args.feature_mode),
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

    print(f"Saved model to {model_path}")
    print(f"Test macro F1: {test_metrics['macro_f1']:.4f}")
    print(f"Test micro F1: {test_metrics['micro_f1']:.4f}")


if __name__ == "__main__":
    main()