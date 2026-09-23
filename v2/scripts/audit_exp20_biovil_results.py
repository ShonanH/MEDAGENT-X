"""Independently audit all frozen Exp20 BioViL evaluation artifacts.

The audit is read-only. It verifies artifact hashes and cohort identity,
reconstructs study aggregation and normalization, repeats validation threshold
selection, and recomputes validation and test metrics from saved rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPERIMENT_DIR = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp20_biovil_native_zero_shot_comparison"
)
DEFAULT_VALIDATION_MANIFEST = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp16_chexpert_competition_val_thresholds"
    / "competition_val_manifest.csv"
)
DEFAULT_VALIDATION_GROUND_TRUTH = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp16_chexpert_competition_val_thresholds"
    / "competition_val_ground_truth.csv"
)
DEFAULT_TEST_MANIFEST = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp14_chexpert_competition_auroc"
    / "competition_view_manifest.csv"
)
DEFAULT_TEST_GROUND_TRUTH = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp14_chexpert_competition_auroc"
    / "competition_ground_truth.csv"
)
DEFAULT_EXP17_DIR = (
    PROJECT_ROOT / "v2" / "experiments" / "exp17_constrained_thresholds"
)

MODEL_NAME = "biovil_resnet50_native_zero_shot"
PROMPT_POLICY_VERSION = "biovil_native_positive_negative_margin_exp20_v1"
THRESHOLD_POLICY_VERSION = (
    "biovil_native_max_f1_specificity_floor_exp20_v1"
)
EXPECTED_HASHES = {
    "prompt_policy.json": (
        "086297ab423635da83acac73752c7a21"
        "a610f17a4be6bfda0d34f7214ec44a82"
    ),
    "threshold_policy.json": (
        "048f8f06857ebe9d47d0d0e1e5ee88e"
        "49eca7ff726a48660314d8258781775e5"
    ),
    "validation_inference_run_config.json": (
        "13534b3717e766bbbbfdd95cd2799a6e"
        "7c20b84699500add9f09cc2133653bba"
    ),
    "validation_raw_scores.csv": (
        "e00203689ad3147e3e595318537cb33d"
        "e6f31a5848e43a2ea938f75f475bc941"
    ),
    "test_prediction_lock.json": (
        "3d3582dfecf021ac0c79947509f37518"
        "26c7a371dda86490c5fd9e74b39d70e0"
    ),
}
EXPECTED_TEST_EVALUATOR_SHA256 = (
    "49450e7bc7a5eba65de2b91cca9cf505"
    "604987256704f5e635bb073b9e525330"
)
EXPECTED_COHORT_HASHES = {
    "validation_manifest": (
        "684f12cc181a6fb987436e0ef01ccc7d"
        "dfd8b86f60669c78e564ff39ebb306be"
    ),
    "validation_ground_truth": (
        "1caf1a4639711f32a1566ab514aed4d7"
        "9f45f6f3477152c19811370586453026"
    ),
    "test_manifest": (
        "fe4084cbb7acb349ffe9aa45f5e56074"
        "0562f76ce6496c3436918fee6444f6aa"
    ),
    "test_ground_truth": (
        "9bab723d2051e2c35b3869e8d659c71"
        "c9c3da78ea21814d3a337120e4150f489"
    ),
}
LABELS = (
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
)
FLOAT_TOLERANCE = 1e-9


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only integrity and metric audit for Exp20 BioViL."
    )
    parser.add_argument(
        "--experiment-dir", type=Path, default=DEFAULT_EXPERIMENT_DIR
    )
    parser.add_argument(
        "--validation-manifest",
        type=Path,
        default=DEFAULT_VALIDATION_MANIFEST,
    )
    parser.add_argument(
        "--validation-ground-truth",
        type=Path,
        default=DEFAULT_VALIDATION_GROUND_TRUTH,
    )
    parser.add_argument(
        "--test-manifest", type=Path, default=DEFAULT_TEST_MANIFEST
    )
    parser.add_argument(
        "--test-ground-truth", type=Path, default=DEFAULT_TEST_GROUND_TRUTH
    )
    parser.add_argument("--exp17-dir", type=Path, default=DEFAULT_EXP17_DIR)
    return parser


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Missing {description}: {resolved}")
    return resolved


def require_directory(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"Missing {description}: {resolved}")
    return resolved


def assert_equal(observed: Any, expected: Any, description: str) -> None:
    if observed != expected:
        raise RuntimeError(
            f"{description}: expected {expected!r}, observed {observed!r}"
        )


def assert_close(
    observed: float,
    expected: float,
    description: str,
    tolerance: float = FLOAT_TOLERANCE,
) -> None:
    if not np.isclose(observed, expected, rtol=0.0, atol=tolerance):
        raise RuntimeError(
            f"{description}: expected {expected}, observed {observed}"
        )


def positive_column(label: str) -> str:
    return f"positive_{label}"


def negative_column(label: str) -> str:
    return f"negative_{label}"


def raw_column(label: str) -> str:
    return f"raw_{label}"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def verify_checksum_file(
    artifact_path: Path, checksum_path: Path
) -> None:
    fields = checksum_path.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[1] != artifact_path.name:
        raise RuntimeError(f"Malformed checksum file: {checksum_path}")
    assert_equal(sha256(artifact_path), fields[0], f"Checksum for {artifact_path}")


def verify_recorded_hashes(
    root: Path, recorded: dict[str, str], description: str
) -> None:
    for filename, expected in recorded.items():
        path = require_file(root / filename, f"{description}: {filename}")
        assert_equal(sha256(path), expected, f"{description}: {filename}")


def safe_divide(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def binary_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, scores: np.ndarray
) -> dict[str, float | int]:
    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    return {
        "study_count": len(y_true),
        "ground_truth_positive": int(y_true.sum()),
        "ground_truth_negative": int((y_true == 0).sum()),
        "predicted_positive": int(y_pred.sum()),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": safe_divide(tp, tp + fp),
        "recall": safe_divide(tp, tp + fn),
        "f1": safe_divide(2 * tp, 2 * tp + fp + fn),
        "specificity": safe_divide(tn, tn + fp),
        "accuracy": safe_divide(tp + tn, len(y_true)),
        "auroc": float(roc_auc_score(y_true, scores)),
        "average_precision": float(average_precision_score(y_true, scores)),
    }


def compare_metric_table(
    rows: pd.DataFrame,
    reported: pd.DataFrame,
    description: str,
) -> tuple[pd.DataFrame, dict[str, float]]:
    recalculated_rows: list[dict[str, Any]] = []
    for label in LABELS:
        subset = rows.loc[rows["label"].eq(label)].copy()
        subset = subset.sort_values("study_key", kind="stable")
        y_true = subset["ground_truth"].to_numpy(dtype=int)
        y_pred = subset["predicted_positive"].to_numpy(dtype=int)
        scores = subset["score"].to_numpy(dtype=float)
        values = {"label": label, **binary_metrics(y_true, y_pred, scores)}
        values["threshold"] = float(subset["threshold"].iloc[0])
        recalculated_rows.append(values)
    recalculated = pd.DataFrame(recalculated_rows)
    reported_by_label = reported.set_index("label")
    integer_columns = (
        "study_count",
        "ground_truth_positive",
        "ground_truth_negative",
        "predicted_positive",
        "tp",
        "tn",
        "fp",
        "fn",
    )
    float_columns = (
        "threshold",
        "precision",
        "recall",
        "f1",
        "specificity",
        "accuracy",
        "auroc",
        "average_precision",
    )
    for item in recalculated.to_dict(orient="records"):
        label = item["label"]
        if label not in reported_by_label.index:
            raise RuntimeError(f"{description} lacks {label}")
        for column in integer_columns:
            assert_equal(
                int(reported_by_label.loc[label, column]),
                int(item[column]),
                f"{description} {label} {column}",
            )
        for column in float_columns:
            assert_close(
                float(reported_by_label.loc[label, column]),
                float(item[column]),
                f"{description} {label} {column}",
            )

    y_true_all = rows["ground_truth"].to_numpy(dtype=int)
    y_pred_all = rows["predicted_positive"].to_numpy(dtype=int)
    tp = int(np.sum((y_pred_all == 1) & (y_true_all == 1)))
    tn = int(np.sum((y_pred_all == 0) & (y_true_all == 0)))
    fp = int(np.sum((y_pred_all == 1) & (y_true_all == 0)))
    fn = int(np.sum((y_pred_all == 0) & (y_true_all == 1)))
    aggregate = {
        "macro_auroc": float(recalculated["auroc"].mean()),
        "macro_average_precision": float(
            recalculated["average_precision"].mean()
        ),
        "macro_precision": float(recalculated["precision"].mean()),
        "macro_recall": float(recalculated["recall"].mean()),
        "macro_f1": float(recalculated["f1"].mean()),
        "macro_specificity": float(recalculated["specificity"].mean()),
        "macro_accuracy": float(recalculated["accuracy"].mean()),
        "micro_precision": safe_divide(tp, tp + fp),
        "micro_recall": safe_divide(tp, tp + fn),
        "micro_f1": safe_divide(2 * tp, 2 * tp + fp + fn),
        "micro_specificity": safe_divide(tn, tn + fp),
        "micro_accuracy": safe_divide(tp + tn, len(y_true_all)),
    }
    return recalculated, aggregate


def verify_summary(
    summary: dict[str, Any], aggregate: dict[str, float], description: str
) -> None:
    for name, expected in aggregate.items():
        assert_close(float(summary[name]), expected, f"{description} {name}")


def verify_margin_identity(frame: pd.DataFrame, description: str) -> None:
    for label in LABELS:
        positive = frame[positive_column(label)].to_numpy(dtype=float)
        negative = frame[negative_column(label)].to_numpy(dtype=float)
        margin = frame[raw_column(label)].to_numpy(dtype=float)
        if not np.allclose(
            positive - negative, margin, rtol=0.0, atol=1e-6
        ):
            raise RuntimeError(f"{description} margin identity failed for {label}")


def verify_study_aggregation(
    image_scores: pd.DataFrame,
    study_scores: pd.DataFrame,
    expected_multi_view: int,
    description: str,
) -> None:
    score_columns = [
        column
        for label in LABELS
        for column in (
            positive_column(label),
            negative_column(label),
            raw_column(label),
        )
    ]
    expected = image_scores.groupby("study_key", sort=True)[score_columns].mean()
    observed = study_scores.set_index("study_key").loc[expected.index]
    expected_values = expected.to_numpy(dtype=float)
    observed_values = observed[score_columns].to_numpy(dtype=float)
    absolute_difference = np.abs(expected_values - observed_values)
    maximum_difference = float(np.max(absolute_difference))
    maximum_position = np.unravel_index(
        int(np.argmax(absolute_difference)), absolute_difference.shape
    )
    maximum_study = str(expected.index[maximum_position[0]])
    maximum_column = score_columns[maximum_position[1]]
    print(
        f"{description} aggregation maximum absolute difference: "
        f"{maximum_difference:.12g}"
    )
    if maximum_difference > 1e-6:
        expected_value = float(expected_values[maximum_position])
        observed_value = float(observed_values[maximum_position])
        raise RuntimeError(
            f"{description} study aggregation changed beyond float32 "
            f"tolerance: study={maximum_study!r}, "
            f"column={maximum_column!r}, expected={expected_value}, "
            f"observed={observed_value}, difference={maximum_difference}"
        )
    expected_counts = image_scores.groupby("study_key").size().sort_index()
    observed_counts = observed["frontal_view_count"].astype(int).sort_index()
    if not expected_counts.equals(observed_counts):
        raise RuntimeError(f"{description} frontal view counts changed")
    assert_equal(
        int((observed_counts > 1).sum()),
        expected_multi_view,
        f"{description} multi-frontal study count",
    )


def verify_normalization(
    scores: pd.DataFrame,
    policy: dict[str, Any],
    validation: bool,
    description: str,
) -> None:
    normalization = policy["validation_normalization"]
    for label in LABELS:
        raw = scores[raw_column(label)].to_numpy(dtype=float)
        mean = float(normalization[label]["raw_mean"])
        std = float(normalization[label]["raw_std"])
        expected = (raw - mean) / std
        observed = scores[label].to_numpy(dtype=float)
        if not np.allclose(expected, observed, rtol=0.0, atol=1e-8):
            raise RuntimeError(f"{description} normalization failed for {label}")
        if validation:
            assert_close(
                float(np.mean(observed)),
                0.0,
                f"{description} normalized mean for {label}",
                tolerance=1e-7,
            )
            assert_close(
                float(np.std(observed, ddof=0)),
                1.0,
                f"{description} normalized std for {label}",
                tolerance=1e-7,
            )


def verify_predictions_against_scores(
    scores: pd.DataFrame,
    predictions: pd.DataFrame,
    policy: dict[str, Any],
    description: str,
) -> None:
    score_index = scores.set_index("study_key")
    for label in LABELS:
        rows = predictions.loc[predictions["label"].eq(label)].copy()
        rows = rows.set_index("study_key").loc[score_index.index]
        expected_scores = score_index[label].to_numpy(dtype=float)
        expected_raw = score_index[raw_column(label)].to_numpy(dtype=float)
        threshold = float(policy["selected_thresholds"][label])
        if not np.allclose(
            rows["score"].to_numpy(dtype=float),
            expected_scores,
            rtol=0.0,
            atol=1e-9,
        ):
            raise RuntimeError(f"{description} scores differ for {label}")
        if not np.allclose(
            rows["raw_score"].to_numpy(dtype=float),
            expected_raw,
            rtol=0.0,
            atol=1e-9,
        ):
            raise RuntimeError(f"{description} raw scores differ for {label}")
        expected_predictions = (expected_scores >= threshold).astype(int)
        if not np.array_equal(
            rows["predicted_positive"].to_numpy(dtype=int),
            expected_predictions,
        ):
            raise RuntimeError(f"{description} predictions differ for {label}")
        if not np.allclose(
            rows["threshold"].to_numpy(dtype=float),
            threshold,
            rtol=0.0,
            atol=1e-12,
        ):
            raise RuntimeError(f"{description} thresholds differ for {label}")


def verify_threshold_selection(
    validation_predictions: pd.DataFrame,
    threshold_report: pd.DataFrame,
    threshold_policy: dict[str, Any],
) -> None:
    minimum_specificity = float(threshold_policy["minimum_specificity"])
    report = threshold_report.set_index("label")
    for label in LABELS:
        rows = validation_predictions.loc[
            validation_predictions["label"].eq(label)
        ].copy()
        y_true = rows["ground_truth"].to_numpy(dtype=int)
        scores = rows["score"].to_numpy(dtype=float)
        candidates: list[dict[str, float]] = []
        for threshold in np.unique(scores):
            y_pred = (scores >= threshold).astype(int)
            values = binary_metrics(y_true, y_pred, scores)
            if float(values["specificity"]) >= minimum_specificity:
                candidates.append(
                    {
                        "threshold": float(threshold),
                        "f1": float(values["f1"]),
                        "precision": float(values["precision"]),
                    }
                )
        if not candidates:
            raise RuntimeError(f"No eligible validation threshold for {label}")
        selected = max(
            candidates,
            key=lambda row: (
                row["f1"],
                row["precision"],
                row["threshold"],
            ),
        )
        expected = float(threshold_policy["selected_thresholds"][label])
        assert_close(
            selected["threshold"], expected, f"Selected threshold for {label}"
        )
        assert_close(
            float(report.loc[label, "threshold"]),
            expected,
            f"Threshold report for {label}",
        )
        if float(report.loc[label, "specificity"]) < minimum_specificity:
            raise RuntimeError(f"Specificity floor violated for {label}")


def verify_ground_truth_rows(
    evaluation_rows: pd.DataFrame,
    source_path: Path,
    description: str,
) -> None:
    source = pd.read_csv(source_path)
    source = source.loc[source["label"].isin(LABELS)].copy()
    source["expected_ground_truth"] = (
        source["ground_truth_status"].astype(str).eq("present").astype(int)
    )
    comparison = evaluation_rows.loc[
        :, ["study_key", "label", "ground_truth"]
    ].merge(
        source.loc[:, ["study_key", "label", "expected_ground_truth"]],
        on=["study_key", "label"],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if not comparison["_merge"].eq("both").all():
        raise RuntimeError(f"{description} ground-truth rows do not align")
    if not np.array_equal(
        comparison["ground_truth"].to_numpy(dtype=int),
        comparison["expected_ground_truth"].to_numpy(dtype=int),
    ):
        raise RuntimeError(f"{description} ground-truth values changed")


def main() -> None:
    args = build_parser().parse_args()
    experiment_dir = require_directory(
        args.experiment_dir, "Exp20 experiment directory"
    )
    exp17_dir = require_directory(args.exp17_dir, "Exp17 experiment directory")
    validation_manifest = require_file(
        args.validation_manifest, "validation manifest"
    )
    validation_ground_truth = require_file(
        args.validation_ground_truth, "validation ground truth"
    )
    test_manifest = require_file(args.test_manifest, "test manifest")
    test_ground_truth = require_file(args.test_ground_truth, "test ground truth")

    filenames = (
        "prompt_policy.json",
        "prompt_policy.sha256",
        "validation_image_scores.csv",
        "validation_raw_scores.csv",
        "validation_inference_run_config.json",
        "validation_scores.csv",
        "validation_predictions.csv",
        "validation_threshold_report.csv",
        "threshold_policy.json",
        "threshold_policy.sha256",
        "validation_summary.json",
        "validation_threshold_run_config.json",
        "test_image_scores.csv",
        "test_raw_scores.csv",
        "test_scores.csv",
        "test_predictions.csv",
        "test_prediction_lock.json",
        "test_evaluation_rows.csv",
        "test_per_label_metrics.csv",
        "test_summary.json",
        "test_run_config.json",
    )
    paths = {
        name: require_file(experiment_dir / name, name) for name in filenames
    }

    print("=== ARTIFACT INTEGRITY ===")
    for filename, expected in EXPECTED_HASHES.items():
        assert_equal(sha256(paths[filename]), expected, filename)
        print(f"OK  {filename}: {expected}")
    verify_checksum_file(
        paths["prompt_policy.json"], paths["prompt_policy.sha256"]
    )
    verify_checksum_file(
        paths["threshold_policy.json"], paths["threshold_policy.sha256"]
    )

    prompt_policy = read_json(paths["prompt_policy.json"])
    threshold_policy = read_json(paths["threshold_policy.json"])
    validation_inference_config = read_json(
        paths["validation_inference_run_config.json"]
    )
    validation_threshold_config = read_json(
        paths["validation_threshold_run_config.json"]
    )
    test_lock = read_json(paths["test_prediction_lock.json"])
    test_run_config = read_json(paths["test_run_config.json"])
    validation_summary = read_json(paths["validation_summary.json"])
    test_summary = read_json(paths["test_summary.json"])

    assert_equal(
        prompt_policy["policy_version"],
        PROMPT_POLICY_VERSION,
        "Prompt-policy version",
    )
    assert_equal(
        threshold_policy["policy_version"],
        THRESHOLD_POLICY_VERSION,
        "Threshold-policy version",
    )
    assert_equal(
        threshold_policy["source_prompt_policy_sha256"],
        EXPECTED_HASHES["prompt_policy.json"],
        "Threshold-to-prompt linkage",
    )
    assert_equal(
        threshold_policy["test_data_used_for_selection"],
        False,
        "Test data used for threshold selection",
    )
    assert_equal(
        validation_inference_config["ground_truth_read"],
        False,
        "Ground truth read during validation inference",
    )
    verify_recorded_hashes(
        experiment_dir,
        validation_inference_config["outputs"]["sha256"],
        "Validation inference outputs",
    )
    verify_recorded_hashes(
        experiment_dir,
        validation_threshold_config["artifact_sha256"],
        "Validation threshold outputs",
    )
    verify_recorded_hashes(
        experiment_dir,
        test_lock["artifact_sha256"],
        "Locked test predictions",
    )
    verify_recorded_hashes(
        experiment_dir,
        test_run_config["artifact_sha256"],
        "Final test outputs",
    )
    assert_equal(
        test_lock["test_ground_truth_opened_before_prediction_lock"],
        False,
        "Ground truth opened before prediction lock",
    )
    assert_equal(
        test_lock["test_time_tuning"], False, "Test-lock tuning flag"
    )
    assert_equal(
        test_run_config["predictions_locked_before_ground_truth"],
        True,
        "Prediction-lock flag",
    )
    assert_equal(
        test_run_config["test_time_tuning"], False, "Test run tuning flag"
    )
    assert_equal(
        test_run_config["script_sha256"],
        EXPECTED_TEST_EVALUATOR_SHA256,
        "Locked test evaluator hash",
    )
    evaluator_path = require_file(
        Path(test_run_config["script_path"]), "locked test evaluator"
    )
    assert_equal(
        sha256(evaluator_path),
        EXPECTED_TEST_EVALUATOR_SHA256,
        "Current test evaluator hash",
    )
    evaluator_source = evaluator_path.read_text(encoding="utf-8")
    for forbidden in ("select_threshold", "np.mean(", "np.std(", ".fit("):
        if forbidden in evaluator_source:
            raise RuntimeError(
                f"Locked test evaluator contains forbidden fitting token: {forbidden}"
            )
    prediction_columns = set(pd.read_csv(paths["test_predictions.csv"], nrows=0))
    if {"ground_truth", "ground_truth_status"} & prediction_columns:
        raise RuntimeError("Locked test predictions contain ground truth")
    print("All recorded artifact hashes and locking controls passed.")

    print("\n=== COHORT IDENTITY ===")
    cohort_paths = {
        "validation_manifest": validation_manifest,
        "validation_ground_truth": validation_ground_truth,
        "test_manifest": test_manifest,
        "test_ground_truth": test_ground_truth,
    }
    for name, path in cohort_paths.items():
        assert_equal(sha256(path), EXPECTED_COHORT_HASHES[name], name)
        print(f"OK  {name}: {EXPECTED_COHORT_HASHES[name]}")
    exp17_pairs = (
        (
            validation_manifest,
            exp17_dir / "competition_val_manifest.csv",
            "Exp17 validation manifest",
        ),
        (
            validation_ground_truth,
            exp17_dir / "competition_val_ground_truth.csv",
            "Exp17 validation ground truth",
        ),
        (
            test_manifest,
            exp17_dir / "competition_fusion" / "competition_view_manifest.csv",
            "Exp17 test manifest",
        ),
        (
            test_ground_truth,
            exp17_dir / "competition_fusion" / "competition_ground_truth.csv",
            "Exp17 test ground truth",
        ),
    )
    for source, comparison, description in exp17_pairs:
        comparison = require_file(comparison, description)
        assert_equal(sha256(source), sha256(comparison), description)
        print("IDENTICAL", description)
    validation_studies = set(pd.read_csv(validation_manifest)["study_key"])
    test_studies = set(pd.read_csv(test_manifest)["study_key"])
    assert_equal(
        len(validation_studies & test_studies), 0, "Validation/test overlap"
    )

    print("\n=== SCORE AND AGGREGATION AUDIT ===")
    validation_images = pd.read_csv(paths["validation_image_scores.csv"])
    validation_raw = pd.read_csv(paths["validation_raw_scores.csv"])
    validation_scores = pd.read_csv(paths["validation_scores.csv"])
    validation_predictions = pd.read_csv(paths["validation_predictions.csv"])
    validation_report = pd.read_csv(paths["validation_threshold_report.csv"])
    test_images = pd.read_csv(paths["test_image_scores.csv"])
    test_raw = pd.read_csv(paths["test_raw_scores.csv"])
    test_scores = pd.read_csv(paths["test_scores.csv"])
    test_predictions = pd.read_csv(paths["test_predictions.csv"])
    test_rows = pd.read_csv(paths["test_evaluation_rows.csv"])
    test_metrics = pd.read_csv(paths["test_per_label_metrics.csv"])

    expected_counts = {
        "validation image scores": (len(validation_images), 202),
        "validation raw scores": (len(validation_raw), 200),
        "validation scores": (len(validation_scores), 200),
        "validation predictions": (len(validation_predictions), 1000),
        "validation report": (len(validation_report), 5),
        "test image scores": (len(test_images), 518),
        "test raw scores": (len(test_raw), 500),
        "test scores": (len(test_scores), 500),
        "test predictions": (len(test_predictions), 2500),
        "test evaluation rows": (len(test_rows), 2500),
        "test metrics": (len(test_metrics), 5),
    }
    for description, (observed, expected) in expected_counts.items():
        assert_equal(observed, expected, description)
    for frame, description in (
        (validation_raw, "validation raw scores"),
        (validation_scores, "validation scores"),
        (test_raw, "test raw scores"),
        (test_scores, "test scores"),
    ):
        if frame["study_key"].duplicated().any():
            raise RuntimeError(f"Duplicate study key in {description}")
    for frame, description in (
        (validation_predictions, "validation predictions"),
        (test_predictions, "test predictions"),
        (test_rows, "test evaluation rows"),
    ):
        if frame.duplicated(["study_key", "label"]).any():
            raise RuntimeError(f"Duplicate study-label row in {description}")

    verify_margin_identity(validation_images, "Validation image")
    verify_margin_identity(validation_raw, "Validation study")
    verify_margin_identity(test_images, "Test image")
    verify_margin_identity(test_raw, "Test study")
    verify_study_aggregation(
        validation_images,
        validation_raw,
        expected_multi_view=2,
        description="Validation",
    )
    verify_study_aggregation(
        test_images,
        test_raw,
        expected_multi_view=18,
        description="Test",
    )
    verify_normalization(
        validation_scores,
        threshold_policy,
        validation=True,
        description="Validation",
    )
    verify_normalization(
        test_scores,
        threshold_policy,
        validation=False,
        description="Test",
    )
    verify_predictions_against_scores(
        validation_scores,
        validation_predictions,
        threshold_policy,
        "Validation",
    )
    verify_predictions_against_scores(
        test_scores, test_predictions, threshold_policy, "Test"
    )
    verify_threshold_selection(
        validation_predictions, validation_report, threshold_policy
    )
    print("Margins, aggregation, normalization, predictions, and thresholds passed.")

    print("\n=== INDEPENDENT METRIC RECALCULATION ===")
    verify_ground_truth_rows(
        validation_predictions,
        validation_ground_truth,
        "Validation",
    )
    verify_ground_truth_rows(test_rows, test_ground_truth, "Test")
    _, validation_aggregate = compare_metric_table(
        validation_predictions,
        validation_report,
        "Validation threshold report",
    )
    _, test_aggregate = compare_metric_table(
        test_rows, test_metrics, "Test per-label metrics"
    )
    verify_summary(
        validation_summary, validation_aggregate, "Validation summary"
    )
    verify_summary(test_summary, test_aggregate, "Test summary")
    assert_equal(test_summary["study_count"], 500, "Test summary studies")
    assert_equal(
        test_summary["study_label_count"], 2500, "Test summary labels"
    )
    assert_equal(test_summary["test_time_tuning"], False, "Summary tuning flag")
    assert_equal(
        test_summary["predictions_locked_before_ground_truth"],
        True,
        "Summary prediction-lock flag",
    )
    print("Validation and test metrics independently reproduce exactly.")

    print("\n=== AUDITED TEST SUMMARY ===")
    for name in (
        "macro_auroc",
        "macro_average_precision",
        "macro_f1",
        "macro_precision",
        "macro_recall",
        "macro_specificity",
        "micro_f1",
        "micro_precision",
        "micro_recall",
        "micro_specificity",
        "micro_accuracy",
    ):
        print(f"{name}: {test_aggregate[name]:.12f}")
    print("\nNo files were created or changed.")
    print("STEP 8 EXP20 AUDIT SUCCEEDED")


if __name__ == "__main__":
    main()
