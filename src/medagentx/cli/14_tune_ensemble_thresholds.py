#!/usr/bin/env python3
"""
Tune ensemble per-label thresholds from weak report labels and classifier probabilities.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from medagentx._bootstrap import ensure_src_on_path

ensure_src_on_path()

from medagentx.fusion.calibration import thresholds_to_json_payload, tune_thresholds_precision_favored
from medagentx.fusion.constants import (
    DEFAULT_ENSEMBLE_PREDICTIONS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_LABEL_TABLE,
    DISEASE_LABELS,
    snake_label,
)
from medagentx.fusion.paths import clean_dicom_path


DEFAULT_ENSEMBLE_THRESHOLDS = DEFAULT_OUTPUT_DIR / "ensemble_thresholds.json"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-label-table", type=Path, default=DEFAULT_REPORT_LABEL_TABLE)
    parser.add_argument("--ensemble-csv", type=Path, default=DEFAULT_ENSEMBLE_PREDICTIONS)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_ENSEMBLE_THRESHOLDS)
    return parser.parse_args()


def build_arrays(label_df: pd.DataFrame, ensemble_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    merged = label_df.merge(
        ensemble_df[["study_key", "dicom_path"] + [f"ensemble_prob_{snake_label(l)}" for l in DISEASE_LABELS]],
        on=["study_key", "dicom_path"],
        how="inner",
    )

    study_df = merged.groupby("study_key", sort=False).first().reset_index()

    y = []
    mask = []
    probs = []

    for _, row in study_df.iterrows():
        y_row = []
        m_row = []
        p_row = []
        for label in DISEASE_LABELS:
            slug = snake_label(label)
            value = row.get(f"weak_value_{slug}")
            if value is None or value == "" or (isinstance(value, float) and np.isnan(value)):
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


def main():
    args = parse_args()

    label_df = pd.read_csv(args.report_label_table, dtype=str)
    ensemble_df = pd.read_csv(args.ensemble_csv, dtype=str)
    label_df["dicom_path"] = label_df["dicom_path"].map(clean_dicom_path)
    ensemble_df["dicom_path"] = ensemble_df["dicom_path"].map(clean_dicom_path)

    probs, y, mask = build_arrays(label_df, ensemble_df)
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
        model_version="ensemble_densenet_fusion_v2_tuned",
    )
    payload["validation_scores"] = {
        snake_label(label): float(scores[i]) for i, label in enumerate(DISEASE_LABELS)
    }

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote tuned ensemble thresholds to {args.output_path}")


if __name__ == "__main__":
    main()
