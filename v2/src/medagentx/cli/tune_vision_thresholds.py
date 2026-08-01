"""Tune constrained per-label vision thresholds from validation predictions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from medagentx.data.balanced_constants import DEFAULT_BALANCED_COHORT_ROOT
from medagentx.evaluation.threshold_tuning import (
    ThresholdTuningConstraints,
    threshold_policy_payload,
    threshold_tuning_report_frame,
    tune_thresholds_from_frames,
)
from medagentx.reasoning.constants import DEFAULT_FUSION_SUBDIR


def build_parser() -> argparse.ArgumentParser:
    """Build the threshold tuning command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Tune per-label vision thresholds on validation predictions with "
            "guardrails against overcalling disease."
        )
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path(DEFAULT_BALANCED_COHORT_ROOT),
    )
    parser.add_argument(
        "--vision-predictions-csv",
        type=Path,
        default=None,
        help=(
            "Vision prediction CSV. Defaults to "
            "cohort-root/reasoning/fusion_eval_v1/<split>/vision_study_predictions.csv"
        ),
    )
    parser.add_argument(
        "--study-labels-csv",
        type=Path,
        default=None,
        help="Defaults to cohort-root/study_label_table.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Defaults to "
            "cohort-root/reasoning/fusion_eval_v1/<split>/threshold_tuning"
        ),
    )
    parser.add_argument(
        "--split",
        default="val",
        help="Source split name for policy metadata and default input paths.",
    )
    parser.add_argument("--max-threshold-drop", type=float, default=0.10)
    parser.add_argument("--min-precision-drop", type=float, default=0.02)
    parser.add_argument(
        "--max-positive-rate-multiplier",
        type=float,
        default=1.25,
    )
    parser.add_argument(
        "--strict-sanity-f1-drop-allowed",
        type=float,
        default=0.0,
    )
    parser.add_argument("--min-label-f1-gain", type=float, default=0.01)
    parser.add_argument("--threshold-min", type=float, default=0.01)
    parser.add_argument("--threshold-max", type=float, default=0.99)
    parser.add_argument("--grid-steps", type=int, default=197)
    return parser


def _validate_constraints(constraints: ThresholdTuningConstraints) -> None:
    if constraints.max_threshold_drop < 0:
        raise ValueError("max-threshold-drop must be >= 0")
    if constraints.min_precision_drop < 0:
        raise ValueError("min-precision-drop must be >= 0")
    if constraints.max_positive_rate_multiplier < 1:
        raise ValueError("max-positive-rate-multiplier must be >= 1")
    if constraints.strict_sanity_f1_drop_allowed < 0:
        raise ValueError("strict-sanity-f1-drop-allowed must be >= 0")
    if constraints.min_label_f1_gain < 0:
        raise ValueError("min-label-f1-gain must be >= 0")
    if not 0 <= constraints.threshold_min < constraints.threshold_max <= 1:
        raise ValueError("threshold-min/max must satisfy 0 <= min < max <= 1")
    if constraints.grid_steps < 2:
        raise ValueError("grid-steps must be >= 2")


def main(argv: list[str] | None = None) -> int:
    """Run threshold tuning and write report + policy artifacts."""
    args = build_parser().parse_args(argv)
    cohort_root: Path = args.cohort_root
    fusion_eval_root = cohort_root / DEFAULT_FUSION_SUBDIR / args.split
    vision_predictions_csv = args.vision_predictions_csv or (
        fusion_eval_root / "vision_study_predictions.csv"
    )
    study_labels_csv = args.study_labels_csv or (
        cohort_root / "study_label_table.csv"
    )
    output_dir = args.output_dir or (fusion_eval_root / "threshold_tuning")

    constraints = ThresholdTuningConstraints(
        max_threshold_drop=args.max_threshold_drop,
        min_precision_drop=args.min_precision_drop,
        max_positive_rate_multiplier=args.max_positive_rate_multiplier,
        strict_sanity_f1_drop_allowed=args.strict_sanity_f1_drop_allowed,
        min_label_f1_gain=args.min_label_f1_gain,
        threshold_min=args.threshold_min,
        threshold_max=args.threshold_max,
        grid_steps=args.grid_steps,
    )
    _validate_constraints(constraints)

    for path in (vision_predictions_csv, study_labels_csv):
        if not path.exists():
            raise FileNotFoundError(f"Required threshold tuning input missing: {path}")

    print(f"[ThresholdTune] loading vision predictions from {vision_predictions_csv}")
    vision_predictions = pd.read_csv(vision_predictions_csv)
    if args.split and "split" in vision_predictions:
        split_values = sorted(str(value) for value in vision_predictions["split"].unique())
        print(f"[ThresholdTune] prediction split values: {split_values}")

    print(f"[ThresholdTune] loading study labels from {study_labels_csv}")
    study_labels = pd.read_csv(study_labels_csv, dtype=str)

    results = tune_thresholds_from_frames(
        vision_predictions=vision_predictions,
        study_labels=study_labels,
        constraints=constraints,
    )
    report = threshold_tuning_report_frame(results)
    policy = threshold_policy_payload(
        results=results,
        constraints=constraints,
        split=args.split,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    report_csv = output_dir / "threshold_tuning_report.csv"
    policy_json = output_dir / "threshold_policy_v2.json"
    report.to_csv(report_csv, index=False)
    policy_json.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n")

    accepted = [result for result in results if result.accepted]
    current_macro = report["current_judge_f1"].mean()
    selected_macro = report["selected_judge_f1"].mean()
    strict_current_macro = report["current_strict_f1"].mean()
    strict_selected_macro = report["selected_strict_f1"].mean()

    print(f"[ThresholdTune] wrote report -> {report_csv}")
    print(f"[ThresholdTune] wrote policy -> {policy_json}")
    print(
        f"[ThresholdTune] accepted_labels={len(accepted)}/{len(results)} "
        f"judge_macro_f1={current_macro:.4f}->{selected_macro:.4f} "
        f"strict_macro_f1={strict_current_macro:.4f}->{strict_selected_macro:.4f}"
    )
    for result in results:
        if result.accepted:
            print(
                "[ThresholdTune] accepted "
                f"{result.label}: {result.current_threshold:.4f} -> "
                f"{result.selected_threshold:.4f}"
            )
        else:
            print(
                "[ThresholdTune] kept "
                f"{result.label}: {result.current_threshold:.4f} "
                f"({result.reject_reason})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
