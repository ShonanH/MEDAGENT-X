#!/usr/bin/env python3
"""
Compute and log batch calibration metrics (RMSE, PLCC, SRCC) plus workflow disease F1.

Run automatically at the end of scripts/run_bulk_medagentx_and_judge.py, or standalone:

    python scripts/15_log_batch_calibration_metrics.py \\
        --batch-dir outputs/chexpert_plus/batch_first_100 \\
        --limit 100
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.fusion.batch_metrics import (
    print_batch_calibration_summary,
    write_batch_calibration_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log batch calibration and disease F1 metrics.")
    parser.add_argument(
        "--batch-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "chexpert_plus" / "batch_first_100",
        help="Directory containing combined judge and disease reasoning CSV outputs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Batch size suffix used for output filenames (e.g. first_100).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = write_batch_calibration_report(args.batch_dir, limit=args.limit)
    paths = {
        "json": args.batch_dir / f"batch_calibration_metrics_first_{args.limit}.json",
        "md": args.batch_dir / f"batch_calibration_metrics_first_{args.limit}.md",
    }
    print_batch_calibration_summary(report)
    print(f"[Batch Metrics] JSON: {paths['json']}", flush=True)
    print(f"[Batch Metrics] Markdown: {paths['md']}", flush=True)


if __name__ == "__main__":
    main()
