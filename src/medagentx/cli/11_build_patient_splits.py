#!/usr/bin/env python3
"""
Build frozen patient-level cohort splits from quality-gate-passing cases only.

Run after script 10 (quality gate) and before script 12 (fusion training).

Writes:
  - quality_gate_eligible_cohort.csv
  - patient_split_metadata.csv
  - agent_eval_patient_manifest.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from medagentx._bootstrap import ensure_src_on_path

ensure_src_on_path()

from medagentx.fusion.constants import (
    AGENT_EVAL_MIN_CASES,
    AGENT_EVAL_PATIENT_COUNT,
    AGENT_EVAL_SPLIT,
    DEFAULT_AGENT_EVAL_MANIFEST,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_QUALITY_GATE_CSV,
    DEFAULT_QUALITY_GATE_ELIGIBLE_COHORT,
    DEFAULT_SPLIT_METADATA,
    FUSION_TEST_SPLIT,
    FUSION_TRAIN_SPLIT,
    FUSION_VAL_SPLIT,
    SPLIT_SEED,
)
from medagentx.fusion.splits import (
    build_cohort_split_table_from_quality_gate,
    save_patient_split_artifacts,
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--quality-gate-csv",
        type=Path,
        default=DEFAULT_QUALITY_GATE_CSV,
        help="Quality gate decisions from script 10.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--eligible-cohort-csv",
        type=Path,
        default=DEFAULT_QUALITY_GATE_ELIGIBLE_COHORT,
    )
    parser.add_argument("--agent-eval-count", type=int, default=AGENT_EVAL_PATIENT_COUNT)
    parser.add_argument("--agent-eval-min-cases", type=int, default=AGENT_EVAL_MIN_CASES)
    parser.add_argument("--seed", type=int, default=SPLIT_SEED)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    quality_gate_df = pd.read_csv(args.quality_gate_csv, dtype=str)

    split_table, eligible_df, stats = build_cohort_split_table_from_quality_gate(
        quality_gate_df,
        agent_eval_patient_count=args.agent_eval_count,
        agent_eval_min_cases=args.agent_eval_min_cases,
        seed=args.seed,
    )

    args.eligible_cohort_csv.parent.mkdir(parents=True, exist_ok=True)
    eligible_df.to_csv(args.eligible_cohort_csv, index=False)

    split_metadata_path = args.output_dir / DEFAULT_SPLIT_METADATA.name
    agent_eval_manifest_path = args.output_dir / DEFAULT_AGENT_EVAL_MANIFEST.name
    save_patient_split_artifacts(
        split_table,
        split_metadata_path,
        agent_eval_manifest_path,
        cohort_patient_count=stats["eligible_patients"],
        seed=args.seed,
        stats=stats,
    )

    print(f"Wrote {stats['eligible_cases']} eligible cases to {args.eligible_cohort_csv}")
    print(f"Wrote patient split metadata to {split_metadata_path}")
    print(f"Wrote agent eval manifest to {agent_eval_manifest_path}")
    print(f"Eligible cases: {stats['eligible_cases']}")
    print(f"agent_eval: {stats['agent_eval_cases']} cases")
    print(f"train: {stats['train_cases']} cases")
    print(f"validation: {stats['validation_cases']} cases")
    print(f"test: {stats['test_cases']} cases")


if __name__ == "__main__":
    main()
