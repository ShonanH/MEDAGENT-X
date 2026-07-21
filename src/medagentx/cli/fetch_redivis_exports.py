#!/usr/bin/env python3
"""
Run named CheXpert Plus Redivis SQL exports to local CSV files.

Examples:
  python src/medagentx/cli/fetch_redivis_exports.py --list
  python src/medagentx/cli/fetch_redivis_exports.py metadata_train
  python src/medagentx/cli/fetch_redivis_exports.py chexpert_labels_file_index
  python src/medagentx/cli/fetch_redivis_exports.py metadata_probe
"""

from __future__ import annotations

import argparse
from pathlib import Path

from medagentx._bootstrap import ensure_src_on_path

ensure_src_on_path()

from medagentx.helpers.redivis_queries import get_export, list_exports
from medagentx.helpers.redivis_query_client import run_redivis_export


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch named Redivis exports to CSV.")
    parser.add_argument(
        "export_names",
        nargs="*",
        help=f"Export name(s). Available: {', '.join(list_exports())}",
    )
    parser.add_argument("--list", action="store_true", help="List available exports and exit.")
    parser.add_argument("--row-limit", type=int, default=None, help="Override max query rows.")
    parser.add_argument("--output-csv", type=Path, default=None, help="Override output CSV path.")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.list or not args.export_names:
        print("Available Redivis exports:\n")
        for name in list_exports():
            spec = get_export(name)
            print(f"  {name}")
            print(f"    {spec.description}")
            print(f"    default: {spec.default_output_csv}")
            print()
        if not args.export_names:
            return

    for export_name in args.export_names:
        spec = get_export(export_name)
        output_csv = args.output_csv or spec.default_output_csv
        row_limit = args.row_limit

        print(f"Running export '{export_name}'...")
        df = run_redivis_export(
            export_name,
            output_csv=output_csv,
            max_results=row_limit,
            row_limit=row_limit or spec.default_max_results,
        )
        print(f"Wrote {len(df)} rows to {output_csv}")


if __name__ == "__main__":
    main()
