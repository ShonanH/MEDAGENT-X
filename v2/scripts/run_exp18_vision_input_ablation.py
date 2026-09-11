"""Compare CheXpert JPG preprocessing and multi-view aggregation on validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd
import torch
from PIL import Image

from medagentx.evaluation.chexpert_competition import (
    EXPECTED_VALIDATION_STUDIES,
    EXPECTED_VALIDATION_VIEWS,
    build_competition_validation_ground_truth,
    build_competition_view_manifest,
)
from medagentx.labels.constants import CHEXPERT_COMPETITION_LABELS, DISEASE_LABELS
from medagentx.vision.backend import FineTunedRadDinoBackend
from medagentx.vision.data import (
    StudyInferenceRecord,
    build_study_inference_records,
    raster_to_pil_rgb,
)


DEFAULT_DATASET_ROOT = Path(
    "v2/data/chexpert_competition_test/chexlocalize/CheXpert"
)
DEFAULT_CHECKPOINT = Path(
    "v2/artifacts/cohort_balanced_v1/vision/"
    "raddino_finetuned_v1_last4_blocks/best_checkpoint.pt"
)
DEFAULT_OUTPUT_DIR = Path("v2/experiments/exp18_vision_input_ablation")
DEFAULT_BOOTSTRAP_SAMPLES = 1000
DEFAULT_SEED = 20260910
OUTPUT_FILENAMES = (
    "run_config.json",
    "variant_scores.csv",
    "per_label_auroc.csv",
    "variant_summary.csv",
)


def percentile_normalized_raster(path: str | Path) -> Image.Image:
    """Load a raster using the DICOM loader's percentile normalization."""
    with Image.open(path) as image:
        pixels = np.asarray(image.convert("L"), dtype=np.float32)
    if pixels.ndim != 2 or pixels.size == 0:
        raise ValueError(f"Expected non-empty grayscale raster: {path}")
    if not np.isfinite(pixels).all():
        raise ValueError(f"Raster contains non-finite pixels: {path}")
    low, high = np.percentile(pixels, [0.5, 99.5])
    if high <= low:
        normalized = np.zeros_like(pixels, dtype=np.float32)
    else:
        normalized = np.clip((pixels - low) / (high - low), 0.0, 1.0)
    uint8 = np.rint(normalized * 255.0).astype(np.uint8)
    return Image.fromarray(uint8, mode="L").convert("RGB")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _prepare_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [
        output_dir / filename
        for filename in OUTPUT_FILENAMES
        if (output_dir / filename).exists()
    ]
    if existing and not overwrite:
        raise FileExistsError(
            "Experiment outputs already exist; pass --overwrite:\n"
            + "\n".join(str(path) for path in existing)
        )
    if overwrite:
        for path in existing:
            path.unlink()


def _view_records(manifest: pd.DataFrame) -> list[StudyInferenceRecord]:
    records: list[StudyInferenceRecord] = []
    for _, row in manifest.iterrows():
        records.append(
            StudyInferenceRecord(
                study_key=str(row["study_key"]),
                deid_patient_id=str(row["deid_patient_id"]),
                split="competition_val",
                dicom_paths=(str(row["dicom_path"]),),
            )
        )
    return records


def _collect_variant_scores(
    backend: FineTunedRadDinoBackend,
    *,
    records: Sequence[StudyInferenceRecord],
    image_root: Path,
    image_loader: Callable[[str | Path], Image.Image],
    aggregation: str,
    batch_size: int,
    num_workers: int,
) -> tuple[dict[str, np.ndarray], float]:
    started = time.perf_counter()
    predictions = backend._collect_predictions(
        records,
        dicom_root=image_root,
        batch_size=batch_size,
        num_workers=num_workers,
        image_loader=image_loader,
    )
    probabilities = np.asarray(predictions["probabilities"], dtype=np.float64)
    study_keys = [str(key) for key in predictions["study_keys"]]
    grouped: dict[str, list[np.ndarray]] = {}
    for study_key, row in zip(study_keys, probabilities):
        grouped.setdefault(study_key, []).append(row)

    scores: dict[str, np.ndarray] = {}
    for study_key, rows in grouped.items():
        stacked = np.stack(rows, axis=0)
        if aggregation == "study_model":
            if len(stacked) != 1:
                raise ValueError(
                    "Study-model inference must return one row per study"
                )
            scores[study_key] = stacked[0]
        elif aggregation == "max_probability":
            scores[study_key] = stacked.max(axis=0)
        else:
            raise ValueError(f"Unsupported aggregation: {aggregation}")
    return scores, time.perf_counter() - started


