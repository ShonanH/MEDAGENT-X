"""Run offline vision-only vs fusion evaluation with Judge metrics."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd
import torch

from medagentx.data.balanced_constants import DEFAULT_BALANCED_COHORT_ROOT
from medagentx.evaluation.fusion_eval import (
    filter_gray_zone_ground_truth,
    fusion_change_analysis_frame,
    fusion_changed_cells_frame,
    fusion_results_to_frame,
    fusion_status_map,
    named_judge_summary_payload,
    per_label_metrics_frame,
    run_named_judge_result,
    status_confusion_by_label_frame,
    study_labels_to_ground_truth,
    study_outputs_by_key,
    uncertain_status_metrics_frame,
    vision_status_map,
)
from medagentx.reasoning.constants import (
    DEFAULT_FUSION_SUBDIR,
    FUSION_RETRIEVAL_TOP_K,
    FUSION_POLICY_VERSION,
    GRAY_ZONE_MARGIN,
)
from medagentx.reasoning.fuse import fuse_study_labels
from medagentx.reasoning.retrieve import (
    default_retrieval_chroma_dir,
    open_retrieval_collection,
    retrieve_similar_reports,
)
from medagentx.reasoning.vision_adapter import fusion_vision_inputs
from medagentx.retrieval.constants import DEFAULT_COLLECTION_NAME
from medagentx.vision.backend import FineTunedRadDinoBackend
from medagentx.vision.constants import DEFAULT_BATCH_SIZE, DEFAULT_NUM_WORKERS
from medagentx.vision.data import build_study_inference_records
from medagentx.vision.inference_output import study_outputs_to_prediction_frame


def build_parser() -> argparse.ArgumentParser:
    """Build the fusion evaluation command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Run vision + retrieval + label fusion on a split and compare "
            "vision-only vs fusion with the offline Judge."
        )
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path(DEFAULT_BALANCED_COHORT_ROOT),
    )
    parser.add_argument("--views-csv", type=Path, default=None)
    parser.add_argument("--study-labels-csv", type=Path, default=None)
    parser.add_argument("--dicom-root", type=Path, default=None)
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument(
        "--vector-db-dir",
        type=Path,
        default=None,
        help="Defaults to cohort-root/retrieval/raddino_train_v1/chroma",
    )
    parser.add_argument(
        "--collection-name",
        default=DEFAULT_COLLECTION_NAME,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Defaults to cohort-root/{DEFAULT_FUSION_SUBDIR}/<split>",
    )
    parser.add_argument(
        "--split",
        choices=("val", "test"),
        default="test",
        help="Evaluation split. Train is index-only and excluded here.",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--num-workers", type=int, default=DEFAULT_NUM_WORKERS)
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
    )
    parser.add_argument("--no-mixed-precision", action="store_true")
    parser.add_argument(
        "--gray-zone-margin",
        type=float,
        default=GRAY_ZONE_MARGIN,
    )
    parser.add_argument(
        "--max-studies",
        type=int,
        default=None,
        help="Optional smoke-test limit on the number of studies.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Log retrieval/fusion progress every N studies.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the locked vision -> retrieval -> fusion evaluation pipeline."""
    args = build_parser().parse_args(argv)
    if args.batch_size <= 0:
        raise ValueError("batch-size must be > 0")
    if args.num_workers < 0:
        raise ValueError("num-workers must be >= 0")
    if args.gray_zone_margin < 0:
        raise ValueError("gray-zone-margin must be >= 0")
    if args.progress_every <= 0:
        raise ValueError("progress-every must be > 0")
    if args.max_studies is not None and args.max_studies <= 0:
        raise ValueError("max-studies must be > 0")

    cohort_root: Path = args.cohort_root
    views_csv = args.views_csv or (cohort_root / "splits" / "view_splits.csv")
    study_labels_csv = args.study_labels_csv or (
        cohort_root / "study_label_table.csv"
    )
    dicom_root = args.dicom_root or (cohort_root / "dicom_train")
    checkpoint_path = args.checkpoint or (
        cohort_root
        / "vision"
        / "raddino_finetuned_v1"
        / "best_checkpoint.pt"
    )
    vector_db_dir = args.vector_db_dir or default_retrieval_chroma_dir(cohort_root)
    output_dir = args.output_dir or (
        cohort_root / DEFAULT_FUSION_SUBDIR / args.split
    )

    for path in (views_csv, study_labels_csv, checkpoint_path, vector_db_dir):
        if not path.exists():
            raise FileNotFoundError(f"Required fusion-eval artifact missing: {path}")
    if not dicom_root.exists():
        raise FileNotFoundError(f"DICOM root missing: {dicom_root}")

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")

    print(
        f"[FusionEval] split={args.split} policy={FUSION_POLICY_VERSION} "
        f"device={device} gray_margin={args.gray_zone_margin}"
    )
    print(f"[FusionEval] loading views from {views_csv}")
    views = pd.read_csv(views_csv, dtype=str)
    records = build_study_inference_records(views, split=args.split)
    if args.max_studies is not None:
        records = records[: args.max_studies]
    if not records:
        raise ValueError(f"No studies found for split={args.split!r}")

    print(
        f"[FusionEval] loading checkpoint {checkpoint_path} onto {device}"
    )
    backend = FineTunedRadDinoBackend.from_checkpoint(
        checkpoint_path,
        device=device,
        mixed_precision=not args.no_mixed_precision,
    )

    vision_start = time.perf_counter()
    print(
        f"[FusionEval] running vision on {len(records)} studies "
        f"(batch_size={args.batch_size}, num_workers={args.num_workers})"
    )
    study_outputs = backend.predict_study_outputs(
        records,
        dicom_root=dicom_root,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
    )
    vision_elapsed = time.perf_counter() - vision_start
    print(
        f"[FusionEval] vision complete studies={len(study_outputs)} "
        f"elapsed={vision_elapsed:.1f}s"
    )

    print(f"[FusionEval] opening retrieval collection at {vector_db_dir}")
    collection = open_retrieval_collection(
        vector_db_dir,
        collection_name=args.collection_name,
    )

    fusion_results = []
    retrieval_start = time.perf_counter()
    total_studies = len(study_outputs)
    for index, study_output in enumerate(study_outputs, start=1):
        retrieved = retrieve_similar_reports(collection, study_output)
        fusion_results.append(
            fuse_study_labels(
                fusion_vision_inputs(study_output),
                retrieved,
                study_key=study_output.study_key,
                margin=args.gray_zone_margin,
            )
        )
        if index == 1 or index % args.progress_every == 0 or index == total_studies:
            elapsed = time.perf_counter() - retrieval_start
            print(
                f"[FusionEval] fused {index}/{total_studies} studies "
                f"elapsed={elapsed:.1f}s"
            )

    study_keys = [output.study_key for output in study_outputs]
    print(f"[FusionEval] loading ground truth from {study_labels_csv}")
    study_labels = pd.read_csv(study_labels_csv, dtype=str)
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
    fusion_predictions = fusion_status_map(fusion_results)

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
    judge_payload = {
        "split": args.split,
        "fusion_policy_version": FUSION_POLICY_VERSION,
        "gray_zone_margin": args.gray_zone_margin,
        "study_count": len(study_outputs),
        "ground_truth_rows": len(ground_truth_records),
        "gray_zone_rows": len(gray_zone_records),
        "runs": [named_judge_summary_payload(run) for run in judge_runs],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    vision_csv = output_dir / "vision_study_predictions.csv"
    fusion_csv = output_dir / "fusion_label_predictions.csv"
    judge_json = output_dir / "judge_summary.json"
    per_label_metrics_csv = output_dir / "per_label_metrics.csv"
    fusion_change_analysis_csv = output_dir / "fusion_change_analysis.csv"
    fusion_changed_cells_csv = output_dir / "fusion_changed_cells.csv"
    uncertain_status_metrics_csv = output_dir / "uncertain_status_metrics.csv"
    status_confusion_csv = output_dir / "status_confusion_by_label.csv"

    study_outputs_to_prediction_frame(study_outputs).to_csv(vision_csv, index=False)
    fusion_results_to_frame(fusion_results).to_csv(fusion_csv, index=False)
    per_label_metrics_frame(judge_runs).to_csv(per_label_metrics_csv, index=False)
    fusion_change_analysis_frame(
        ground_truth_records=ground_truth_records,
        fusion_results=fusion_results,
    ).to_csv(fusion_change_analysis_csv, index=False)
    fusion_changed_cells_frame(
        ground_truth_records=ground_truth_records,
        fusion_results=fusion_results,
        retrieved_top_k=FUSION_RETRIEVAL_TOP_K,
    ).to_csv(fusion_changed_cells_csv, index=False)
    uncertain_status_metrics_frame(judge_runs).to_csv(
        uncertain_status_metrics_csv,
        index=False,
    )
    status_confusion_by_label_frame(judge_runs).to_csv(
        status_confusion_csv,
        index=False,
    )
    judge_json.write_text(json.dumps(judge_payload, indent=2, sort_keys=True) + "\n")

    print(f"[FusionEval] wrote vision predictions -> {vision_csv}")
    print(f"[FusionEval] wrote fusion predictions -> {fusion_csv}")
    print(f"[FusionEval] wrote judge summary -> {judge_json}")
    print(f"[FusionEval] wrote per-label metrics -> {per_label_metrics_csv}")
    print(
        "[FusionEval] wrote fusion change analysis -> "
        f"{fusion_change_analysis_csv}"
    )
    print(f"[FusionEval] wrote fusion changed cells -> {fusion_changed_cells_csv}")
    print(
        "[FusionEval] wrote uncertain status metrics -> "
        f"{uncertain_status_metrics_csv}"
    )
    print(f"[FusionEval] wrote status confusion -> {status_confusion_csv}")
    for run in judge_payload["runs"]:
        if run.get("skipped"):
            print(f"[FusionEval] {run['name']}: skipped ({run['reason']})")
            continue
        macro_f1 = run.get("macro_f1")
        macro_f1_text = f"{macro_f1:.4f}" if macro_f1 is not None else "n/a"
        print(
            f"[FusionEval] {run['name']}: macro_f1={macro_f1_text} "
            f"coverage={run['coverage']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
