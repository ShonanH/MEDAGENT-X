#!/usr/bin/env python3
"""
Run fusion classifier inference and emit Workflow-B-compatible predictions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from medagentx._bootstrap import ensure_src_on_path

ensure_src_on_path()

from medagentx.fusion.constants import (
    DEFAULT_FUSION_PREDICTIONS,
    DEFAULT_MODEL_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_THRESHOLDS_PATH,
    DISEASE_LABELS,
    FUSION_MODEL_VERSION,
    NON_DISEASE_LABELS,
    snake_label,
)
from medagentx.fusion.features import aggregate_study_features, concat_image_features, load_feature_manifests
from medagentx.fusion.labels import derive_no_finding_status
from medagentx.fusion.model import FusionMLP


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--thresholds-path", type=Path, default=DEFAULT_THRESHOLDS_PATH)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_FUSION_PREDICTIONS)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()


from medagentx.fusion.calibration import prob_to_status
def main():
    args = parse_args()
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    checkpoint = torch.load(args.model_path, map_location="cpu")
    thresholds_payload = json.loads(args.thresholds_path.read_text(encoding="utf-8"))
    thresholds = {
        label: thresholds_payload["thresholds"][snake_label(label)]
        for label in DISEASE_LABELS
    }

    model = FusionMLP(
        input_dim=checkpoint["input_dim"],
        num_labels=checkpoint["num_labels"],
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(args.device)
    model.eval()

    feature_mode = checkpoint["feature_mode"]
    feature_df = load_feature_manifests()
    feature_df = feature_df[feature_df["feature_ready"]].copy()

    study_predictions = {}

    for study_key, group in feature_df.groupby("study_key", sort=False):
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
        x_tensor = torch.from_numpy(x_study.astype(np.float32)).unsqueeze(0).to(args.device)

        with torch.no_grad():
            probs = torch.sigmoid(model(x_tensor)).cpu().numpy()[0]

        disease_statuses = {}
        study_pred = {}

        for i, label in enumerate(DISEASE_LABELS):
            slug = snake_label(label)
            prob = float(probs[i])
            threshold = float(thresholds[label])
            status = prob_to_status(prob, threshold)
            disease_statuses[label] = status

            study_pred[f"fusion_prob_{slug}"] = prob
            study_pred[f"fusion_status_{slug}"] = status
            study_pred[f"fusion_threshold_{slug}"] = threshold

        no_finding_status = derive_no_finding_status(disease_statuses)
        study_pred["fusion_status_support_devices"] = "not_computed"
        study_pred["fusion_status_no_finding"] = no_finding_status
        study_pred["fusion_model_version"] = checkpoint.get("model_version", FUSION_MODEL_VERSION)

        study_predictions[study_key] = study_pred

    rows = []
    for _, row in feature_df.iterrows():
        pred = study_predictions[row["study_key"]]
        out = {
            "study_key": row["study_key"],
            "dicom_path": row["dicom_path"],
            **pred,
        }
        rows.append(out)

    pd.DataFrame(rows).to_csv(args.output_csv, index=False)
    print(f"Wrote {len(rows)} rows to {args.output_csv}")


if __name__ == "__main__":
    main()