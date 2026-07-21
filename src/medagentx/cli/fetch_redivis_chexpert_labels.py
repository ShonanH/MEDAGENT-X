#!/usr/bin/env python3
"""
Build per-image CheXpert labels for local metadata rows from findings_fixed.json.

Labels live in the Redivis CheXpert Labels asset (JSONL), not in the metadata SQL table.
Use --download-findings to fetch the ~84MB file from Redivis on first run.

Writes:
  src/outputs/chexpert_plus/chexpert_labels.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from medagentx._bootstrap import ensure_src_on_path

ensure_src_on_path()

from medagentx.fusion.chexpert_labels import (
    expand_label_columns,
    merge_chexpert_labels,
    normalize_path_to_image,
)
from medagentx.fusion.constants import (
    DEFAULT_CHEXPERT_FINDINGS_JSON,
    DEFAULT_CHEXPERT_LABELS_CSV,
    DEFAULT_REDIVIS_CSV,
)
from medagentx.helpers.chexpert_findings_json import (
    ensure_findings_fixed_json,
    load_findings_labels_for_paths,
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_REDIVIS_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_CHEXPERT_LABELS_CSV)
    parser.add_argument(
        "--findings-json",
        type=Path,
        default=DEFAULT_CHEXPERT_FINDINGS_JSON,
        help="Local path to findings_fixed.json (JSONL).",
    )
    parser.add_argument(
        "--download-findings",
        action="store_true",
        help="Download findings_fixed.json from Redivis if missing.",
    )
    parser.add_argument(
        "--overwrite-findings",
        action="store_true",
        help="Re-download findings_fixed.json even if cached locally.",
    )
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
    wanted_keys = {normalize_path_to_image(path) for path in paths if normalize_path_to_image(path)}

    findings_json = ensure_findings_fixed_json(
        args.findings_json,
        download=args.download_findings or args.overwrite_findings or not args.findings_json.exists(),
        overwrite=args.overwrite_findings,
    )
    print(f"Loading CheXpert labels from {findings_json} for {len(wanted_keys)} image paths...")
    labels_df = load_findings_labels_for_paths(findings_json, paths)
    print(f"Matched {len(labels_df)}/{len(wanted_keys)} local image paths in findings_fixed.json")

    merged = merge_chexpert_labels(rows_df, labels_df)
    out_df = expand_label_columns(merged) if args.expand_status_columns else merged

    out_df.to_csv(args.output_csv, index=False)
    print(f"Wrote {len(out_df)} rows to {args.output_csv}")
    print("Next:")
    print("  python src/medagentx/cli/audit_chexpert_labels.py")
    print("  python src/medagentx/cli/09_build_fusion_report_label_table.py")


if __name__ == "__main__":
    main()
