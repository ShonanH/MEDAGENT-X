#!/usr/bin/env python3
"""
Run fusion classifier inference and emit Workflow-B-compatible predictions.

Supports v2 stacked models with per-image DenseNet probability inputs and
temperature-scaled probabilities.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.fusion.calibration import prob_to_status
from src.medagentx.fusion.constants import (
    DEFAULT_DENSENET_PREDICTIONS,
    DEFAULT_FUSION_PREDICTIONS,
    DEFAULT_MODEL_PATH,
    DEFAULT_THRESHOLDS_PATH,
    DISEASE_LABELS,
    FUSION_MODEL_VERSION,
    snake_label,
)
from src.medagentx.fusion.densenet_features import densenet_prob_lookup, load_densenet_prediction_table
from src.medagentx.fusion.features import concat_image_features, load_feature_manifests
from src.medagentx.fusion.model import FusionMLP


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--thresholds-path", type=Path, default=DEFAULT_THRESHOLDS_PATH)
    parser.add_argument("--densenet-csv", type=Path, default=DEFAULT_DENSENET_PREDICTIONS)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_FUSION_PREDICTIONS)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()


def load_model(checkpoint_path: Path, device: str) -> tuple[FusionMLP, dict]:
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    model = FusionMLP(
        input_dim=int(checkpoint["input_dim"]),
        num_labels=int(checkpoint["num_labels"]),
        densenet_dim=int(checkpoint.get("densenet_dim", 0)),
        per_label_heads=bool(checkpoint.get("per_label_heads", True)),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return model, checkpoint


def main():
    args = parse_args()
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    model, checkpoint = load_model(args.model_path, args.device)
    thresholds_payload = json.loads(args.thresholds_path.read_text(encoding="utf-8"))
    thresholds = {
        label: float(thresholds_payload["thresholds"][snake_label(label)])
        for label in DISEASE_LABELS
    }
    temperature = float(
        thresholds_payload.get(
            "temperature",
            checkpoint.get("temperature", 1.0),
        )
    )

    densenet_lookup = {}
    if model.densenet_dim > 0 and args.densenet_csv.exists():
        densenet_lookup = densenet_prob_lookup(load_densenet_prediction_table(args.densenet_csv))

    feature_mode = checkpoint["feature_mode"]
    feature_df = load_feature_manifests()
    feature_df = feature_df[feature_df["feature_ready"]].copy()

    rows = []
    for _, row in feature_df.iterrows():
        embedding = concat_image_features(
            row["convnext_feature_path"],
            row["raddino_feature_path"],
            feature_mode=feature_mode,
        )
        x_tensor = torch.from_numpy(embedding.astype(np.float32)).unsqueeze(0).to(args.device)

        densenet_tensor = None
        if model.densenet_dim > 0:
            dicom_path = row["dicom_path"]
            densenet_vec = densenet_lookup.get(dicom_path, np.zeros(model.densenet_dim, dtype=np.float32))
            densenet_tensor = torch.from_numpy(densenet_vec.astype(np.float32)).unsqueeze(0).to(args.device)

        with torch.no_grad():
            logits = model(x_tensor, densenet_probs=densenet_tensor)
            probs = torch.sigmoid(logits / max(temperature, 1e-3)).cpu().numpy()[0]

        disease_statuses = {}
        out = {
            "study_key": row["study_key"],
            "dicom_path": row["dicom_path"],
            "fusion_model_version": checkpoint.get("model_version", FUSION_MODEL_VERSION),
            "fusion_temperature": temperature,
        }

        for i, label in enumerate(DISEASE_LABELS):
            slug = snake_label(label)
            prob = float(probs[i])
            threshold = float(thresholds[label])
            status = prob_to_status(prob, threshold)
            disease_statuses[label] = status

            out[f"fusion_prob_{slug}"] = prob
            out[f"fusion_status_{slug}"] = status
            out[f"fusion_threshold_{slug}"] = threshold

        out["fusion_status_support_devices"] = "not_computed"
        out["fusion_status_no_finding"] = "absent" if any(
            disease_statuses[label] == "present" for label in DISEASE_LABELS
        ) else "present"
        rows.append(out)

    pd.DataFrame(rows).to_csv(args.output_csv, index=False)
    print(f"Wrote {len(rows)} rows to {args.output_csv}")


if __name__ == "__main__":
    main()
