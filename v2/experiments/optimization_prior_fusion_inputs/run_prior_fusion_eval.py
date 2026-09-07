"""Run retrieval-prior fusion with the Exp05-matched vision setup.

This runner evaluates:

    last4-block vision checkpoint + tuned thresholds + default prior-fusion rules

The defaults intentionally match the Exp05 vision/retrieval inputs so the
remaining difference is the prior-fusion rule itself.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


EXPERIMENT_DIR = Path(__file__).resolve().parent
V2_ROOT = Path(__file__).resolve().parents[2]
V2_SRC = V2_ROOT / "src"
if str(V2_SRC) not in sys.path:
    sys.path.insert(0, str(V2_SRC))
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

import pandas as pd
import torch

from medagentx.data.balanced_constants import DEFAULT_BALANCED_COHORT_ROOT
from medagentx.evaluation.fusion_eval import (
    filter_gray_zone_ground_truth,
    named_judge_summary_payload,
    per_label_metrics_frame,
    run_named_judge_result,
    status_confusion_by_label_frame,
    study_labels_to_ground_truth,
    study_outputs_by_key,
    uncertain_status_metrics_frame,
    vision_status_map,
)
from medagentx.evaluation.matching import MatchOutcome, compare_statuses
from medagentx.labels.statuses import LabelStatus
from medagentx.reasoning.constants import FUSION_RETRIEVAL_TOP_K
from medagentx.reasoning.retrieve import (
    open_retrieval_collection,
    retrieve_similar_reports,
)
from medagentx.vision.backend import FineTunedRadDinoBackend
from medagentx.vision.constants import DEFAULT_BATCH_SIZE, DEFAULT_NUM_WORKERS
from medagentx.vision.data import build_study_inference_records
from medagentx.vision.inference_output import (
    VisionStudyOutput,
    study_outputs_to_prediction_frame,
)
from prior_fusion import (
    DISEASE_LABELS,
    GRAY_ZONE_MARGIN,
    PRIOR_FUSION_POLICY_VERSION,
    PriorFusionStudyResult,
    PriorVisionLabelPrediction,
    fuse_study_labels_with_priors,
)
from retrieval_prior import (
    RetrievalLabelPrior,
    compute_retrieval_priors,
    load_study_label_status_lookup,
)


DEFAULT_OUTPUT_DIR = V2_ROOT / "experiments" / "exp08_prior_fusion_last4_tuned"
DEFAULT_VIEWS_CSV = EXPERIMENT_DIR / "splits" / "view_splits.csv"
DEFAULT_STUDY_LABELS_CSV = EXPERIMENT_DIR / "splits" / "study_label_table.csv"
DEFAULT_COLLECTION_NAME = "medagentx_train_studies_v1"
OUTPUT_FILENAMES = (
    "run_config.json",
    "vision_study_predictions.csv",
    "retrieval_prior_features.csv",
    "prior_fusion_label_predictions.csv",
    "prior_fusion_changed_cells.csv",
    "prior_fusion_change_analysis.csv",
    "per_label_metrics.csv",
    "uncertain_status_metrics.csv",
    "status_confusion_by_label.csv",
    "judge_summary.json",
)


def _default_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def build_parser() -> argparse.ArgumentParser:
    """Build the prior-fusion evaluation CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Run vision + image retrieval + structured retrieval-prior fusion "
            "and compare vision-only vs prior-fusion with Judge metrics."
        )
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path(DEFAULT_BALANCED_COHORT_ROOT),
    )
    parser.add_argument("--views-csv", type=Path, default=DEFAULT_VIEWS_CSV)
    parser.add_argument(
        "--study-labels-csv",
        type=Path,
        default=DEFAULT_STUDY_LABELS_CSV,
    )
    parser.add_argument("--dicom-root", type=Path, default=None)
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--threshold-policy-json", type=Path, default=None)
    parser.add_argument("--vector-db-dir", type=Path, default=None)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--split",
        choices=("val", "test"),
        default="test",
        help="Evaluation split. Use val for tuning; test for locked evaluation.",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--num-workers", type=int, default=DEFAULT_NUM_WORKERS)
    parser.add_argument("--device", default=_default_device())
    parser.add_argument("--no-mixed-precision", action="store_true")
    parser.add_argument("--gray-zone-margin", type=float, default=GRAY_ZONE_MARGIN)
    parser.add_argument("--retrieval-top-k", type=int, default=FUSION_RETRIEVAL_TOP_K)
    parser.add_argument("--max-studies", type=int, default=None)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing output files in --output-dir.",
    )
    return parser


