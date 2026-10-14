"""Run and evaluate GLoRIA on the expert-labeled CheXpert test cohort.

The script never estimates normalization parameters or decision thresholds
from test data. It applies the validation statistics and frozen thresholds in
``threshold_policy.json`` to raw test similarities.
"""

from __future__ import annotations

import argparse
import gc
import json
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GLORIA_ROOT = PROJECT_ROOT / "external" / "gloria"
DEFAULT_CHECKPOINT = (
    DEFAULT_GLORIA_ROOT / "pretrained" / "chexpert_resnet50.ckpt"
)
DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp14_chexpert_competition_auroc"
    / "competition_view_manifest.csv"
)
DEFAULT_GROUND_TRUTH = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp14_chexpert_competition_auroc"
    / "competition_ground_truth.csv"
)
DEFAULT_IMAGE_ROOT = (
    PROJECT_ROOT
    / "v2"
    / "data"
    / "chexpert_competition_test"
    / "chexlocalize"
    / "CheXpert"
    / "test"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "v2" / "experiments" / "gloria_zero_shot_comparison"
)
DEFAULT_POLICY = DEFAULT_OUTPUT_DIR / "threshold_policy.json"

LABELS: tuple[str, ...] = (
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
)
MODEL_NAME = "gloria_resnet50_zero_shot"
PROMPT_SEED = 6


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run GLoRIA on CheXpert test frontal images and apply frozen "
            "validation normalization and thresholds."
        )
    )
    parser.add_argument("--gloria-root", type=Path, default=DEFAULT_GLORIA_ROOT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH)
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    parser.add_argument("--threshold-policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--expected-studies", type=int, default=500)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--seed", type=int, default=20260916)
    return parser


