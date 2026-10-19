"""Evaluate frozen MedCLIP zero-shot policy on the held-out CheXpert cohort.

Predictions are generated and checksummed before this command opens the test
ground-truth CSV. Consequently, neither prompt selection, normalization, nor
threshold selection can use the test labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

import run_medclip_validation_inference as medclip


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPERIMENT_DIR = PROJECT_ROOT / "v2" / "experiments" / "medclip_zero_shot_comparison"
DEFAULT_MANIFEST = PROJECT_ROOT / "v2" / "experiments" / "exp14_chexpert_competition_auroc" / "competition_view_manifest.csv"
DEFAULT_GROUND_TRUTH = PROJECT_ROOT / "v2" / "experiments" / "exp14_chexpert_competition_auroc" / "competition_ground_truth.csv"
DEFAULT_IMAGE_ROOT = PROJECT_ROOT / "v2" / "data" / "chexpert_competition_test" / "chexlocalize" / "CheXpert" / "test"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run locked MedCLIP inference and evaluate the held-out CheXpert test set."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    parser.add_argument("--threshold-policy", type=Path, default=DEFAULT_EXPERIMENT_DIR / "threshold_policy.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_EXPERIMENT_DIR)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--expected-views", type=int, default=668)
    parser.add_argument("--expected-frontal-images", type=int, default=518)
    parser.add_argument("--expected-studies", type=int, default=500)
    parser.add_argument("--prompt-count", type=int, default=medclip.PROMPT_COUNT)
    parser.add_argument("--seed", type=int, default=20261019)
    parser.add_argument("--device", default="cuda:0" if torch.cuda.is_available() else "cpu")
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate locked non-label inputs without loading a model or opening test labels.",
    )
    return parser


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def write_json_atomic(value: dict[str, Any], path: Path) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("model_name") != medclip.MODEL_NAME:
        raise ValueError(f"Threshold policy is not for MedCLIP ViT: {policy.get('model_name')!r}")
    thresholds = policy.get("selected_thresholds")
    normalization = policy.get("validation_normalization")
    if not isinstance(thresholds, dict) or not isinstance(normalization, dict):
        raise ValueError("Threshold policy lacks selected thresholds or validation normalization")
    for label in medclip.LABELS:
        if label not in thresholds or label not in normalization:
            raise ValueError(f"Threshold policy is missing {label}")
        values = normalization[label]
        if values.get("method") != "zscore_population" or float(values["raw_std"]) <= 0:
            raise ValueError(f"Invalid validation normalization for {label}")
    return policy


def apply_frozen_policy(image_scores: pd.DataFrame, policy: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate test views, then apply validation statistics and thresholds."""
    study_scores, _unused_test_statistics = medclip.aggregate_and_normalize(image_scores)
    normalization = policy["validation_normalization"]
    thresholds = policy["selected_thresholds"]
    for label in medclip.LABELS:
        values = normalization[label]
        study_scores[label] = (study_scores[medclip.raw_column(label)] - float(values["raw_mean"])) / float(values["raw_std"])
    predictions = study_scores.melt(
        id_vars=["model_name", "study_key"],
        value_vars=list(medclip.LABELS),
        var_name="label",
        value_name="score",
    )
    predictions["threshold"] = predictions["label"].map(thresholds)
    predictions["predicted_positive"] = (predictions["score"] >= predictions["threshold"]).astype(int)
    predictions["predicted_status"] = predictions["predicted_positive"].map({1: "present", 0: "absent"})
    return study_scores, predictions.sort_values(["study_key", "label"], kind="stable").reset_index(drop=True)