def _default_checkpoint(cohort_root: Path) -> Path:
    return (
        cohort_root
        / "vision"
        / "raddino_finetuned_v1_last4_blocks"
        / "best_checkpoint.pt"
    )


def _default_dicom_root(cohort_root: Path) -> Path:
    return cohort_root / "dicom_train"


def _default_retrieval_chroma_dir(cohort_root: Path) -> Path:
    return cohort_root / "retrieval" / "raddino_train_v1_last4_blocks" / "chroma"


def _default_threshold_policy_json(cohort_root: Path) -> Path:
    return (
        cohort_root
        / "reasoning"
        / "fusion_eval_v1"
        / "val_last4_blocks"
        / "val"
        / "threshold_tuning"
        / "threshold_policy_v2.json"
    )


def _load_threshold_overrides(
    path: Path | None,
) -> tuple[dict[str, float] | None, str | None]:
    if path is None:
        return None, None
    payload = json.loads(path.read_text())
    selected = payload.get("selected_thresholds")
    if not isinstance(selected, dict):
        raise ValueError(f"{path} must contain a selected_thresholds object")
    thresholds = {str(label): float(value) for label, value in selected.items()}
    return thresholds, payload.get("threshold_policy_version")


def _require_existing_paths(paths: Mapping[str, Path]) -> None:
    missing = [f"{name}: {path}" for name, path in paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Required prior-fusion artifacts are missing:\n" + "\n".join(missing)
        )


def _prepare_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [
        output_dir / name for name in OUTPUT_FILENAMES if (output_dir / name).exists()
    ]
    if existing and not overwrite:
        raise FileExistsError(
            "Prior-fusion output files already exist. Pass --overwrite to replace:\n"
            + "\n".join(str(path) for path in existing)
        )
    if overwrite:
        for path in existing:
            path.unlink()


def _label_status(value: str) -> LabelStatus:
    return LabelStatus(str(value).strip().lower())


def _vision_predictions_for_prior_fusion(
    study_output: VisionStudyOutput,
) -> dict[str, PriorVisionLabelPrediction]:
    return {
        label_output.label: PriorVisionLabelPrediction(
            label=label_output.label,
            probability=label_output.probability,
            threshold=label_output.threshold,
            status=label_output.status.value,
        )
        for label_output in study_output.labels
    }


def prior_fusion_status_map(
    fusion_results: Sequence[PriorFusionStudyResult],
) -> dict[tuple[str, str], LabelStatus]:
    """Flatten prior-fusion outputs into Judge prediction keys."""
    predictions: dict[tuple[str, str], LabelStatus] = {}
    for result in fusion_results:
        for label_result in result.labels:
            predictions[(result.study_key, label_result.label)] = _label_status(
                label_result.fused_status
            )
    return predictions


def retrieval_prior_features_to_frame(
    priors_by_study: Mapping[str, Mapping[str, RetrievalLabelPrior]],
) -> pd.DataFrame:
    """Flatten retrieval-prior features into a long-form audit table."""
    rows: list[dict[str, Any]] = []
    for study_key, priors in priors_by_study.items():
        for label, prior in priors.items():
            rows.append(
                {
                    "study_key": study_key,
                    "label": label,
                    "retrieval_present_prior": prior.present_prior,
                    "retrieval_absent_prior": prior.absent_prior,
                    "retrieval_uncertain_rate": prior.uncertain_rate,
                    "retrieval_unmentioned_rate": prior.unmentioned_rate,
                    "retrieval_confidence": prior.retrieval_confidence,
                    "retrieval_scoreable_weight": prior.scoreable_weight,
                    "retrieval_total_weight": prior.total_weight,
                    "retrieval_mean_similarity": prior.mean_similarity,
                    "retrieval_count": prior.retrieved_count,
                    "retrieval_scoreable_count": prior.scoreable_count,
                    "top_supporting_cases": "|".join(prior.top_supporting_cases),
                    "top_contradicting_cases": "|".join(
                        prior.top_contradicting_cases
                    ),
                }
            )
    return pd.DataFrame(rows)


