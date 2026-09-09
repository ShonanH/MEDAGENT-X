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
    ranking_cells_frame,
    ranking_metrics_frame,
    ranking_summary_payload,
    run_named_judge_result,
    status_confusion_by_label_frame,
    study_labels_to_ground_truth,
    uncertain_status_metrics_frame,
)
from medagentx.evaluation.ground_truth import GroundTruthRecord
from medagentx.evaluation.matching import MatchOutcome, compare_statuses
from medagentx.labels.constants import (
    CHEXPERT_COMPETITION_LABELS,
    DISEASE_LABELS,
)
from medagentx.labels.schema import snake_label
from medagentx.labels.statuses import LabelStatus
from medagentx.reasoning.fuse import FusedLabelPrediction, FusionStudyResult


DEFAULT_GRAPH_REASONING_DIR = Path(DEFAULT_BALANCED_COHORT_ROOT) / "graph_reasoning"
REQUIRED_RUN_FILES = (
    "vision_study_predictions.csv",
    "fusion_label_predictions.csv",
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _is_graph_reasoning_run_dir(path: Path) -> bool:
    return path.is_dir() and all((path / name).exists() for name in REQUIRED_RUN_FILES)


def _resolve_graph_reasoning_run_dir(path: Path) -> Path:
    if _is_graph_reasoning_run_dir(path):
        return path
    if not path.exists():
        raise FileNotFoundError(f"Graph reasoning path does not exist: {path}")
    candidates = sorted(
        (child for child in path.iterdir() if _is_graph_reasoning_run_dir(child)),
        key=lambda child: child.name,
    )
    if not candidates:
        raise FileNotFoundError(
            "No graph reasoning run folders found under "
            f"{path}. Expected files: {', '.join(REQUIRED_RUN_FILES)}"
        )
    return candidates[-1]


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


def _vision_score_map(
    vision_frame: pd.DataFrame,
) -> dict[tuple[str, str], float]:
    """Flatten continuous vision probabilities into ranking keys."""
    predictions: dict[tuple[str, str], float] = {}
    for row in vision_frame.itertuples(index=False):
        study_key = str(getattr(row, "study_key"))
        for label in DISEASE_LABELS:
            slug = snake_label(label)
            column = f"probability_{slug}"
            if not hasattr(row, column):
                raise ValueError(
                    f"vision_study_predictions missing required column {column!r}"
                )
            predictions[(study_key, label)] = float(getattr(row, column))
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


LLM_POLICY_AUDIT_COLUMNS = (
    "study_key",
    "label",
    "gt_status",
    "vision_status",
    "deterministic_status",
    "fused_status",
    "llm_action",
    "llm_confidence",
    "llm_evidence_assessment",
    "llm_applied",
    "llm_policy_reason",
    "deterministic_outcome",
    "final_outcome",
    "helped",
    "impact",
)


LLM_POLICY_SUMMARY_COLUMNS = (
    "label",
    "llm_action",
    "llm_confidence",
    "llm_evidence_assessment",
    "llm_applied",
    "llm_policy_reason",
    "reviewed_cells",
    "helped",
    "hurt",
    "no_change",
    "unscored",
    "net_helped",
)


def _ground_truth_status_map(
    ground_truth_records: list[GroundTruthRecord],
) -> dict[tuple[str, str], LabelStatus]:
    return {
        (record.study_key, record.label): record.ground_truth_status
        for record in ground_truth_records
    }


def _optional_row_value(row: Any, column: str, default: str = "") -> str:
    value = getattr(row, column, default)
    if value is None:
        return default
    text = str(value)
    if text == "nan":
        return default
    return text


def _outcome_score(outcome: MatchOutcome) -> int | None:
    if outcome in (MatchOutcome.TP, MatchOutcome.TN):
        return 1
    if outcome in (MatchOutcome.FP, MatchOutcome.FN, MatchOutcome.MISS_UNCERTAIN):
        return -1
    return None


def _llm_policy_impact(
    deterministic_outcome: MatchOutcome,
    final_outcome: MatchOutcome,
) -> tuple[bool | None, str]:
    before = _outcome_score(deterministic_outcome)
    after = _outcome_score(final_outcome)
    if before is None or after is None:
        return None, "unscored"
    if after > before:
        return True, "helped"
    if after < before:
        return False, "hurt"
    return False, "no_change"


def _llm_policy_audit_frame(
    *,
    fusion_frame: pd.DataFrame,
    ground_truth_records: list[GroundTruthRecord],
) -> pd.DataFrame:
    """Build one row per LLM-reviewed label with deterministic-vs-final impact."""

    if "llm_action" not in fusion_frame.columns:
        return pd.DataFrame(columns=LLM_POLICY_AUDIT_COLUMNS)

    gt_by_key = _ground_truth_status_map(ground_truth_records)
    rows: list[dict[str, Any]] = []
    for row in fusion_frame.itertuples(index=False):
        llm_action = _optional_row_value(row, "llm_action")
        if not llm_action:
            continue

        study_key = str(row.study_key)
        label = str(row.label)
        gt_status = gt_by_key.get((study_key, label))
        if gt_status is None:
            continue

        vision_status = _parse_status(row.vision_status)
        deterministic_status = _parse_status(
            _optional_row_value(row, "deterministic_status", str(row.fused_status))
        )
        final_status = _parse_status(row.fused_status)
        deterministic_match = compare_statuses(
            study_key=study_key,
            label=label,
            ground_truth_status=gt_status,
            predicted_status=deterministic_status,
        )
        final_match = compare_statuses(
            study_key=study_key,
            label=label,
            ground_truth_status=gt_status,
            predicted_status=final_status,
        )
        helped, impact = _llm_policy_impact(
            deterministic_match.outcome,
            final_match.outcome,
        )

        rows.append(
            {
                "study_key": study_key,
                "label": label,
                "gt_status": gt_status.value,
                "vision_status": vision_status.value,
                "deterministic_status": deterministic_status.value,
                "fused_status": final_status.value,
                "llm_action": llm_action,
                "llm_confidence": _optional_row_value(row, "llm_confidence"),
                "llm_evidence_assessment": _optional_row_value(
                    row,
                    "llm_evidence_assessment",
                ),
                "llm_applied": _optional_row_value(row, "llm_applied"),
                "llm_policy_reason": _optional_row_value(row, "llm_policy_reason"),
                "deterministic_outcome": deterministic_match.outcome.value,
                "final_outcome": final_match.outcome.value,
                "helped": helped,
                "impact": impact,
            }
        )

    return pd.DataFrame(rows, columns=LLM_POLICY_AUDIT_COLUMNS)


def _llm_policy_summary_frame(audit_frame: pd.DataFrame) -> pd.DataFrame:
    """Summarize LLM policy impact by action, confidence, and policy reason."""

    if audit_frame.empty:
        return pd.DataFrame(columns=LLM_POLICY_SUMMARY_COLUMNS)

    group_columns = [
        "label",
        "llm_action",
        "llm_confidence",
        "llm_evidence_assessment",
        "llm_applied",
        "llm_policy_reason",
    ]
    rows: list[dict[str, Any]] = []
    for values, group in audit_frame.groupby(group_columns, dropna=False):
        impact_counts = group["impact"].value_counts()
        helped = int(impact_counts.get("helped", 0))
        hurt = int(impact_counts.get("hurt", 0))
        no_change = int(impact_counts.get("no_change", 0))
        unscored = int(impact_counts.get("unscored", 0))
        rows.append(
            {
                **dict(zip(group_columns, values)),
                "reviewed_cells": int(len(group)),
                "helped": helped,
                "hurt": hurt,
                "no_change": no_change,
                "unscored": unscored,
                "net_helped": helped - hurt,
            }
        )

    return pd.DataFrame(rows, columns=LLM_POLICY_SUMMARY_COLUMNS).sort_values(
        by=["net_helped", "reviewed_cells"],
        ascending=[False, False],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate saved graph reasoning outputs with Judge metrics."
    )
    parser.add_argument(
        "--graph-reasoning-dir",
        type=Path,
        default=DEFAULT_GRAPH_REASONING_DIR,
        help=(
            "Graph reasoning run folder, or parent directory containing timestamped "
            "run folders. Defaults to the latest run under cohort-root/graph_reasoning."
        ),
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path(DEFAULT_BALANCED_COHORT_ROOT),
    )
    parser.add_argument("--study-labels-csv", type=Path, default=None)
    parser.add_argument(
        "--require-all-ranking-labels",
        action="store_true",
        help=(
            "Fail if any competition label lacks both positive and negative "
            "binary ground truth. Use this for official competition evaluation."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Defaults to graph_reasoning_dir/judge_evaluation.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    graph_reasoning_dir = _resolve_graph_reasoning_run_dir(args.graph_reasoning_dir)

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
    vision_scores = _vision_score_map(vision_frame)
    fusion_predictions = _fusion_status_map(fusion_frame)
    fusion_results = _fusion_results_from_frame(fusion_frame)

    judge_runs = [
        run_named_judge_result(
            name="vision_full",
            eval_scope="full",
            ground_truth_records=ground_truth_records,
            predicted_statuses=vision_predictions,
            predicted_scores=vision_scores,
            ranking_labels=CHEXPERT_COMPETITION_LABELS,
            require_two_classes_per_ranking_label=args.require_all_ranking_labels,
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
    ranking_payload = ranking_summary_payload(judge_runs)
    ranking_payload.update(
        {
            "labels": list(CHEXPERT_COMPETITION_LABELS),
            "ground_truth_policy": (
                "present=1; absent=0; uncertain/unmentioned excluded"
            ),
            "vision_score_source": "vision_study_predictions probability columns",
            "fusion_score_status": (
                "not_available: fusion_label_predictions has no fused_score"
            ),
            "macro_policy": (
                "mean over labels with both positive and negative ground truth; "
                "inspect scored_label_count and complete"
            ),
        }
    )
    _write_json(output_dir / "ranking_summary.json", ranking_payload)
    ranking_metrics_frame(judge_runs).to_csv(
        output_dir / "ranking_metrics.csv",
        index=False,
    )
    ranking_cells_frame(judge_runs).to_csv(
        output_dir / "ranking_cells.csv",
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
    llm_policy_audit = _llm_policy_audit_frame(
        fusion_frame=fusion_frame,
        ground_truth_records=ground_truth_records,
    )
    llm_policy_audit.to_csv(output_dir / "llm_policy_audit.csv", index=False)
    _llm_policy_summary_frame(llm_policy_audit).to_csv(
        output_dir / "llm_policy_summary.csv",
        index=False,
    )
    print(f"[GraphReasoningEval] wrote Judge metrics -> {output_dir}")


if __name__ == "__main__":
    main()
