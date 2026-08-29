"""Run the offline DICOM quality gate for a label-gated cohort."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from medagentx.quality.pipeline import run_quality_pipeline


def build_parser() -> argparse.ArgumentParser:
    """Build the quality gate command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Compute DICOM-only per-view quality metrics, drop failed views, "
            "and retain studies with at least one usable view."
        )
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path("v2/artifacts/cohort"),
        help="Root containing the label-gated cohort artifacts.",
    )
    parser.add_argument(
        "--eligible-csv",
        type=Path,
        default=None,
        help="Input view table. Defaults to cohort-root/eligible_dicom_rows.csv.",
    )
    parser.add_argument(
        "--dicom-root",
        type=Path,
        default=None,
        help="DICOM root. Defaults to cohort-root/dicom_train.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Quality artifact root. Defaults to cohort-root/quality.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the locked offline quality workflow."""
    args = build_parser().parse_args(argv)
    try:
        import pydicom  # noqa: F401
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The quality gate requires pydicom. Install project dependencies "
            "before running this command."
        ) from exc

    cohort_root: Path = args.cohort_root
    eligible_csv = args.eligible_csv or (
        cohort_root / "eligible_dicom_rows.csv"
    )
    dicom_root = args.dicom_root or (cohort_root / "dicom_train")
    output_root = args.output_root or (cohort_root / "quality")

    if not eligible_csv.exists():
        raise FileNotFoundError(f"Eligible cohort CSV not found: {eligible_csv}")
    if not dicom_root.exists():
        raise FileNotFoundError(f"DICOM root not found: {dicom_root}")

    print(f"[Quality] Loading label-gated views from {eligible_csv}")
    eligible_rows = pd.read_csv(eligible_csv, dtype=str)
    quality_eligible, paths = run_quality_pipeline(
        eligible_rows,
        dicom_root=dicom_root,
        output_root=output_root,
    )

    summary = pd.read_csv(paths["summary"]).iloc[0].to_dict()
    print(f"[Quality] Summary: {summary}")
    print(f"[Quality] Downstream cohort -> {paths['eligible_rows']}")
    print(f"[Quality] View decisions -> {paths['view_decisions']}")
    print(f"[Quality] Failed views -> {paths['failed_views']}")
    print(f"[Quality] Dropped studies -> {paths['dropped_studies']}")

    if quality_eligible.empty:
        print("[Quality] No usable views remain.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