def prior_fusion_results_to_frame(
    fusion_results: Sequence[PriorFusionStudyResult],
) -> pd.DataFrame:
    """Flatten prior-fusion outputs into an auditable label table."""
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
                    "probability_minus_threshold": (
                        label_result.probability_minus_threshold
                    ),
                    "vision_status": label_result.vision_status,
                    "fused_status": label_result.fused_status,
                    "in_gray_zone": label_result.in_gray_zone,
                    "retrieval_present_prior": (
                        label_result.retrieval_present_prior
                    ),
                    "retrieval_absent_prior": label_result.retrieval_absent_prior,
                    "retrieval_uncertain_rate": (
                        label_result.retrieval_uncertain_rate
                    ),
                    "retrieval_unmentioned_rate": (
                        label_result.retrieval_unmentioned_rate
                    ),
                    "retrieval_confidence": label_result.retrieval_confidence,
                    "retrieval_contradiction_signal": (
                        label_result.retrieval_contradiction_signal
                    ),
                    "vision_retrieval_agreement": (
                        label_result.vision_retrieval_agreement
                    ),
                    "retrieval_scoreable_weight": (
                        label_result.retrieval_scoreable_weight
                    ),
                    "retrieval_total_weight": label_result.retrieval_total_weight,
                    "retrieval_mean_similarity": (
                        label_result.retrieval_mean_similarity
                    ),
                    "retrieval_scoreable_count": (
                        label_result.retrieval_scoreable_count
                    ),
                    "retrieval_count": label_result.retrieval_count,
                    "top_supporting_cases": "|".join(
                        label_result.top_supporting_cases
                    ),
                    "top_contradicting_cases": "|".join(
                        label_result.top_contradicting_cases
                    ),
                    "refinement_reason": label_result.refinement_reason,
                }
            )
    return pd.DataFrame(rows)


def _ground_truth_map(ground_truth_records) -> dict[tuple[str, str], LabelStatus]:
    return {
        (record.study_key, record.label): record.ground_truth_status
        for record in ground_truth_records
    }


def _change_type(vision_status: str, fusion_status: str) -> str:
    if vision_status == "absent" and fusion_status == "present":
        return "promotion"
    if vision_status == "present" and fusion_status in {"absent", "uncertain"}:
        return "demotion"
    return "other"


def _outcome_counts_as_fn(outcome: MatchOutcome) -> bool:
    return outcome in (MatchOutcome.FN, MatchOutcome.MISS_UNCERTAIN)


def prior_fusion_changed_cells_frame(
    *,
    ground_truth_records,
    fusion_results: Sequence[PriorFusionStudyResult],
    retrieved_top_k: int | None = None,
) -> pd.DataFrame:
    """Build one row per study-label cell changed by prior fusion."""
    gt_by_key = _ground_truth_map(ground_truth_records)
    rows: list[dict[str, Any]] = []
    for result in fusion_results:
        for label_result in result.labels:
            if label_result.vision_status == label_result.fused_status:
                continue
            gt_status = gt_by_key.get((result.study_key, label_result.label))
            rows.append(
                {
                    "study_key": result.study_key,
                    "label": label_result.label,
                    "gt_status": gt_status.value if gt_status is not None else None,
                    "vision_status": label_result.vision_status,
                    "fusion_status": label_result.fused_status,
                    "vision_prob": label_result.probability,
                    "vision_threshold": label_result.threshold,
                    "probability_minus_threshold": (
                        label_result.probability_minus_threshold
                    ),
                    "gray_zone": label_result.in_gray_zone,
                    "change_type": _change_type(
                        label_result.vision_status,
                        label_result.fused_status,
                    ),
                    "retrieval_present_prior": (
                        label_result.retrieval_present_prior
                    ),
                    "retrieval_absent_prior": label_result.retrieval_absent_prior,
                    "retrieval_confidence": label_result.retrieval_confidence,
                    "retrieval_contradiction_signal": (
                        label_result.retrieval_contradiction_signal
                    ),
                    "retrieved_top_k": retrieved_top_k,
                    "refinement_reason": label_result.refinement_reason,
                }
            )
    return pd.DataFrame(rows)


