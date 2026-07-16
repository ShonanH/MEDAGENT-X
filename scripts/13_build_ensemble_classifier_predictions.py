#!/usr/bin/env python3
"""
Combine DenseNet and fusion classifier predictions into calibrated ensemble evidence.
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

from src.medagentx.fusion.constants import DEFAULT_OUTPUT_DIR, snake_label
from src.medagentx.fusion.calibration import DEFAULT_ABSENT_THRESHOLD, DEFAULT_PRESENT_THRESHOLD
from src.medagentx.fusion.calibration import (
    agreement_field,
    apply_threshold_floor,
    default_densenet_thresholds,
    ensemble_present_status,
    ensemble_prob_blend,
    load_threshold_json,
    prob_to_status,
    thresholds_to_json_payload,
)
from src.medagentx.fusion.constants import (
    DEFAULT_DENSENET_PREDICTIONS,
    DEFAULT_ENSEMBLE_CALIBRATOR,
    DEFAULT_ENSEMBLE_PREDICTIONS,
    DEFAULT_FUSION_PREDICTIONS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_THRESHOLDS_PATH,
    DISEASE_LABELS,
    snake_label,
)
from src.medagentx.fusion.ensemble_calibrator import load_ensemble_calibrator
from src.medagentx.fusion.labels import derive_no_finding_status
from src.medagentx.fusion.paths import clean_dicom_path


DEFAULT_ENSEMBLE_THRESHOLDS = DEFAULT_OUTPUT_DIR / "ensemble_thresholds.json"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--densenet-csv", type=Path, default=DEFAULT_DENSENET_PREDICTIONS)
    parser.add_argument("--fusion-csv", type=Path, default=DEFAULT_FUSION_PREDICTIONS)
    parser.add_argument("--fusion-thresholds-path", type=Path, default=DEFAULT_THRESHOLDS_PATH)
    parser.add_argument("--ensemble-thresholds-path", type=Path, default=DEFAULT_ENSEMBLE_THRESHOLDS)
    parser.add_argument("--calibrator-path", type=Path, default=DEFAULT_ENSEMBLE_CALIBRATOR)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_ENSEMBLE_PREDICTIONS)
    parser.add_argument("--fusion-weight", type=float, default=0.5)
    parser.add_argument(
        "--require-agreement",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Only call present when DenseNet and fusion strongly agree.",
    )
    return parser.parse_args()


def safe_float(value):
    if value is None or value == "" or (isinstance(value, float) and np.isnan(value)):
        return None
    return float(value)


def load_fusion_thresholds(path: Path) -> dict[str, float]:
    if path.exists():
        loaded = load_threshold_json(path)
        if loaded:
            return loaded
    return {label: apply_threshold_floor(label, DEFAULT_PRESENT_THRESHOLD) for label in DISEASE_LABELS}


def load_ensemble_thresholds(
    path: Path,
    fusion_thresholds: dict[str, float],
    densenet_thresholds: dict[str, float],
) -> dict[str, float]:
    if path.exists():
        loaded = load_threshold_json(path)
        if loaded:
            return loaded

    return {
        label: apply_threshold_floor(
            label,
            max(fusion_thresholds[label], densenet_thresholds[label]),
        )
        for label in DISEASE_LABELS
    }


def densenet_status_from_row(row: pd.Series, label: str, threshold: float) -> tuple[float | None, str]:
    slug = snake_label(label)
    prob = safe_float(row.get(f"classifier_prob_{slug}"))
    status = clean_string(row.get(f"classifier_status_{slug}"))
    if prob is None:
        return None, "unavailable"
    if status in {"present", "absent", "uncertain"}:
        return prob, status
    return prob, prob_to_status(prob, present_threshold=threshold)


def fusion_status_from_row(row: pd.Series, label: str, threshold: float) -> tuple[float | None, str]:
    slug = snake_label(label)
    prob = safe_float(row.get(f"fusion_prob_{slug}"))
    status = clean_string(row.get(f"fusion_status_{slug}"))
    if prob is None:
        return None, "unavailable"
    if status in {"present", "absent", "uncertain"}:
        return prob, status
    return prob, prob_to_status(prob, present_threshold=threshold)


def clean_string(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value).strip()


def main():
    args = parse_args()
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    densenet_df = pd.read_csv(args.densenet_csv, dtype=str)
    fusion_df = pd.read_csv(args.fusion_csv, dtype=str)

    densenet_df["dicom_path"] = densenet_df["dicom_path"].map(clean_dicom_path)
    fusion_df["dicom_path"] = fusion_df["dicom_path"].map(clean_dicom_path)

    densenet_thresholds = default_densenet_thresholds()
    fusion_thresholds = load_fusion_thresholds(args.fusion_thresholds_path)
    ensemble_thresholds = load_ensemble_thresholds(
        args.ensemble_thresholds_path,
        fusion_thresholds,
        densenet_thresholds,
    )

    calibrator = None
    if args.calibrator_path.exists():
        calibrator = load_ensemble_calibrator(args.calibrator_path)
        print(f"Loaded ensemble calibrator from {args.calibrator_path}")

    if not args.ensemble_thresholds_path.exists():
        args.ensemble_thresholds_path.parent.mkdir(parents=True, exist_ok=True)
        args.ensemble_thresholds_path.write_text(
            json.dumps(
                thresholds_to_json_payload(
                    ensemble_thresholds,
                    model_version="ensemble_densenet_fusion_v4_tiered",
                ),
                indent=2,
            ),
            encoding="utf-8",
        )

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
            "ensemble_model_version": "densenet_fusion_v4_tiered",
            "ensemble_fusion_weight": args.fusion_weight,
            "ensemble_require_agreement": args.require_agreement,
            "present_threshold_default": DEFAULT_PRESENT_THRESHOLD,
            "absent_threshold_default": DEFAULT_ABSENT_THRESHOLD,
        }

        disease_statuses = {}

        for label in DISEASE_LABELS:
            slug = snake_label(label)
            d_threshold = densenet_thresholds[label]
            f_threshold = fusion_thresholds[label]
            e_threshold = ensemble_thresholds[label]

            d_prob, d_status = densenet_status_from_row(row, label, d_threshold)
            f_prob, f_status = fusion_status_from_row(row, label, f_threshold)

            if d_prob is not None and f_prob is not None:
                e_prob = ensemble_prob_blend(label, d_prob, f_prob, fusion_weight=args.fusion_weight)
            elif d_prob is not None:
                e_prob = d_prob
            elif f_prob is not None:
                e_prob = f_prob
            else:
                e_prob = None

            raw_prob = e_prob
            if calibrator is not None and e_prob is not None:
                e_prob = calibrator.predict(label, d_prob, f_prob, e_prob)

            e_status = ensemble_present_status(
                label=label,
                d_prob=d_prob,
                f_prob=f_prob,
                e_prob=e_prob,
                d_threshold=d_threshold,
                f_threshold=f_threshold,
                e_threshold=e_threshold,
                require_agreement=args.require_agreement,
            )
            disease_statuses[label] = e_status
            agreement = agreement_field(d_prob, f_prob, d_threshold, f_threshold)

            out[f"densenet_prob_{slug}"] = d_prob
            out[f"fusion_prob_{slug}"] = f_prob
            out[f"ensemble_prob_raw_{slug}"] = raw_prob
            out[f"ensemble_prob_{slug}"] = e_prob

            out[f"densenet_threshold_{slug}"] = d_threshold
            out[f"fusion_threshold_{slug}"] = f_threshold
            out[f"ensemble_threshold_{slug}"] = e_threshold

            out[f"densenet_status_{slug}"] = d_status
            out[f"fusion_status_{slug}"] = f_status
            out[f"ensemble_status_{slug}"] = e_status
            out[f"ensemble_agreement_{slug}"] = agreement

            # Drop-in fields for Disease Reasoning Agent.
            out[f"classifier_prob_{slug}"] = e_prob
            out[f"classifier_status_{slug}"] = e_status
            out[f"classifier_threshold_{slug}"] = e_threshold
            out[f"classifier_source_label_{slug}"] = "ensemble"

        out["classifier_status_support_devices"] = "unavailable"
        out["classifier_status_no_finding"] = derive_no_finding_status(disease_statuses)
        out["classifier_model"] = "ensemble_densenet_fusion"
        out["route_next"] = "retrieval_agent"

        rows.append(out)

    pd.DataFrame(rows).to_csv(args.output_csv, index=False)
    print(f"Wrote {len(rows)} rows to {args.output_csv}")
    print(f"Saved ensemble thresholds to {args.ensemble_thresholds_path}")


if __name__ == "__main__":
    main()
