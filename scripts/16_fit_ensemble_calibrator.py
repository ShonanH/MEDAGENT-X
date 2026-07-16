#!/usr/bin/env python3
"""
Fit per-label ensemble calibrators on validation labels and classifier probabilities.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.fusion.constants import (
    DEFAULT_ENSEMBLE_CALIBRATOR,
    DEFAULT_ENSEMBLE_PREDICTIONS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_LABEL_TABLE,
)
from src.medagentx.fusion.ensemble_calibrator import (
    fit_ensemble_calibrator_from_tables,
    save_ensemble_calibrator,
)
from src.medagentx.fusion.labels import LABEL_MODE_JUDGE, LABEL_MODE_WEAK
from src.medagentx.fusion.paths import clean_dicom_path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-label-table", type=Path, default=DEFAULT_REPORT_LABEL_TABLE)
    parser.add_argument("--ensemble-csv", type=Path, default=DEFAULT_ENSEMBLE_PREDICTIONS)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_ENSEMBLE_CALIBRATOR)
    parser.add_argument("--label-mode", choices=[LABEL_MODE_WEAK, LABEL_MODE_JUDGE], default=LABEL_MODE_JUDGE)
    parser.add_argument("--split", choices=["all", "validation"], default="validation")
    parser.add_argument("--split-metadata", type=Path, default=DEFAULT_OUTPUT_DIR / "patient_split_metadata.csv")
    return parser.parse_args()


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

    calibrator = fit_ensemble_calibrator_from_tables(
        label_df=label_df,
        ensemble_df=ensemble_df,
        label_mode=args.label_mode,
    )
    save_ensemble_calibrator(calibrator, args.output_path)
    print(f"Wrote ensemble calibrator to {args.output_path}")


if __name__ == "__main__":
    main()
