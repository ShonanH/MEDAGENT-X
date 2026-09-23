"""Fit validation normalization and thresholds for Exp20 BioViL scores.

This command reads only frozen validation inference artifacts and validation
ground truth. It never reads the test cohort. Per-label thresholds maximize F1
subject to specificity >= 0.60, with precision and then the higher threshold
used as deterministic tie-breakers.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp20_biovil_native_zero_shot_comparison"
)
DEFAULT_PROMPT_POLICY = DEFAULT_OUTPUT_DIR / "prompt_policy.json"
DEFAULT_RAW_SCORES = DEFAULT_OUTPUT_DIR / "validation_raw_scores.csv"
DEFAULT_INFERENCE_CONFIG = (
    DEFAULT_OUTPUT_DIR / "validation_inference_run_config.json"
)
DEFAULT_GROUND_TRUTH = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp16_chexpert_competition_val_thresholds"
    / "competition_val_ground_truth.csv"
)

PROMPT_POLICY_VERSION = "biovil_native_positive_negative_margin_exp20_v1"
THRESHOLD_POLICY_VERSION = (
    "biovil_native_max_f1_specificity_floor_exp20_v1"
)
MODEL_NAME = "biovil_resnet50_native_zero_shot"
EXPECTED_GROUND_TRUTH_SHA256 = (
    "1caf1a4639711f32a1566ab514aed4d7"
    "9f45f6f3477152c19811370586453026"
)
LABELS = (
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fit Exp20 validation-only z-score normalization and maximum-F1 "
            "thresholds subject to a specificity floor."
        )
    )
    parser.add_argument(
        "--prompt-policy", type=Path, default=DEFAULT_PROMPT_POLICY
    )
    parser.add_argument("--raw-scores", type=Path, default=DEFAULT_RAW_SCORES)
    parser.add_argument(
        "--inference-config", type=Path, default=DEFAULT_INFERENCE_CONFIG
    )
    parser.add_argument(
        "--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--expected-studies", type=int, default=200)
    parser.add_argument("--minimum-specificity", type=float, default=0.60)
    return parser


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_file(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Missing {description}: {resolved}")
    return resolved


def resolve_directory(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"Missing {description}: {resolved}")
    return resolved


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def positive_column(label: str) -> str:
    return f"positive_{label}"


def negative_column(label: str) -> str:
    return f"negative_{label}"


def raw_column(label: str) -> str:
    return f"raw_{label}"


def load_checksum_policy(
    policy_path: Path,
    checksum_name: str,
    expected_version: str,
) -> tuple[dict[str, Any], str]:
    checksum_path = resolve_file(
        policy_path.with_name(checksum_name), f"checksum for {policy_path.name}"
    )
    fields = checksum_path.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[1] != policy_path.name:
        raise RuntimeError(f"Malformed checksum file: {checksum_path}")
    observed = sha256(policy_path)
    if observed != fields[0]:
        raise RuntimeError(f"Checksum mismatch for {policy_path}")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("policy_version") != expected_version:
        raise RuntimeError(
            f"Expected policy version {expected_version!r}, "
            f"found {policy.get('policy_version')!r}"
        )
    return policy, observed


def validate_inference_inputs(
    *,
    prompt_policy_path: Path,
    raw_scores_path: Path,
    inference_config_path: Path,
    ground_truth_path: Path,
    expected_studies: int,
) -> tuple[
    dict[str, Any],
    str,
    dict[str, Any],
    str,
    pd.DataFrame,
    str,
    pd.DataFrame,
    str,
]:
    prompt_policy, prompt_policy_hash = load_checksum_policy(
        prompt_policy_path,
        "prompt_policy.sha256",
        PROMPT_POLICY_VERSION,
    )
    if tuple(prompt_policy.get("labels", ())) != LABELS:
        raise RuntimeError("Prompt-policy labels or order changed")
    inference_config = json.loads(
        inference_config_path.read_text(encoding="utf-8")
    )
    inference_config_hash = sha256(inference_config_path)
    if inference_config.get("experiment_id") != "exp20":
        raise RuntimeError("Inference config is not from Exp20")
    if inference_config.get("model_name") != MODEL_NAME:
        raise RuntimeError("Inference config model name changed")
    if inference_config.get("policy_version") != PROMPT_POLICY_VERSION:
        raise RuntimeError("Inference config prompt-policy version changed")
    if inference_config.get("prompt_policy_sha256") != prompt_policy_hash:
        raise RuntimeError("Inference config used a different prompt policy")
    if inference_config.get("ground_truth_read") is not False:
        raise RuntimeError("Validation inference was not ground-truth blind")
    if inference_config.get("normalization_applied") is not False:
        raise RuntimeError("Validation inference unexpectedly normalized scores")
    if inference_config.get("thresholds_applied") is not False:
        raise RuntimeError("Validation inference unexpectedly applied thresholds")

    raw_scores_hash = sha256(raw_scores_path)
    configured_hash = (
        inference_config.get("outputs", {})
        .get("sha256", {})
        .get("validation_raw_scores.csv")
    )
    if configured_hash != raw_scores_hash:
        raise RuntimeError(
            "validation_raw_scores.csv differs from its inference run config"
        )
    raw_scores = pd.read_csv(raw_scores_path)
    required_score_columns = {
        "model_name",
        "policy_version",
        "study_key",
        "frontal_view_count",
        "frontal_dicom_paths",
        *(
            column
            for label in LABELS
            for column in (
                positive_column(label),
                negative_column(label),
                raw_column(label),
            )
        ),
    }
    missing_score_columns = sorted(
        required_score_columns - set(raw_scores.columns)
    )
    if missing_score_columns:
        raise ValueError(
            f"Raw score file is missing columns: {missing_score_columns}"
        )
    if len(raw_scores) != expected_studies:
        raise RuntimeError(
            f"Expected {expected_studies} validation study scores, "
            f"found {len(raw_scores)}"
        )
    if raw_scores["study_key"].duplicated().any():
        raise RuntimeError("Raw scores contain duplicate study keys")
    if set(raw_scores["model_name"].astype(str)) != {MODEL_NAME}:
        raise RuntimeError("Raw score model name changed")
    if set(raw_scores["policy_version"].astype(str)) != {
        PROMPT_POLICY_VERSION
    }:
        raise RuntimeError("Raw score prompt-policy version changed")
    if int((raw_scores["frontal_view_count"] > 1).sum()) != 2:
        raise RuntimeError("Unexpected multi-frontal validation study count")
    for label in LABELS:
        positive = raw_scores[positive_column(label)].to_numpy(dtype=float)
        negative = raw_scores[negative_column(label)].to_numpy(dtype=float)
        margin = raw_scores[raw_column(label)].to_numpy(dtype=float)
        if not np.isfinite(positive).all():
            raise RuntimeError(f"Non-finite positive scores for {label}")
        if not np.isfinite(negative).all():
            raise RuntimeError(f"Non-finite negative scores for {label}")
        if not np.isfinite(margin).all():
            raise RuntimeError(f"Non-finite margins for {label}")
        if not np.allclose(positive - negative, margin, rtol=0.0, atol=1e-6):
            raise RuntimeError(f"Margin identity failed for {label}")

    ground_truth_hash = sha256(ground_truth_path)
    if ground_truth_hash != EXPECTED_GROUND_TRUTH_SHA256:
        raise RuntimeError(
            "Validation ground-truth SHA-256 mismatch: expected "
            f"{EXPECTED_GROUND_TRUTH_SHA256}, observed {ground_truth_hash}"
        )
    ground_truth = pd.read_csv(ground_truth_path)
    required_truth_columns = {
        "study_key",
        "label",
        "ground_truth_status",
    }
    missing_truth_columns = sorted(
        required_truth_columns - set(ground_truth.columns)
    )
    if missing_truth_columns:
        raise ValueError(
            f"Ground truth is missing columns: {missing_truth_columns}"
        )
    ground_truth = ground_truth.loc[
        ground_truth["label"].isin(LABELS)
    ].copy()
    if len(ground_truth) != expected_studies * len(LABELS):
        raise RuntimeError(
            f"Expected {expected_studies * len(LABELS)} validation labels, "
            f"found {len(ground_truth)}"
        )
    if ground_truth.duplicated(["study_key", "label"]).any():
        raise RuntimeError("Ground truth contains duplicate study-label rows")
    if ground_truth["study_key"].nunique() != expected_studies:
        raise RuntimeError("Unexpected validation ground-truth study count")
    if set(ground_truth["study_key"].astype(str)) != set(
        raw_scores["study_key"].astype(str)
    ):
        raise RuntimeError("Validation score and ground-truth studies differ")
    if set(ground_truth["label"].astype(str)) != set(LABELS):
        raise RuntimeError("Validation ground-truth labels differ")
    statuses = set(ground_truth["ground_truth_status"].astype(str))
    if statuses != {"absent", "present"}:
        raise RuntimeError(f"Ground truth is not binary: {sorted(statuses)}")
    if "binary_scoreable" in ground_truth.columns:
        scoreable = (
            ground_truth["binary_scoreable"]
            .astype(str)
            .str.lower()
            .isin({"true", "1"})
        )
        if not scoreable.all():
            raise RuntimeError("Ground truth contains non-scoreable rows")

    return (
        prompt_policy,
        prompt_policy_hash,
        inference_config,
        inference_config_hash,
        raw_scores,
        raw_scores_hash,
        ground_truth,
        ground_truth_hash,
    )


def safe_divide(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def metrics_at_threshold(
    y_true: np.ndarray, scores: np.ndarray, threshold: float
) -> dict[str, Any]:
    predicted = scores >= threshold
    positive = y_true == 1
    negative = ~positive
    tp = int(np.sum(predicted & positive))
    tn = int(np.sum(~predicted & negative))
    fp = int(np.sum(predicted & negative))
    fn = int(np.sum(~predicted & positive))
    return {
        "threshold": float(threshold),
        "predicted_positive": int(predicted.sum()),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": safe_divide(tp, tp + fp),
        "recall": safe_divide(tp, tp + fn),
        "f1": safe_divide(2 * tp, 2 * tp + fp + fn),
        "specificity": safe_divide(tn, tn + fp),
        "accuracy": safe_divide(tp + tn, len(y_true)),
    }


def select_threshold(
    y_true: np.ndarray,
    scores: np.ndarray,
    minimum_specificity: float,
) -> dict[str, Any]:
    candidates = np.unique(scores.astype(float))
    evaluated = [
        metrics_at_threshold(y_true, scores, float(threshold))
        for threshold in candidates
    ]
    eligible = [
        row
        for row in evaluated
        if row["specificity"] >= minimum_specificity
    ]
    if not eligible:
        raise RuntimeError(
            "No threshold satisfies specificity >= "
            f"{minimum_specificity}"
        )
    return max(
        eligible,
        key=lambda row: (row["f1"], row["precision"], row["threshold"]),
    )


def normalize_scores(
    raw_scores: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    scores = raw_scores.copy()
    normalization: dict[str, dict[str, Any]] = {}
    for label in LABELS:
        raw = raw_scores[raw_column(label)].to_numpy(dtype=float)
        mean = float(np.mean(raw))
        std = float(np.std(raw, ddof=0))
        if not np.isfinite(mean) or not np.isfinite(std) or std <= 0:
            raise RuntimeError(
                f"Invalid validation normalization for {label}: "
                f"mean={mean}, std={std}"
            )
        scores[label] = (raw - mean) / std
        normalization[label] = {
            "raw_mean": mean,
            "raw_std": std,
            "method": "zscore_population",
            "ddof": 0,
            "fit_split": "competition_validation_only",
        }
        normalized = scores[label].to_numpy(dtype=float)
        if not np.isclose(np.mean(normalized), 0.0, atol=1e-6):
            raise RuntimeError(f"Normalized mean check failed for {label}")
        if not np.isclose(np.std(normalized, ddof=0), 1.0, atol=1e-6):
            raise RuntimeError(f"Normalized std check failed for {label}")
    metadata_columns = [
        "model_name",
        "policy_version",
        "study_key",
        "frontal_view_count",
        "frontal_dicom_paths",
    ]
    source_columns = [
        column
        for label in LABELS
        for column in (
            positive_column(label),
            negative_column(label),
            raw_column(label),
        )
    ]
    return scores.loc[:, [*metadata_columns, *LABELS, *source_columns]], normalization


def tune_thresholds(
    scores: pd.DataFrame,
    ground_truth: pd.DataFrame,
    minimum_specificity: float,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    dict[str, float],
    dict[str, float],
    dict[str, float],
]:
    long_scores = scores.melt(
        id_vars=["study_key"],
        value_vars=list(LABELS),
        var_name="label",
        value_name="score",
    )
    raw_long = scores.melt(
        id_vars=["study_key"],
        value_vars=[raw_column(label) for label in LABELS],
        var_name="raw_label",
        value_name="raw_score",
    )
    raw_long["label"] = raw_long["raw_label"].str.removeprefix("raw_")
    raw_long = raw_long.drop(columns="raw_label")
    joined = long_scores.merge(
        raw_long,
        on=["study_key", "label"],
        validate="one_to_one",
    )
    truth = ground_truth.loc[
        :, ["study_key", "label", "ground_truth_status"]
    ].copy()
    joined = joined.merge(
        truth,
        on=["study_key", "label"],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if not joined["_merge"].eq("both").all():
        raise RuntimeError(
            "Validation scores and ground truth do not align: "
            f"{joined['_merge'].value_counts().to_dict()}"
        )
    joined = joined.drop(columns="_merge")
    joined["ground_truth"] = (
        joined["ground_truth_status"].astype(str).eq("present").astype(int)
    )

    report_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    thresholds: dict[str, float] = {}
    raw_thresholds: dict[str, float] = {}
    aurocs: dict[str, float] = {}
    average_precisions: dict[str, float] = {}

    for label in LABELS:
        rows = joined.loc[joined["label"].eq(label)].copy()
        rows = rows.sort_values("study_key", kind="stable").reset_index(drop=True)
        y_true = rows["ground_truth"].to_numpy(dtype=int)
        label_scores = rows["score"].to_numpy(dtype=float)
        if set(np.unique(y_true)) != {0, 1}:
            raise RuntimeError(f"{label} lacks both validation classes")
        selected = select_threshold(
            y_true, label_scores, minimum_specificity
        )
        threshold = float(selected["threshold"])
        thresholds[label] = threshold
        selected_raw_values = rows.loc[
            np.isclose(label_scores, threshold, rtol=0.0, atol=1e-12),
            "raw_score",
        ]
        if selected_raw_values.empty:
            raise RuntimeError(f"Unable to recover raw threshold for {label}")
        raw_thresholds[label] = float(selected_raw_values.iloc[0])
        aurocs[label] = float(roc_auc_score(y_true, label_scores))
        average_precisions[label] = float(
            average_precision_score(y_true, label_scores)
        )
        report_rows.append(
            {
                "label": label,
                **selected,
                "raw_margin_threshold": raw_thresholds[label],
                "study_count": len(rows),
                "ground_truth_positive": int(y_true.sum()),
                "ground_truth_negative": int((y_true == 0).sum()),
                "auroc": aurocs[label],
                "average_precision": average_precisions[label],
                "selection_metric": "f1",
                "minimum_specificity": minimum_specificity,
                "tie_breaker": "precision_then_higher_threshold",
            }
        )
        rows["threshold"] = threshold
        rows["predicted_positive"] = (
            rows["score"] >= threshold
        ).astype(int)
        rows["predicted_status"] = rows["predicted_positive"].map(
            {1: "present", 0: "absent"}
        )
        prediction_frames.append(rows)

    report = pd.DataFrame(report_rows).loc[
        :,
        [
            "label",
            "threshold",
            "raw_margin_threshold",
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
            "minimum_specificity",
            "tie_breaker",
        ],
    ]
    predictions = pd.concat(prediction_frames, ignore_index=True).loc[
        :,
        [
            "study_key",
            "label",
            "raw_score",
            "score",
            "threshold",
            "ground_truth_status",
            "ground_truth",
            "predicted_positive",
            "predicted_status",
        ],
    ]
    return report, predictions, thresholds, raw_thresholds, {
        "macro_auroc": float(np.mean(list(aurocs.values()))),
        "macro_average_precision": float(
            np.mean(list(average_precisions.values()))
        ),
    }


def aggregate_metrics(
    report: pd.DataFrame, predictions: pd.DataFrame
) -> dict[str, float]:
    y_true = predictions["ground_truth"].to_numpy(dtype=int)
    y_pred = predictions["predicted_positive"].to_numpy(dtype=int)
    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    return {
        "macro_precision": float(report["precision"].mean()),
        "macro_recall": float(report["recall"].mean()),
        "macro_f1": float(report["f1"].mean()),
        "macro_specificity": float(report["specificity"].mean()),
        "macro_accuracy": float(report["accuracy"].mean()),
        "micro_precision": safe_divide(tp, tp + fp),
        "micro_recall": safe_divide(tp, tp + fn),
        "micro_f1": safe_divide(2 * tp, 2 * tp + fp + fn),
        "micro_specificity": safe_divide(tn, tn + fp),
        "micro_accuracy": safe_divide(tp + tn, len(y_true)),
    }


def write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        frame.to_csv(temporary, index=False)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_json_atomic(value: dict[str, Any], path: Path) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    args = build_parser().parse_args()
    if not 0.0 <= args.minimum_specificity <= 1.0:
        raise ValueError("--minimum-specificity must be between 0 and 1")

    output_dir = resolve_directory(args.output_dir, "Exp20 output directory")
    prompt_policy_path = resolve_file(
        args.prompt_policy, "Exp20 prompt policy"
    )
    raw_scores_path = resolve_file(
        args.raw_scores, "validation raw scores"
    )
    inference_config_path = resolve_file(
        args.inference_config, "validation inference run config"
    )
    ground_truth_path = resolve_file(
        args.ground_truth, "validation ground truth"
    )
    script_path = Path(__file__).resolve()

    output_paths = {
        "scores": output_dir / "validation_scores.csv",
        "predictions": output_dir / "validation_predictions.csv",
        "report": output_dir / "validation_threshold_report.csv",
        "policy": output_dir / "threshold_policy.json",
        "policy_checksum": output_dir / "threshold_policy.sha256",
        "summary": output_dir / "validation_summary.json",
        "run_config": output_dir / "validation_threshold_run_config.json",
    }
    existing = [path for path in output_paths.values() if path.exists()]
    if existing:
        formatted = "\n".join(str(path) for path in existing)
        raise FileExistsError(
            "Refusing to overwrite existing validation threshold outputs:\n"
            + formatted
        )

    print("=== VERIFYING VALIDATION-ONLY INPUTS ===")
    (
        prompt_policy,
        prompt_policy_hash,
        inference_config,
        inference_config_hash,
        raw_scores,
        raw_scores_hash,
        ground_truth,
        ground_truth_hash,
    ) = validate_inference_inputs(
        prompt_policy_path=prompt_policy_path,
        raw_scores_path=raw_scores_path,
        inference_config_path=inference_config_path,
        ground_truth_path=ground_truth_path,
        expected_studies=args.expected_studies,
    )
    print("Prompt-policy SHA-256:", prompt_policy_hash)
    print("Inference-config SHA-256:", inference_config_hash)
    print("Raw-score SHA-256:", raw_scores_hash)
    print("Ground-truth SHA-256:", ground_truth_hash)
    print("Studies:", len(raw_scores))
    print("Study-label pairs:", len(ground_truth))
    print("Test cohort read:", False)

    scores, normalization = normalize_scores(raw_scores)
    (
        report,
        predictions,
        thresholds,
        raw_thresholds,
        ranking_metrics,
    ) = tune_thresholds(
        scores,
        ground_truth,
        args.minimum_specificity,
    )
    if not report["specificity"].ge(args.minimum_specificity).all():
        raise RuntimeError("A selected threshold violates the specificity floor")
    aggregate = {
        **ranking_metrics,
        **aggregate_metrics(report, predictions),
    }

    threshold_policy = {
        "policy_version": THRESHOLD_POLICY_VERSION,
        "experiment_id": "exp20",
        "model_name": MODEL_NAME,
        "source_prompt_policy_version": PROMPT_POLICY_VERSION,
        "source_prompt_policy_sha256": prompt_policy_hash,
        "selection_split": "competition_validation",
        "selection_metric": "per_label_maximum_f1_with_specificity_floor",
        "minimum_specificity": args.minimum_specificity,
        "tie_breaker": "maximum_precision_then_higher_threshold",
        "score_definition": "positive_similarity - negative_similarity",
        "study_aggregation": "mean_of_frontal_image_continuous_scores",
        "normalization": "per_label_validation_only_zscore_population",
        "validation_normalization": normalization,
        "selected_thresholds": thresholds,
        "selected_raw_margin_thresholds": raw_thresholds,
        "labels": list(LABELS),
        "prompts": prompt_policy["prompts"],
        "study_count": args.expected_studies,
        "study_label_count": args.expected_studies * len(LABELS),
        "frozen_inputs": {
            "validation_raw_scores": {
                "path": str(raw_scores_path),
                "sha256": raw_scores_hash,
            },
            "validation_inference_run_config": {
                "path": str(inference_config_path),
                "sha256": inference_config_hash,
            },
            "validation_ground_truth": {
                "path": str(ground_truth_path),
                "sha256": ground_truth_hash,
            },
            "prompt_policy": {
                "path": str(prompt_policy_path),
                "sha256": prompt_policy_hash,
            },
        },
        "test_data_used_for_selection": False,
    }
    summary = {
        "experiment_id": "exp20",
        "model_name": MODEL_NAME,
        "evaluation_split": "competition_validation",
        "study_count": args.expected_studies,
        "study_label_count": args.expected_studies * len(LABELS),
        "label_count": len(LABELS),
        "threshold_policy_version": THRESHOLD_POLICY_VERSION,
        "selection_metric": "per_label_maximum_f1_with_specificity_floor",
        "minimum_specificity": args.minimum_specificity,
        "selected_thresholds": thresholds,
        "selected_raw_margin_thresholds": raw_thresholds,
        **aggregate,
        "test_cohort_read": False,
    }

    for path in output_paths.values():
        if path.exists():
            raise FileExistsError(f"Output appeared during tuning: {path}")
    write_csv_atomic(scores, output_paths["scores"])
    write_csv_atomic(predictions, output_paths["predictions"])
    write_csv_atomic(report, output_paths["report"])
    write_json_atomic(threshold_policy, output_paths["policy"])
    threshold_policy_hash = sha256(output_paths["policy"])
    output_paths["policy_checksum"].write_text(
        f"{threshold_policy_hash}  threshold_policy.json\n",
        encoding="utf-8",
    )
    summary["threshold_policy_sha256"] = threshold_policy_hash
    write_json_atomic(summary, output_paths["summary"])

    artifact_hashes = {
        path.name: sha256(path)
        for key, path in output_paths.items()
        if key != "run_config"
    }
    run_config = {
        "experiment_id": "exp20",
        "model_name": MODEL_NAME,
        "script_path": str(script_path),
        "script_sha256": sha256(script_path),
        "python": sys.version,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": package_version("scikit-learn"),
        "input_hashes": {
            "prompt_policy": prompt_policy_hash,
            "validation_inference_run_config": inference_config_hash,
            "validation_raw_scores": raw_scores_hash,
            "validation_ground_truth": ground_truth_hash,
        },
        "inference_script_sha256": inference_config.get("script_sha256"),
        "minimum_specificity": args.minimum_specificity,
        "normalization": "validation_only_zscore_population_ddof_0",
        "selection_metric": "maximum_f1",
        "tie_breaker": "maximum_precision_then_higher_threshold",
        "test_cohort_read": False,
        "artifact_sha256": artifact_hashes,
    }
    write_json_atomic(run_config, output_paths["run_config"])

    print("\n=== SELECTED VALIDATION THRESHOLDS ===")
    print(
        report[
            [
                "label",
                "threshold",
                "raw_margin_threshold",
                "precision",
                "recall",
                "f1",
                "specificity",
                "auroc",
                "average_precision",
            ]
        ].to_string(index=False)
    )
    print("\n=== VALIDATION SUMMARY ===")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("\nThreshold-policy SHA-256:", threshold_policy_hash)
    for path in output_paths.values():
        print("Saved:", path)
    print("Test cohort read:", False)
    print("STEP 5 VALIDATION THRESHOLD TUNING SUCCEEDED")


if __name__ == "__main__":
    main()
