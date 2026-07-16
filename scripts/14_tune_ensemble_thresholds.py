#!/usr/bin/env python3
"""
Tune ensemble per-label thresholds from report labels and classifier probabilities.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.fusion.calibration import thresholds_to_json_payload, tune_thresholds_precision_favored
from src.medagentx.fusion.constants import (
    DEFAULT_ENSEMBLE_PREDICTIONS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_LABEL_TABLE,
    DISEASE_LABELS,
    snake_label,
)
from src.medagentx.fusion.labels import LABEL_MODE_JUDGE, LABEL_MODE_WEAK, training_value_from_row
from src.medagentx.fusion.paths import clean_dicom_path


DEFAULT_ENSEMBLE_THRESHOLDS = DEFAULT_OUTPUT_DIR / "ensemble_thresholds.json"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-label-table", type=Path, default=DEFAULT_REPORT_LABEL_TABLE)
    parser.add_argument("--ensemble-csv", type=Path, default=DEFAULT_ENSEMBLE_PREDICTIONS)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_ENSEMBLE_THRESHOLDS)
    parser.add_argument("--label-mode", choices=[LABEL_MODE_WEAK, LABEL_MODE_JUDGE], default=LABEL_MODE_JUDGE)
    parser.add_argument("--split", choices=["all", "validation"], default="validation")
    parser.add_argument("--split-metadata", type=Path, default=DEFAULT_OUTPUT_DIR / "patient_split_metadata.csv")
    return parser.parse_args()


def build_arrays(
    label_df: pd.DataFrame,
    ensemble_df: pd.DataFrame,
    label_mode: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    merged = label_df.merge(
        ensemble_df[["study_key", "dicom_path"] + [f"ensemble_prob_{snake_label(l)}" for l in DISEASE_LABELS]],
        on=["study_key", "dicom_path"],
        how="inner",
    )

    y = []
    mask = []
    probs = []

    for _, row in merged.iterrows():
        y_row = []
        m_row = []
        p_row = []
        for label in DISEASE_LABELS:
            slug = snake_label(label)
            value = training_value_from_row(row, label, label_mode)
            if value is None:
                y_row.append(0.0)
                m_row.append(0.0)
            else:
                y_row.append(float(value))
                m_row.append(1.0)
            p_row.append(float(row.get(f"ensemble_prob_{slug}", 0.0)))
        y.append(y_row)
        mask.append(m_row)
        probs.append(p_row)

    return (
        np.asarray(probs, dtype=np.float32),
        np.asarray(y, dtype=np.float32),
        np.asarray(mask, dtype=np.float32),
    )


def filter_validation_rows(label_df: pd.DataFrame, split_metadata: Path) -> pd.DataFrame:
    if not split_metadata.exists():
        return label_df
    split_df = pd.read_csv(split_metadata, dtype=str)
    val_patients = set(split_df[split_df["split"] == "validation"]["deid_patient_id"])
    return label_df[label_df["deid_patient_id"].isin(val_patients)].copy()


def main():
    args = parse_args()

    label_df = pd.read_csv(args.report_label_table, dtype=str)
    ensemble_df = pd.read_csv(args.ensemble_csv, dtype=str)
    label_df["dicom_path"] = label_df["dicom_path"].map(clean_dicom_path)
    ensemble_df["dicom_path"] = ensemble_df["dicom_path"].map(clean_dicom_path)

    if args.split == "validation":
        label_df = filter_validation_rows(label_df, args.split_metadata)

    probs, y, mask = build_arrays(label_df, ensemble_df, args.label_mode)
    thresholds, scores = tune_thresholds_precision_favored(
        y,
        probs,
        mask,
        DISEASE_LABELS,
        beta=0.5,
        min_precision=0.40,
    )

    threshold_map = {label: float(thresholds[i]) for i, label in enumerate(DISEASE_LABELS)}
    payload = thresholds_to_json_payload(
        threshold_map,
        model_version="ensemble_densenet_fusion_v4_judge_tuned",
    )
    payload["label_mode"] = args.label_mode
    payload["split"] = args.split
    payload["validation_scores"] = {
        snake_label(label): float(scores[i]) for i, label in enumerate(DISEASE_LABELS)
    }

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote tuned ensemble thresholds to {args.output_path}")


if __name__ == "__main__":
    main()
