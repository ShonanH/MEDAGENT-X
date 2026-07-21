#!/usr/bin/env python3
"""
Fetch official CheXpert labeler labels from Redivis for rows in the local metadata CSV.

Writes:
  src/outputs/chexpert_plus/chexpert_labels.csv

Join key: path_to_image
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from medagentx._bootstrap import ensure_src_on_path

ensure_src_on_path()

from medagentx.fusion.chexpert_labels import ALL_CHEXPERT_LABELS, expand_label_columns, merge_chexpert_labels
from medagentx.fusion.constants import DEFAULT_CHEXPERT_LABELS_CSV, DEFAULT_REDIVIS_CSV
from medagentx.helpers.redivis_query_client import fetch_chexpert_labels_for_paths


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_REDIVIS_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CHEXPERT_LABELS_CSV)
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument(
        "--expand-status-columns",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Add weak_status_*/weak_value_* columns to the output CSV.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    rows_df = pd.read_csv(args.input_csv, dtype=str)
    if "path_to_image" not in rows_df.columns:
        raise ValueError(f"{args.input_csv} must include path_to_image.")

    paths = rows_df["path_to_image"].dropna().astype(str).tolist()
    print(f"Fetching CheXpert labels for {len(paths)} image paths from Redivis...")
    labels_df = fetch_chexpert_labels_for_paths(paths, batch_size=args.batch_size)
    print(f"Redivis returned {len(labels_df)} label rows")

    merged = merge_chexpert_labels(rows_df, labels_df)
    matched = 0
    for label in ALL_CHEXPERT_LABELS:
        if label in merged.columns:
            matched = int(merged[label].notna().sum())
            break
    print(f"Matched {matched}/{len(rows_df)} local rows to CheXpert labels")

    if args.expand_status_columns:
        out_df = expand_label_columns(merged)
    else:
        out_df = merged

    out_df.to_csv(args.output_csv, index=False)
    print(f"Wrote {len(out_df)} rows to {args.output_csv}")
    print("Next:")
    print("  python src/medagentx/cli/09_build_fusion_report_label_table.py")
    print("  python src/medagentx/cli/audit_chexpert_labels.py")


if __name__ == "__main__":
    main()