def safe_divide(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def evaluate_predictions(predictions: pd.DataFrame, ground_truth_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    try:
        from sklearn.metrics import average_precision_score, roc_auc_score
    except ImportError as exc:
        raise RuntimeError(
            "scikit-learn is required for MedCLIP evaluation. Install it in "
            "the isolated MedCLIP environment."
        ) from exc
    ground_truth = pd.read_csv(ground_truth_path)
    required = {"study_key", "label", "ground_truth_status"}
    missing = sorted(required - set(ground_truth.columns))
    if missing:
        raise ValueError(f"Test ground truth is missing columns: {missing}")
    ground_truth = ground_truth.loc[ground_truth["label"].isin(medclip.LABELS), ["study_key", "label", "ground_truth_status"]].copy()
    statuses = set(ground_truth["ground_truth_status"].astype(str))
    if statuses - {"present", "absent"}:
        raise ValueError(f"Test ground truth must be binary, received {sorted(statuses)}")
    rows = predictions.merge(ground_truth, on=["study_key", "label"], how="outer", validate="one_to_one", indicator=True)
    if not rows["_merge"].eq("both").all():
        raise ValueError(f"Test predictions and ground truth do not align: {rows['_merge'].value_counts().to_dict()}")
    rows = rows.drop(columns="_merge")
    rows["ground_truth"] = rows["ground_truth_status"].eq("present").astype(int)

    metric_rows: list[dict[str, Any]] = []
    for label in medclip.LABELS:
        label_rows = rows.loc[rows["label"].eq(label)].copy()
        y_true = label_rows["ground_truth"].to_numpy(dtype=int)
        y_pred = label_rows["predicted_positive"].to_numpy(dtype=int)
        label_scores = label_rows["score"].to_numpy(dtype=float)
        if set(np.unique(y_true)) != {0, 1}:
            raise ValueError(f"{label} does not contain both test classes")
        tp = int(np.sum((y_pred == 1) & (y_true == 1)))
        tn = int(np.sum((y_pred == 0) & (y_true == 0)))
        fp = int(np.sum((y_pred == 1) & (y_true == 0)))
        fn = int(np.sum((y_pred == 0) & (y_true == 1)))
        metric_rows.append({
            "label": label,
            "threshold": float(label_rows["threshold"].iloc[0]),
            "study_count": len(label_rows),
            "ground_truth_positive": int(y_true.sum()),
            "ground_truth_negative": int((y_true == 0).sum()),
            "predicted_positive": int(y_pred.sum()),
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "precision": safe_divide(tp, tp + fp),
            "recall": safe_divide(tp, tp + fn),
            "f1": safe_divide(2 * tp, 2 * tp + fp + fn),
            "specificity": safe_divide(tn, tn + fp),
            "accuracy": safe_divide(tp + tn, len(y_true)),
            "auroc": float(roc_auc_score(y_true, label_scores)),
            "average_precision": float(average_precision_score(y_true, label_scores)),
        })
    metrics = pd.DataFrame(metric_rows)
    tp, tn, fp, fn = (int(metrics[column].sum()) for column in ("tp", "tn", "fp", "fn"))
    aggregate = {
        "macro_auroc": float(metrics["auroc"].mean()),
        "macro_average_precision": float(metrics["average_precision"].mean()),
        "macro_precision": float(metrics["precision"].mean()),
        "macro_recall": float(metrics["recall"].mean()),
        "macro_f1": float(metrics["f1"].mean()),
        "micro_precision": safe_divide(tp, tp + fp),
        "micro_recall": safe_divide(tp, tp + fn),
        "micro_f1": safe_divide(2 * tp, 2 * tp + fp + fn),
    }
    return rows.sort_values(["study_key", "label"], kind="stable").reset_index(drop=True), metrics, aggregate


def main() -> None:
    args = build_parser().parse_args()
    if args.batch_size <= 0 or args.prompt_count <= 0:
        raise ValueError("--batch-size and --prompt-count must be positive")
    np.random.seed(args.seed)
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True

    manifest = medclip.resolve_file(args.manifest, "test manifest")
    image_root = medclip.resolve_directory(args.image_root, "test image directory")
    policy_path = medclip.resolve_file(args.threshold_policy, "frozen threshold policy")
    policy = load_policy(policy_path)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "image_scores": output_dir / "test_image_scores.csv",
        "study_scores": output_dir / "test_scores.csv",
        "predictions": output_dir / "test_predictions.csv",
        "prediction_lock": output_dir / "test_prediction_lock.json",
        "evaluation_rows": output_dir / "test_evaluation_rows.csv",
        "metrics": output_dir / "test_per_label_metrics.csv",
        "summary": output_dir / "test_summary.json",
        "run_config": output_dir / "test_run_config.json",
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError("Refusing to overwrite existing MedCLIP test outputs:\n" + "\n".join(str(path) for path in existing))
    frontal = medclip.prepare_frontal_manifest(
        manifest, image_root, expected_views=args.expected_views,
        expected_frontal_images=args.expected_frontal_images, expected_studies=args.expected_studies,
    )
    if args.preflight_only:
        print("MedCLIP test preflight succeeded; test ground truth opened: False")
        return
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(f"Requested {device}, but CUDA is unavailable")
    classifier, processor, prompt_inputs, prompts = medclip.load_medclip(device, args.prompt_count)
    image_scores = medclip.score_images(classifier=classifier, processor=processor, prompt_inputs=prompt_inputs, frontal=frontal, device=device, batch_size=args.batch_size)
    study_scores, predictions = apply_frozen_policy(image_scores, policy)
    if len(study_scores) != args.expected_studies or len(predictions) != args.expected_studies * len(medclip.LABELS):
        raise RuntimeError("Unexpected MedCLIP held-out prediction count")

    # Persist immutable, label-blind predictions before opening the test labels.
    write_csv_atomic(image_scores, paths["image_scores"])
    write_csv_atomic(study_scores, paths["study_scores"])
    write_csv_atomic(predictions, paths["predictions"])
    prediction_hashes = {paths[key].name: sha256(paths[key]) for key in ("image_scores", "study_scores", "predictions")}
    lock = {
        "model_name": medclip.MODEL_NAME,
        "test_manifest_sha256": sha256(manifest),
        "threshold_policy_sha256": sha256(policy_path),
        "test_ground_truth_opened_before_prediction_lock": False,
        "normalization_source": "competition_validation_only",
        "threshold_source": "competition_validation_only",
        "test_time_tuning": False,
        "artifact_sha256": prediction_hashes,
    }
    write_json_atomic(lock, paths["prediction_lock"])
    for filename, expected_hash in prediction_hashes.items():
        if sha256(output_dir / filename) != expected_hash:
            raise RuntimeError(f"Prediction artifact changed before evaluation: {filename}")

    ground_truth = medclip.resolve_file(args.ground_truth, "test ground truth")
    evaluation_rows, metrics, aggregate = evaluate_predictions(predictions, ground_truth)
    write_csv_atomic(evaluation_rows, paths["evaluation_rows"])
    write_csv_atomic(metrics, paths["metrics"])
    summary: dict[str, Any] = {
        "model_name": medclip.MODEL_NAME,
        "evaluation_split": "competition_test",
        "study_count": args.expected_studies,
        "study_label_count": args.expected_studies * len(medclip.LABELS),
        "label_count": len(medclip.LABELS),
        "threshold_policy_version": policy.get("policy_version"),
        "normalization_source": "competition_validation_only",
        "threshold_source": "competition_validation_only",
        "test_time_tuning": False,
        "predictions_locked_before_ground_truth": True,
        **aggregate,
    }
    write_json_atomic(summary, paths["summary"])
    run_config: dict[str, Any] = {
        "model_name": medclip.MODEL_NAME,
        "model_variant": "MedCLIP ViT official pretrained checkpoint",
        "manifest": str(manifest), "ground_truth": str(ground_truth),
        "threshold_policy": str(policy_path), "labels": list(medclip.LABELS),
        "prompts": prompts, "score_definition": "official_MedCLIP_PromptClassifier_logits",
        "study_aggregation": "mean_of_frontal_image_continuous_scores",
        "validation_normalization": policy["validation_normalization"],
        "selected_thresholds": policy["selected_thresholds"],
        "predictions_locked_before_ground_truth": True,
        "execution": {"device": str(device), "batch_size": args.batch_size, "seed": args.seed, "torch": torch.__version__, "medclip": medclip.package_version("medclip")},
        "artifact_sha256": {path.name: sha256(path) for path in paths.values() if path.exists()},
    }
    write_json_atomic(run_config, paths["run_config"])
    print(metrics.to_string(index=False))
    print(json.dumps(summary, indent=2, sort_keys=True))
    for name, path in paths.items():
        print(f"Saved {name}: {path}")


if __name__ == "__main__":
    main()
