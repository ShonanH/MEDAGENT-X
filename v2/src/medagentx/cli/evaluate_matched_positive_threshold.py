"""Compare retrieval fusion with a matched-positive threshold baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from medagentx.evaluation.fusion_eval import (
    filter_gray_zone_ground_truth,
    named_judge_summary_payload,
    per_label_metrics_frame,
    run_named_judge_result,
    status_confusion_by_label_frame,
    study_labels_to_ground_truth_strata,
    study_outputs_by_key,
    uncertain_status_metrics_frame,
    vision_status_map,
)
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.statuses import LabelStatus
from medagentx.reasoning.constants import GRAY_ZONE_MARGIN
from medagentx.vision.inference_output import (
    VisionStudyOutput,
    load_vision_study_outputs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a label-wise probability-threshold baseline with exactly "
            "the same positive prediction counts as deterministic fusion."
        )
    )
    parser.add_argument("--vision-outputs-cache", type=Path, required=True)
    parser.add_argument("--fusion-predictions-csv", type=Path, required=True)
    parser.add_argument("--study-labels-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--gray-zone-margin",
        type=float,
        default=GRAY_ZONE_MARGIN,
    )
    return parser


def _fusion_status_map(frame: pd.DataFrame) -> dict[tuple[str, str], LabelStatus]:
    required = {"study_key", "label", "fused_status"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Fusion predictions are missing columns: {missing}")
    if frame.duplicated(["study_key", "label"]).any():
        raise ValueError("Fusion predictions contain duplicate study-label rows")
    return {
        (str(row.study_key), str(row.label)): LabelStatus(
            str(row.fused_status).strip().lower()
        )
        for row in frame.itertuples(index=False)
    }


def build_matched_positive_predictions(
    outputs: Sequence[VisionStudyOutput],
    fusion_predictions: Mapping[tuple[str, str], LabelStatus],
    *,
    gray_zone_margin: float,
) -> tuple[
    dict[tuple[str, str], LabelStatus],
    pd.DataFrame,
    pd.DataFrame,
]:
    """Rank probabilities per label to match fusion's positive count exactly."""
    if not outputs:
        raise ValueError("outputs must not be empty")
    predictions: dict[tuple[str, str], LabelStatus] = {}
    threshold_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []

    for label in DISEASE_LABELS:
        candidates = []
        for output in outputs:
            item = output.label_map()[label]
            key = (output.study_key, label)
            if key not in fusion_predictions:
                raise ValueError(f"Missing fusion prediction for {key!r}")
            candidates.append(
                {
                    "study_key": output.study_key,
                    "probability": float(item.probability),
                    "checkpoint_threshold": float(item.threshold),
                    "vision_status": item.status,
                    "fusion_status": fusion_predictions[key],
                }
            )

        target_positive_count = sum(
            row["fusion_status"] is LabelStatus.PRESENT for row in candidates
        )
        ranked = sorted(
            candidates,
            key=lambda row: (-row["probability"], row["study_key"]),
        )
        positive_keys = {
            row["study_key"] for row in ranked[:target_positive_count]
        }
        if target_positive_count == 0:
            effective_threshold = 1.0
            boundary_tie = False
        elif target_positive_count == len(ranked):
            effective_threshold = 0.0
            boundary_tie = False
        else:
            last_positive = ranked[target_positive_count - 1]["probability"]
            first_negative = ranked[target_positive_count]["probability"]
            effective_threshold = (last_positive + first_negative) / 2.0
            boundary_tie = last_positive == first_negative

        checkpoint_thresholds = {
            row["checkpoint_threshold"] for row in candidates
        }
        if len(checkpoint_thresholds) != 1:
            raise ValueError(f"Checkpoint threshold varies within label {label!r}")
        checkpoint_threshold = next(iter(checkpoint_thresholds))
        lower = checkpoint_threshold - gray_zone_margin
        upper = checkpoint_threshold + gray_zone_margin

        achieved_positive_count = 0
        for row in candidates:
            status = (
                LabelStatus.PRESENT
                if row["study_key"] in positive_keys
                else LabelStatus.ABSENT
            )
            predictions[(row["study_key"], label)] = status
            achieved_positive_count += status is LabelStatus.PRESENT
            prediction_rows.append(
                {
                    "study_key": row["study_key"],
                    "label": label,
                    "probability": row["probability"],
                    "checkpoint_threshold": checkpoint_threshold,
                    "matched_effective_threshold": effective_threshold,
                    "vision_status": row["vision_status"].value,
                    "fusion_status": row["fusion_status"].value,
                    "matched_threshold_status": status.value,
                }
            )
        if achieved_positive_count != target_positive_count:
            raise RuntimeError(f"Failed to match positive count for {label!r}")

        vision_positive_count = sum(
            row["vision_status"] is LabelStatus.PRESENT for row in candidates
        )
        threshold_rows.append(
            {
                "label": label,
                "study_count": len(candidates),
                "vision_positive_count": vision_positive_count,
                "fusion_positive_count": target_positive_count,
                "matched_positive_count": achieved_positive_count,
                "checkpoint_threshold": checkpoint_threshold,
                "matched_effective_threshold": effective_threshold,
                "threshold_shift": effective_threshold - checkpoint_threshold,
                "within_original_gray_zone": lower
                <= effective_threshold
                <= upper,
                "boundary_probability_tie": boundary_tie,
                "deterministic_tie_break": "study_key_ascending",
            }
        )

    return (
        predictions,
        pd.DataFrame(threshold_rows),
        pd.DataFrame(prediction_rows),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.gray_zone_margin < 0:
        raise ValueError("gray-zone-margin must be >= 0")
    for path in (
        args.vision_outputs_cache,
        args.fusion_predictions_csv,
        args.study_labels_csv,
    ):
        if not path.is_file():
            raise FileNotFoundError(f"Required baseline input is missing: {path}")

    outputs, cache_metadata = load_vision_study_outputs(
        args.vision_outputs_cache
    )
    fusion_frame = pd.read_csv(args.fusion_predictions_csv, dtype=str)
    fusion_predictions = _fusion_status_map(fusion_frame)
    vision_predictions = vision_status_map(outputs)
    (
        matched_predictions,
        threshold_frame,
        matched_prediction_frame,
    ) = build_matched_positive_predictions(
        outputs,
        fusion_predictions,
        gray_zone_margin=args.gray_zone_margin,
    )

    study_keys = [output.study_key for output in outputs]
    study_labels = pd.read_csv(args.study_labels_csv, dtype=str)
    ground_truth = study_labels_to_ground_truth_strata(
        study_labels,
        study_keys=study_keys,
    )
    policy_records = {
        "explicit": ground_truth.explicit,
        "no_finding_derived": ground_truth.no_finding_derived,
        "combined_training_policy": ground_truth.combined,
    }
    predictions_by_method = {
        "vision": vision_predictions,
        "fusion": fusion_predictions,
        "matched_threshold": matched_predictions,
    }
    outputs_by_key = study_outputs_by_key(outputs)
    judge_runs = []
    for policy_name, full_records in policy_records.items():
        gray_records = filter_gray_zone_ground_truth(
            full_records,
            outputs_by_key,
            margin=args.gray_zone_margin,
        )
        for scope, scope_records in (
            ("full", full_records),
            ("gray_zone", gray_records),
        ):
            for method, predictions in predictions_by_method.items():
                judge_runs.append(
                    run_named_judge_result(
                        name=f"{method}_{policy_name}_{scope}",
                        eval_scope=scope,
                        ground_truth_records=scope_records,
                        predicted_statuses=predictions,
                        ground_truth_policy=policy_name,
                    )
                )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    threshold_frame.to_csv(
        args.output_dir / "matched_thresholds_by_label.csv", index=False
    )
    matched_prediction_frame.to_csv(
        args.output_dir / "matched_threshold_predictions.csv", index=False
    )
    per_label_metrics_frame(judge_runs).to_csv(
        args.output_dir / "per_label_metrics.csv", index=False
    )
    uncertain_status_metrics_frame(judge_runs).to_csv(
        args.output_dir / "uncertain_status_metrics.csv", index=False
    )
    status_confusion_by_label_frame(judge_runs).to_csv(
        args.output_dir / "status_confusion_by_label.csv", index=False
    )
    summary = {
        "experiment": "matched_positive_threshold_baseline_v1",
        "vision_outputs_cache": str(args.vision_outputs_cache),
        "vision_cache_metadata": cache_metadata,
        "fusion_predictions_csv": str(args.fusion_predictions_csv),
        "study_labels_csv": str(args.study_labels_csv),
        "gray_zone_margin": args.gray_zone_margin,
        "study_count": len(outputs),
        "ground_truth_scoreable_cells": {
            "explicit": int(ground_truth.provenance["explicit_scoreable"].sum()),
            "no_finding_derived": int(
                ground_truth.provenance["no_finding_derived_scoreable"].sum()
            ),
            "combined_training_policy": int(
                ground_truth.provenance["combined_scoreable"].sum()
            ),
        },
        "runs": [named_judge_summary_payload(run) for run in judge_runs],
    }
    (args.output_dir / "judge_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )

    print(
        "[MatchedThreshold] wrote outputs -> "
        f"{args.output_dir}"
    )
    for run in summary["runs"]:
        if run.get("skipped") or run["eval_scope"] != "full":
            continue
        macro_f1 = run.get("macro_f1")
        macro_text = "n/a" if macro_f1 is None else f"{macro_f1:.4f}"
        print(
            f"[MatchedThreshold] {run['name']}: "
            f"macro_f1={macro_text} coverage={run['coverage']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
