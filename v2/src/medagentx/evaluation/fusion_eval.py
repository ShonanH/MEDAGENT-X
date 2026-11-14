"""Offline helpers for vision-only vs fusion Judge comparisons."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import pandas as pd

from medagentx.evaluation.ground_truth import GroundTruthRecord, build_ground_truth_records
from medagentx.evaluation.judge import JudgeResult, run_judge
from medagentx.evaluation.matching import MatchOutcome, compare_statuses
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label
from medagentx.labels.statuses import LabelStatus
from medagentx.reasoning.constants import GRAY_ZONE_MARGIN
from medagentx.reasoning.fuse import FusionStudyResult, is_gray_zone
from medagentx.vision.inference_output import VisionStudyOutput


@dataclass(frozen=True)
class NamedJudgeRun:
    """One named Judge run plus its intended reporting scope."""

    name: str
    eval_scope: str
    result: JudgeResult | None
    skipped_reason: str | None = None
    ground_truth_policy: str = "unspecified"


@dataclass(frozen=True)
class GroundTruthStrata:
    """Evaluation rows under explicit and No-Finding-derived policies."""

    explicit: tuple[GroundTruthRecord, ...]
    no_finding_derived: tuple[GroundTruthRecord, ...]
    combined: tuple[GroundTruthRecord, ...]
    provenance: pd.DataFrame


EXPLICIT_GT_POLICY_VERSION = "chexpert_explicit_present_absent_v1"
NO_FINDING_GT_POLICY_VERSION = "chexpert_no_finding_derived_negative_v1"
COMBINED_GT_POLICY_VERSION = "chexpert_training_policy_supervision_v1"


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


def study_labels_to_ground_truth_strata(
    study_labels: pd.DataFrame,
    *,
    study_keys: Sequence[str] | None = None,
) -> GroundTruthStrata:
    """Build auditable explicit, derived-negative, and combined GT strata.

    The explicit stratum preserves the canonical report-derived statuses.
    The derived-negative stratum contains only unmentioned disease cells that
    the locked training policy supervises as negative because No Finding is
    present.  The combined stratum applies that same conversion while leaving
    uncertain and all other unmentioned cells unscoreable.
    """
    if study_labels.empty:
        raise ValueError("study_labels must not be empty")

    selected = study_labels.copy()
    selected["study_key"] = selected["study_key"].astype(str).str.strip()
    if selected["study_key"].duplicated().any():
        duplicates = selected.loc[
            selected["study_key"].duplicated(keep=False), "study_key"
        ].unique()
        raise ValueError(
            "study_labels contains duplicate study keys: "
            f"{duplicates[:10].tolist()}"
        )
    if study_keys is not None:
        ordered_keys = [str(key).strip() for key in study_keys]
        key_set = set(ordered_keys)
        selected = selected[selected["study_key"].isin(key_set)].copy()
        missing = sorted(key_set - set(selected["study_key"]))
        if missing:
            raise ValueError(
                "No study-label row for requested study keys: "
                f"{missing[:10]}"
            )
        order = {key: index for index, key in enumerate(ordered_keys)}
        selected["_requested_order"] = selected["study_key"].map(order)
        selected = selected.sort_values("_requested_order", kind="stable")

    required_columns: list[str] = []
    for label in DISEASE_LABELS:
        slug = snake_label(label)
        required_columns.extend(
            (
                f"status_{slug}",
                f"training_target_{slug}",
                f"training_mask_{slug}",
            )
        )
    missing_columns = [
        column for column in required_columns if column not in selected.columns
    ]
    if missing_columns:
        raise ValueError(
            "study_labels is missing ground-truth provenance columns: "
            f"{missing_columns}"
        )

    explicit_records: list[GroundTruthRecord] = []
    derived_records: list[GroundTruthRecord] = []
    combined_records: list[GroundTruthRecord] = []
    provenance_rows: list[dict[str, Any]] = []

    for _, row in selected.iterrows():
        study_key = str(row["study_key"])
        for label in DISEASE_LABELS:
            slug = snake_label(label)
            original = _parse_label_status(row[f"status_{slug}"])
            mask_value = pd.to_numeric(
                pd.Series([row[f"training_mask_{slug}"]]), errors="coerce"
            ).iloc[0]
            target_value = pd.to_numeric(
                pd.Series([row[f"training_target_{slug}"]]), errors="coerce"
            ).iloc[0]
            mask = 0 if pd.isna(mask_value) else int(mask_value)
            target = None if pd.isna(target_value) else float(target_value)
            if mask not in (0, 1):
                raise ValueError(
                    f"Invalid training mask for {study_key!r}, {label!r}: {mask}"
                )

            is_derived_negative = (
                original is LabelStatus.UNMENTIONED
                and mask == 1
                and target == 0.0
            )
            combined_status = (
                LabelStatus.ABSENT if is_derived_negative else original
            )
            provenance = (
                "explicit_present"
                if original is LabelStatus.PRESENT
                else "explicit_absent"
                if original is LabelStatus.ABSENT
                else "no_finding_derived_negative"
                if is_derived_negative
                else "uncertain"
                if original is LabelStatus.UNCERTAIN
                else "unmentioned_unscored"
            )

            explicit_records.append(
                GroundTruthRecord(
                    study_key=study_key,
                    label=label,
                    ground_truth_status=original,
                    ground_truth_source="chexpert_report_status",
                    ground_truth_policy_version=EXPLICIT_GT_POLICY_VERSION,
                )
            )
            combined_records.append(
                GroundTruthRecord(
                    study_key=study_key,
                    label=label,
                    ground_truth_status=combined_status,
                    ground_truth_source=(
                        "chexpert_no_finding_rule"
                        if is_derived_negative
                        else "chexpert_report_status"
                    ),
                    ground_truth_policy_version=COMBINED_GT_POLICY_VERSION,
                )
            )
            if is_derived_negative:
                derived_records.append(
                    GroundTruthRecord(
                        study_key=study_key,
                        label=label,
                        ground_truth_status=LabelStatus.ABSENT,
                        ground_truth_source="chexpert_no_finding_rule",
                        ground_truth_policy_version=NO_FINDING_GT_POLICY_VERSION,
                    )
                )

            provenance_rows.append(
                {
                    "study_key": study_key,
                    "label": label,
                    "original_status": original.value,
                    "effective_combined_status": combined_status.value,
                    "target_provenance": provenance,
                    "training_mask": mask,
                    "training_target": target,
                    "explicit_scoreable": original
                    in (LabelStatus.PRESENT, LabelStatus.ABSENT),
                    "no_finding_derived_scoreable": is_derived_negative,
                    "combined_scoreable": combined_status
                    in (LabelStatus.PRESENT, LabelStatus.ABSENT),
                }
            )

    return GroundTruthStrata(
        explicit=tuple(explicit_records),
        no_finding_derived=tuple(derived_records),
        combined=tuple(combined_records),
        provenance=pd.DataFrame(provenance_rows),
    )


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


def named_judge_summary_payload(run: NamedJudgeRun) -> dict[str, Any]:
    """Serialize one named Judge run for JSON reporting."""
    if run.result is None:
        return {
            "name": run.name,
            "eval_scope": run.eval_scope,
            "ground_truth_policy": run.ground_truth_policy,
            "skipped": True,
            "reason": run.skipped_reason or "no ground-truth rows in slice",
        }

    payload = judge_summary_payload(run.name, run.result)
    payload["eval_scope"] = run.eval_scope
    payload["ground_truth_policy"] = run.ground_truth_policy
    return payload


def run_named_judge_result(
    *,
    name: str,
    eval_scope: str,
    ground_truth_records: Sequence[GroundTruthRecord],
    predicted_statuses: Mapping[tuple[str, str], LabelStatus],
    ground_truth_policy: str = "unspecified",
) -> NamedJudgeRun:
    """Run Judge and keep the full result for diagnostic CSVs."""
    if not ground_truth_records:
        return NamedJudgeRun(
            name=name,
            eval_scope=eval_scope,
            result=None,
            skipped_reason="no ground-truth rows in slice",
            ground_truth_policy=ground_truth_policy,
        )

    result = run_judge(
        ground_truth_records=ground_truth_records,
        predicted_statuses=predicted_statuses,
    )
    return NamedJudgeRun(
        name=name,
        eval_scope=eval_scope,
        result=result,
        ground_truth_policy=ground_truth_policy,
    )


def run_named_judge(
    *,
    name: str,
    ground_truth_records: Sequence[GroundTruthRecord],
    predicted_statuses: Mapping[tuple[str, str], LabelStatus],
) -> dict[str, Any]:
    """Run Judge and return a JSON-friendly summary payload."""
    run = run_named_judge_result(
        name=name,
        eval_scope="unknown",
        ground_truth_records=ground_truth_records,
        predicted_statuses=predicted_statuses,
    )
    payload = named_judge_summary_payload(run)
    payload.pop("eval_scope", None)
    return payload


def per_label_metrics_frame(runs: Sequence[NamedJudgeRun]) -> pd.DataFrame:
    """Build per-label Judge metrics rows for diagnostic CSV output."""
    rows: list[dict[str, Any]] = []
    for run in runs:
        if run.result is None:
            continue
        for metrics in run.result.per_label_metrics:
            scoreable_cells = metrics.gt_present + metrics.gt_absent
            coverage_rate = (
                scoreable_cells / metrics.total if metrics.total else 0.0
            )
            rows.append(
                {
                    "run_name": run.name,
                    "label": metrics.label,
                    "eval_scope": run.eval_scope,
                    "ground_truth_policy": run.ground_truth_policy,
                    "scoreable_cells": scoreable_cells,
                    "gt_present": metrics.gt_present,
                    "gt_absent": metrics.gt_absent,
                    "pred_present": metrics.pred_present,
                    "pred_absent": metrics.pred_absent,
                    "tp": metrics.tp,
                    "tn": metrics.tn,
                    "fp": metrics.fp,
                    "fn": metrics.fn,
                    "precision": metrics.precision,
                    "recall": metrics.recall,
                    "f1": metrics.f1,
                    "specificity": metrics.specificity,
                    "coverage_rate": coverage_rate,
                }
            )
    return pd.DataFrame(rows)


def uncertain_status_metrics_frame(runs: Sequence[NamedJudgeRun]) -> pd.DataFrame:
    """Build uncertain-status diagnostic rows for CSV output."""
    rows: list[dict[str, Any]] = []
    for run in runs:
        if run.result is None:
            continue
        for metrics in run.result.uncertain_status_metrics:
            rows.append(
                {
                    "run_name": run.name,
                    "label": metrics.label,
                    "eval_scope": run.eval_scope,
                    "ground_truth_policy": run.ground_truth_policy,
                    "gt_uncertain": metrics.gt_uncertain,
                    "pred_uncertain": metrics.pred_uncertain,
                    "uncertain_matches": metrics.uncertain_matches,
                    "uncertain_match_rate": metrics.uncertain_match_rate,
                    "uncertain_overcalls": metrics.uncertain_overcalls,
                    "uncertain_undercalls": metrics.uncertain_undercalls,
                }
            )
    return pd.DataFrame(rows)


def status_confusion_by_label_frame(runs: Sequence[NamedJudgeRun]) -> pd.DataFrame:
    """Build long-form status confusion rows for CSV output."""
    rows: list[dict[str, Any]] = []
    for run in runs:
        if run.result is None:
            continue
        for count in run.result.status_confusion_counts:
            rows.append(
                {
                    "run_name": run.name,
                    "label": count.label,
                    "eval_scope": run.eval_scope,
                    "ground_truth_policy": run.ground_truth_policy,
                    "gt_status": count.ground_truth_status.value,
                    "pred_status": count.predicted_status.value,
                    "cell_count": count.cell_count,
                }
            )
    return pd.DataFrame(rows)


def _ground_truth_map(
    ground_truth_records: Sequence[GroundTruthRecord],
) -> dict[tuple[str, str], LabelStatus]:
    return {
        (record.study_key, record.label): record.ground_truth_status
        for record in ground_truth_records
    }


def _change_type(
    vision_status: LabelStatus,
    fusion_status: LabelStatus,
) -> str:
    if vision_status is LabelStatus.ABSENT and fusion_status is LabelStatus.PRESENT:
        return "promotion"
    if vision_status is LabelStatus.PRESENT and fusion_status in (
        LabelStatus.ABSENT,
        LabelStatus.UNCERTAIN,
    ):
        return "demotion"
    return "other"


def _outcome_counts_as_fn(outcome: MatchOutcome) -> bool:
    return outcome in (MatchOutcome.FN, MatchOutcome.MISS_UNCERTAIN)


def fusion_change_analysis_frame(
    *,
    ground_truth_records: Sequence[GroundTruthRecord],
    fusion_results: Sequence[FusionStudyResult],
) -> pd.DataFrame:
    """Summarize fusion changes by label and whether they helped."""
    gt_by_key = _ground_truth_map(ground_truth_records)
    summaries: dict[str, dict[str, Any]] = {
        label: {
            "label": label,
            "total_cells": 0,
            "gray_zone_cells": 0,
            "changed_cells": 0,
            "promotions": 0,
            "demotions": 0,
            "other_changes": 0,
            "promotion_tp": 0,
            "promotion_fp": 0,
            "promotion_unscored": 0,
            "demotion_tp": 0,
            "demotion_fp": 0,
            "demotion_unscored": 0,
            "net_tp_change": 0,
            "net_fp_change": 0,
            "net_fn_change": 0,
        }
        for label in DISEASE_LABELS
    }

    for result in fusion_results:
        for label_result in result.labels:
            label = label_result.label
            gt_status = gt_by_key.get((result.study_key, label))
            if gt_status is None:
                continue
            summary = summaries.setdefault(label, {"label": label})
            summary["total_cells"] = summary.get("total_cells", 0) + 1
            if label_result.in_gray_zone:
                summary["gray_zone_cells"] = summary.get("gray_zone_cells", 0) + 1
            if label_result.vision_status is label_result.fused_status:
                continue

            change_type = _change_type(
                label_result.vision_status,
                label_result.fused_status,
            )
            summary["changed_cells"] += 1
            if change_type == "promotion":
                summary["promotions"] += 1
                if gt_status is LabelStatus.PRESENT:
                    summary["promotion_tp"] += 1
                elif gt_status is LabelStatus.ABSENT:
                    summary["promotion_fp"] += 1
                else:
                    summary["promotion_unscored"] += 1
            elif change_type == "demotion":
                summary["demotions"] += 1
                if gt_status is LabelStatus.ABSENT:
                    summary["demotion_tp"] += 1
                elif gt_status is LabelStatus.PRESENT:
                    summary["demotion_fp"] += 1
                else:
                    summary["demotion_unscored"] += 1
            else:
                summary["other_changes"] += 1

            before = compare_statuses(
                study_key=result.study_key,
                label=label,
                ground_truth_status=gt_status,
                predicted_status=label_result.vision_status,
            )
            after = compare_statuses(
                study_key=result.study_key,
                label=label,
                ground_truth_status=gt_status,
                predicted_status=label_result.fused_status,
            )
            summary["net_tp_change"] += int(after.outcome is MatchOutcome.TP) - int(
                before.outcome is MatchOutcome.TP
            )
            summary["net_fp_change"] += int(after.outcome is MatchOutcome.FP) - int(
                before.outcome is MatchOutcome.FP
            )
            summary["net_fn_change"] += int(
                _outcome_counts_as_fn(after.outcome)
            ) - int(_outcome_counts_as_fn(before.outcome))

    rows: list[dict[str, Any]] = []
    for label in sorted(summaries):
        summary = summaries[label]
        total_cells = summary.get("total_cells", 0)
        changed_cells = summary.get("changed_cells", 0)
        rows.append(
            {
                "label": summary["label"],
                "total_cells": total_cells,
                "gray_zone_cells": summary.get("gray_zone_cells", 0),
                "changed_cells": changed_cells,
                "changed_rate": changed_cells / total_cells if total_cells else 0.0,
                "promotions": summary.get("promotions", 0),
                "demotions": summary.get("demotions", 0),
                "other_changes": summary.get("other_changes", 0),
                "promotion_tp": summary.get("promotion_tp", 0),
                "promotion_fp": summary.get("promotion_fp", 0),
                "promotion_unscored": summary.get("promotion_unscored", 0),
                "demotion_tp": summary.get("demotion_tp", 0),
                "demotion_fp": summary.get("demotion_fp", 0),
                "demotion_unscored": summary.get("demotion_unscored", 0),
                "net_tp_change": summary.get("net_tp_change", 0),
                "net_fp_change": summary.get("net_fp_change", 0),
                "net_fn_change": summary.get("net_fn_change", 0),
            }
        )
    return pd.DataFrame(rows)


def fusion_changed_cells_frame(
    *,
    ground_truth_records: Sequence[GroundTruthRecord],
    fusion_results: Sequence[FusionStudyResult],
    retrieved_top_k: int | None = None,
) -> pd.DataFrame:
    """Build one row per study-label cell changed by fusion."""
    gt_by_key = _ground_truth_map(ground_truth_records)
    rows: list[dict[str, Any]] = []
    for result in fusion_results:
        for label_result in result.labels:
            if label_result.vision_status is label_result.fused_status:
                continue
            gt_status = gt_by_key.get((result.study_key, label_result.label))
            if gt_status is None:
                continue
            rows.append(
                {
                    "study_key": result.study_key,
                    "label": label_result.label,
                    "gt_status": gt_status.value,
                    "vision_status": label_result.vision_status.value,
                    "fusion_status": label_result.fused_status.value,
                    "vision_prob": label_result.probability,
                    "vision_threshold": label_result.threshold,
                    "gray_zone": label_result.in_gray_zone,
                    "change_type": _change_type(
                        label_result.vision_status,
                        label_result.fused_status,
                    ),
                    "retrieved_pos_mentions": label_result.positive_count,
                    "retrieved_neg_mentions": label_result.negative_count,
                    "retrieved_top_k": retrieved_top_k,
                }
            )
    return pd.DataFrame(rows)


def fusion_results_to_frame(
    fusion_results: Sequence[FusionStudyResult],
) -> pd.DataFrame:
    """Flatten fusion outputs into an auditable long-form table."""
    rows: list[dict[str, Any]] = []
    for result in fusion_results:
        for label_result in result.labels:
            deterministic_status = (
                label_result.deterministic_status or label_result.fused_status
            )
            rows.append(
                {
                    "study_key": result.study_key,
                    "fusion_policy_version": result.fusion_policy_version,
                    "label": label_result.label,
                    "probability": label_result.probability,
                    "threshold": label_result.threshold,
                    "vision_status": label_result.vision_status.value,
                    "deterministic_status": deterministic_status.value,
                    "fused_status": label_result.fused_status.value,
                    "in_gray_zone": label_result.in_gray_zone,
                    "positive_count": label_result.positive_count,
                    "negative_count": label_result.negative_count,
                    "llm_action": label_result.llm_action,
                    "llm_confidence": label_result.llm_confidence,
                    "llm_evidence_assessment": label_result.llm_evidence_assessment,
                    "llm_applied": label_result.llm_applied,
                    "llm_policy_reason": label_result.llm_policy_reason,
                    "refinement_reason": label_result.refinement_reason,
                }
            )
    return pd.DataFrame(rows)