def _require_file(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Missing {description}: {resolved}")
    return resolved


def _raw_column(label: str) -> str:
    return f"raw_{label}"


def _load_gloria(gloria_root: Path) -> Any:
    root = gloria_root.expanduser().resolve()
    if not (root / "gloria" / "__init__.py").is_file():
        raise FileNotFoundError(f"GLoRIA source package not found under: {root}")
    sys.path.insert(0, str(root))
    try:
        import gloria  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError(
            "Unable to import GLoRIA. Confirm that the Python-3.12 "
            "compatibility patches have been applied."
        ) from exc
    return gloria


def _prepare_frontal_manifest(manifest_path: Path, image_root: Path) -> pd.DataFrame:
    frame = pd.read_csv(manifest_path)
    required = {"study_key", "dicom_path"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Manifest is missing columns: {missing}")
    frontal = frame.loc[
        frame["dicom_path"].astype(str).str.contains(
            r"_frontal\.(?:jpg|jpeg|png)$",
            case=False,
            regex=True,
            na=False,
        )
    ].copy()
    frontal = frontal.sort_values(
        ["study_key", "dicom_path"], kind="stable"
    ).reset_index(drop=True)
    frontal["image_path"] = frontal["dicom_path"].map(
        lambda value: str((image_root / str(value)).resolve())
    )
    missing_images = [
        path for path in frontal["image_path"] if not Path(path).is_file()
    ]
    if missing_images:
        raise FileNotFoundError(
            f"Missing {len(missing_images)} test images; first: {missing_images[0]}"
        )
    return frontal


def _score_images(
    *,
    gloria: Any,
    model: Any,
    processed_text: Any,
    frontal: pd.DataFrame,
    device: str,
    batch_size: int,
) -> pd.DataFrame:
    batches: list[pd.DataFrame] = []
    for start in range(0, len(frontal), batch_size):
        stop = min(start + batch_size, len(frontal))
        batch = frontal.iloc[start:stop].reset_index(drop=True)
        processed_images = model.process_img(batch["image_path"].tolist(), device)
        raw_by_label: dict[str, np.ndarray] = {}
        with torch.inference_mode():
            for label, class_text in processed_text.items():
                if label not in LABELS:
                    continue
                similarities = gloria.get_similarities(
                    model,
                    processed_images,
                    class_text,
                    similarity_type="both",
                )
                raw_by_label[_raw_column(label)] = similarities.max(axis=1)
        missing = [
            label for label in LABELS if _raw_column(label) not in raw_by_label
        ]
        if missing:
            raise RuntimeError(f"GLoRIA output is missing labels: {missing}")
        output = pd.DataFrame(raw_by_label)
        if len(output) != len(batch):
            raise RuntimeError(
                f"Batch returned {len(output)} rows for {len(batch)} images"
            )
        output.insert(0, "image_path", batch["image_path"])
        output.insert(0, "dicom_path", batch["dicom_path"].astype(str))
        output.insert(0, "study_key", batch["study_key"].astype(str))
        output.insert(0, "model_name", MODEL_NAME)
        batches.append(output)
        print(f"Processed {stop}/{len(frontal)} frontal images", flush=True)
        del processed_images
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    result = pd.concat(batches, ignore_index=True)
    raw_columns = [_raw_column(label) for label in LABELS]
    if result[raw_columns].isna().any().any():
        raise RuntimeError("GLoRIA produced missing raw test scores")
    return result


def _load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text())
    thresholds = policy.get("selected_thresholds")
    normalization = policy.get("validation_normalization")
    if not isinstance(thresholds, dict) or not isinstance(normalization, dict):
        raise ValueError(
            "Threshold policy must contain selected_thresholds and "
            "validation_normalization"
        )
    for label in LABELS:
        if label not in thresholds or label not in normalization:
            raise ValueError(f"Threshold policy is missing {label}")
        values = normalization[label]
        if values.get("method") != "zscore_population":
            raise ValueError(f"Unsupported normalization policy for {label}: {values}")
        if float(values["raw_std"]) <= 0:
            raise ValueError(f"Invalid validation standard deviation for {label}")
    return policy


def _aggregate_and_normalize(
    image_scores: pd.DataFrame, policy: dict[str, Any]
) -> pd.DataFrame:
    raw_columns = [_raw_column(label) for label in LABELS]
    grouped = image_scores.groupby("study_key", sort=True, as_index=False)
    studies = grouped[raw_columns].mean()
    view_counts = grouped.size().rename(columns={"size": "frontal_view_count"})
    view_paths = grouped["dicom_path"].agg(
        lambda values: json.dumps(list(values), separators=(",", ":"))
    ).rename(columns={"dicom_path": "frontal_dicom_paths"})
    studies = view_counts.merge(studies, on="study_key", validate="one_to_one")
    studies = studies.merge(view_paths, on="study_key", validate="one_to_one")

    normalization = policy["validation_normalization"]
    for label in LABELS:
        values = normalization[label]
        studies[label] = (
            studies[_raw_column(label)] - float(values["raw_mean"])
        ) / float(values["raw_std"])
    studies.insert(0, "model_name", MODEL_NAME)
    return studies[
        [
            "model_name",
            "study_key",
            "frontal_view_count",
            "frontal_dicom_paths",
            *LABELS,
            *raw_columns,
        ]
    ]


def _safe_div(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _evaluate(
    study_scores: pd.DataFrame,
    ground_truth_path: Path,
    policy: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    scores = study_scores.melt(
        id_vars=["study_key"],
        value_vars=list(LABELS),
        var_name="label",
        value_name="score",
    )
    ground_truth = pd.read_csv(ground_truth_path)
    ground_truth = ground_truth.loc[
        ground_truth["label"].isin(LABELS),
        ["study_key", "label", "ground_truth_status"],
    ].copy()
    unexpected = sorted(
        set(ground_truth["ground_truth_status"].astype(str)) - {"present", "absent"}
    )
    if unexpected:
        raise ValueError(f"Test ground truth is not fully binary: {unexpected}")
    joined = scores.merge(
        ground_truth,
        on=["study_key", "label"],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if not (joined["_merge"] == "both").all():
        raise ValueError(
            f"Test scores and ground truth do not align: "
            f"{joined['_merge'].value_counts().to_dict()}"
        )
    joined = joined.drop(columns="_merge")
    joined["ground_truth"] = (
        joined["ground_truth_status"].astype(str) == "present"
    ).astype(int)
    joined["threshold"] = joined["label"].map(policy["selected_thresholds"])
    if joined["threshold"].isna().any():
        raise ValueError("At least one test row has no frozen threshold")
    joined["predicted_positive"] = (
        joined["score"] >= joined["threshold"]
    ).astype(int)
    joined["predicted_status"] = joined["predicted_positive"].map(
        {1: "present", 0: "absent"}
    )

    metric_rows: list[dict[str, Any]] = []
    for label in LABELS:
        rows = joined.loc[joined["label"] == label]
        y_true = rows["ground_truth"].to_numpy(dtype=int)
        predicted = rows["predicted_positive"].to_numpy(dtype=int)
        scores_for_label = rows["score"].to_numpy(dtype=float)
        tp = int(np.sum((predicted == 1) & (y_true == 1)))
        tn = int(np.sum((predicted == 0) & (y_true == 0)))
        fp = int(np.sum((predicted == 1) & (y_true == 0)))
        fn = int(np.sum((predicted == 0) & (y_true == 1)))
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        metric_rows.append(
            {
                "label": label,
                "threshold": float(policy["selected_thresholds"][label]),
                "study_count": len(rows),
                "ground_truth_positive": int(y_true.sum()),
                "ground_truth_negative": int((y_true == 0).sum()),
                "predicted_positive": int(predicted.sum()),
                "tp": tp,
                "tn": tn,
                "fp": fp,
                "fn": fn,
                "precision": precision,
                "recall": recall,
                "f1": _safe_div(2 * tp, 2 * tp + fp + fn),
                "specificity": _safe_div(tn, tn + fp),
                "accuracy": _safe_div(tp + tn, len(rows)),
                "auroc": float(roc_auc_score(y_true, scores_for_label)),
                "average_precision": float(
                    average_precision_score(y_true, scores_for_label)
                ),
            }
        )
    metrics = pd.DataFrame(metric_rows)
    total_tp = int(metrics["tp"].sum())
    total_fp = int(metrics["fp"].sum())
    total_fn = int(metrics["fn"].sum())
    summary = {
        "model_name": MODEL_NAME,
        "evaluation_split": "competition_test",
        "study_count": int(study_scores["study_key"].nunique()),
        "label_count": len(LABELS),
        "study_label_count": len(joined),
        "normalization_source": "competition_validation_only",
        "threshold_source": "competition_validation_maximum_f1",
        "threshold_policy_version": policy.get("policy_version"),
        "prompt_seed": PROMPT_SEED,
        "macro_f1": float(metrics["f1"].mean()),
        "macro_precision": float(metrics["precision"].mean()),
        "macro_recall": float(metrics["recall"].mean()),
        "macro_auroc": float(metrics["auroc"].mean()),
        "macro_average_precision": float(metrics["average_precision"].mean()),
        "micro_f1": _safe_div(2 * total_tp, 2 * total_tp + total_fp + total_fn),
        "micro_precision": _safe_div(total_tp, total_tp + total_fp),
        "micro_recall": _safe_div(total_tp, total_tp + total_fn),
    }
    return joined, metrics, summary


def main() -> None:
    args = build_parser().parse_args()
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be positive")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    checkpoint = _require_file(args.checkpoint, "GLoRIA checkpoint")
    manifest = _require_file(args.manifest, "test view manifest")
    ground_truth = _require_file(args.ground_truth, "test ground truth")
    policy_path = _require_file(args.threshold_policy, "threshold policy")
    image_root = args.image_root.expanduser().resolve()
    if not image_root.is_dir():
        raise FileNotFoundError(f"Missing test image directory: {image_root}")
    policy = _load_policy(policy_path)
    frontal = _prepare_frontal_manifest(manifest, image_root)
    study_count = frontal["study_key"].nunique()
    print(f"Frontal image rows: {len(frontal)}")
    print(f"Unique studies: {study_count}")
    if study_count != args.expected_studies:
        raise RuntimeError(
            f"Expected {args.expected_studies} studies, found {study_count}"
        )

    gloria = _load_gloria(args.gloria_root)
    print(f"Device: {args.device}")
    print("Loading GLoRIA checkpoint...", flush=True)
    model = gloria.load_gloria(name=str(checkpoint), device=args.device)
    model.eval()
    random.seed(PROMPT_SEED)
    prompts = gloria.generate_chexpert_class_prompts()
    processed_text = model.process_class_prompts(prompts, args.device)
    image_scores = _score_images(
        gloria=gloria,
        model=model,
        processed_text=processed_text,
        frontal=frontal,
        device=args.device,
        batch_size=args.batch_size,
    )
    study_scores = _aggregate_and_normalize(image_scores, policy)
    if len(study_scores) != args.expected_studies:
        raise RuntimeError(
            f"Expected {args.expected_studies} study rows, found {len(study_scores)}"
        )
    predictions, metrics, summary = _evaluate(
        study_scores, ground_truth, policy
    )

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "image_scores": output_dir / "test_image_scores.csv",
        "study_scores": output_dir / "test_scores.csv",
        "predictions": output_dir / "test_predictions.csv",
        "metrics": output_dir / "test_per_label_metrics.csv",
        "summary": output_dir / "test_summary.json",
        "run_config": output_dir / "test_run_config.json",
    }
    image_scores.to_csv(paths["image_scores"], index=False)
    study_scores.to_csv(paths["study_scores"], index=False)
    predictions.to_csv(paths["predictions"], index=False)
    metrics.to_csv(paths["metrics"], index=False)
    paths["summary"].write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    run_config = {
        "model_name": MODEL_NAME,
        "checkpoint": str(checkpoint),
        "manifest": str(manifest),
        "ground_truth": str(ground_truth),
        "image_root": str(image_root),
        "threshold_policy": str(policy_path),
        "batch_size": args.batch_size,
        "device": args.device,
        "seed": args.seed,
        "prompt_seed": PROMPT_SEED,
        "prompts": prompts,
        "frontal_image_count": len(frontal),
        "study_count": len(study_scores),
        "multi_frontal_study_count": int(
            (study_scores["frontal_view_count"] > 1).sum()
        ),
    }
    paths["run_config"].write_text(
        json.dumps(run_config, indent=2, sort_keys=True) + "\n"
    )

    print("\nPer-label test metrics:")
    print(metrics.to_string(index=False))
    print("\nTest summary:")
    print(json.dumps(summary, indent=2, sort_keys=True))
    for name, path in paths.items():
        print(f"Saved {name}: {path}")


if __name__ == "__main__":
    main()
