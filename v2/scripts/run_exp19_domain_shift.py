"""Compare internal and CheXpert competition vision score behavior."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from medagentx.evaluation.ground_truth import GroundTruthRecord
from medagentx.evaluation.ranking import RankingResult, compute_ranking_metrics
from medagentx.labels.constants import CHEXPERT_COMPETITION_LABELS
from medagentx.labels.schema import snake_label
from medagentx.labels.statuses import LabelStatus


DEFAULT_OUTPUT_DIR = Path("v2/experiments/exp19_domain_shift")
OUTPUT_FILENAMES = (
    "run_config.json",
    "metrics_by_dataset.csv",
    "score_distribution_by_label.csv",
    "dataset_characteristics.csv",
    "checkpoint_comparison.csv",
    "domain_shift_summary.json",
)


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    predictions_path: Path
    ground_truth_path: Path
    ground_truth_format: str


DEFAULT_PATH_CANDIDATES: dict[str, tuple[Path, ...]] = {
    "internal_test_predictions": (
        Path(
            "v2/artifacts/cohort_balanced_v1/vision/"
            "raddino_finetuned_v1_last4_blocks/test_study_predictions.csv"
        ),
        Path(
            "v2/experiments/exp05_llm_fusion_with_retrieval_graph/"
            "vision_study_predictions.csv"
        ),
        Path("v2/artifactsLocal/results/test_study_predictions.csv"),
    ),
    "internal_ground_truth": (
        Path("v2/artifacts/cohort_balanced_v1/study_label_table.csv"),
        Path(
            "v2/experiments/optimization_prior_fusion_inputs/splits/"
            "study_label_table.csv"
        ),
        Path("v2/artifactsLocal/val_last4_blocks_0818/val/study_label_table.csv"),
    ),
    "competition_val_predictions": (
        Path(
            "v2/experiments/exp16_chexpert_competition_val_thresholds/"
            "vision_study_predictions.csv"
        ),
    ),
    "competition_val_ground_truth": (
        Path(
            "v2/experiments/exp16_chexpert_competition_val_thresholds/"
            "competition_val_ground_truth.csv"
        ),
    ),
    "competition_test_predictions": (
        Path(
            "v2/experiments/exp14_chexpert_competition_auroc/"
            "vision_study_predictions.csv"
        ),
        Path(
            "v2/experiments/exp15_competition_exp05_fusion/competition/"
            "vision_study_predictions.csv"
        ),
    ),
    "competition_test_ground_truth": (
        Path(
            "v2/experiments/exp14_chexpert_competition_auroc/"
            "competition_ground_truth.csv"
        ),
        Path(
            "v2/experiments/exp15_competition_exp05_fusion/competition/"
            "competition_ground_truth.csv"
        ),
    ),
}


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _resolve_path(value: Path | None, *, name: str) -> Path:
    if value is not None:
        if not value.is_file():
            raise FileNotFoundError(f"{name} missing: {value}")
        return value
    candidates = DEFAULT_PATH_CANDIDATES[name]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Could not find {name}; checked: "
        + ", ".join(str(path) for path in candidates)
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


def _load_predictions(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"study_key", "view_count", "dicom_paths"}
    required.update(
        f"probability_{snake_label(label)}"
        for label in CHEXPERT_COMPETITION_LABELS
    )
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Prediction file {path} is missing columns: {missing}")
    if frame.empty:
        raise ValueError(f"Prediction file is empty: {path}")

    frame = frame.copy()
    frame["study_key"] = frame["study_key"].astype(str).str.strip()
    if frame["study_key"].eq("").any():
        raise ValueError(f"Prediction file contains an empty study_key: {path}")
    if frame["study_key"].duplicated().any():
        duplicates = frame.loc[
            frame["study_key"].duplicated(), "study_key"
        ].head(5)
        raise ValueError(
            f"Prediction file contains duplicate studies: {duplicates.tolist()}"
        )

    for label in CHEXPERT_COMPETITION_LABELS:
        column = f"probability_{snake_label(label)}"
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        values = frame[column].to_numpy(dtype=np.float64)
        if not np.isfinite(values).all() or ((values < 0) | (values > 1)).any():
            raise ValueError(f"{column} in {path} must be finite and in [0, 1]")
    frame["view_count"] = pd.to_numeric(frame["view_count"], errors="raise")
    if (frame["view_count"] <= 0).any():
        raise ValueError(f"view_count in {path} must be positive")
    return frame


def _status(value: object, *, context: str) -> LabelStatus:
    try:
        return LabelStatus(str(value).strip().lower())
    except ValueError as error:
        raise ValueError(f"Invalid status {value!r} for {context}") from error


def _internal_ground_truth_records(
    frame: pd.DataFrame,
    *,
    study_keys: Sequence[str],
) -> list[GroundTruthRecord]:
    required = {"study_key"}
    for label in CHEXPERT_COMPETITION_LABELS:
        slug = snake_label(label)
        required.update(
            {
                f"status_{slug}",
                f"training_target_{slug}",
                f"training_mask_{slug}",
            }
        )
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Internal ground truth is missing columns: {missing}")

    selected = frame.copy()
    selected["study_key"] = selected["study_key"].astype(str).str.strip()
    if selected["study_key"].duplicated().any():
        raise ValueError("Internal ground truth contains duplicate study_key values")
    selected = selected.set_index("study_key")
    missing_studies = sorted(set(study_keys) - set(selected.index))
    if missing_studies:
        raise ValueError(
            "Internal ground truth is missing prediction studies: "
            f"{missing_studies[:10]}"
        )

    records: list[GroundTruthRecord] = []
    for study_key in study_keys:
        row = selected.loc[study_key]
        for label in CHEXPERT_COMPETITION_LABELS:
            slug = snake_label(label)
            raw_status = _status(
                row[f"status_{slug}"], context=f"{study_key}/{label}"
            )
            mask = int(row[f"training_mask_{slug}"])
            if mask not in (0, 1):
                raise ValueError(
                    f"Invalid training mask {mask!r} for {study_key}/{label}"
                )
            if mask:
                target = float(row[f"training_target_{slug}"])
                if target not in (0.0, 1.0):
                    raise ValueError(
                        f"Invalid training target {target!r} for {study_key}/{label}"
                    )
                evaluation_status = (
                    LabelStatus.PRESENT if target == 1.0 else LabelStatus.ABSENT
                )
            else:
                evaluation_status = (
                    raw_status
                    if raw_status in (LabelStatus.UNCERTAIN, LabelStatus.UNMENTIONED)
                    else LabelStatus.UNCERTAIN
                )
            records.append(
                GroundTruthRecord(
                    study_key=study_key,
                    label=label,
                    ground_truth_status=evaluation_status,
                    ground_truth_source="chexpert_plus_training_target_and_mask",
                    ground_truth_policy_version="chexpert_training_policy_v1",
                )
            )
    return records


def _competition_ground_truth_records(
    frame: pd.DataFrame,
    *,
    study_keys: Sequence[str],
) -> list[GroundTruthRecord]:
    required = {"study_key", "label", "ground_truth_status"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Competition ground truth is missing columns: {missing}")

    selected = frame.copy()
    selected["study_key"] = selected["study_key"].astype(str).str.strip()
    selected["label"] = selected["label"].astype(str).str.strip()
    selected = selected[
        selected["study_key"].isin(study_keys)
        & selected["label"].isin(CHEXPERT_COMPETITION_LABELS)
    ]
    if selected.duplicated(["study_key", "label"]).any():
        raise ValueError("Competition ground truth contains duplicate study-label rows")

    expected = {
        (study_key, label)
        for study_key in study_keys
        for label in CHEXPERT_COMPETITION_LABELS
    }
    actual = set(zip(selected["study_key"], selected["label"]))
    missing_cells = sorted(expected - actual)
    if missing_cells:
        raise ValueError(
            "Competition ground truth is missing prediction cells: "
            f"{missing_cells[:10]}"
        )

    records: list[GroundTruthRecord] = []
    for row in selected.itertuples(index=False):
        source = getattr(row, "ground_truth_source", "chexpert_expert")
        policy = getattr(row, "ground_truth_policy_version", "competition")
        records.append(
            GroundTruthRecord(
                study_key=str(row.study_key),
                label=str(row.label),
                ground_truth_status=_status(
                    row.ground_truth_status,
                    context=f"{row.study_key}/{row.label}",
                ),
                ground_truth_source=str(source),
                ground_truth_policy_version=str(policy),
            )
        )
    return records


def _prediction_scores(frame: pd.DataFrame) -> dict[tuple[str, str], float]:
    return {
        (str(row.study_key), label): float(
            getattr(row, f"probability_{snake_label(label)}")
        )
        for row in frame.itertuples(index=False)
        for label in CHEXPERT_COMPETITION_LABELS
    }


def _score_distribution(values: np.ndarray) -> dict[str, float | int]:
    return {
        "count": int(len(values)),
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "minimum": float(np.min(values)),
        "p05": float(np.quantile(values, 0.05)),
        "p25": float(np.quantile(values, 0.25)),
        "median": float(np.median(values)),
        "p75": float(np.quantile(values, 0.75)),
        "p95": float(np.quantile(values, 0.95)),
        "maximum": float(np.max(values)),
    }


def _metric_and_distribution_rows(
    dataset: str,
    result: RankingResult,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cells_by_label = {
        label: [cell for cell in result.cells if cell.label == label and cell.included]
        for label in CHEXPERT_COMPETITION_LABELS
    }
    metric_rows: list[dict[str, Any]] = []
    distribution_rows: list[dict[str, Any]] = []
    for metrics in result.per_label_metrics:
        cells = cells_by_label[metrics.label]
        positive_scores = np.asarray(
            [cell.prediction_score for cell in cells if cell.ground_truth_binary == 1],
            dtype=np.float64,
        )
        negative_scores = np.asarray(
            [cell.prediction_score for cell in cells if cell.ground_truth_binary == 0],
            dtype=np.float64,
        )
        positive_mean = float(np.mean(positive_scores))
        negative_mean = float(np.mean(negative_scores))
        metric_rows.append(
            {
                "dataset": dataset,
                "level": "label",
                "label": metrics.label,
                "total_cells": metrics.total,
                "evaluated_cells": metrics.evaluated,
                "binary_coverage": metrics.evaluated / metrics.total,
                "positive": metrics.positive,
                "negative": metrics.negative,
                "positive_prevalence": metrics.positive / metrics.evaluated,
                "excluded_uncertain": metrics.excluded_uncertain,
                "excluded_unmentioned": metrics.excluded_unmentioned,
                "auroc": metrics.auroc,
                "average_precision": metrics.average_precision,
                "positive_score_mean": positive_mean,
                "negative_score_mean": negative_mean,
                "mean_score_separation": positive_mean - negative_mean,
            }
        )
        for ground_truth_binary, name, values in (
            (0, "absent", negative_scores),
            (1, "present", positive_scores),
        ):
            distribution_rows.append(
                {
                    "dataset": dataset,
                    "label": metrics.label,
                    "ground_truth_binary": ground_truth_binary,
                    "ground_truth_status": name,
                    **_score_distribution(values),
                }
            )

    metric_rows.append(
        {
            "dataset": dataset,
            "level": "macro",
            "label": "Macro",
            "total_cells": sum(item.total for item in result.per_label_metrics),
            "evaluated_cells": sum(
                item.evaluated for item in result.per_label_metrics
            ),
            "binary_coverage": sum(
                item.evaluated for item in result.per_label_metrics
            )
            / sum(item.total for item in result.per_label_metrics),
            "positive": sum(item.positive for item in result.per_label_metrics),
            "negative": sum(item.negative for item in result.per_label_metrics),
            "positive_prevalence": None,
            "excluded_uncertain": sum(
                item.excluded_uncertain for item in result.per_label_metrics
            ),
            "excluded_unmentioned": sum(
                item.excluded_unmentioned for item in result.per_label_metrics
            ),
            "auroc": result.macro_auroc,
            "average_precision": result.macro_average_precision,
            "positive_score_mean": None,
            "negative_score_mean": None,
            "mean_score_separation": None,
        }
    )
    return metric_rows, distribution_rows


def _dataset_characteristics(
    dataset: str,
    predictions: pd.DataFrame,
    result: RankingResult,
) -> dict[str, Any]:
    suffixes: Counter[str] = Counter()
    orientations: Counter[str] = Counter()
    listed_paths = 0
    for value in predictions["dicom_paths"].fillna(""):
        for raw_path in str(value).split("|"):
            raw_path = raw_path.strip()
            if not raw_path:
                continue
            listed_paths += 1
            path = Path(raw_path)
            suffixes[path.suffix.lower() or "none"] += 1
            filename = path.name.lower()
            if "frontal" in filename:
                orientations["frontal"] += 1
            elif "lateral" in filename:
                orientations["lateral"] += 1
            else:
                orientations["unknown"] += 1

    views = predictions["view_count"].to_numpy(dtype=np.float64)
    evaluated = sum(item.evaluated for item in result.per_label_metrics)
    total = sum(item.total for item in result.per_label_metrics)
    return {
        "dataset": dataset,
        "studies": len(predictions),
        "patients": int(predictions["deid_patient_id"].nunique())
        if "deid_patient_id" in predictions
        else None,
        "reported_views": int(views.sum()),
        "listed_image_paths": listed_paths,
        "path_count_matches_reported_views": listed_paths == int(views.sum()),
        "single_view_studies": int((views == 1).sum()),
        "multi_view_studies": int((views > 1).sum()),
        "mean_views_per_study": float(np.mean(views)),
        "median_views_per_study": float(np.median(views)),
        "minimum_views_per_study": int(np.min(views)),
        "maximum_views_per_study": int(np.max(views)),
        "image_format_counts": json.dumps(dict(sorted(suffixes.items()))),
        "orientation_counts": json.dumps(dict(sorted(orientations.items()))),
        "ground_truth_cells": total,
        "binary_scoreable_cells": evaluated,
        "binary_ground_truth_coverage": evaluated / total,
    }


def _analyze_dataset(
    spec: DatasetSpec,
) -> tuple[pd.DataFrame, list[GroundTruthRecord], RankingResult]:
    predictions = _load_predictions(spec.predictions_path)
    ground_truth_frame = pd.read_csv(spec.ground_truth_path)
    study_keys = predictions["study_key"].tolist()
    if spec.ground_truth_format == "internal_wide":
        records = _internal_ground_truth_records(
            ground_truth_frame,
            study_keys=study_keys,
        )
    elif spec.ground_truth_format == "competition_long":
        records = _competition_ground_truth_records(
            ground_truth_frame,
            study_keys=study_keys,
        )
    else:
        raise ValueError(f"Unsupported ground-truth format: {spec.ground_truth_format}")
    result = compute_ranking_metrics(
        ground_truth_records=records,
        predicted_scores=_prediction_scores(predictions),
        labels=CHEXPERT_COMPETITION_LABELS,
        require_two_classes_per_label=True,
    )
    return predictions, records, result


def _domain_shift_summary(
    results: dict[str, RankingResult],
) -> dict[str, Any]:
    macro_aurocs = {
        dataset: result.macro_auroc for dataset, result in results.items()
    }
    per_label = {
        dataset: {item.label: item.auroc for item in result.per_label_metrics}
        for dataset, result in results.items()
    }
    baseline = per_label["internal_test"]
    label_deltas: dict[str, dict[str, float | None]] = {}
    for label in CHEXPERT_COMPETITION_LABELS:
        label_deltas[label] = {}
        for dataset in ("competition_val", "competition_test"):
            internal_value = baseline[label]
            competition_value = per_label[dataset][label]
            label_deltas[label][f"{dataset}_minus_internal_test"] = (
                None
                if internal_value is None or competition_value is None
                else competition_value - internal_value
            )

    return {
        "experiment": "exp19_domain_shift",
        "checkpoint": "raddino_finetuned_v1_last4_blocks",
        "labels": list(CHEXPERT_COMPETITION_LABELS),
        "macro_auroc_by_dataset": macro_aurocs,
        "macro_auroc_delta_vs_internal_test": {
            dataset: value - macro_aurocs["internal_test"]
            for dataset, value in macro_aurocs.items()
            if dataset.startswith("competition_")
            and value is not None
            and macro_aurocs["internal_test"] is not None
        },
        "per_label_auroc_delta_vs_internal_test": label_deltas,
        "interpretation_guardrails": [
            "AUROC uses continuous RAD-DINO probabilities and is threshold-independent.",
            "Internal targets follow the checkpoint's training_target and training_mask policy.",
            "Masked internal cells are excluded; policy-derived negative targets are retained.",
            "Competition validation and test labels are expert binary labels with full coverage.",
            "A performance delta can reflect both image-domain shift and ground-truth protocol shift.",
            "Image characteristics are derived from saved path/view metadata; pixels are not reread.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare last-four-block RAD-DINO scores across internal and "
            "expert-labeled CheXpert competition validation/test datasets."
        )
    )
    parser.add_argument("--internal-test-predictions", type=Path)
    parser.add_argument("--internal-ground-truth", type=Path)
    parser.add_argument("--competition-val-predictions", type=Path)
    parser.add_argument("--competition-val-ground-truth", type=Path)
    parser.add_argument("--competition-test-predictions", type=Path)
    parser.add_argument("--competition-test-ground-truth", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = {
        name: _resolve_path(getattr(args, name), name=name)
        for name in DEFAULT_PATH_CANDIDATES
    }
    specs = (
        DatasetSpec(
            "internal_test",
            paths["internal_test_predictions"],
            paths["internal_ground_truth"],
            "internal_wide",
        ),
        DatasetSpec(
            "competition_val",
            paths["competition_val_predictions"],
            paths["competition_val_ground_truth"],
            "competition_long",
        ),
        DatasetSpec(
            "competition_test",
            paths["competition_test_predictions"],
            paths["competition_test_ground_truth"],
            "competition_long",
        ),
    )
    _prepare_output_dir(args.output_dir, overwrite=args.overwrite)

    all_metric_rows: list[dict[str, Any]] = []
    all_distribution_rows: list[dict[str, Any]] = []
    characteristic_rows: list[dict[str, Any]] = []
    results: dict[str, RankingResult] = {}
    for spec in specs:
        print(f"[DomainShift] analyzing {spec.name}", flush=True)
        predictions, _, result = _analyze_dataset(spec)
        metric_rows, distribution_rows = _metric_and_distribution_rows(
            spec.name,
            result,
        )
        all_metric_rows.extend(metric_rows)
        all_distribution_rows.extend(distribution_rows)
        characteristic_rows.append(
            _dataset_characteristics(spec.name, predictions, result)
        )
        results[spec.name] = result
        print(
            f"[DomainShift] {spec.name} macro_AUROC={result.macro_auroc:.4f} "
            f"macro_AP={result.macro_average_precision:.4f}",
            flush=True,
        )

    metrics_frame = pd.DataFrame(all_metric_rows)
    metrics_frame.to_csv(args.output_dir / "metrics_by_dataset.csv", index=False)
    pd.DataFrame(all_distribution_rows).to_csv(
        args.output_dir / "score_distribution_by_label.csv",
        index=False,
    )
    pd.DataFrame(characteristic_rows).to_csv(
        args.output_dir / "dataset_characteristics.csv",
        index=False,
    )
    metrics_frame.loc[
        metrics_frame["level"].eq("macro"),
        [
            "dataset",
            "auroc",
            "average_precision",
            "binary_coverage",
            "evaluated_cells",
        ],
    ].assign(checkpoint="raddino_finetuned_v1_last4_blocks").to_csv(
        args.output_dir / "checkpoint_comparison.csv",
        index=False,
    )
    summary = _domain_shift_summary(results)
    _write_json(args.output_dir / "domain_shift_summary.json", summary)
    _write_json(
        args.output_dir / "run_config.json",
        {
            "experiment": "exp19_domain_shift",
            "labels": list(CHEXPERT_COMPETITION_LABELS),
            "output_dir": str(args.output_dir),
            "inputs": {name: str(path) for name, path in paths.items()},
            "inference_run": False,
            "retrieval_run": False,
            "llm_run": False,
            "checkpoint": "raddino_finetuned_v1_last4_blocks",
        },
    )
    print(f"[DomainShift] wrote results -> {args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
