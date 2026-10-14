"""Run RAD-DINO on the released expert-labeled CheXpert test set."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import torch

from medagentx.evaluation.chexpert_competition import (
    EXPECTED_STUDIES,
    EXPECTED_VIEWS,
    build_competition_ground_truth,
    build_competition_view_manifest,
)
from medagentx.evaluation.fusion_eval import (
    named_judge_summary_payload,
    per_label_metrics_frame,
    ranking_cells_frame,
    ranking_metrics_frame,
    ranking_summary_payload,
    run_named_judge_result,
    status_confusion_by_label_frame,
    uncertain_status_metrics_frame,
    vision_score_map,
    vision_status_map,
)
from medagentx.evaluation.ground_truth import ground_truth_record_to_row
from medagentx.labels.constants import CHEXPERT_COMPETITION_LABELS
from medagentx.vision.backend import FineTunedRadDinoBackend
from medagentx.vision.constants import DEFAULT_BATCH_SIZE, DEFAULT_NUM_WORKERS
from medagentx.vision.data import (
    build_study_inference_records,
    raster_to_pil_rgb,
)
from medagentx.vision.inference_output import study_outputs_to_prediction_frame


DEFAULT_DATASET_ROOT = Path(
    "v2/data/chexpert_competition_test/chexlocalize/CheXpert"
)
DEFAULT_EXPERT_LABELS = Path("v2/data/groundtruth.csv")
DEFAULT_CHECKPOINT = Path(
    "v2/artifacts/cohort_balanced_v1/vision/"
    "raddino_finetuned_v1_last4_blocks/best_checkpoint.pt"
)
DEFAULT_OUTPUT_DIR = Path("v2/experiments/exp14_chexpert_competition_auroc")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _require_file(path: Path, name: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{name} missing: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fine-tuned RAD-DINO model on the 500-study expert-labeled "
            "CheXpert test set and calculate the five competition AUROCs."
        )
    )
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--test-labels-csv", type=Path, default=None)
    parser.add_argument(
        "--expert-labels-csv",
        type=Path,
        default=DEFAULT_EXPERT_LABELS,
    )
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--num-workers", type=int, default=DEFAULT_NUM_WORKERS)
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
    )
    parser.add_argument("--no-mixed-precision", action="store_true")
    parser.add_argument(
        "--max-studies",
        type=int,
        default=None,
        help="Optional non-official smoke-test limit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be > 0")
    if args.num_workers < 0:
        raise ValueError("--num-workers must be >= 0")
    if args.max_studies is not None and args.max_studies <= 0:
        raise ValueError("--max-studies must be > 0")

    dataset_root: Path = args.dataset_root
    image_root = dataset_root / "test"
    test_labels_csv = args.test_labels_csv or (dataset_root / "test_labels.csv")
    expert_labels_csv: Path = args.expert_labels_csv
    checkpoint: Path = args.checkpoint
    output_dir: Path = args.output_dir

    if not image_root.is_dir():
        raise FileNotFoundError(f"CheXpert test image directory missing: {image_root}")
    _require_file(test_labels_csv, "test labels CSV")
    _require_file(expert_labels_csv, "expert ground-truth CSV")
    _require_file(checkpoint, "RAD-DINO checkpoint")

    test_labels = pd.read_csv(test_labels_csv, dtype=str)
    manifest = build_competition_view_manifest(
        test_labels,
        image_root=image_root,
    )
    full_view_count = len(manifest)
    full_study_count = int(manifest["study_key"].nunique())
    if args.max_studies is None:
        if full_view_count != EXPECTED_VIEWS or full_study_count != EXPECTED_STUDIES:
            raise ValueError(
                "Released CheXpert test-set size mismatch: "
                f"expected {EXPECTED_STUDIES} studies/{EXPECTED_VIEWS} views, got "
                f"{full_study_count} studies/{full_view_count} views"
            )

    records = build_study_inference_records(manifest)
    if args.max_studies is not None:
        records = records[: args.max_studies]
    study_keys = [record.study_key for record in records]
    selected_key_set = set(study_keys)
    selected_manifest = manifest[
        manifest["study_key"].isin(selected_key_set)
    ].copy()

    expert_labels = pd.read_csv(expert_labels_csv, dtype=str)
    ground_truth_records = build_competition_ground_truth(
        expert_labels,
        study_keys=study_keys,
    )

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")

    print(
        "[CheXpertCompetition] "
        f"studies={len(records)} views={len(selected_manifest)} device={device}",
        flush=True,
    )
    print(
        f"[CheXpertCompetition] loading checkpoint {checkpoint}",
        flush=True,
    )
    backend = FineTunedRadDinoBackend.from_checkpoint(
        checkpoint,
        device=device,
        mixed_precision=not args.no_mixed_precision,
    )

    started = time.perf_counter()
    print(
        "[CheXpertCompetition] running vision "
        f"(batch_size={args.batch_size}, num_workers={args.num_workers})",
        flush=True,
    )
    study_outputs = backend.predict_study_outputs(
        records,
        dicom_root=image_root,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        image_loader=raster_to_pil_rgb,
    )
    elapsed = time.perf_counter() - started
    print(
        f"[CheXpertCompetition] vision complete elapsed={elapsed:.1f}s",
        flush=True,
    )

    predicted_statuses = vision_status_map(study_outputs)
    predicted_scores = vision_score_map(
        study_outputs,
        labels=CHEXPERT_COMPETITION_LABELS,
    )
    official_complete = args.max_studies is None
    judge_run = run_named_judge_result(
        name="vision_full",
        eval_scope="competition_test",
        ground_truth_records=ground_truth_records,
        predicted_statuses=predicted_statuses,
        predicted_scores=predicted_scores,
        ranking_labels=CHEXPERT_COMPETITION_LABELS,
        require_two_classes_per_ranking_label=official_complete,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    selected_manifest.to_csv(output_dir / "competition_view_manifest.csv", index=False)
    pd.DataFrame(
        [ground_truth_record_to_row(record) for record in ground_truth_records]
    ).to_csv(output_dir / "competition_ground_truth.csv", index=False)
    study_outputs_to_prediction_frame(study_outputs).to_csv(
        output_dir / "vision_study_predictions.csv",
        index=False,
    )
    per_label_metrics_frame([judge_run]).to_csv(
        output_dir / "per_label_metrics.csv",
        index=False,
    )
    ranking_metrics_frame([judge_run]).to_csv(
        output_dir / "ranking_metrics.csv",
        index=False,
    )
    ranking_cells_frame([judge_run]).to_csv(
        output_dir / "ranking_cells.csv",
        index=False,
    )
    uncertain_status_metrics_frame([judge_run]).to_csv(
        output_dir / "uncertain_status_metrics.csv",
        index=False,
    )
    status_confusion_by_label_frame([judge_run]).to_csv(
        output_dir / "status_confusion_by_label.csv",
        index=False,
    )

    ranking_summary = ranking_summary_payload([judge_run])
    ranking_summary.update(
        {
            "competition_labels": list(CHEXPERT_COMPETITION_LABELS),
            "official_protocol_complete": official_complete,
            "study_count": len(study_outputs),
            "view_count": len(selected_manifest),
            "score_source": "RAD-DINO study probability",
            "ground_truth_source": "expert majority vote",
        }
    )
    _write_json(output_dir / "ranking_summary.json", ranking_summary)

    judge_summary = {
        "experiment": "exp14_chexpert_competition_auroc",
        "official_protocol_complete": official_complete,
        "runs": [named_judge_summary_payload(judge_run)],
    }
    _write_json(output_dir / "judge_summary.json", judge_summary)
    _write_json(
        output_dir / "run_config.json",
        {
            "experiment": "exp14_chexpert_competition_auroc",
            "dataset_root": str(dataset_root),
            "image_root": str(image_root),
            "test_labels_csv": str(test_labels_csv),
            "expert_labels_csv": str(expert_labels_csv),
            "checkpoint": str(checkpoint),
            "output_dir": str(output_dir),
            "batch_size": args.batch_size,
            "num_workers": args.num_workers,
            "device": str(device),
            "mixed_precision": not args.no_mixed_precision,
            "max_studies": args.max_studies,
            "study_count": len(study_outputs),
            "view_count": len(selected_manifest),
            "elapsed_seconds": elapsed,
            "official_protocol_complete": official_complete,
        },
    )

    if judge_run.result is None or judge_run.result.ranking_result is None:
        raise RuntimeError("Competition ranking result was not produced")
    ranking = judge_run.result.ranking_result
    for metrics in ranking.per_label_metrics:
        auroc = f"{metrics.auroc:.4f}" if metrics.auroc is not None else "n/a"
        print(
            f"[CheXpertCompetition] {metrics.label}: AUROC={auroc} "
            f"n={metrics.evaluated} positive={metrics.positive} "
            f"negative={metrics.negative}",
            flush=True,
        )
    macro = (
        f"{ranking.macro_auroc:.4f}"
        if ranking.macro_auroc is not None
        else "n/a"
    )
    print(f"[CheXpertCompetition] macro AUROC={macro}", flush=True)
    print(f"[CheXpertCompetition] wrote results -> {output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
