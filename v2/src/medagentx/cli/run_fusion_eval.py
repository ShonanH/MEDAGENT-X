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
    study_labels_to_ground_truth_strata,
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
from medagentx.vision.cache import sha256_file
from medagentx.vision.constants import DEFAULT_BATCH_SIZE, DEFAULT_NUM_WORKERS
from medagentx.vision.data import build_study_inference_records
from medagentx.vision.inference_output import (
    load_vision_study_outputs,
    save_vision_study_outputs,
    study_outputs_to_prediction_frame,
)


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
        "--threshold-policy-json",
        type=Path,
        default=None,
        help=(
            "Optional threshold_policy_v2.json. When provided, selected_thresholds "
            "override checkpoint thresholds during vision prediction."
        ),
    )
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
        "--model-ready-cache-root",
        type=Path,
        default=None,
        help=(
            "Optional validated model-ready image cache. When provided, "
            "vision inference uses the GPU-resident cache instead of DICOM reads."
        ),
    )
    parser.add_argument(
        "--gpu-cache-preload-chunk-size",
        type=int,
        default=64,
        help="Views copied to GPU per model-ready-cache preload chunk.",
    )
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
        "--retrieval-top-k",
        type=int,
        default=FUSION_RETRIEVAL_TOP_K,
        help=(
            "Number of similar train studies retrieved per query. "
            f"Default preserves the locked fusion setting: {FUSION_RETRIEVAL_TOP_K}."
        ),
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
    parser.add_argument(
        "--vision-outputs-cache",
        type=Path,
        default=None,
        help=(
            "Lossless probabilities/embedding cache. Defaults to "
            "output-dir/vision_study_outputs.npz."
        ),
    )
    parser.add_argument(
        "--reuse-vision-outputs",
        action="store_true",
        help="Skip vision inference and reuse a strictly compatible cache.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the locked vision -> retrieval -> fusion evaluation pipeline."""
    args = build_parser().parse_args(argv)
    if args.batch_size <= 0:
        raise ValueError("batch-size must be > 0")
    if args.num_workers < 0:
        raise ValueError("num-workers must be >= 0")
    if args.gpu_cache_preload_chunk_size <= 0:
        raise ValueError("gpu-cache-preload-chunk-size must be > 0")
    if args.gray_zone_margin < 0:
        raise ValueError("gray-zone-margin must be >= 0")
    if args.retrieval_top_k <= 0:
        raise ValueError("retrieval-top-k must be > 0")
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
    vision_outputs_cache = args.vision_outputs_cache or (
        output_dir / "vision_study_outputs.npz"
    )

    for path in (views_csv, study_labels_csv, checkpoint_path, vector_db_dir):
        if not path.exists():
            raise FileNotFoundError(f"Required fusion-eval artifact missing: {path}")
    if not dicom_root.exists():
        raise FileNotFoundError(f"DICOM root missing: {dicom_root}")
    if (
        args.model_ready_cache_root is not None
        and not args.model_ready_cache_root.is_dir()
    ):
        raise FileNotFoundError(
            "Model-ready cache root missing: "
            f"{args.model_ready_cache_root}"
        )
    threshold_overrides = None
    threshold_policy_version = None
    if args.threshold_policy_json is not None:
        if not args.threshold_policy_json.exists():
            raise FileNotFoundError(
                f"Threshold policy JSON missing: {args.threshold_policy_json}"
            )
        threshold_policy = json.loads(args.threshold_policy_json.read_text())
        selected_thresholds = threshold_policy.get("selected_thresholds")
        if not isinstance(selected_thresholds, dict):
            raise ValueError(
                "Threshold policy JSON must contain selected_thresholds object"
            )
        threshold_overrides = {
            str(label): float(value)
            for label, value in selected_thresholds.items()
        }
        threshold_policy_version = threshold_policy.get("threshold_policy_version")

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")

    print(
        f"[FusionEval] split={args.split} policy={FUSION_POLICY_VERSION} "
        f"device={device} gray_margin={args.gray_zone_margin} "
        f"retrieval_top_k={args.retrieval_top_k}"
    )
    if args.threshold_policy_json is not None:
        print(
            "[FusionEval] using threshold policy "
            f"{threshold_policy_version or 'unknown'} -> "
            f"{args.threshold_policy_json}"
        )
    print(f"[FusionEval] loading views from {views_csv}")
    views = pd.read_csv(views_csv, dtype=str)
    records = build_study_inference_records(views, split=args.split)
    if args.max_studies is not None:
        records = records[: args.max_studies]
    if not records:
        raise ValueError(f"No studies found for split={args.split!r}")

    vision_start = time.perf_counter()
    checkpoint_sha256 = sha256_file(checkpoint_path)
    if args.reuse_vision_outputs:
        print(f"[FusionEval] reusing vision outputs from {vision_outputs_cache}")
        study_outputs, vision_cache_metadata = load_vision_study_outputs(
            vision_outputs_cache
        )
        expected_metadata = {
            "checkpoint_sha256": checkpoint_sha256,
            "split": args.split,
            "threshold_policy_version": threshold_policy_version,
            "threshold_overrides": threshold_overrides,
        }
        mismatches = {
            key: (vision_cache_metadata.get(key), expected)
            for key, expected in expected_metadata.items()
            if vision_cache_metadata.get(key) != expected
        }
        expected_study_keys = [record.study_key for record in records]
        actual_study_keys = [output.study_key for output in study_outputs]
        if actual_study_keys != expected_study_keys:
            mismatches["study_keys"] = (
                f"cache_count={len(actual_study_keys)}",
                f"expected_count={len(expected_study_keys)}",
            )
        if mismatches:
            raise ValueError(
                "Refusing incompatible vision output cache reuse: "
                f"{mismatches}"
            )
    else:
        print(
            f"[FusionEval] loading checkpoint {checkpoint_path} onto {device}"
        )
        backend = FineTunedRadDinoBackend.from_checkpoint(
            checkpoint_path,
            device=device,
            mixed_precision=not args.no_mixed_precision,
        )
        print(
            f"[FusionEval] running vision on {len(records)} studies "
            f"(batch_size={args.batch_size}, num_workers={args.num_workers})"
        )
        if args.model_ready_cache_root is None:
            study_outputs = backend.predict_study_outputs(
                records,
                dicom_root=dicom_root,
                batch_size=args.batch_size,
                num_workers=args.num_workers,
                threshold_overrides=threshold_overrides,
            )
        else:
            study_outputs = backend.predict_study_outputs_from_model_ready_cache(
                records,
                cache_root=args.model_ready_cache_root,
                cohort_root=cohort_root,
                dicom_root=dicom_root,
                view_splits_csv=views_csv,
                batch_size=args.batch_size,
                preload_chunk_size=args.gpu_cache_preload_chunk_size,
                threshold_overrides=threshold_overrides,
            )
        save_vision_study_outputs(
            vision_outputs_cache,
            study_outputs,
            metadata={
                "checkpoint": str(checkpoint_path),
                "checkpoint_sha256": checkpoint_sha256,
                "split": args.split,
                "threshold_policy_version": threshold_policy_version,
                "threshold_overrides": threshold_overrides,
            },
        )
        print(
            "[FusionEval] saved reusable vision outputs -> "
            f"{vision_outputs_cache}"
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
        retrieved = retrieve_similar_reports(
            collection,
            study_output,
            top_k=args.retrieval_top_k,
        )
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
    ground_truth = study_labels_to_ground_truth_strata(
        study_labels,
        study_keys=study_keys,
    )
    outputs_by_key = study_outputs_by_key(study_outputs)

    vision_predictions = vision_status_map(study_outputs)
    fusion_predictions = fusion_status_map(fusion_results)

    policy_records = {
        "explicit": ground_truth.explicit,
        "no_finding_derived": ground_truth.no_finding_derived,
        "combined_training_policy": ground_truth.combined,
    }
    judge_runs = []
    gray_zone_counts: dict[str, int] = {}
    for policy_name, full_records in policy_records.items():
        gray_records = filter_gray_zone_ground_truth(
            full_records,
            outputs_by_key,
            margin=args.gray_zone_margin,
        )
        gray_zone_counts[policy_name] = len(gray_records)
        for scope, scope_records in (
            ("full", full_records),
            ("gray_zone", gray_records),
        ):
            for prediction_name, predictions in (
                ("vision", vision_predictions),
                ("fusion", fusion_predictions),
            ):
                judge_runs.append(
                    run_named_judge_result(
                        name=f"{prediction_name}_{policy_name}_{scope}",
                        eval_scope=scope,
                        ground_truth_records=scope_records,
                        predicted_statuses=predictions,
                        ground_truth_policy=policy_name,
                    )
                )
    judge_payload = {
        "split": args.split,
        "fusion_policy_version": FUSION_POLICY_VERSION,
        "threshold_policy_version": threshold_policy_version,
        "threshold_policy_json": (
            str(args.threshold_policy_json)
            if args.threshold_policy_json is not None
            else None
        ),
        "gray_zone_margin": args.gray_zone_margin,
        "retrieval_top_k": args.retrieval_top_k,
        "model_ready_cache_root": (
            str(args.model_ready_cache_root)
            if args.model_ready_cache_root is not None
            else None
        ),
        "vision_outputs_cache": str(vision_outputs_cache),
        "vision_outputs_reused": args.reuse_vision_outputs,
        "checkpoint_sha256": checkpoint_sha256,
        "study_count": len(study_outputs),
        "ground_truth_rows": {
            name: len(records) for name, records in policy_records.items()
        },
        "gray_zone_rows": gray_zone_counts,
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

    output_dir.mkdir(parents=True, exist_ok=True)
    vision_csv = output_dir / "vision_study_predictions.csv"
    fusion_csv = output_dir / "fusion_label_predictions.csv"
    judge_json = output_dir / "judge_summary.json"
    per_label_metrics_csv = output_dir / "per_label_metrics.csv"
    fusion_change_analysis_csv = output_dir / "fusion_change_analysis.csv"
    fusion_changed_cells_csv = output_dir / "fusion_changed_cells.csv"
    uncertain_status_metrics_csv = output_dir / "uncertain_status_metrics.csv"
    status_confusion_csv = output_dir / "status_confusion_by_label.csv"
    ground_truth_provenance_csv = output_dir / "ground_truth_provenance.csv"

    study_outputs_to_prediction_frame(study_outputs).to_csv(vision_csv, index=False)
    fusion_results_to_frame(fusion_results).to_csv(fusion_csv, index=False)
    per_label_metrics_frame(judge_runs).to_csv(per_label_metrics_csv, index=False)
    change_analysis_frames = []
    changed_cell_frames = []
    for policy_name, records_for_policy in policy_records.items():
        change_frame = fusion_change_analysis_frame(
            ground_truth_records=records_for_policy,
            fusion_results=fusion_results,
        )
        change_frame.insert(0, "ground_truth_policy", policy_name)
        change_analysis_frames.append(change_frame)
        changed_frame = fusion_changed_cells_frame(
            ground_truth_records=records_for_policy,
            fusion_results=fusion_results,
            retrieved_top_k=args.retrieval_top_k,
        )
        changed_frame.insert(0, "ground_truth_policy", policy_name)
        changed_cell_frames.append(changed_frame)
    pd.concat(change_analysis_frames, ignore_index=True).to_csv(
        fusion_change_analysis_csv,
        index=False,
    )
    pd.concat(changed_cell_frames, ignore_index=True).to_csv(
        fusion_changed_cells_csv,
        index=False,
    )
    uncertain_status_metrics_frame(judge_runs).to_csv(
        uncertain_status_metrics_csv,
        index=False,
    )
    status_confusion_by_label_frame(judge_runs).to_csv(
        status_confusion_csv,
        index=False,
    )
    ground_truth.provenance.to_csv(ground_truth_provenance_csv, index=False)
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
    print(
        "[FusionEval] wrote ground-truth provenance -> "
        f"{ground_truth_provenance_csv}"
    )
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
