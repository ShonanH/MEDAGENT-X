#!/usr/bin/env python3
"""
Build CheXpert labeler training labels for the fusion classifier.

Output:
  src/outputs/chexpert_plus/fusion_classifier/report_label_training_table.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from medagentx._bootstrap import ensure_src_on_path

ensure_src_on_path()

from medagentx.fusion.chexpert_labels import (
    ALL_CHEXPERT_LABELS,
    LABEL_SOURCE_CHEXPERT,
    aggregate_study_label_items,
    expand_label_columns,
    labels_from_chexpert_row,
    merge_chexpert_labels,
    study_label_conflict_flags,
)
from medagentx.fusion.constants import (
    AGENT_EVAL_PATIENT_COUNT,
    DEFAULT_AGENT_EVAL_MANIFEST,
    DEFAULT_CHEXPERT_LABELS_CSV,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REDIVIS_CSV,
    DEFAULT_REPORT_LABEL_TABLE,
    DEFAULT_SPLIT_METADATA,
    SPLIT_SEED,
    snake_label,
)
from medagentx.fusion.labels import build_report_text_for_weak_labels
from medagentx.fusion.paths import clean_dicom_path, parse_study_key_from_dcm
from medagentx.fusion.splits import build_cohort_split_table, save_patient_split_artifacts


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_REDIVIS_CSV)
    parser.add_argument("--labels-csv", type=Path, default=DEFAULT_CHEXPERT_LABELS_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_REPORT_LABEL_TABLE)
    return parser.parse_args()


def load_labeled_rows(input_csv: Path, labels_csv: Path) -> pd.DataFrame:
    rows_df = pd.read_csv(input_csv, dtype=str)
    rows_df["dicom_path"] = rows_df["path_to_dcm"].map(clean_dicom_path)
    rows_df["study_key"] = rows_df["path_to_dcm"].map(parse_study_key_from_dcm)

    if labels_csv.exists():
        labels_df = pd.read_csv(labels_csv, dtype=str)
        if any(str(col).startswith("weak_status_") for col in labels_df.columns):
            merged = labels_df.copy()
            if "study_key" not in merged.columns:
                merged["study_key"] = merged["path_to_dcm"].map(parse_study_key_from_dcm)
            if "dicom_path" not in merged.columns:
                merged["dicom_path"] = merged["path_to_dcm"].map(clean_dicom_path)
            return merged

        merged = merge_chexpert_labels(rows_df, labels_df)
        return expand_label_columns(merged)

    raise FileNotFoundError(
        f"CheXpert labels not found at {labels_csv}. "
        "Run: python src/medagentx/cli/02_fetch_redivis_chexpert_labels.py"
    )


def build_study_label_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for study_key, group in df.groupby("study_key", sort=False):
        first = group.iloc[0]
        report_text, _ = build_report_text_for_weak_labels(first)
        view_label_maps = [labels_from_chexpert_row(row) for _, row in group.iterrows()]
        label_items = aggregate_study_label_items(view_label_maps)
        conflicts = study_label_conflict_flags(group)

        row = {
            "study_key": study_key,
            "deid_patient_id": first["deid_patient_id"],
            "report_text": report_text,
            "label_source": LABEL_SOURCE_CHEXPERT,
            "image_count": len(group),
            "study_label_conflicts_json": str(conflicts),
        }

        for label in ALL_CHEXPERT_LABELS:
            slug = snake_label(label)
            item = label_items[label]
            row[f"chexpert_value_{slug}"] = item["chexpert_raw_value"]
            row[f"weak_status_{slug}"] = item["weak_status"]
            row[f"weak_value_{slug}"] = item["weak_value"]
            row[f"judge_status_{slug}"] = item["judge_status"]
            row[f"label_evidence_{slug}"] = item["evidence"]

        rows.append(row)

    return pd.DataFrame(rows)


def main():
    args = parse_args()
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    labeled_df = load_labeled_rows(args.input_csv, args.labels_csv)
    missing = labeled_df["study_key"].eq("").sum()
    if missing:
        raise ValueError(f"Failed to parse study_key for {missing} rows")

    study_table = build_study_label_table(labeled_df)
    study_lookup = study_table.set_index("study_key")

    image_rows = []
    for _, row in labeled_df.iterrows():
        study_key = row["study_key"]
        study_info = study_lookup.loc[study_key]

        out = {
            "study_key": study_key,
            "dicom_path": row["dicom_path"],
            "deid_patient_id": row["deid_patient_id"],
            "report_text": study_info["report_text"],
            "label_source": study_info["label_source"],
        }

        for label in ALL_CHEXPERT_LABELS:
            slug = snake_label(label)
            out[f"weak_status_{slug}"] = study_info[f"weak_status_{slug}"]
            out[f"weak_value_{slug}"] = study_info[f"weak_value_{slug}"]
            out[f"judge_status_{slug}"] = study_info[f"judge_status_{slug}"]

        image_rows.append(out)

    out_df = pd.DataFrame(image_rows)
    out_df.to_csv(args.output_csv, index=False)

    patient_count = out_df["deid_patient_id"].nunique()
    split_table = build_cohort_split_table(
        out_df,
        agent_eval_count=AGENT_EVAL_PATIENT_COUNT,
        seed=SPLIT_SEED,
    )
    split_metadata_path = DEFAULT_OUTPUT_DIR / DEFAULT_SPLIT_METADATA.name
    agent_eval_manifest_path = DEFAULT_OUTPUT_DIR / DEFAULT_AGENT_EVAL_MANIFEST.name
    save_patient_split_artifacts(
        split_table,
        split_metadata_path,
        agent_eval_manifest_path,
        cohort_patient_count=patient_count,
        seed=SPLIT_SEED,
    )

    print(f"Wrote {len(out_df)} rows to {args.output_csv}")
    print(f"Unique studies: {out_df['study_key'].nunique()}")
    print(f"Unique patients: {patient_count}")
    print(f"Label source: {LABEL_SOURCE_CHEXPERT}")
    print(f"Wrote patient splits to {split_metadata_path}")
    print(f"Wrote agent eval manifest to {agent_eval_manifest_path}")


if __name__ == "__main__":
    main()
