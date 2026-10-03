"""Replay Experiment 4 fusion using Experiment 3 vision predictions.

The permanent vision-prediction CSV does not contain RAD-DINO query embeddings,
so it cannot drive a new Chroma retrieval query by itself.  This utility uses
the complete per-cell mention counts retained in a prior Experiment 4
``fusion_label_predictions.csv`` as an evidence cache, applies the locked
deterministic fusion policy to Experiment 3's saved vision predictions, and
re-runs the offline Judge.

The output is deliberately marked as a cached-evidence replay rather than a
fresh live-retrieval run.  A fresh run requires the original checkpoint, DICOM
cohort, and Chroma index.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


_V2_ROOT = Path(__file__).resolve().parents[1]
if str(_V2_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_V2_ROOT / "src"))

from medagentx.evaluation.ground_truth import GroundTruthRecord, build_ground_truth_records
from medagentx.evaluation.judge import JudgeResult, run_judge
from medagentx.evaluation.matching import MatchOutcome, compare_statuses
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label
from medagentx.labels.statuses import LabelStatus
from medagentx.reasoning.constants import FUSION_POLICY_VERSION, GRAY_ZONE_MARGIN
from medagentx.reasoning.fuse import FusedLabelPrediction, VisionLabelPrediction, fuse_label
from medagentx.reasoning.mentions import MentionCounts


DEFAULT_SOURCE_VISION_CSV = Path(
    "v2/experiments/exp03_fusion_no_retrieval/vision_study_predictions.csv"
)
DEFAULT_RETRIEVAL_EVIDENCE_CSV = Path(
    "v2/artifactsLocal/Evaluation_output_last4_blocks_top10/test/"
    "fusion_label_predictions.csv"
)
DEFAULT_STUDY_LABELS_CSV = Path(
    "v2/artifactsLocal/val_last4_blocks_0818/val/study_label_table.csv"
)
DEFAULT_OUTPUT_DIR = Path(
    "v2/experiments/exp04_fusion_with_retrieval/from_exp03_cached_retrieval"
)


@dataclass(frozen=True)
class NamedJudgeRun:
    """A Judge result plus its name and evaluation slice."""

    name: str
    eval_scope: str
    result: JudgeResult


def _parse_status(value: object) -> LabelStatus:
    return LabelStatus(str(value).strip().lower())


def _require_file(path: Path, *, description: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{description} does not exist or is not a file: {path}")


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader), list(reader.fieldnames)


def _require_columns(
    columns: Sequence[str], required: Iterable[str], *, description: str
) -> None:
    missing = [column for column in required if column not in columns]
    if missing:
        raise ValueError(f"{description} is missing columns: {missing}")


def _vision_required_columns() -> list[str]:
    columns = ["study_key"]
    for label in DISEASE_LABELS:
        slug = snake_label(label)
        columns.extend(
            [
                f"probability_{slug}",
                f"threshold_{slug}",
                f"status_{slug}",
            ]
        )
    return columns


def _index_evidence(rows: Sequence[dict[str, str]]) -> dict[tuple[str, str], MentionCounts]:
    evidence: dict[tuple[str, str], MentionCounts] = {}
    for row in rows:
        key = (row["study_key"], row["label"])
        if key in evidence:
            raise ValueError(f"Duplicate retrieval evidence row for {key!r}")
        evidence[key] = MentionCounts(
            positive_count=int(row["positive_count"]),
            negative_count=int(row["negative_count"]),
        )
    return evidence


def _build_ground_truth(
    study_labels_rows: Sequence[dict[str, str]], *, study_keys: set[str]
) -> list[GroundTruthRecord]:
    ground_truth: list[GroundTruthRecord] = []
    seen: set[str] = set()
    for row in study_labels_rows:
        study_key = row["study_key"]
        if study_key not in study_keys:
            continue
        if study_key in seen:
            raise ValueError(f"Duplicate ground-truth study key: {study_key}")
        seen.add(study_key)
        statuses = {
            label: _parse_status(row[f"status_{snake_label(label)}"])
            for label in DISEASE_LABELS
        }
        ground_truth.extend(
            build_ground_truth_records(study_key=study_key, statuses=statuses)
        )
    missing = sorted(study_keys - seen)
    if missing:
        raise ValueError(
            "Ground-truth table lacks source studies; first missing keys: "
            + ", ".join(missing[:10])
        )
    return ground_truth


def _judge_summary(run: NamedJudgeRun) -> dict[str, object]:
    aggregate = run.result.aggregate_metrics
    return {
        "name": run.name,
        "eval_scope": run.eval_scope,
        "judge_metric_version": run.result.judge_metric_version,
        "macro_precision": aggregate.macro_precision,
        "macro_recall": aggregate.macro_recall,
        "macro_f1": aggregate.macro_f1,
        "micro_precision": aggregate.micro_precision,
        "micro_recall": aggregate.micro_recall,
        "micro_f1": aggregate.micro_f1,
        "coverage": aggregate.coverage,
        "label_count": len(run.result.per_label_metrics),
        "match_count": len(run.result.matches),
    }


def _write_csv(path: Path, rows: Sequence[dict[str, object]], fields: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _status_map_from_vision(
    vision_rows: Sequence[dict[str, str]],
) -> dict[tuple[str, str], LabelStatus]:
    return {
        (row["study_key"], label): _parse_status(row[f"status_{snake_label(label)}"])
        for row in vision_rows
        for label in DISEASE_LABELS
    }


def _gray_zone_ground_truth(
    ground_truth: Sequence[GroundTruthRecord],
    vision_rows: Sequence[dict[str, str]],
    *,
    margin: float,
) -> list[GroundTruthRecord]:
    gray_zone_keys = {
        (row["study_key"], label)
        for row in vision_rows
        for label in DISEASE_LABELS
        if abs(
            float(row[f"probability_{snake_label(label)}"])
            - float(row[f"threshold_{snake_label(label)}"])
        )
        <= margin
    }
    return [
        record
        for record in ground_truth
        if (record.study_key, record.label) in gray_zone_keys
    ]


def _fusion_change_type(vision: LabelStatus, fused: LabelStatus) -> str:
    if vision is LabelStatus.ABSENT and fused is LabelStatus.PRESENT:
        return "promotion"
    if vision is LabelStatus.PRESENT and fused in (
        LabelStatus.ABSENT,
        LabelStatus.UNCERTAIN,
    ):
        return "demotion"
    return "other"


def _outcome_counts_as_fn(outcome: MatchOutcome) -> bool:
    return outcome in (MatchOutcome.FN, MatchOutcome.MISS_UNCERTAIN)


def _fusion_change_analysis_rows(
    fused_labels: Sequence[tuple[str, FusedLabelPrediction]],
    ground_truth: Sequence[GroundTruthRecord],
) -> list[dict[str, object]]:
    gt_by_key = {
        (record.study_key, record.label): record.ground_truth_status
        for record in ground_truth
    }
    summaries = {
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
    for study_key, fused in fused_labels:
        summary = summaries[fused.label]
        summary["total_cells"] += 1
        summary["gray_zone_cells"] += int(fused.in_gray_zone)
        if fused.vision_status is fused.fused_status:
            continue
        summary["changed_cells"] += 1
        change_type = _fusion_change_type(fused.vision_status, fused.fused_status)
        if change_type == "promotion":
            summary["promotions"] += 1
        elif change_type == "demotion":
            summary["demotions"] += 1
        else:
            summary["other_changes"] += 1
        gt_status = gt_by_key[(study_key, fused.label)]
        if change_type == "promotion":
            if gt_status is LabelStatus.PRESENT:
                summary["promotion_tp"] += 1
            elif gt_status is LabelStatus.ABSENT:
                summary["promotion_fp"] += 1
            else:
                summary["promotion_unscored"] += 1
        elif change_type == "demotion":
            if gt_status is LabelStatus.ABSENT:
                summary["demotion_tp"] += 1
            elif gt_status is LabelStatus.PRESENT:
                summary["demotion_fp"] += 1
            else:
                summary["demotion_unscored"] += 1
        before = compare_statuses(
            study_key=study_key,
            label=fused.label,
            ground_truth_status=gt_status,
            predicted_status=fused.vision_status,
        )
        after = compare_statuses(
            study_key=study_key,
            label=fused.label,
            ground_truth_status=gt_status,
            predicted_status=fused.fused_status,
        )
        summary["net_tp_change"] += int(after.outcome is MatchOutcome.TP) - int(
            before.outcome is MatchOutcome.TP
        )
        summary["net_fp_change"] += int(after.outcome is MatchOutcome.FP) - int(
            before.outcome is MatchOutcome.FP
        )
        summary["net_fn_change"] += int(_outcome_counts_as_fn(after.outcome)) - int(
            _outcome_counts_as_fn(before.outcome)
        )
    for summary in summaries.values():
        total = int(summary["total_cells"])
        changed = int(summary["changed_cells"])
        summary["changed_rate"] = changed / total if total else 0.0
    return [summaries[label] for label in sorted(summaries)]


def _diagnostic_rows(runs: Sequence[NamedJudgeRun]) -> dict[str, list[dict[str, object]]]:
    per_label: list[dict[str, object]] = []
    uncertain: list[dict[str, object]] = []
    confusion: list[dict[str, object]] = []
    matches: list[dict[str, object]] = []
    for run in runs:
        for metric in run.result.per_label_metrics:
            per_label.append(
                {
                    "run_name": run.name,
                    "label": metric.label,
                    "eval_scope": run.eval_scope,
                    "scoreable_cells": metric.gt_present + metric.gt_absent,
                    "gt_present": metric.gt_present,
                    "gt_absent": metric.gt_absent,
                    "pred_present": metric.pred_present,
                    "pred_absent": metric.pred_absent,
                    "tp": metric.tp,
                    "tn": metric.tn,
                    "fp": metric.fp,
                    "fn": metric.fn,
                    "precision": metric.precision,
                    "recall": metric.recall,
                    "f1": metric.f1,
                    "specificity": metric.specificity,
                    "coverage_rate": metric.coverage_rate,
                }
            )
        for metric in run.result.uncertain_status_metrics:
            uncertain.append(
                {
                    "run_name": run.name,
                    "label": metric.label,
                    "eval_scope": run.eval_scope,
                    "gt_uncertain": metric.gt_uncertain,
                    "pred_uncertain": metric.pred_uncertain,
                    "uncertain_matches": metric.uncertain_matches,
                    "uncertain_match_rate": metric.uncertain_match_rate,
                    "uncertain_overcalls": metric.uncertain_overcalls,
                    "uncertain_undercalls": metric.uncertain_undercalls,
                }
            )
        for count in run.result.status_confusion_counts:
            confusion.append(
                {
                    "run_name": run.name,
                    "label": count.label,
                    "eval_scope": run.eval_scope,
                    "gt_status": count.ground_truth_status.value,
                    "pred_status": count.predicted_status.value,
                    "cell_count": count.cell_count,
                }
            )
        for match in run.result.matches:
            matches.append(
                {
                    "run_name": run.name,
                    "eval_scope": run.eval_scope,
                    "study_key": match.study_key,
                    "label": match.label,
                    "ground_truth_status": match.ground_truth_status.value,
                    "predicted_status": match.predicted_status.value,
                    "outcome": match.outcome.value,
                    "binary_scoreable": match.binary_scoreable,
                }
            )
    return {
        "per_label_metrics": per_label,
        "uncertain_status_metrics": uncertain,
        "status_confusion_by_label": confusion,
        "judge_matches": matches,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-vision-csv", type=Path, default=DEFAULT_SOURCE_VISION_CSV)
    parser.add_argument(
        "--retrieval-evidence-csv", type=Path, default=DEFAULT_RETRIEVAL_EVIDENCE_CSV
    )
    parser.add_argument("--study-labels-csv", type=Path, default=DEFAULT_STUDY_LABELS_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--gray-zone-margin", type=float, default=GRAY_ZONE_MARGIN)
    parser.add_argument("--retrieval-top-k", type=int, default=10)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.gray_zone_margin < 0:
        raise ValueError("--gray-zone-margin must be >= 0")
    if args.retrieval_top_k <= 0:
        raise ValueError("--retrieval-top-k must be > 0")
    for path, description in (
        (args.source_vision_csv, "source vision CSV"),
        (args.retrieval_evidence_csv, "retrieval evidence CSV"),
        (args.study_labels_csv, "study labels CSV"),
    ):
        _require_file(path, description=description)

    vision_rows, vision_columns = _read_csv(args.source_vision_csv)
    _require_columns(
        vision_columns, _vision_required_columns(), description="source vision CSV"
    )
    if not vision_rows:
        raise ValueError("source vision CSV has no prediction rows")
    study_keys = [row["study_key"] for row in vision_rows]
    if len(set(study_keys)) != len(study_keys):
        raise ValueError("source vision CSV contains duplicate study_key values")

    evidence_rows, evidence_columns = _read_csv(args.retrieval_evidence_csv)
    _require_columns(
        evidence_columns,
        ("study_key", "label", "positive_count", "negative_count"),
        description="retrieval evidence CSV",
    )
    evidence = _index_evidence(evidence_rows)
    required_evidence = {(study_key, label) for study_key in study_keys for label in DISEASE_LABELS}
    missing_evidence = sorted(required_evidence - set(evidence))
    if missing_evidence:
        raise ValueError(
            "Retrieval evidence is incomplete; first missing cells: "
            + ", ".join(f"{study_key}/{label}" for study_key, label in missing_evidence[:10])
        )

    study_labels_rows, study_labels_columns = _read_csv(args.study_labels_csv)
    _require_columns(
        study_labels_columns,
        ["study_key", *[f"status_{snake_label(label)}" for label in DISEASE_LABELS]],
        description="study labels CSV",
    )
    ground_truth = _build_ground_truth(study_labels_rows, study_keys=set(study_keys))

    fused_labels: list[tuple[str, FusedLabelPrediction]] = []
    fusion_rows: list[dict[str, object]] = []
    fusion_statuses: dict[tuple[str, str], LabelStatus] = {}
    for row in vision_rows:
        study_key = row["study_key"]
        for label in DISEASE_LABELS:
            slug = snake_label(label)
            prediction = VisionLabelPrediction(
                label=label,
                probability=float(row[f"probability_{slug}"]),
                threshold=float(row[f"threshold_{slug}"]),
                status=_parse_status(row[f"status_{slug}"]),
            )
            fused = fuse_label(
                prediction,
                evidence[(study_key, label)],
                margin=args.gray_zone_margin,
            )
            fused_labels.append((study_key, fused))
            fusion_statuses[(study_key, label)] = fused.fused_status
            fusion_rows.append(
                {
                    "study_key": study_key,
                    "fusion_policy_version": FUSION_POLICY_VERSION,
                    "label": label,
                    "probability": fused.probability,
                    "threshold": fused.threshold,
                    "vision_status": fused.vision_status.value,
                    "fused_status": fused.fused_status.value,
                    "in_gray_zone": fused.in_gray_zone,
                    "positive_count": fused.positive_count,
                    "negative_count": fused.negative_count,
                    "refinement_reason": fused.refinement_reason,
                }
            )

    vision_statuses = _status_map_from_vision(vision_rows)
    gray_zone_ground_truth = _gray_zone_ground_truth(
        ground_truth, vision_rows, margin=args.gray_zone_margin
    )
    runs = [
        NamedJudgeRun("vision_full", "full", run_judge(
            ground_truth_records=ground_truth, predicted_statuses=vision_statuses
        )),
        NamedJudgeRun("fusion_full", "full", run_judge(
            ground_truth_records=ground_truth, predicted_statuses=fusion_statuses
        )),
        NamedJudgeRun("vision_gray_zone", "gray_zone", run_judge(
            ground_truth_records=gray_zone_ground_truth, predicted_statuses=vision_statuses
        )),
        NamedJudgeRun("fusion_gray_zone", "gray_zone", run_judge(
            ground_truth_records=gray_zone_ground_truth, predicted_statuses=fusion_statuses
        )),
    ]

    if args.output_dir.exists() and any(args.output_dir.iterdir()) and not args.overwrite:
        raise FileExistsError(
            f"Output directory is not empty: {args.output_dir}. Pass --overwrite to reuse it."
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.source_vision_csv, args.output_dir / "vision_study_predictions.csv")
    _write_csv(
        args.output_dir / "fusion_label_predictions.csv",
        fusion_rows,
        (
            "study_key", "fusion_policy_version", "label", "probability", "threshold",
            "vision_status", "fused_status", "in_gray_zone", "positive_count",
            "negative_count", "refinement_reason",
        ),
    )
    diagnostics = _diagnostic_rows(runs)
    _write_csv(
        args.output_dir / "per_label_metrics.csv",
        diagnostics["per_label_metrics"],
        (
            "run_name", "label", "eval_scope", "scoreable_cells", "gt_present", "gt_absent",
            "pred_present", "pred_absent", "tp", "tn", "fp", "fn", "precision", "recall",
            "f1", "specificity", "coverage_rate",
        ),
    )
    _write_csv(
        args.output_dir / "uncertain_status_metrics.csv",
        diagnostics["uncertain_status_metrics"],
        (
            "run_name", "label", "eval_scope", "gt_uncertain", "pred_uncertain",
            "uncertain_matches", "uncertain_match_rate", "uncertain_overcalls",
            "uncertain_undercalls",
        ),
    )
    _write_csv(
        args.output_dir / "status_confusion_by_label.csv",
        diagnostics["status_confusion_by_label"],
        ("run_name", "label", "eval_scope", "gt_status", "pred_status", "cell_count"),
    )
    _write_csv(
        args.output_dir / "judge_matches.csv",
        diagnostics["judge_matches"],
        (
            "run_name", "eval_scope", "study_key", "label", "ground_truth_status",
            "predicted_status", "outcome", "binary_scoreable",
        ),
    )
    _write_csv(
        args.output_dir / "fusion_change_analysis.csv",
        _fusion_change_analysis_rows(fused_labels, ground_truth),
        (
            "label", "total_cells", "gray_zone_cells", "changed_cells", "changed_rate",
            "promotions", "demotions", "other_changes", "promotion_tp", "promotion_fp",
            "promotion_unscored", "demotion_tp", "demotion_fp", "demotion_unscored",
            "net_tp_change", "net_fp_change", "net_fn_change",
        ),
    )
    changed_rows = [
        {
            "study_key": study_key,
            "label": fused.label,
            "gt_status": next(
                record.ground_truth_status.value
                for record in ground_truth
                if record.study_key == study_key and record.label == fused.label
            ),
            "vision_status": fused.vision_status.value,
            "fusion_status": fused.fused_status.value,
            "vision_prob": fused.probability,
            "vision_threshold": fused.threshold,
            "gray_zone": fused.in_gray_zone,
            "change_type": _fusion_change_type(fused.vision_status, fused.fused_status),
            "retrieved_pos_mentions": fused.positive_count,
            "retrieved_neg_mentions": fused.negative_count,
            "retrieved_top_k": args.retrieval_top_k,
        }
        for study_key, fused in fused_labels
        if fused.vision_status is not fused.fused_status
    ]
    _write_csv(
        args.output_dir / "fusion_changed_cells.csv",
        changed_rows,
        (
            "study_key", "label", "gt_status", "vision_status", "fusion_status",
            "vision_prob", "vision_threshold", "gray_zone", "change_type",
            "retrieved_pos_mentions", "retrieved_neg_mentions", "retrieved_top_k",
        ),
    )
    metadata = {
        "experiment": "exp04_fusion_with_retrieval_from_exp03",
        "fusion_policy_version": FUSION_POLICY_VERSION,
        "gray_zone_margin": args.gray_zone_margin,
        "retrieval_top_k": args.retrieval_top_k,
        "retrieval_evidence_mode": "cached_mention_counts_from_prior_exp04",
        "live_retrieval_performed": False,
        "source_vision_csv": str(args.source_vision_csv),
        "retrieval_evidence_csv": str(args.retrieval_evidence_csv),
        "study_labels_csv": str(args.study_labels_csv),
        "output_dir": str(args.output_dir),
        "study_count": len(study_keys),
        "ground_truth_rows": len(ground_truth),
        "gray_zone_rows": len(gray_zone_ground_truth),
        "runs": [_judge_summary(run) for run in runs],
    }
    (args.output_dir / "run_config.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "judge_summary.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for run in runs:
        aggregate = run.result.aggregate_metrics
        print(
            f"[Exp04Replay] {run.name}: macro_f1={aggregate.macro_f1:.4f} "
            f"coverage={aggregate.coverage:.4f}"
        )
    print(f"[Exp04Replay] wrote artifacts -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
