#!/usr/bin/env python3
"""
Fetch CheXpert Plus report/metadata rows from the Redivis REST API.

Writes or merges into:
  outputs/chexpert_plus/redivis_chexpert_plus_filtered_rows.csv

This file feeds script 09 (fusion labels) and bulk judge ground truth.
Fusion training still requires ConvNeXt/RAD-DINO features for each row
(scripts 01 -> 03 -> 05/06).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from medagentx._bootstrap import ensure_src_on_path

ensure_src_on_path()

from medagentx.fusion.constants import DEFAULT_REDIVIS_CSV
from medagentx.helpers.redivis_query_client import (
    build_train_split_query,
    limit_unique_patients,
    merge_redivis_row_tables,
    run_redivis_query,
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_REDIVIS_CSV)
    parser.add_argument(
        "--row-limit",
        type=int,
        default=25000,
        help="Max image-level rows to request from Redivis (train split).",
    )
    parser.add_argument(
        "--patient-limit",
        type=int,
        default=None,
        help="Keep at most this many unique deid_patient_id values from the fetch.",
    )
    parser.add_argument(
        "--merge-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Merge with existing output CSV instead of overwriting.",
    )
    parser.add_argument(
        "--overwrite-output",
        action="store_true",
        help="Replace output CSV with fetch results only (ignores --merge-existing).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    print(f"Fetching up to {args.row_limit} train-split rows from Redivis...")
    fetched = run_redivis_query(
        build_train_split_query(args.row_limit),
        max_results=args.row_limit,
    )
    print(f"Redivis returned {len(fetched)} rows")

    fetched = limit_unique_patients(fetched, args.patient_limit)
    if args.patient_limit:
        print(
            f"After patient_limit={args.patient_limit}: "
            f"{len(fetched)} rows, {fetched['deid_patient_id'].nunique()} patients"
        )

    if args.overwrite_output or not args.merge_existing or not args.output_csv.exists():
        out_df = fetched
    else:
        existing = pd.read_csv(args.output_csv, dtype=str)
        out_df = merge_redivis_row_tables(existing, fetched)
        print(f"Merged with existing CSV: {len(existing)} -> {len(out_df)} rows")

    out_df.to_csv(args.output_csv, index=False)

    patients = out_df["deid_patient_id"].nunique() if "deid_patient_id" in out_df.columns else 0
    print(f"Wrote {len(out_df)} rows ({patients} patients) to {args.output_csv}")
    print("Next: expand DICOM + features, then rebuild fusion labels:")
    print("  python src/medagentx/cli/01_build_chexpert_manifest.py --study-limit 1500 --row-limit 20000")
    print("  python src/medagentx/cli/03_download_manifest_dicoms.py --manifest-path <manifest.csv>")
    print("  python src/medagentx/cli/05_extract_convnext_features.py --manifest-path <manifest.csv>")
    print("  python src/medagentx/cli/06_extract_raddino_features.py --manifest-path <manifest.csv>")
    print("  python src/medagentx/cli/11_run_densenet_predictions.py")
    print("  python src/medagentx/cli/09_build_fusion_report_label_table.py")
    print("  python src/medagentx/cli/10_train_fusion_classifier.py")


if __name__ == "__main__":
    main()
