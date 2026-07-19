#!/usr/bin/env python3
"""
Build weak report-derived labels for fusion classifier training.

Output:
  outputs/chexpert_plus/fusion_classifier/report_label_training_table.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from medagentx._bootstrap import ensure_src_on_path

ensure_src_on_path()

from medagentx.fusion.constants import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REDIVIS_CSV,
    DEFAULT_REPORT_LABEL_TABLE,
    DISEASE_LABELS,
    snake_label,
)
from medagentx.fusion.labels import build_report_text_for_weak_labels, infer_study_weak_labels
from medagentx.fusion.paths import clean_dicom_path, parse_study_key_from_dcm


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_REDIVIS_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_REPORT_LABEL_TABLE)
    return parser.parse_args()


def build_study_report_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for study_key, group in df.groupby("study_key", sort=False):
        first = group.iloc[0]
        report_text, label_source = build_report_text_for_weak_labels(first)
        weak_labels = infer_study_weak_labels(report_text)

        row = {
            "study_key": study_key,
            "deid_patient_id": first["deid_patient_id"],
            "report_text": report_text,
            "label_source": label_source,
            "image_count": len(group),
        }

        for label in DISEASE_LABELS:
            slug = snake_label(label)
            item = weak_labels[label]
            row[f"weak_status_{slug}"] = item["weak_status"]
            row[f"weak_value_{slug}"] = item["weak_value"]
            row[f"judge_status_{slug}"] = item["judge_status"]
            row[f"label_evidence_{slug}"] = item["evidence"]

        rows.append(row)

    return pd.DataFrame(rows)


def main():
    args = parse_args()
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input_csv, dtype=str)
    df["dicom_path"] = df["path_to_dcm"].map(clean_dicom_path)
    df["study_key"] = df["path_to_dcm"].map(parse_study_key_from_dcm)

    missing = df["study_key"].eq("").sum()
    if missing:
        raise ValueError(f"Failed to parse study_key for {missing} rows")

    study_table = build_study_report_table(df)
    study_lookup = study_table.set_index("study_key")

    image_rows = []
    for _, row in df.iterrows():
        study_key = row["study_key"]
        study_info = study_lookup.loc[study_key]

        out = {
            "study_key": study_key,
            "dicom_path": row["dicom_path"],
            "deid_patient_id": row["deid_patient_id"],
            "report_text": study_info["report_text"],
            "label_source": study_info["label_source"],
        }

        for label in DISEASE_LABELS:
            slug = snake_label(label)
            out[f"weak_status_{slug}"] = study_info[f"weak_status_{slug}"]
            out[f"weak_value_{slug}"] = study_info[f"weak_value_{slug}"]
            out[f"judge_status_{slug}"] = study_info[f"judge_status_{slug}"]

        image_rows.append(out)

    out_df = pd.DataFrame(image_rows)
    out_df.to_csv(args.output_csv, index=False)

    print(f"Wrote {len(out_df)} rows to {args.output_csv}")
    print(f"Unique studies: {out_df['study_key'].nunique()}")
    print(f"Unique patients: {out_df['deid_patient_id'].nunique()}")


if __name__ == "__main__":
    main()
