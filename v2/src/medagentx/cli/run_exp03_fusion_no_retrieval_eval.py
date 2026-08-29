"""Run Experiment 3: gray-zone uncertainty fusion without retrieval evidence."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

from medagentx.cli.experiment_eval_utils import (
    fusion_change_analysis_frame,
    fusion_changed_cells_frame,
    fusion_results_to_frame,
    fusion_status_map,
    gray_zone_ground_truth_from_vision_frame,
    named_judge_summary_payload,
    parse_label_status,
    require_existing_file,
    require_vision_prediction_columns,
    run_named_judge_result,
    study_labels_to_ground_truth,
    vision_status_map_from_frame,
    write_judge_artifacts,
    write_json,
)
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label
from medagentx.labels.statuses import LabelStatus
from medagentx.reasoning.constants import FUSION_POLICY_VERSION, GRAY_ZONE_MARGIN
from medagentx.reasoning.fuse import (
    FusedLabelPrediction,
    FusionStudyResult,
    VisionLabelPrediction,
    is_gray_zone,
)


DEFAULT_EXPERIMENT_DIR = Path("v2/experiments/exp03_fusion_no_retrieval")
DEFAULT_SOURCE_VISION_CSV = Path(
    "v2/experiments/exp01_vision_only/vision_study_predictions.csv"
)
DEFAULT_STUDY_LABELS_CSV = Path(
    "v2/artifactsLocal/val_last4_blocks_0818/val/study_label_table.csv"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the no-retrieval gray-zone uncertainty fusion variant. "
            "Labels inside the RAD-DINO gray zone are set to uncertain."
        )
    )
    parser.add_argument(
        "--source-vision-csv",
        type=Path,
        default=DEFAULT_SOURCE_VISION_CSV,
        help="Vision-only prediction CSV to reuse as the experiment input.",
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
        help="Directory where experiment artifacts will be written.",
    )
    parser.add_argument(
        "--gray-zone-margin",
        type=float,
        default=GRAY_ZONE_MARGIN,
    )
    return parser


def _run_gray_zone_uncertainty_fusion(
    vision_frame: pd.DataFrame,
    *,
    margin: float,
) -> list[FusionStudyResult]:
    require_vision_prediction_columns(vision_frame)
    fusion_results: list[FusionStudyResult] = []
    for row in vision_frame.itertuples(index=False):
        study_key = str(row.study_key)
        fused_labels: list[FusedLabelPrediction] = []
        for label in DISEASE_LABELS:
            slug = snake_label(label)
            vision_prediction = VisionLabelPrediction(
                label=label,
                probability=float(getattr(row, f"probability_{slug}")),
                threshold=float(getattr(row, f"threshold_{slug}")),
                status=parse_label_status(getattr(row, f"status_{slug}")),
            )
            gray_zone = is_gray_zone(
                vision_prediction.probability,
                vision_prediction.threshold,
                margin=margin,
            )
            fused_status = (
                LabelStatus.UNCERTAIN
                if gray_zone
                else vision_prediction.vision_status
            )
            fused_labels.append(
                FusedLabelPrediction(
                    label=label,
                    vision_status=vision_prediction.vision_status,
                    fused_status=fused_status,
                    probability=vision_prediction.probability,
                    threshold=vision_prediction.threshold,
                    in_gray_zone=gray_zone,
                    positive_count=0,
                    negative_count=0,
                    refinement_reason=(
                        "gray-zone label marked uncertain without retrieval"
                        if gray_zone
                        else "vision kept (strong zone)"
                    ),
                )
            )
        fusion_results.append(
            FusionStudyResult(
                study_key=study_key,
                fusion_policy_version="gray_zone_uncertainty_no_retrieval_v1",
                labels=tuple(fused_labels),
            )
        )
    return fusion_results


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.gray_zone_margin < 0:
        raise ValueError("--gray-zone-margin must be >= 0")
    require_existing_file(args.source_vision_csv, name="source vision CSV")
    require_existing_file(args.study_labels_csv, name="study labels CSV")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    vision_csv = args.output_dir / "vision_study_predictions.csv"
    shutil.copy2(args.source_vision_csv, vision_csv)

    vision_frame = pd.read_csv(vision_csv, dtype=str)
    study_labels = pd.read_csv(args.study_labels_csv, dtype=str)
    study_keys = vision_frame["study_key"].astype(str).tolist()

    fusion_results = _run_gray_zone_uncertainty_fusion(
        vision_frame,
        margin=args.gray_zone_margin,
    )
    fusion_results_to_frame(fusion_results).to_csv(
        args.output_dir / "fusion_label_predictions.csv",
        index=False,
    )

    ground_truth_records = study_labels_to_ground_truth(
        study_labels,
        study_keys=study_keys,
    )
    gray_zone_records = gray_zone_ground_truth_from_vision_frame(
        ground_truth_records,
        vision_frame,
        margin=args.gray_zone_margin,
    )
    vision_predictions = vision_status_map_from_frame(vision_frame)
    fusion_predictions = fusion_status_map(fusion_results)

    judge_runs = [
        run_named_judge_result(
            name="vision_full",
            eval_scope="full",
            ground_truth_records=ground_truth_records,
            predicted_statuses=vision_predictions,
        ),
        run_named_judge_result(
            name="fusion_no_retrieval_full",
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
            name="fusion_no_retrieval_gray_zone",
            eval_scope="gray_zone",
            ground_truth_records=gray_zone_records,
            predicted_statuses=fusion_predictions,
        ),
    ]

    summary = {
        "experiment": "exp03_fusion_no_retrieval",
        "source_vision_csv": str(args.source_vision_csv),
        "study_labels_csv": str(args.study_labels_csv),
        "fusion_policy_version": "gray_zone_uncertainty_no_retrieval_v1",
        "base_fusion_policy_version": FUSION_POLICY_VERSION,
        "gray_zone_margin": args.gray_zone_margin,
        "retrieval_enabled": False,
        "retrieved_top_k": 0,
        "gray_zone_action": "set_fused_status_to_uncertain",
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
    fusion_change_analysis_frame(
        ground_truth_records=ground_truth_records,
        fusion_results=fusion_results,
    ).to_csv(args.output_dir / "fusion_change_analysis.csv", index=False)
    fusion_changed_cells_frame(
        ground_truth_records=ground_truth_records,
        fusion_results=fusion_results,
        retrieved_top_k=0,
    ).to_csv(args.output_dir / "fusion_changed_cells.csv", index=False)
    write_json(
        args.output_dir / "run_config.json",
        {
            "experiment": "exp03_fusion_no_retrieval",
            "source_vision_csv": str(args.source_vision_csv),
            "study_labels_csv": str(args.study_labels_csv),
            "output_dir": str(args.output_dir),
            "fusion_policy_version": "gray_zone_uncertainty_no_retrieval_v1",
            "base_fusion_policy_version": FUSION_POLICY_VERSION,
            "gray_zone_margin": args.gray_zone_margin,
            "retrieval_enabled": False,
            "retrieved_top_k": 0,
            "gray_zone_action": "set_fused_status_to_uncertain",
        },
    )
    print(f"[Exp03FusionNoRetrievalEval] wrote artifacts -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
