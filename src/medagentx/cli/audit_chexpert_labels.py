#!/usr/bin/env python3
"""Audit CheXpert label coverage and compare against legacy report-keyword labels."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from medagentx._bootstrap import ensure_src_on_path

ensure_src_on_path()

from medagentx.fusion.chexpert_labels import (
    ALL_CHEXPERT_LABELS,
    chexpert_value_to_status,
    summarize_label_coverage,
)
from medagentx.fusion.constants import DEFAULT_CHEXPERT_LABELS_CSV, snake_label
from medagentx.fusion.labels import build_report_text_for_weak_labels, infer_study_weak_labels
from medagentx.fusion.paths import parse_study_key_from_dcm


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels-csv", type=Path, default=DEFAULT_CHEXPERT_LABELS_CSV)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_CHEXPERT_LABELS_CSV.parent / "fusion_classifier" / "label_audit",
    )
    return parser.parse_args()


def compare_with_legacy_rules(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for study_key, group in df.groupby("study_key", sort=False):
        first = group.iloc[0]
        report_text, _ = build_report_text_for_weak_labels(first)
        legacy = infer_study_weak_labels(report_text)
        for label in ALL_CHEXPERT_LABELS:
            slug = snake_label(label)
            new_status = str(first.get(f"weak_status_{slug}", "")).lower()
            if label not in legacy:
                continue
            old_status = legacy[label]["weak_status"]
            rows.append(
                {
                    "study_key": study_key,
                    "label": label,
                    "chexpert_status": new_status,
                    "legacy_status": old_status,
                    "agree": new_status == old_status,
                }
            )
    return pd.DataFrame(rows)


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.labels_csv, dtype=str)
    if "study_key" not in df.columns and "path_to_dcm" in df.columns:
        df["study_key"] = df["path_to_dcm"].map(parse_study_key_from_dcm)

    coverage = summarize_label_coverage(df)
    coverage.to_csv(args.output_dir / "chexpert_label_coverage.csv", index=False)

    comparison = compare_with_legacy_rules(df)
    if not comparison.empty:
        summary = (
            comparison.groupby("label", as_index=False)["agree"]
            .mean()
            .rename(columns={"agree": "agreement_rate"})
        )
        comparison.to_csv(args.output_dir / "chexpert_vs_legacy_by_study.csv", index=False)
        summary.to_csv(args.output_dir / "chexpert_vs_legacy_summary.csv", index=False)

    print(f"Wrote audit artifacts to {args.output_dir}")
    print(coverage.to_string(index=False))


if __name__ == "__main__":
    main()