def _binary_auroc(targets: np.ndarray, scores: np.ndarray) -> float:
    positive = int(targets.sum())
    negative = int(len(targets) - positive)
    if positive == 0 or negative == 0:
        raise ValueError("AUROC requires both target classes")
    order = np.argsort(scores, kind="stable")
    sorted_scores = scores[order]
    ranks = np.empty(len(scores), dtype=np.float64)
    index = 0
    while index < len(scores):
        end = index + 1
        while end < len(scores) and sorted_scores[end] == sorted_scores[index]:
            end += 1
        ranks[index:end] = ((index + 1) + end) / 2.0
        index = end
    original_ranks = np.empty_like(ranks)
    original_ranks[order] = ranks
    positive_rank_sum = float(original_ranks[targets == 1].sum())
    return (
        positive_rank_sum - positive * (positive + 1) / 2.0
    ) / (positive * negative)


def _bootstrap_intervals(
    targets: np.ndarray,
    scores: np.ndarray,
    *,
    samples: int,
    seed: int,
) -> tuple[np.ndarray, tuple[float, float]]:
    rng = np.random.default_rng(seed)
    label_samples: list[list[float]] = [[] for _ in CHEXPERT_COMPETITION_LABELS]
    macro_samples: list[float] = []
    for _ in range(samples):
        indices = rng.integers(0, len(targets), size=len(targets))
        sample_aurocs: list[float] = []
        for label_index in range(len(CHEXPERT_COMPETITION_LABELS)):
            sample_targets = targets[indices, label_index]
            if len(np.unique(sample_targets)) < 2:
                continue
            auroc = _binary_auroc(
                sample_targets,
                scores[indices, label_index],
            )
            label_samples[label_index].append(auroc)
            sample_aurocs.append(auroc)
        if len(sample_aurocs) == len(CHEXPERT_COMPETITION_LABELS):
            macro_samples.append(float(np.mean(sample_aurocs)))

    label_intervals = np.asarray(
        [np.quantile(values, [0.025, 0.975]) for values in label_samples]
    )
    macro_interval = tuple(
        float(value) for value in np.quantile(macro_samples, [0.025, 0.975])
    )
    return label_intervals, macro_interval


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare direct versus percentile-normalized JPG input and current "
            "study pooling versus max-across-view probabilities on CheXpert val."
        )
    )
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--val-labels-csv", type=Path, default=None)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
    )
    parser.add_argument("--no-mixed-precision", action="store_true")
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=DEFAULT_BOOTSTRAP_SAMPLES,
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be > 0")
    if args.num_workers < 0:
        raise ValueError("--num-workers must be >= 0")
    if args.bootstrap_samples <= 0:
        raise ValueError("--bootstrap-samples must be > 0")

    image_root = args.dataset_root / "val"
    val_labels_csv = args.val_labels_csv or (args.dataset_root / "val_labels.csv")
    for name, path in {
        "validation image directory": image_root,
        "validation labels CSV": val_labels_csv,
        "checkpoint": args.checkpoint,
    }.items():
        if not path.exists():
            raise FileNotFoundError(f"{name} missing: {path}")
    _prepare_output_dir(args.output_dir, overwrite=args.overwrite)

    val_labels = pd.read_csv(val_labels_csv, dtype=str)
    manifest = build_competition_view_manifest(
        val_labels,
        image_root=image_root,
        source_split="val",
    )
    study_records = build_study_inference_records(manifest)
    view_records = _view_records(manifest)
    if len(manifest) != EXPECTED_VALIDATION_VIEWS:
        raise ValueError(
            f"Expected {EXPECTED_VALIDATION_VIEWS} validation views, "
            f"got {len(manifest)}"
        )
    if len(study_records) != EXPECTED_VALIDATION_STUDIES:
        raise ValueError(
            f"Expected {EXPECTED_VALIDATION_STUDIES} validation studies, "
            f"got {len(study_records)}"
        )

    study_keys = [record.study_key for record in study_records]
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
    targets = np.asarray(
        [
            [
                ground_truth_map[(study_key, label)]
                for label in CHEXPERT_COMPETITION_LABELS
            ]
            for study_key in study_keys
        ],
        dtype=np.int64,
    )

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")
    backend = FineTunedRadDinoBackend.from_checkpoint(
        args.checkpoint,
        device=device,
        mixed_precision=not args.no_mixed_precision,
    )
    label_indices = [
        DISEASE_LABELS.index(label) for label in CHEXPERT_COMPETITION_LABELS
    ]
    variants = (
        ("direct_mean", raster_to_pil_rgb, study_records, "study_model"),
        (
            "normalized_mean",
            percentile_normalized_raster,
            study_records,
            "study_model",
        ),
        ("direct_max", raster_to_pil_rgb, view_records, "max_probability"),
        (
            "normalized_max",
            percentile_normalized_raster,
            view_records,
            "max_probability",
        ),
    )

    score_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    total_started = time.perf_counter()
    for variant_index, (name, loader, records, aggregation) in enumerate(
        variants,
        start=1,
    ):
        print(
            f"[VisionAblation] {variant_index}/{len(variants)} running {name}",
            flush=True,
        )
        score_map, elapsed = _collect_variant_scores(
            backend,
            records=records,
            image_root=image_root,
            image_loader=loader,
            aggregation=aggregation,
            batch_size=args.batch_size,
            num_workers=args.num_workers,
        )
        ordered_scores = np.asarray(
            [score_map[study_key][label_indices] for study_key in study_keys],
            dtype=np.float64,
        )
        aurocs = np.asarray(
            [
                _binary_auroc(targets[:, index], ordered_scores[:, index])
                for index in range(len(CHEXPERT_COMPETITION_LABELS))
            ]
        )
        label_intervals, macro_interval = _bootstrap_intervals(
            targets,
            ordered_scores,
            samples=args.bootstrap_samples,
            seed=args.seed,
        )
        for study_index, study_key in enumerate(study_keys):
            for label_index, label in enumerate(CHEXPERT_COMPETITION_LABELS):
                score_rows.append(
                    {
                        "variant": name,
                        "study_key": study_key,
                        "label": label,
                        "ground_truth": int(targets[study_index, label_index]),
                        "probability": float(ordered_scores[study_index, label_index]),
                    }
                )
        for label_index, label in enumerate(CHEXPERT_COMPETITION_LABELS):
            metric_rows.append(
                {
                    "variant": name,
                    "label": label,
                    "studies": len(study_keys),
                    "positive": int(targets[:, label_index].sum()),
                    "negative": int(len(study_keys) - targets[:, label_index].sum()),
                    "auroc": float(aurocs[label_index]),
                    "auroc_ci_low": float(label_intervals[label_index, 0]),
                    "auroc_ci_high": float(label_intervals[label_index, 1]),
                }
            )
        macro_auroc = float(np.mean(aurocs))
        summary_rows.append(
            {
                "variant": name,
                "macro_auroc": macro_auroc,
                "macro_auroc_ci_low": macro_interval[0],
                "macro_auroc_ci_high": macro_interval[1],
                "inference_seconds": elapsed,
            }
        )
        print(
            f"[VisionAblation] {name} macro_AUROC={macro_auroc:.4f} "
            f"95%_CI=[{macro_interval[0]:.4f}, {macro_interval[1]:.4f}] "
            f"elapsed={elapsed:.1f}s",
            flush=True,
        )

    summary = pd.DataFrame(summary_rows).sort_values(
        "macro_auroc",
        ascending=False,
    )
    pd.DataFrame(score_rows).to_csv(args.output_dir / "variant_scores.csv", index=False)
    pd.DataFrame(metric_rows).to_csv(
        args.output_dir / "per_label_auroc.csv",
        index=False,
    )
    summary.to_csv(args.output_dir / "variant_summary.csv", index=False)
    best_variant = str(summary.iloc[0]["variant"])
    _write_json(
        args.output_dir / "run_config.json",
        {
            "experiment": "exp18_vision_input_ablation",
            "dataset_root": str(args.dataset_root),
            "val_labels_csv": str(val_labels_csv),
            "checkpoint": str(args.checkpoint),
            "output_dir": str(args.output_dir),
            "device": str(device),
            "mixed_precision": not args.no_mixed_precision,
            "batch_size": args.batch_size,
            "num_workers": args.num_workers,
            "bootstrap_samples": args.bootstrap_samples,
            "seed": args.seed,
            "study_count": len(study_keys),
            "view_count": len(manifest),
            "variants": [variant[0] for variant in variants],
            "best_validation_variant": best_variant,
            "selection_metric": "five_label_macro_auroc",
            "test_set_used": False,
            "elapsed_seconds": time.perf_counter() - total_started,
        },
    )
    print(f"[VisionAblation] best validation variant={best_variant}", flush=True)
    print(f"[VisionAblation] wrote results -> {args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
