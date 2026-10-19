"""Evaluate locked MedCLIP test predictions without rerunning image inference.

Use this after recovering the held-out ground-truth CSV when the original test
manifest or image inventory is no longer available. The command verifies the
prediction hash from ``test_prediction_lock.json`` before it opens labels.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

import run_medclip_test_evaluation as test_evaluation
import run_medclip_validation_inference as medclip


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "v2" / "experiments" / "medclip_zero_shot_comparison"
DEFAULT_GROUND_TRUTH = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp14_chexpert_competition_auroc"
    / "competition_ground_truth.csv"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate already locked MedCLIP test predictions. This command "
            "does not require a test manifest, images, or a model checkpoint."
        )
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "test_predictions.csv",
    )
    parser.add_argument(
        "--prediction-lock",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "test_prediction_lock.json",
    )
    parser.add_argument(
        "--threshold-policy",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "threshold_policy.json",
    )
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--expected-studies", type=int, default=500)
    return parser


def load_prediction_lock(path: Path, predictions_path: Path, policy_path: Path) -> dict[str, Any]:
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("model_name") != medclip.MODEL_NAME:
        raise ValueError("Prediction lock is not for the MedCLIP ViT baseline")
    expected_prediction_hash = lock.get("artifact_sha256", {}).get(
        predictions_path.name
    )
    observed_prediction_hash = test_evaluation.sha256(predictions_path)
    if expected_prediction_hash != observed_prediction_hash:
        raise RuntimeError(
            "Locked predictions have changed: expected SHA-256 "
            f"{expected_prediction_hash}, observed {observed_prediction_hash}"
        )
    expected_policy_hash = lock.get("threshold_policy_sha256")
    observed_policy_hash = test_evaluation.sha256(policy_path)
    if expected_policy_hash != observed_policy_hash:
        raise RuntimeError(
            "Threshold policy differs from the one used for locked predictions: "
            f"expected {expected_policy_hash}, observed {observed_policy_hash}"
        )
    return lock


def validate_predictions(predictions: pd.DataFrame, expected_studies: int) -> None:
    required = {
        "model_name",
        "study_key",
        "label",
        "score",
        "threshold",
        "predicted_positive",
        "predicted_status",
    }
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError(f"Saved predictions are missing columns: {missing}")
    expected_rows = expected_studies * len(medclip.LABELS)
    if len(predictions) != expected_rows:
        raise ValueError(f"Expected {expected_rows} predictions, found {len(predictions)}")
    if predictions["study_key"].nunique() != expected_studies:
        raise ValueError("Saved predictions do not contain one row per study and label")
    if predictions.duplicated(["study_key", "label"]).any():
        raise ValueError("Saved predictions contain duplicate study-label rows")
    if set(predictions["model_name"].astype(str)) != {medclip.MODEL_NAME}:
        raise ValueError("Saved predictions contain an unexpected model_name")
    if set(predictions["label"].astype(str)) != set(medclip.LABELS):
        raise ValueError("Saved predictions contain an unexpected label set")
    if set(predictions["predicted_status"].astype(str)) - {"present", "absent"}:
        raise ValueError("Saved predictions contain invalid predicted statuses")


def main() -> None:
    args = build_parser().parse_args()
    predictions_path = medclip.resolve_file(args.predictions, "locked test predictions")
    lock_path = medclip.resolve_file(args.prediction_lock, "prediction lock")
    policy_path = medclip.resolve_file(args.threshold_policy, "threshold policy")
    # The lock and policy are validated before accessing any labels.
    lock = load_prediction_lock(lock_path, predictions_path, policy_path)
    predictions = pd.read_csv(predictions_path)
    validate_predictions(predictions, args.expected_studies)

    ground_truth_path = medclip.resolve_file(args.ground_truth, "test ground truth")
    evaluation_rows, metrics, aggregate = test_evaluation.evaluate_predictions(
        predictions, ground_truth_path
    )
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "evaluation_rows": output_dir / "test_evaluation_rows.csv",
        "metrics": output_dir / "test_per_label_metrics.csv",
        "summary": output_dir / "test_summary.json",
    }
    existing = [path for path in outputs.values() if path.exists()]
    if existing:
        raise FileExistsError(
            "Refusing to overwrite existing MedCLIP evaluation outputs:\n"
            + "\n".join(str(path) for path in existing)
        )
    test_evaluation.write_csv_atomic(evaluation_rows, outputs["evaluation_rows"])
    test_evaluation.write_csv_atomic(metrics, outputs["metrics"])
    summary: dict[str, Any] = {
        "model_name": medclip.MODEL_NAME,
        "evaluation_split": "competition_test",
        "study_count": args.expected_studies,
        "study_label_count": len(predictions),
        "label_count": len(medclip.LABELS),
        "test_inference_reused": True,
        "predictions_locked_before_ground_truth": True,
        "prediction_lock_sha256": test_evaluation.sha256(lock_path),
        "test_predictions_sha256": test_evaluation.sha256(predictions_path),
        "threshold_policy_sha256": test_evaluation.sha256(policy_path),
        "test_manifest_sha256": lock["test_manifest_sha256"],
        **aggregate,
    }
    test_evaluation.write_json_atomic(summary, outputs["summary"])
    print(metrics.to_string(index=False))
    print(json.dumps(summary, indent=2, sort_keys=True))
    for name, path in outputs.items():
        print(f"Saved {name}: {path}")


if __name__ == "__main__":
    main()
