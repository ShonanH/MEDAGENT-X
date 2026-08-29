"""Rebuild label-gated cohort tables and study-level label bundles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.data.cohort import (
    apply_label_gated_cohort,
    load_findings_for_cohort,
    summarize_label_gated_cohort,
    write_label_gated_cohort_artifacts,
)
from medagentx.data.findings_index import summarize_findings_index
from medagentx.labels.study_table import build_study_label_table


def build_parser() -> argparse.ArgumentParser:
    """Build the study-label rebuild parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Apply label-gated cohort rules to an existing eligible table and "
            "write study-level CheXpert label bundles."
        )
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path("v2/artifacts/cohort"),
        help="Cohort artifact root containing eligible rows and findings JSON.",
    )
    parser.add_argument(
        "--eligible-csv",
        type=Path,
        default=None,
        help="Optional eligible rows CSV. Defaults to cohort-root prefilter file.",
    )
    parser.add_argument(
        "--findings-json",
        type=Path,
        default=None,
        help="Optional findings_fixed.json path.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional view-row ceiling applied after label gating (whole studies only).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Rebuild cohort tables and study labels from local artifacts."""
    args = build_parser().parse_args(argv)
    cohort_root: Path = args.cohort_root
    cohort_root.mkdir(parents=True, exist_ok=True)

    eligible_csv = args.eligible_csv or (
        cohort_root / "eligible_dicom_rows_prefilter.csv"
    )
    if not eligible_csv.exists():
        eligible_csv = cohort_root / "eligible_dicom_rows.csv"
    if not eligible_csv.exists():
        raise FileNotFoundError(
            "No eligible rows CSV found. Expected one of: "
            f"{cohort_root / 'eligible_dicom_rows_prefilter.csv'} or "
            f"{cohort_root / 'eligible_dicom_rows.csv'}"
        )

    findings_json = args.findings_json or (
        cohort_root / "chexpert_labels" / "findings_fixed.json"
    )
    if not findings_json.exists():
        raise FileNotFoundError(
            f"findings_fixed.json not found at {findings_json}"
        )

    print(f"[Labels] Loading eligible rows from {eligible_csv}")
    eligible_rows = pd.read_csv(eligible_csv, dtype=str)
    print(f"[Labels] Loading findings index from {findings_json}")
    findings_index = load_findings_for_cohort(findings_json, eligible_rows)
    print(f"[Labels] Findings index summary: {summarize_findings_index(findings_index)}")

    kept, dropped = apply_label_gated_cohort(
        eligible_rows,
        findings_index,
        max_rows=args.max_rows,
    )
    artifacts = write_label_gated_cohort_artifacts(
        cohort_root,
        eligible_rows=eligible_rows,
        kept_rows=kept,
        dropped_rows=dropped,
    )
    summary = summarize_label_gated_cohort(eligible_rows, kept, dropped)
    print(f"[Labels] Label-gated cohort summary: {summary}")
    print(f"[Labels] Wrote eligible rows -> {artifacts['eligible_csv']}")
    print(f"[Labels] Wrote dropped studies -> {artifacts['dropped_csv']}")

    if kept.empty:
        print("[Labels] No label-gated rows remain after filtering.")
        return 1

    study_labels = build_study_label_table(kept, findings_index)
    study_labels_csv = cohort_root / "study_label_table.csv"
    study_labels.to_csv(study_labels_csv, index=False)
    print(
        f"[Labels] Wrote {len(study_labels)} study label rows -> "
        f"{study_labels_csv}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
