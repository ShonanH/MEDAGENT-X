"""Build patient-level train/val/test splits for the quality cohort."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from medagentx.splits.build import build_and_write_splits
from medagentx.splits.constants import SPLIT_SEED


def build_parser() -> argparse.ArgumentParser:
    """Build the patient-split command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Assign deterministic patient-level train/val/test splits "
            "(70/15/15, seed 42) for the quality-passed cohort."
        )
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path("v2/artifacts/cohort"),
        help="Cohort root containing quality/ and splits/ stage folders.",
    )
    parser.add_argument(
        "--eligible-csv",
        type=Path,
        default=None,
        help=(
            "Quality-passed view CSV. Defaults to "
            "cohort-root/quality/eligible_dicom_rows.csv."
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Split artifact root. Defaults to cohort-root/splits.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=SPLIT_SEED,
        help="Deterministic split seed (locked default: 42).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Build and persist patient/study/view split tables."""
    args = build_parser().parse_args(argv)
    cohort_root: Path = args.cohort_root
    eligible_csv = args.eligible_csv or (
        cohort_root / "quality" / "eligible_dicom_rows.csv"
    )
    output_root = args.output_root or (cohort_root / "splits")

    if not eligible_csv.exists():
        raise FileNotFoundError(
            f"Quality-passed cohort CSV not found: {eligible_csv}. "
            "Run the quality gate first."
        )

    print(f"[Splits] Loading quality cohort from {eligible_csv}")
    eligible_rows = pd.read_csv(eligible_csv, dtype=str)
    paths = build_and_write_splits(
        eligible_rows,
        output_root,
        seed=args.seed,
    )
    summary = pd.read_csv(paths["summary"]).iloc[0].to_dict()
    print(f"[Splits] Summary: {summary}")
    print(f"[Splits] Patient table -> {paths['patient_splits']}")
    print(f"[Splits] Study table -> {paths['study_splits']}")
    print(f"[Splits] View table -> {paths['view_splits']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
