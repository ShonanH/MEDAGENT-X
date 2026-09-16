"""Tune per-label GLoRIA thresholds on expert CheXpert validation labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPERIMENT_DIR = (
    PROJECT_ROOT / "v2" / "experiments" / "gloria_zero_shot_comparison"
)
DEFAULT_SCORES = DEFAULT_EXPERIMENT_DIR / "validation_scores.csv"
DEFAULT_GROUND_TRUTH = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp16_chexpert_competition_val_thresholds"
    / "competition_val_ground_truth.csv"
)

LABELS: tuple[str, ...] = (
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
)
MODEL_NAME = "gloria_resnet50_zero_shot"
POLICY_VERSION = "gloria_zero_shot_max_f1_thresholds_v1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select one maximum-F1 validation threshold per GLoRIA label."
    )
    parser.add_argument("--scores", type=Path, default=DEFAULT_SCORES)
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_EXPERIMENT_DIR)
    parser.add_argument("--expected-studies", type=int, default=200)
    return parser


def _require_file(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Missing {description}: {resolved}")
    return resolved


def _safe_div(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _metrics_at_threshold(
    y_true: np.ndarray, scores: np.ndarray, threshold: float
) -> dict[str, Any]:
    predicted = scores >= threshold
    positive = y_true == 1
    negative = ~positive
    tp = int(np.sum(predicted & positive))
    fp = int(np.sum(predicted & negative))
    fn = int(np.sum(~predicted & positive))
    tn = int(np.sum(~predicted & negative))
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * tp, 2 * tp + fp + fn)
    specificity = _safe_div(tn, tn + fp)
    accuracy = _safe_div(tp + tn, len(y_true))
    return {
        "threshold": float(threshold),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "predicted_positive": int(predicted.sum()),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "specificity": specificity,
        "accuracy": accuracy,
    }


def _select_threshold(y_true: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
    candidates = np.unique(scores.astype(float))
    if candidates.size == 0:
        raise ValueError("Cannot tune a threshold without scores")
    rows = [_metrics_at_threshold(y_true, scores, value) for value in candidates]
    # Deterministic tie-breaking: maximum F1, then maximum precision, then the
    # higher (more conservative) threshold.
    return max(
        rows,
        key=lambda row: (row["f1"], row["precision"], row["threshold"]),
    )


def _load_joined_rows(
    scores_path: Path,
    ground_truth_path: Path,
    expected_studies: int,
) -> pd.DataFrame:
    scores = pd.read_csv(scores_path)
    required_scores = {"study_key", *LABELS}
    missing_scores = sorted(required_scores - set(scores.columns))
    if missing_scores:
        raise ValueError(f"Score file is missing columns: {missing_scores}")
    if len(scores) != expected_studies:
        raise ValueError(
            f"Expected {expected_studies} score rows, found {len(scores)}"
        )
    if scores["study_key"].nunique() != expected_studies:
        raise ValueError("Score file must contain exactly one row per study")

    long_scores = scores.melt(
        id_vars=["study_key"],
        value_vars=list(LABELS),
        var_name="label",
        value_name="score",
    )
    ground_truth = pd.read_csv(ground_truth_path)
    required_gt = {"study_key", "label", "ground_truth_status"}
    missing_gt = sorted(required_gt - set(ground_truth.columns))
    if missing_gt:
        raise ValueError(f"Ground-truth file is missing columns: {missing_gt}")
    ground_truth = ground_truth.loc[
        ground_truth["label"].isin(LABELS),
        ["study_key", "label", "ground_truth_status"],
    ].copy()
    duplicates = ground_truth.duplicated(["study_key", "label"], keep=False)
    if duplicates.any():
        raise ValueError("Ground truth contains duplicate study-label rows")
    allowed_statuses = {"present", "absent"}
    observed_statuses = set(ground_truth["ground_truth_status"].astype(str))
    unexpected = sorted(observed_statuses - allowed_statuses)
    if unexpected:
        raise ValueError(f"Ground truth is not fully binary: {unexpected}")

    joined = long_scores.merge(
        ground_truth,
        on=["study_key", "label"],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if not (joined["_merge"] == "both").all():
        counts = joined["_merge"].value_counts().to_dict()
        raise ValueError(f"Scores and ground truth do not align: {counts}")
    joined = joined.drop(columns="_merge")
    joined["ground_truth"] = (
        joined["ground_truth_status"].astype(str) == "present"
    ).astype(int)
    expected_rows = expected_studies * len(LABELS)
    if len(joined) != expected_rows:
        raise ValueError(f"Expected {expected_rows} joined rows, found {len(joined)}")
    return joined.sort_values(["label", "study_key"], kind="stable").reset_index(
        drop=True
    )


def main() -> None:
    args = build_parser().parse_args()
    scores_path = _require_file(args.scores, "GLoRIA validation scores")
    ground_truth_path = _require_file(args.ground_truth, "validation ground truth")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    joined = _load_joined_rows(
        scores_path, ground_truth_path, args.expected_studies
    )
    selected_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []

    for label in LABELS:
        label_rows = joined.loc[joined["label"] == label].copy()
        y_true = label_rows["ground_truth"].to_numpy(dtype=int)
        scores = label_rows["score"].to_numpy(dtype=float)
        if len(np.unique(y_true)) != 2:
            raise ValueError(f"{label} does not contain both binary classes")

        selected = _select_threshold(y_true, scores)
        selected.update(
            {
                "label": label,
                "study_count": len(label_rows),
                "ground_truth_positive": int(y_true.sum()),
                "ground_truth_negative": int((y_true == 0).sum()),
                "auroc": float(roc_auc_score(y_true, scores)),
                "average_precision": float(average_precision_score(y_true, scores)),
                "selection_metric": "f1",
                "tie_breaker": "precision_then_higher_threshold",
            }
        )
        selected_rows.append(selected)

        label_rows["threshold"] = selected["threshold"]
        label_rows["predicted_positive"] = (
            label_rows["score"] >= selected["threshold"]
        ).astype(int)
        label_rows["predicted_status"] = label_rows["predicted_positive"].map(
            {1: "present", 0: "absent"}
        )
        prediction_frames.append(label_rows)

    report = pd.DataFrame(selected_rows)
    report = report[
        [
            "label",
            "threshold",
            "study_count",
            "ground_truth_positive",
            "ground_truth_negative",
            "predicted_positive",
            "tp",
            "tn",
            "fp",
            "fn",
            "precision",
            "recall",
            "f1",
            "specificity",
            "accuracy",
            "auroc",
            "average_precision",
            "selection_metric",
            "tie_breaker",
        ]
    ]
    predictions = pd.concat(prediction_frames, ignore_index=True)
    predictions.insert(0, "model_name", MODEL_NAME)

    total_tp = int(report["tp"].sum())
    total_fp = int(report["fp"].sum())
    total_fn = int(report["fn"].sum())
    micro_precision = _safe_div(total_tp, total_tp + total_fp)
    micro_recall = _safe_div(total_tp, total_tp + total_fn)
    micro_f1 = _safe_div(2 * total_tp, 2 * total_tp + total_fp + total_fn)
    summary = {
        "model_name": MODEL_NAME,
        "policy_version": POLICY_VERSION,
        "selection_split": "competition_val",
        "selection_metric": "per_label_maximum_f1",
        "tie_breaker": "maximum_precision_then_higher_threshold",
        "study_count": args.expected_studies,
        "label_count": len(LABELS),
        "study_label_count": len(predictions),
        "macro_f1": float(report["f1"].mean()),
        "macro_precision": float(report["precision"].mean()),
        "macro_recall": float(report["recall"].mean()),
        "macro_auroc": float(report["auroc"].mean()),
        "macro_average_precision": float(report["average_precision"].mean()),
        "micro_f1": micro_f1,
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "selected_thresholds": {
            str(row["label"]): float(row["threshold"])
            for row in selected_rows
        },
        "scores_csv": str(scores_path),
        "ground_truth_csv": str(ground_truth_path),
    }

    report_path = output_dir / "validation_threshold_report.csv"
    predictions_path = output_dir / "validation_predictions.csv"
    policy_path = output_dir / "threshold_policy.json"
    report.to_csv(report_path, index=False)
    predictions.to_csv(predictions_path, index=False)
    policy_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    print(report.to_string(index=False))
    print("\nValidation summary:")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"\nSaved threshold report: {report_path}")
    print(f"Saved validation predictions: {predictions_path}")
    print(f"Saved frozen threshold policy: {policy_path}")


if __name__ == "__main__":
    main()
