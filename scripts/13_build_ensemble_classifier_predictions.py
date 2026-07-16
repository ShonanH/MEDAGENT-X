#!/usr/bin/env python3
"""
Combine DenseNet and fusion classifier predictions into ensemble evidence.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.fusion.constants import (
    DEFAULT_DENSENET_PREDICTIONS,
    DEFAULT_ENSEMBLE_PREDICTIONS,
    DEFAULT_FUSION_PREDICTIONS,
    DISEASE_LABELS,
    NON_DISEASE_LABELS,
    snake_label,
)
from src.medagentx.fusion.labels import derive_no_finding_status
from src.medagentx.fusion.paths import clean_dicom_path


STRONG_PRESENT = 0.75
MODERATE_PRESENT = 0.60
ABSENT_HIGH = 0.20


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--densenet-csv", type=Path, default=DEFAULT_DENSENET_PREDICTIONS)
    parser.add_argument("--fusion-csv", type=Path, default=DEFAULT_FUSION_PREDICTIONS)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_ENSEMBLE_PREDICTIONS)
    parser.add_argument("--fusion-weight", type=float, default=0.5)
    return parser.parse_args()


def safe_float(value):
    if value is None or value == "" or (isinstance(value, float) and np.isnan(value)):
        return None
    return float(value)


def agreement_field(d_prob: float | None, f_prob: float | None) -> str:
    if d_prob is None and f_prob is None:
        return "insufficient_evidence"
    if d_prob is None or f_prob is None:
        return "insufficient_evidence"

    d_present = d_prob >= MODERATE_PRESENT
    f_present = f_prob >= MODERATE_PRESENT
    d_absent = d_prob <= ABSENT_HIGH
    f_absent = f_prob <= ABSENT_HIGH

    if d_present and f_present:
        return "strong_present"
    if d_absent and f_absent:
        return "strong_absent"
    if d_present and not f_present and not f_absent:
        return "weak_present"
    if f_present and not d_present and not d_absent:
        return "weak_present"
    if d_absent and not f_absent and not f_present:
        return "weak_absent"
    if f_absent and not d_present and not d_present:
        return "weak_absent"
    if (d_present and f_absent) or (f_present and d_absent):
        return "conflict"
    return "insufficient_evidence"


def prob_to_status(prob: float | None) -> str:
    if prob is None:
        return "unavailable"
    if prob >= 0.50:
        return "present"
    if prob <= ABSENT_HIGH:
        return "absent"
    return "uncertain"


def main():
    args = parse_args()
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    densenet_df = pd.read_csv(args.densenet_csv, dtype=str)
    fusion_df = pd.read_csv(args.fusion_csv, dtype=str)

    densenet_df["dicom_path"] = densenet_df["dicom_path"].map(clean_dicom_path)
    fusion_df["dicom_path"] = fusion_df["dicom_path"].map(clean_dicom_path)

    merged = densenet_df.merge(
        fusion_df,
        on=["study_key", "dicom_path"],
        how="outer",
        suffixes=("_densenet", "_fusion"),
    )

    rows = []

    for _, row in merged.iterrows():
        out = {
            "study_key": row["study_key"],
            "dicom_path": row["dicom_path"],
            "ensemble_model_version": "densenet_fusion_v1",
            "ensemble_fusion_weight": args.fusion_weight,
        }

        disease_statuses = {}

        for label in DISEASE_LABELS:
            slug = snake_label(label)

            d_prob = safe_float(row.get(f"classifier_prob_{slug}"))
            f_prob = safe_float(row.get(f"fusion_prob_{slug}"))

            if d_prob is not None and f_prob is not None:
                e_prob = (1.0 - args.fusion_weight) * d_prob + args.fusion_weight * f_prob
            elif d_prob is not None:
                e_prob = d_prob
            elif f_prob is not None:
                e_prob = f_prob
            else:
                e_prob = None

            e_status = prob_to_status(e_prob)
            disease_statuses[label] = e_status

            out[f"densenet_prob_{slug}"] = d_prob
            out[f"fusion_prob_{slug}"] = f_prob
            out[f"ensemble_prob_{slug}"] = e_prob

            out[f"densenet_status_{slug}"] = row.get(f"classifier_status_{slug}", prob_to_status(d_prob))
            out[f"fusion_status_{slug}"] = row.get(f"fusion_status_{slug}", prob_to_status(f_prob))
            out[f"ensemble_status_{slug}"] = e_status
            out[f"ensemble_agreement_{slug}"] = agreement_field(d_prob, f_prob)

            # Drop-in fields for Disease Reasoning Agent
            out[f"classifier_prob_{slug}"] = e_prob
            out[f"classifier_status_{slug}"] = e_status
            out[f"classifier_source_label_{slug}"] = "ensemble"

        out["classifier_status_support_devices"] = "unavailable"
        out["classifier_status_no_finding"] = derive_no_finding_status(disease_statuses)
        out["classifier_model"] = "ensemble_densenet_fusion"
        out["route_next"] = "retrieval_agent"

        rows.append(out)

    pd.DataFrame(rows).to_csv(args.output_csv, index=False)
    print(f"Wrote {len(rows)} rows to {args.output_csv}")


if __name__ == "__main__":
    main()