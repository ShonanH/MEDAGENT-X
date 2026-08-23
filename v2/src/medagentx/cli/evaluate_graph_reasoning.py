"""Evaluate saved graph-reasoning outputs with the Judge module."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from medagentx.data.balanced_constants import DEFAULT_BALANCED_COHORT_ROOT
from medagentx.evaluation.fusion_eval import (
    fusion_change_analysis_frame,
    fusion_changed_cells_frame,
    named_judge_summary_payload,
    per_label_metrics_frame,
    run_named_judge_result,
    status_confusion_by_label_frame,
    study_labels_to_ground_truth,
    uncertain_status_metrics_frame,
)
from medagentx.evaluation.ground_truth import GroundTruthRecord
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label
from medagentx.labels.statuses import LabelStatus
from medagentx.reasoning.fuse import FusedLabelPrediction, FusionStudyResult


DEFAULT_GRAPH_REASONING_DIR = Path(DEFAULT_BALANCED_COHORT_ROOT) / "graph_reasoning"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _parse_status(value: Any) -> LabelStatus:
    if isinstance(value, LabelStatus):
        return value
    return LabelStatus(str(value).strip().lower())


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _vision_status_map(
    vision_frame: pd.DataFrame,
) -> dict[tuple[str, str], LabelStatus]:
    predictions: dict[tuple[str, str], LabelStatus] = {}
    for row in vision_frame.itertuples(index=False):
        study_key = str(getattr(row, "study_key"))
        for label in DISEASE_LABELS:
            status = getattr(row, f"status_{snake_label(label)}")
            predictions[(study_key, label)] = _parse_status(status)
    return predictions


def _fusion_status_map(
    fusion_frame: pd.DataFrame,
) -> dict[tuple[str, str], LabelStatus]:
    predictions: dict[tuple[str, str], LabelStatus] = {}
    for row in fusion_frame.itertuples(index=False):
        predictions[(str(row.study_key), str(row.label))] = _parse_status(
            row.fused_status
        )
    return predictions


def _fusion_results_from_frame(
    fusion_frame: pd.DataFrame,
) -> list[FusionStudyResult]:
    results: list[FusionStudyResult] = []
    for study_key, rows in fusion_frame.groupby("study_key", sort=False):
        labels: list[FusedLabelPrediction] = []
        policy_version = str(rows.iloc[0]["fusion_policy_version"])
        for row in rows.itertuples(index=False):
            labels.append(
                FusedLabelPrediction(
                    label=str(row.label),
                    vision_status=_parse_status(row.vision_status),
                    fused_status=_parse_status(row.fused_status),
                    probability=float(row.probability),
                    threshold=float(row.threshold),
                    in_gray_zone=_parse_bool(row.in_gray_zone),
                    positive_count=int(row.positive_count),
                    negative_count=int(row.negative_count),
                    refinement_reason=str(row.refinement_reason),
                )
            )
        results.append(
            FusionStudyResult(
                study_key=str(study_key),
                fusion_policy_version=policy_version,
                labels=tuple(labels),
            )
        )
    return results


def _gray_zone_ground_truth(
    ground_truth_records: list[GroundTruthRecord],
    fusion_frame: pd.DataFrame,
) -> list[GroundTruthRecord]:
    gray_zone_keys = {
        (str(row.study_key), str(row.label))
        for row in fusion_frame.itertuples(index=False)
        if _parse_bool(row.in_gray_zone)
    }
    return [
        record
        for record in ground_truth_records
        if (record.study_key, record.label) in gray_zone_keys
    ]


def _require_columns(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    frame_name: str,
) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(
            f"{frame_name} missing required columns {missing}. "
            f"Available: {list(frame.columns)}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate saved graph reasoning outputs with Judge metrics."
    )
    parser.add_argument(
        "--graph-reasoning-dir",
        type=Path,
        default=DEFAULT_GRAPH_REASONING_DIR,
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path(DEFAULT_BALANCED_COHORT_ROOT),
    )
    parser.add_argument("--study-labels-csv", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Defaults to graph_reasoning_dir/judge_evaluation.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    graph_reasoning_dir = args.graph_reasoning_dir
    if not graph_reasoning_dir.exists():
        raise FileNotFoundError(
            f"Graph reasoning directory does not exist: {graph_reasoning_dir}"
        )

    output_dir = args.output_dir or (graph_reasoning_dir / "judge_evaluation")
    study_labels_csv = args.study_labels_csv or (
        args.cohort_root / "study_label_table.csv"
    )
    vision_csv = graph_reasoning_dir / "vision_study_predictions.csv"
    fusion_csv = graph_reasoning_dir / "fusion_label_predictions.csv"
    run_config_path = graph_reasoning_dir / "run_config.json"

    for path in (study_labels_csv, vision_csv, fusion_csv):
        if not path.exists():
            raise FileNotFoundError(f"Required evaluation input missing: {path}")

    run_config = _read_json(run_config_path)
    vision_frame = pd.read_csv(vision_csv, dtype=str)
    fusion_frame = pd.read_csv(fusion_csv, dtype=str)
    study_labels = pd.read_csv(study_labels_csv, dtype=str)

    _require_columns(vision_frame, ("study_key",), "vision_study_predictions")
    _require_columns(
        fusion_frame,
        (
            "study_key",
            "fusion_policy_version",
            "label",
            "probability",
            "threshold",
            "vision_status",
            "fused_status",
            "in_gray_zone",
            "positive_count",
            "negative_count",
            "refinement_reason",
        ),
        "fusion_label_predictions",
    )

    study_keys = sorted(set(fusion_frame["study_key"].astype(str)))
    ground_truth_records = study_labels_to_ground_truth(
        study_labels,
        study_keys=study_keys,
    )
    gray_zone_records = _gray_zone_ground_truth(
        ground_truth_records,
        fusion_frame,
    )
    vision_predictions = _vision_status_map(vision_frame)
    fusion_predictions = _fusion_status_map(fusion_frame)
    fusion_results = _fusion_results_from_frame(fusion_frame)

    judge_runs = [
        run_named_judge_result(
            name="vision_full",
            eval_scope="full",
            ground_truth_records=ground_truth_records,
            predicted_statuses=vision_predictions,
        ),
        run_named_judge_result(
            name="fusion_full",
            eval_scope="full",
            ground_truth_records=ground_truth_records,
            predicted_statuses=fusion_predictions,
        ),
        run_named_judge_result(
            name="vision_gray_zone",
            eval_scope="gray_zone",
            ground_truth_records=gray_zone_records,
            predicted_statuses=vision_predictions,
        ),
        run_named_judge_result(
            name="fusion_gray_zone",
            eval_scope="gray_zone",
            ground_truth_records=gray_zone_records,
            predicted_statuses=fusion_predictions,
        ),
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    judge_payload: dict[str, Any] = {
        "graph_reasoning_dir": str(graph_reasoning_dir),
        "run_config": run_config,
        "study_labels_csv": str(study_labels_csv),
        "study_count": len(study_keys),
        "ground_truth_rows": len(ground_truth_records),
        "gray_zone_rows": len(gray_zone_records),
        "retrieval_top_k": run_config.get("retrieval_top_k"),
        "gray_zone_margin": run_config.get("gray_zone_margin"),
        "runs": [named_judge_summary_payload(run) for run in judge_runs],
    }
    _write_json(output_dir / "judge_summary.json", judge_payload)
    per_label_metrics_frame(judge_runs).to_csv(
        output_dir / "per_label_metrics.csv",
        index=False,
    )
    fusion_change_analysis_frame(
        ground_truth_records=ground_truth_records,
        fusion_results=fusion_results,
    ).to_csv(output_dir / "fusion_change_analysis.csv", index=False)
    fusion_changed_cells_frame(
        ground_truth_records=ground_truth_records,
        fusion_results=fusion_results,
        retrieved_top_k=run_config.get("retrieval_top_k"),
    ).to_csv(output_dir / "fusion_changed_cells.csv", index=False)
    uncertain_status_metrics_frame(judge_runs).to_csv(
        output_dir / "uncertain_status_metrics.csv",
        index=False,
    )
    status_confusion_by_label_frame(judge_runs).to_csv(
        output_dir / "status_confusion_by_label.csv",
        index=False,
    )
    print(f"[GraphReasoningEval] wrote Judge metrics -> {output_dir}")


if __name__ == "__main__":
    main()
