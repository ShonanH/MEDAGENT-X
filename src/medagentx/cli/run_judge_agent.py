from __future__ import annotations
from pathlib import Path
import sys
import argparse

from medagentx._bootstrap import ensure_src_on_path
from medagentx.paths import CHEXPERT_OUTPUT_DIR, DATA_DIR, FUSION_OUTPUT_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR, SRC_ROOT, VECTOR_DB_DIR

ensure_src_on_path()

from medagentx.agents.judge_agent import run_judge_agent


if __name__ == "__main__":
    run_judge_agent(
        disease_reasoning_results_path=str(CHEXPERT_OUTPUT_DIR / "disease_reasoning_results.csv"),
        ground_truth_path=str(CHEXPERT_OUTPUT_DIR / "redivis_chexpert_plus_filtered_rows.csv"),
        output_path=str(CHEXPERT_OUTPUT_DIR / "judge_results.csv"),
        report_output_path=str(CHEXPERT_OUTPUT_DIR / "judge_report.md"),
        verbose=True,
    )