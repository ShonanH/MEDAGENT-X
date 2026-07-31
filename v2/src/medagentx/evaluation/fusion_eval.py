"""Offline helpers for vision-only vs fusion Judge comparisons."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd

from medagentx.evaluation.ground_truth import GroundTruthRecord, build_ground_truth_records
from medagentx.evaluation.judge import JudgeResult, run_judge
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label
from medagentx.labels.statuses import LabelStatus
from medagentx.reasoning.constants import GRAY_ZONE_MARGIN
from medagentx.reasoning.fuse import FusionStudyResult, is_gray_zone
from medagentx.vision.inference_output import VisionStudyOutput


def _parse_label_status(value: Any) -> LabelStatus:
    if isinstance(value, LabelStatus):
        return value
    return LabelStatus(str(value).strip().lower())


def study_labels_to_ground_truth(
    study_labels: pd.DataFrame,
    *,
    study_keys: Sequence[str] | None = None,
) -> list[GroundTruthRecord]:
    """Build frozen GT rows for the 12 disease labels from study_label_table."""
    if study_labels.empty:
        raise ValueError("study_labels must not be empty")

    selected = study_labels
    if study_keys is not None:
        key_set = {str(key) for key in study_keys}
        selected = study_labels[
            study_labels["study_key"].astype(str).isin(key_set)
        ].copy()
        if selected.empty:
            raise ValueError("No study_label_table rows matched the requested studies")

    records: list[GroundTruthRecord] = []
    for _, row in selected.iterrows():
        statuses = {
            label: _parse_label_status(row[f"status_{snake_label(label)}"])
            for label in DISEASE_LABELS
        }
        records.extend(
            build_ground_truth_records(
                study_key=str(row["study_key"]),
                statuses=statuses,
                include_non_disease=False,
            )
        )
    return records


def vision_status_map(
    study_outputs: Sequence[VisionStudyOutput],
) -> dict[tuple[str, str], LabelStatus]:
    """Flatten vision study outputs into Judge prediction keys."""
    predictions: dict[tuple[str, str], LabelStatus] = {}
    for output in study_outputs:
        for label_output in output.labels:
            predictions[(output.study_key, label_output.label)] = label_output.status
    return predictions


def fusion_status_map(
    fusion_results: Sequence[FusionStudyResult],
) -> dict[tuple[str, str], LabelStatus]:
    """Flatten fusion study results into Judge prediction keys."""
    predictions: dict[tuple[str, str], LabelStatus] = {}
    for result in fusion_results:
        for label_result in result.labels:
            predictions[(result.study_key, label_result.label)] = (
                label_result.fused_status
            )
    return predictions


def study_outputs_by_key(
    study_outputs: Sequence[VisionStudyOutput],
) -> dict[str, VisionStudyOutput]:
    return {output.study_key: output for output in study_outputs}


def filter_gray_zone_ground_truth(
    ground_truth_records: Sequence[GroundTruthRecord],
    study_outputs: Mapping[str, VisionStudyOutput],
    *,
    margin: float = GRAY_ZONE_MARGIN,
) -> list[GroundTruthRecord]:
    """Keep only study-label GT rows inside the vision gray zone."""
    filtered: list[GroundTruthRecord] = []
    for record in ground_truth_records:
        output = study_outputs.get(record.study_key)
        if output is None:
            continue
        label_output = output.label_map().get(record.label)
        if label_output is None:
            continue
        if is_gray_zone(
            label_output.probability,
            label_output.threshold,
            margin=margin,
        ):
            filtered.append(record)
    return filtered


def judge_summary_payload(name: str, result: JudgeResult) -> dict[str, Any]:
    """Serialize one Judge run for JSON reporting."""
    aggregate = result.aggregate_metrics
    return {
        "name": name,
        "judge_metric_version": result.judge_metric_version,
        "macro_precision": aggregate.macro_precision,
        "macro_recall": aggregate.macro_recall,
        "macro_f1": aggregate.macro_f1,
        "micro_precision": aggregate.micro_precision,
        "micro_recall": aggregate.micro_recall,
        "micro_f1": aggregate.micro_f1,
        "coverage": aggregate.coverage,
        "label_count": len(result.per_label_metrics),
        "match_count": len(result.matches),
    }


def run_named_judge(
    *,
    name: str,
    ground_truth_records: Sequence[GroundTruthRecord],
    predicted_statuses: Mapping[tuple[str, str], LabelStatus],
) -> dict[str, Any]:
    """Run Judge and return a JSON-friendly summary payload."""
    if not ground_truth_records:
        return {
            "name": name,
            "skipped": True,
            "reason": "no ground-truth rows in slice",
        }
    result = run_judge(
        ground_truth_records=ground_truth_records,
        predicted_statuses=predicted_statuses,
    )
    return judge_summary_payload(name, result)


def fusion_results_to_frame(
    fusion_results: Sequence[FusionStudyResult],
) -> pd.DataFrame:
    """Flatten fusion outputs into an auditable long-form table."""
    rows: list[dict[str, Any]] = []
    for result in fusion_results:
        for label_result in result.labels:
            rows.append(
                {
                    "study_key": result.study_key,
                    "fusion_policy_version": result.fusion_policy_version,
                    "label": label_result.label,
                    "probability": label_result.probability,
                    "threshold": label_result.threshold,
                    "vision_status": label_result.vision_status.value,
                    "fused_status": label_result.fused_status.value,
                    "in_gray_zone": label_result.in_gray_zone,
                    "positive_count": label_result.positive_count,
                    "negative_count": label_result.negative_count,
                    "refinement_reason": label_result.refinement_reason,
                }
            )
    return pd.DataFrame(rows)
