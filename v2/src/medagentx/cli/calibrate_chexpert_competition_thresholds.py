"""Calibrate competition-label vision thresholds on CheXpert validation."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time
from typing import Any

import pandas as pd
import torch

from medagentx.cli.run_exp05_llm_fusion_with_retrieval_graph import (
    DEFAULT_LAST4_CHECKPOINT,
    _load_threshold_overrides,
)
from medagentx.evaluation.chexpert_competition import (
    EXPECTED_VALIDATION_STUDIES,
    EXPECTED_VALIDATION_VIEWS,
    build_competition_validation_ground_truth,
    build_competition_view_manifest,
    select_competition_f1_threshold,
)
from medagentx.evaluation.ground_truth import ground_truth_record_to_row
from medagentx.labels.constants import CHEXPERT_COMPETITION_LABELS
from medagentx.vision.backend import FineTunedRadDinoBackend
from medagentx.vision.constants import DEFAULT_BATCH_SIZE, DEFAULT_NUM_WORKERS
from medagentx.vision.data import build_study_inference_records, raster_to_pil_rgb
from medagentx.vision.inference_output import study_outputs_to_prediction_frame


DEFAULT_DATASET_ROOT = Path(
    "v2/data/chexpert_competition_test/chexlocalize/CheXpert"
)
DEFAULT_CURRENT_THRESHOLD_POLICY = Path(
    "v2/artifacts/cohort_balanced_v1/reasoning/fusion_eval_v1/"
    "val_last4_blocks/val/threshold_tuning/threshold_policy_v2.json"
)
DEFAULT_OUTPUT_DIR = Path(
    "v2/experiments/exp16_chexpert_competition_val_thresholds"
)
POLICY_VERSION = "chexpert_competition_validation_f1_v1"
OUTPUT_FILENAMES = (
    "run_config.json",
    "competition_val_manifest.csv",
    "competition_val_ground_truth.csv",
    "vision_study_predictions.csv",
    "threshold_tuning_report.csv",
    "threshold_policy_v2.json",
)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _require_file(path: Path, name: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{name} missing: {path}")


def _prepare_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [output_dir / name for name in OUTPUT_FILENAMES]
    existing = [path for path in existing if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "Calibration outputs already exist; pass --overwrite:\n"
            + "\n".join(str(path) for path in existing)
        )
    if overwrite:
        for path in existing:
            path.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run RAD-DINO on the 200-study expert-labeled CheXpert validation "
            "set and select one F1-optimal threshold per competition label."
        )
    )
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--val-labels-csv", type=Path, default=None)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_LAST4_CHECKPOINT)
    parser.add_argument(
        "--current-threshold-policy-json",
        type=Path,
        default=DEFAULT_CURRENT_THRESHOLD_POLICY,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--num-workers", type=int, default=DEFAULT_NUM_WORKERS)
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
    )
    parser.add_argument("--no-mixed-precision", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be > 0")
    if args.num_workers < 0:
        raise ValueError("--num-workers must be >= 0")

    image_root = args.dataset_root / "val"
    val_labels_csv = args.val_labels_csv or (args.dataset_root / "val_labels.csv")
    if not image_root.is_dir():
        raise FileNotFoundError(
            f"CheXpert validation image directory missing: {image_root}"
        )
    _require_file(val_labels_csv, "validation labels CSV")
    _require_file(args.checkpoint, "RAD-DINO checkpoint")
    _require_file(args.current_threshold_policy_json, "current threshold policy")
    _prepare_output_dir(args.output_dir, overwrite=args.overwrite)

    val_labels = pd.read_csv(val_labels_csv, dtype=str)
    manifest = build_competition_view_manifest(
        val_labels,
        image_root=image_root,
        source_split="val",
    )
    study_count = int(manifest["study_key"].nunique())
    if (
        len(manifest) != EXPECTED_VALIDATION_VIEWS
        or study_count != EXPECTED_VALIDATION_STUDIES
    ):
        raise ValueError(
            "Released CheXpert validation size mismatch: expected "
            f"{EXPECTED_VALIDATION_STUDIES} studies/{EXPECTED_VALIDATION_VIEWS} views, "
            f"got {study_count} studies/{len(manifest)} views"
        )

    records = build_study_inference_records(manifest)
    study_keys = [record.study_key for record in records]
    ground_truth = build_competition_validation_ground_truth(
        val_labels,
        study_keys=study_keys,
    )
    ground_truth_map = {
        (record.study_key, record.label): int(
            record.ground_truth_status.value == "present"
        )
        for record in ground_truth
    }

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")
    current_thresholds = _load_threshold_overrides(
        args.current_threshold_policy_json
    )
    backend = FineTunedRadDinoBackend.from_checkpoint(
        args.checkpoint,
        device=device,
        mixed_precision=not args.no_mixed_precision,
    )

    print(
        "[CompetitionThresholds] "
        f"running vision on {len(records)} studies/{len(manifest)} views "
        f"(batch_size={args.batch_size}, num_workers={args.num_workers})",
        flush=True,
    )
    started = time.perf_counter()
    study_outputs = backend.predict_study_outputs(
        records,
        dicom_root=image_root,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        threshold_overrides=current_thresholds,
        image_loader=raster_to_pil_rgb,
    )
    elapsed = time.perf_counter() - started
    print(
        f"[CompetitionThresholds] vision complete elapsed={elapsed:.1f}s",
        flush=True,
    )

    output_by_key = {output.study_key: output for output in study_outputs}
    report_rows: list[dict[str, Any]] = []
    selected_thresholds: dict[str, float] = {}
    for label in CHEXPERT_COMPETITION_LABELS:
        probabilities = [
            output_by_key[key].label_map()[label].probability for key in study_keys
        ]
        targets = [ground_truth_map[(key, label)] for key in study_keys]
        current_threshold = output_by_key[study_keys[0]].label_map()[label].threshold
        selection = select_competition_f1_threshold(
            probabilities,
            targets,
            current_threshold=current_threshold,
        )
        selected_thresholds[label] = selection.selected.threshold
        row: dict[str, Any] = {
            "label": label,
            "studies": len(study_keys),
            "positive": sum(targets),
            "negative": len(targets) - sum(targets),
            "f1_gain": selection.selected.f1 - selection.current.f1,
        }
        row.update(
            {
                f"current_{key}": value
                for key, value in asdict(selection.current).items()
            }
        )
        row.update(
            {
                f"selected_{key}": value
                for key, value in asdict(selection.selected).items()
            }
        )
        report_rows.append(row)
        print(
            f"[CompetitionThresholds] {label}: "
            f"threshold={selection.current.threshold:.4f}"
            f"->{selection.selected.threshold:.4f} "
            f"F1={selection.current.f1:.4f}->{selection.selected.f1:.4f} "
            f"precision={selection.selected.precision:.4f} "
            f"recall={selection.selected.recall:.4f}",
            flush=True,
        )

    report = pd.DataFrame(report_rows)
    policy = {
        "threshold_policy_version": POLICY_VERSION,
        "source_split": "competition_val",
        "objective": "maximize_per_label_positive_class_f1",
        "labels": list(CHEXPERT_COMPETITION_LABELS),
        "study_count": len(study_keys),
        "view_count": len(manifest),
        "current_threshold_policy_json": str(args.current_threshold_policy_json),
        "current_thresholds": {
            label: report_rows[index]["current_threshold"]
            for index, label in enumerate(CHEXPERT_COMPETITION_LABELS)
        },
        "selected_thresholds": selected_thresholds,
        "test_set_used": False,
    }

    manifest.to_csv(args.output_dir / "competition_val_manifest.csv", index=False)
    pd.DataFrame(
        [ground_truth_record_to_row(record) for record in ground_truth]
    ).to_csv(args.output_dir / "competition_val_ground_truth.csv", index=False)
    study_outputs_to_prediction_frame(study_outputs).to_csv(
        args.output_dir / "vision_study_predictions.csv",
        index=False,
    )
    report.to_csv(args.output_dir / "threshold_tuning_report.csv", index=False)
    _write_json(args.output_dir / "threshold_policy_v2.json", policy)
    _write_json(
        args.output_dir / "run_config.json",
        {
            "experiment": "exp16_chexpert_competition_val_thresholds",
            "dataset_root": str(args.dataset_root),
            "val_labels_csv": str(val_labels_csv),
            "checkpoint": str(args.checkpoint),
            "current_threshold_policy_json": str(args.current_threshold_policy_json),
            "output_dir": str(args.output_dir),
            "device": str(device),
            "mixed_precision": not args.no_mixed_precision,
            "batch_size": args.batch_size,
            "num_workers": args.num_workers,
            "study_count": len(study_keys),
            "view_count": len(manifest),
            "elapsed_seconds": elapsed,
            "test_set_used": False,
        },
    )
    print(f"[CompetitionThresholds] wrote results -> {args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
