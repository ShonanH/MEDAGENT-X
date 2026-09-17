"""Evaluate saved GLoRIA test scores with a different frozen policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from run_gloria_test_evaluation import (
    LABELS,
    MODEL_NAME,
    PROJECT_ROOT,
    _evaluate,
    _load_policy,
    _raw_column,
    _require_file,
)


DEFAULT_SOURCE_DIR = (
    PROJECT_ROOT / "v2" / "experiments" / "gloria_zero_shot_comparison"
)
DEFAULT_POLICY_DIR = DEFAULT_SOURCE_DIR / "matched_exp17_policy"
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
            "Apply a frozen GLoRIA threshold policy to existing test study scores."
        )
    )
    parser.add_argument(
        "--test-scores",
        type=Path,
        default=DEFAULT_SOURCE_DIR / "test_scores.csv",
    )
    parser.add_argument(
        "--threshold-policy",
        type=Path,
        default=DEFAULT_POLICY_DIR / "threshold_policy.json",
    )
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_POLICY_DIR)
    parser.add_argument("--expected-studies", type=int, default=500)
    return parser


def _validate_saved_scores(
    scores: pd.DataFrame,
    policy: dict,
    expected_studies: int,
) -> None:
    required = {
        "model_name",
        "study_key",
        *LABELS,
        *(_raw_column(label) for label in LABELS),
    }
    missing = sorted(required - set(scores.columns))
    if missing:
        raise ValueError(f"Saved test scores are missing columns: {missing}")
    if len(scores) != expected_studies:
        raise ValueError(
            f"Expected {expected_studies} saved study rows, found {len(scores)}"
        )
    if scores["study_key"].nunique() != expected_studies:
        raise ValueError("Saved scores must contain exactly one row per study")
    if set(scores["model_name"].astype(str)) != {MODEL_NAME}:
        raise ValueError("Saved scores contain an unexpected model_name")

    # Prove that the saved normalized values use the same validation-only
    # parameters as the requested policy before reusing them.
    for label in LABELS:
        values = policy["validation_normalization"][label]
        reconstructed = (
            scores[_raw_column(label)].to_numpy(dtype=float)
            - float(values["raw_mean"])
        ) / float(values["raw_std"])
        saved = scores[label].to_numpy(dtype=float)
        maximum_error = float(np.max(np.abs(reconstructed - saved)))
        if maximum_error > 1e-5:
            raise ValueError(
                f"Saved {label} scores do not use the requested validation "
                f"normalization; maximum error={maximum_error}"
            )


def main() -> None:
    args = build_parser().parse_args()
    scores_path = _require_file(args.test_scores, "saved GLoRIA test scores")
    policy_path = _require_file(args.threshold_policy, "threshold policy")
    ground_truth_path = _require_file(args.ground_truth, "test ground truth")
    policy = _load_policy(policy_path)
    scores = pd.read_csv(scores_path)
    _validate_saved_scores(scores, policy, args.expected_studies)

    predictions, metrics, summary = _evaluate(
        scores, ground_truth_path, policy
    )
    summary["saved_test_scores_csv"] = str(scores_path)
    summary["threshold_policy_json"] = str(policy_path)
    summary["test_inference_reused"] = True

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = output_dir / "test_predictions.csv"
    metrics_path = output_dir / "test_per_label_metrics.csv"
    summary_path = output_dir / "test_summary.json"
    predictions.to_csv(predictions_path, index=False)
    metrics.to_csv(metrics_path, index=False)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    print("Per-label test metrics:")
    print(metrics.to_string(index=False))
    print("\nTest summary:")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"\nSaved predictions: {predictions_path}")
    print(f"Saved metrics: {metrics_path}")
    print(f"Saved summary: {summary_path}")


if __name__ == "__main__":
    main()