def prior_fusion_change_analysis_frame(
    *,
    ground_truth_records,
    fusion_results: Sequence[PriorFusionStudyResult],
) -> pd.DataFrame:
    """Summarize prior-fusion changes by label and whether they helped."""
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
            summary = summaries[label_result.label]
            summary["total_cells"] += 1
            if label_result.in_gray_zone:
                summary["gray_zone_cells"] += 1
            if label_result.vision_status == label_result.fused_status:
                continue

            gt_status = gt_by_key.get((result.study_key, label_result.label))
            if gt_status is None:
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
                label=label_result.label,
                ground_truth_status=gt_status,
                predicted_status=_label_status(label_result.vision_status),
            )
            after = compare_statuses(
                study_key=result.study_key,
                label=label_result.label,
                ground_truth_status=gt_status,
                predicted_status=_label_status(label_result.fused_status),
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
        total_cells = summary["total_cells"]
        changed_cells = summary["changed_cells"]
        row = dict(summary)
        row["changed_rate"] = changed_cells / total_cells if total_cells else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Run prior-fusion evaluation and write experiment artifacts."""
    args = build_parser().parse_args(argv)
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be > 0")
    if args.num_workers < 0:
        raise ValueError("--num-workers must be >= 0")
    if args.gray_zone_margin < 0:
        raise ValueError("--gray-zone-margin must be >= 0")
    if args.retrieval_top_k <= 0:
        raise ValueError("--retrieval-top-k must be > 0")
    if args.max_studies is not None and args.max_studies <= 0:
        raise ValueError("--max-studies must be > 0")
    if args.progress_every <= 0:
        raise ValueError("--progress-every must be > 0")

    cohort_root: Path = args.cohort_root
    dicom_root = args.dicom_root or _default_dicom_root(cohort_root)
    checkpoint = args.checkpoint or _default_checkpoint(cohort_root)
    vector_db_dir = args.vector_db_dir or _default_retrieval_chroma_dir(cohort_root)
    threshold_policy_json = (
        args.threshold_policy_json or _default_threshold_policy_json(cohort_root)
    )
    threshold_overrides, threshold_policy_version = _load_threshold_overrides(
        threshold_policy_json
    )

    required_paths = {
        "views_csv": args.views_csv,
        "study_labels_csv": args.study_labels_csv,
        "dicom_root": dicom_root,
        "checkpoint": checkpoint,
        "vector_db_dir": vector_db_dir,
    }
    if threshold_policy_json is not None:
        required_paths["threshold_policy_json"] = threshold_policy_json
    _require_existing_paths(required_paths)
    _prepare_output_dir(args.output_dir, overwrite=args.overwrite)

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")

    print(
        "[PriorFusionEval] "
        f"split={args.split} policy={PRIOR_FUSION_POLICY_VERSION} "
        f"device={device} gray_margin={args.gray_zone_margin} "
        f"retrieval_top_k={args.retrieval_top_k}"
    )
    if threshold_policy_json is None:
        print("[PriorFusionEval] using checkpoint/default vision thresholds")
    else:
        print(
            "[PriorFusionEval] using threshold policy "
            f"{threshold_policy_version or 'unknown'} -> "
            f"{threshold_policy_json}"
        )

    views = pd.read_csv(args.views_csv, dtype=str)
    records = build_study_inference_records(views, split=args.split)
    if args.max_studies is not None:
        records = records[: args.max_studies]
    if not records:
        raise ValueError(f"No studies found for split={args.split!r}")

    print(f"[PriorFusionEval] loading checkpoint {checkpoint}")
    backend = FineTunedRadDinoBackend.from_checkpoint(
        checkpoint,
        device=device,
        mixed_precision=not args.no_mixed_precision,
    )

    vision_start = time.perf_counter()
    print(
        f"[PriorFusionEval] running vision on {len(records)} studies "
        f"(batch_size={args.batch_size}, num_workers={args.num_workers})"
    )
    study_outputs = backend.predict_study_outputs(
        records,
        dicom_root=dicom_root,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        threshold_overrides=threshold_overrides,
    )
    print(
        "[PriorFusionEval] vision complete "
        f"studies={len(study_outputs)} "
        f"elapsed={time.perf_counter() - vision_start:.1f}s"
    )

    print(f"[PriorFusionEval] opening retrieval collection at {vector_db_dir}")
    collection = open_retrieval_collection(
        vector_db_dir,
        collection_name=args.collection_name,
    )
    study_label_statuses = load_study_label_status_lookup(args.study_labels_csv)

    fusion_results: list[PriorFusionStudyResult] = []
    priors_by_study: dict[str, dict[str, RetrievalLabelPrior]] = {}
    retrieval_start = time.perf_counter()
    total_studies = len(study_outputs)
    for index, study_output in enumerate(study_outputs, start=1):
        retrieved = retrieve_similar_reports(
            collection,
            study_output,
            top_k=args.retrieval_top_k,
        )
        retrieval_priors = compute_retrieval_priors(
            retrieved_cases=retrieved,
            study_label_statuses=study_label_statuses,
        )
        priors_by_study[study_output.study_key] = retrieval_priors
        fusion_results.append(
            fuse_study_labels_with_priors(
                _vision_predictions_for_prior_fusion(study_output),
                retrieval_priors,
                study_key=study_output.study_key,
                margin=args.gray_zone_margin,
            )
        )
        if index == 1 or index % args.progress_every == 0 or index == total_studies:
            elapsed = time.perf_counter() - retrieval_start
            print(
                f"[PriorFusionEval] fused {index}/{total_studies} studies "
                f"elapsed={elapsed:.1f}s"
            )

    study_keys = [output.study_key for output in study_outputs]
    print(f"[PriorFusionEval] loading ground truth from {args.study_labels_csv}")
    study_labels = pd.read_csv(args.study_labels_csv, dtype=str)
    ground_truth_records = study_labels_to_ground_truth(
        study_labels,
        study_keys=study_keys,
    )
    outputs_by_key = study_outputs_by_key(study_outputs)
    gray_zone_records = filter_gray_zone_ground_truth(
        ground_truth_records,
        outputs_by_key,
        margin=args.gray_zone_margin,
    )

    vision_predictions = vision_status_map(study_outputs)
    prior_fusion_predictions = prior_fusion_status_map(fusion_results)
    judge_runs = [
        run_named_judge_result(
            name="vision_full",
            eval_scope="full",
            ground_truth_records=ground_truth_records,
            predicted_statuses=vision_predictions,
        ),
        run_named_judge_result(
            name="prior_fusion_full",
            eval_scope="full",
            ground_truth_records=ground_truth_records,
            predicted_statuses=prior_fusion_predictions,
        ),
        run_named_judge_result(
            name="vision_gray_zone",
            eval_scope="gray_zone",
            ground_truth_records=gray_zone_records,
            predicted_statuses=vision_predictions,
        ),
        run_named_judge_result(
            name="prior_fusion_gray_zone",
            eval_scope="gray_zone",
            ground_truth_records=gray_zone_records,
            predicted_statuses=prior_fusion_predictions,
        ),
    ]

    run_config = {
        "experiment": args.output_dir.name,
        "fusion_policy_version": PRIOR_FUSION_POLICY_VERSION,
        "threshold_mode": (
            "threshold_policy_json"
            if threshold_policy_json is not None
            else "checkpoint_default"
        ),
        "threshold_policy_version": threshold_policy_version,
        "threshold_policy_json": (
            str(threshold_policy_json) if threshold_policy_json is not None else None
        ),
        "split": args.split,
        "cohort_root": str(cohort_root),
        "views_csv": str(args.views_csv),
        "study_labels_csv": str(args.study_labels_csv),
        "dicom_root": str(dicom_root),
        "checkpoint": str(checkpoint),
        "vector_db_dir": str(vector_db_dir),
        "collection_name": args.collection_name,
        "gray_zone_margin": args.gray_zone_margin,
        "retrieval_top_k": args.retrieval_top_k,
        "study_count": len(study_outputs),
        "ground_truth_rows": len(ground_truth_records),
        "gray_zone_rows": len(gray_zone_records),
    }
    judge_payload = {
        **run_config,
        "judge_runs": [named_judge_summary_payload(run) for run in judge_runs],
    }

    output_dir = args.output_dir
    _write_json(output_dir / "run_config.json", run_config)
    study_outputs_to_prediction_frame(study_outputs).to_csv(
        output_dir / "vision_study_predictions.csv",
        index=False,
    )
    retrieval_prior_features_to_frame(priors_by_study).to_csv(
        output_dir / "retrieval_prior_features.csv",
        index=False,
    )
    prior_fusion_results_to_frame(fusion_results).to_csv(
        output_dir / "prior_fusion_label_predictions.csv",
        index=False,
    )
    prior_fusion_changed_cells_frame(
        ground_truth_records=ground_truth_records,
        fusion_results=fusion_results,
        retrieved_top_k=args.retrieval_top_k,
    ).to_csv(output_dir / "prior_fusion_changed_cells.csv", index=False)
    prior_fusion_change_analysis_frame(
        ground_truth_records=ground_truth_records,
        fusion_results=fusion_results,
    ).to_csv(output_dir / "prior_fusion_change_analysis.csv", index=False)
    per_label_metrics_frame(judge_runs).to_csv(
        output_dir / "per_label_metrics.csv",
        index=False,
    )
    uncertain_status_metrics_frame(judge_runs).to_csv(
        output_dir / "uncertain_status_metrics.csv",
        index=False,
    )
    status_confusion_by_label_frame(judge_runs).to_csv(
        output_dir / "status_confusion_by_label.csv",
        index=False,
    )
    _write_json(output_dir / "judge_summary.json", judge_payload)

    print(f"[PriorFusionEval] wrote outputs -> {output_dir}")
    for run in judge_payload["judge_runs"]:
        if run.get("skipped"):
            print(f"[PriorFusionEval] {run['name']}: skipped ({run['reason']})")
            continue
        macro_f1 = run.get("macro_f1")
        macro_f1_text = f"{macro_f1:.4f}" if macro_f1 is not None else "n/a"
        print(
            f"[PriorFusionEval] {run['name']}: macro_f1={macro_f1_text} "
            f"coverage={run['coverage']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
