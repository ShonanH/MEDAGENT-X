#!/usr/bin/env python3
"""
Build frozen patient-level cohort splits for fusion training and agent evaluation.

Writes:
  - patient_split_metadata.csv (all patients -> train/validation/test/agent_eval)
  - agent_eval_patient_manifest.csv (100 held-out patients for script 16)

Run after script 03 (or whenever the cohort patient list changes).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from medagentx._bootstrap import ensure_src_on_path

ensure_src_on_path()

from medagentx.fusion.constants import (
    AGENT_EVAL_PATIENT_COUNT,
    AGENT_EVAL_SPLIT,
    DEFAULT_AGENT_EVAL_MANIFEST,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REDIVIS_CSV,
    DEFAULT_REPORT_LABEL_TABLE,
    DEFAULT_SPLIT_METADATA,
    FUSION_TEST_SPLIT,
    FUSION_TRAIN_SPLIT,
    FUSION_VAL_SPLIT,
    SPLIT_SEED,
)
from medagentx.fusion.splits import (
    build_cohort_split_table,
    save_patient_split_artifacts,
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=DEFAULT_REPORT_LABEL_TABLE,
        help="Image- or study-level table with deid_patient_id (default: report_label_training_table.csv).",
    )
    parser.add_argument(
        "--fallback-input-csv",
        type=Path,
        default=DEFAULT_REDIVIS_CSV,
        help="Used when --input-csv is missing.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--agent-eval-count", type=int, default=AGENT_EVAL_PATIENT_COUNT)
    parser.add_argument("--seed", type=int, default=SPLIT_SEED)
    return parser.parse_args()


def load_cohort_table(input_csv: Path, fallback_csv: Path) -> pd.DataFrame:
    path = input_csv if input_csv.exists() else fallback_csv
    if not path.exists():
        raise FileNotFoundError(
            f"Cohort table not found at {input_csv} or {fallback_csv}. "
            "Run scripts 01 and 03 first."
        )

    df = pd.read_csv(path, dtype=str)
    if "deid_patient_id" not in df.columns:
        raise ValueError(f"{path} is missing deid_patient_id")
    return df


def main() -> None:
    args = parse_args()
    cohort_df = load_cohort_table(args.input_csv, args.fallback_input_csv)
    patient_count = cohort_df["deid_patient_id"].nunique()

    split_table = build_cohort_split_table(
        cohort_df,
        agent_eval_count=args.agent_eval_count,
        seed=args.seed,
    )

    split_metadata_path = args.output_dir / DEFAULT_SPLIT_METADATA.name
    agent_eval_manifest_path = args.output_dir / DEFAULT_AGENT_EVAL_MANIFEST.name
    save_patient_split_artifacts(
        split_table,
        split_metadata_path,
        agent_eval_manifest_path,
        cohort_patient_count=patient_count,
        seed=args.seed,
    )

    print(f"Wrote {len(split_table)} patients to {split_metadata_path}")
    print(f"Wrote agent eval manifest to {agent_eval_manifest_path}")
    print(f"Cohort patients: {patient_count}")
    print(f"agent_eval: {len(split_table[split_table['split'] == AGENT_EVAL_SPLIT])}")
    print(f"train: {len(split_table[split_table['split'] == FUSION_TRAIN_SPLIT])}")
    print(f"validation: {len(split_table[split_table['split'] == FUSION_VAL_SPLIT])}")
    print(f"test: {len(split_table[split_table['split'] == FUSION_TEST_SPLIT])}")


if __name__ == "__main__":
    main()
