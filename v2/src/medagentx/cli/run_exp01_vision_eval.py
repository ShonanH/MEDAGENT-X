"""Run Judge evaluation for Experiment 1: RAD-DINO vision only."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from medagentx.cli.experiment_eval_utils import (
    gray_zone_ground_truth_from_vision_frame,
    named_judge_summary_payload,
    require_existing_file,
    run_named_judge_result,
    study_labels_to_ground_truth,
    vision_status_map_from_frame,
    write_judge_artifacts,
    write_json,
)
from medagentx.reasoning.constants import GRAY_ZONE_MARGIN


DEFAULT_EXPERIMENT_DIR = Path("v2/experiments/exp01_vision_only")
DEFAULT_PREDICTION_CSV = DEFAULT_EXPERIMENT_DIR / "vision_study_predictions.csv"
DEFAULT_STUDY_LABELS_CSV = Path(
    "v2/artifactsLocal/val_last4_blocks_0818/val/study_label_table.csv"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate Experiment 1 vision-only predictions with Judge."
    )
    parser.add_argument(
        "--prediction-csv",
        type=Path,
        default=DEFAULT_PREDICTION_CSV,
        help="Vision prediction CSV from medagentx.cli.predict_raddino.",
    )
    parser.add_argument(
        "--study-labels-csv",
        type=Path,
        default=DEFAULT_STUDY_LABELS_CSV,
        help="Study-level ground-truth label table.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_EXPERIMENT_DIR,
        help="Directory where Judge artifacts will be written.",
    )
    parser.add_argument(
        "--gray-zone-margin",
        type=float,
        default=GRAY_ZONE_MARGIN,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.gray_zone_margin < 0:
        raise ValueError("--gray-zone-margin must be >= 0")
    require_existing_file(args.prediction_csv, name="prediction CSV")
    require_existing_file(args.study_labels_csv, name="study labels CSV")

    predictions = pd.read_csv(args.prediction_csv, dtype=str)
    study_labels = pd.read_csv(args.study_labels_csv, dtype=str)
    study_keys = predictions["study_key"].astype(str).tolist()

    ground_truth_records = study_labels_to_ground_truth(
        study_labels,
        study_keys=study_keys,
    )
    gray_zone_records = gray_zone_ground_truth_from_vision_frame(
        ground_truth_records,
        predictions,
        margin=args.gray_zone_margin,
    )
    predicted_statuses = vision_status_map_from_frame(predictions)

    judge_runs = [
        run_named_judge_result(
            name="vision_full",
            eval_scope="full",
            ground_truth_records=ground_truth_records,
            predicted_statuses=predicted_statuses,
        ),
        run_named_judge_result(
            name="vision_gray_zone",
            eval_scope="gray_zone",
            ground_truth_records=gray_zone_records,
            predicted_statuses=predicted_statuses,
        ),
    ]

    summary = {
        "experiment": "exp01_vision_only",
        "prediction_csv": str(args.prediction_csv),
        "study_labels_csv": str(args.study_labels_csv),
        "gray_zone_margin": args.gray_zone_margin,
        "study_count": len(study_keys),
        "ground_truth_rows": len(ground_truth_records),
        "gray_zone_rows": len(gray_zone_records),
        "runs": [named_judge_summary_payload(run) for run in judge_runs],
    }
    write_judge_artifacts(
        output_dir=args.output_dir,
        summary=summary,
        judge_runs=judge_runs,
    )
    write_json(
        args.output_dir / "run_config.json",
        {
            "experiment": "exp01_vision_only",
            "prediction_csv": str(args.prediction_csv),
            "study_labels_csv": str(args.study_labels_csv),
            "output_dir": str(args.output_dir),
            "gray_zone_margin": args.gray_zone_margin,
        },
    )
    print(f"[Exp01VisionEval] wrote Judge artifacts -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
