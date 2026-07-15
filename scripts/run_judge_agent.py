from __future__ import annotations
from pathlib import Path
import sys
import argparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.agents.judge_agent import run_judge_agent


if __name__ == "__main__":
    run_judge_agent(
        disease_reasoning_results_path="outputs/chexpert_plus/disease_reasoning_results.csv",
        ground_truth_path="outputs/chexpert_plus/retrieval_results.csv",
        output_path="outputs/chexpert_plus/judge_results.csv",
        report_output_path="outputs/chexpert_plus/judge_report.md",
        verbose=True,
    )