"""Evaluate frozen BioViL zero-shot policy on the CheXpert test cohort.

The script never fits normalization parameters or selects thresholds. It
verifies and applies the artifacts frozen by run_biovil_validation_inference.py.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score
from transformers import BertTokenizer

import run_biovil_validation_inference as validation_pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_DIR = (
    PROJECT_ROOT / "v2" / "experiments" / "biovil_zero_shot_comparison"
)
DEFAULT_BIOVIL_ROOT = PROJECT_ROOT / "external" / "biovil"
DEFAULT_MODEL_DIR = (
    DEFAULT_BIOVIL_ROOT
    / "checkpoints"
    / "BiomedVLP-CXR-BERT-specialized-v1.1"
)
DEFAULT_IMAGE_CHECKPOINT = (
    DEFAULT_MODEL_DIR / "biovil_image_resnet50_proj_size_128.pt"
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
DEFAULT_PROMPT_POLICY = EXPERIMENT_DIR / "prompt_policy.json"
DEFAULT_THRESHOLD_POLICY = EXPERIMENT_DIR / "threshold_policy.json"
DEFAULT_VALIDATION_RUN_CONFIG = EXPERIMENT_DIR / "validation_run_config.json"

LABELS = validation_pipeline.LABELS
MODEL_NAME = validation_pipeline.MODEL_NAME
EXPECTED_PROMPT_POLICY_SHA256 = (
    "b0ae0a58bc3b4a5a7a3b92618f1b235c2a999d7c05437d3a5f5b71a8915d1d50"
)
EXPECTED_THRESHOLD_POLICY_SHA256 = (
    "93268d37fd29a9153053f8e564171706d6c528ab04c3ac7ab9c3dc344631c5db"
)
EXPECTED_VALIDATION_SCRIPT_SHA256 = (
    "3f20b78d9452ac3ee1762323003813d5e46269f873f8ac337121fdc0a4fbb5f0"
)
EXPECTED_TEST_MANIFEST_SHA256 = (
    "fe4084cbb7acb349ffe9aa45f5e560740562f76ce6496c3436918fee6444f6aa"
)
EXPECTED_TEST_GROUND_TRUTH_SHA256 = (
    "9bab723d2051e2c35b3869e8d659c71c9c3da78ea21814d3a337120e4150f489"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate BioViL on the frozen 500-study CheXpert test cohort "
            "using validation-only normalization and thresholds."
        )
    )
    parser.add_argument("--biovil-root", type=Path, default=DEFAULT_BIOVIL_ROOT)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument(
        "--image-checkpoint", type=Path, default=DEFAULT_IMAGE_CHECKPOINT
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH
    )
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    parser.add_argument(
        "--prompt-policy", type=Path, default=DEFAULT_PROMPT_POLICY
    )
    parser.add_argument(
        "--threshold-policy", type=Path, default=DEFAULT_THRESHOLD_POLICY
    )
    parser.add_argument(
        "--validation-run-config",
        type=Path,
        default=DEFAULT_VALIDATION_RUN_CONFIG,
    )
    parser.add_argument("--output-dir", type=Path, default=EXPERIMENT_DIR)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--expected-views", type=int, default=668)
    parser.add_argument("--expected-frontal-images", type=int, default=518)
    parser.add_argument("--expected-studies", type=int, default=500)
    parser.add_argument(
        "--device", default="cuda:0" if torch.cuda.is_available() else "cpu"
    )
    parser.add_argument("--seed", type=int, default=20260916)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing BioViL test artifacts.",
    )
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_file(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Missing {description}: {resolved}")
    return resolved


def _resolve_directory(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"Missing {description}: {resolved}")
    return resolved


def _verify_hash(path: Path, expected: str, description: str) -> str:
    observed = _sha256(path)
    if observed != expected:
        raise RuntimeError(
            f"{description} SHA-256 mismatch: expected {expected}, "
            f"observed {observed}"
        )
    return observed


def _load_frozen_policies(
    prompt_policy_path: Path,
    threshold_policy_path: Path,
    validation_run_config_path: Path,
) -> tuple[
    dict[str, Any],
    dict[str, list[str]],
    dict[str, Any],
    dict[str, Any],
]:
    _verify_hash(
        prompt_policy_path,
        EXPECTED_PROMPT_POLICY_SHA256,
        "Prompt policy",
    )
    _verify_hash(
        threshold_policy_path,
        EXPECTED_THRESHOLD_POLICY_SHA256,
        "Threshold policy",
    )
    prompt_policy, prompts = validation_pipeline._load_prompt_policy(
        prompt_policy_path
    )
    threshold_policy = json.loads(
        threshold_policy_path.read_text(encoding="utf-8")
    )
    validation_run_config = json.loads(
        validation_run_config_path.read_text(encoding="utf-8")
    )

    if threshold_policy.get("model_name") != MODEL_NAME:
        raise RuntimeError("Threshold policy belongs to a different model")
    if threshold_policy.get("policy_version") != (
        "biovil_zero_shot_max_f1_specificity_floor_v1"
    ):
        raise RuntimeError(
            "Unexpected threshold-policy version: "
            f"{threshold_policy.get('policy_version')!r}"
        )
    if threshold_policy.get("selection_split") != "competition_val":
        raise RuntimeError("Thresholds were not selected on validation")
    if threshold_policy.get("minimum_specificity") != 0.6:
        raise RuntimeError("Threshold policy does not use specificity >= 0.60")
    if threshold_policy.get("prompt_policy_sha256") != (
        EXPECTED_PROMPT_POLICY_SHA256
    ):
        raise RuntimeError("Threshold and prompt policies are not linked")
    if threshold_policy.get("prompt_sha256") != (
        prompt_policy["prompt_source"]["prompt_sha256"]
    ):
        raise RuntimeError("Threshold-policy prompt content hash differs")

    thresholds = threshold_policy.get("selected_thresholds")
    normalization = threshold_policy.get("validation_normalization")
    if not isinstance(thresholds, dict) or set(thresholds) != set(LABELS):
        raise RuntimeError("Threshold policy lacks exactly five thresholds")
    if not isinstance(normalization, dict) or set(normalization) != set(LABELS):
        raise RuntimeError("Threshold policy lacks exactly five normalizers")
    for label in LABELS:
        threshold = float(thresholds[label])
        mean = float(normalization[label]["raw_mean"])
        std = float(normalization[label]["raw_std"])
        if not np.isfinite(threshold):
            raise RuntimeError(f"Non-finite threshold for {label}")
        if not np.isfinite(mean) or not np.isfinite(std) or std <= 0:
            raise RuntimeError(f"Invalid validation normalizer for {label}")
        if normalization[label].get("method") != "zscore_population":
            raise RuntimeError(f"Unexpected normalization method for {label}")
        if normalization[label].get("fit_split") != (
            "competition_validation_only"
        ):
            raise RuntimeError(f"Normalizer for {label} was not fit on validation")

    if validation_run_config.get("script_sha256") != (
        EXPECTED_VALIDATION_SCRIPT_SHA256
    ):
        raise RuntimeError("Validation run config records an unexpected script")
    validation_script = Path(validation_pipeline.__file__).resolve()
    _verify_hash(
        validation_script,
        EXPECTED_VALIDATION_SCRIPT_SHA256,
        "Validation pipeline module",
    )
    if validation_run_config.get("selected_thresholds") != thresholds:
        raise RuntimeError("Run-config and threshold-policy thresholds differ")
    if validation_run_config.get("normalization") != normalization:
        raise RuntimeError("Run-config and threshold-policy normalizers differ")
    return (
        prompt_policy,
        prompts,
        threshold_policy,
        validation_run_config,
    )


def _aggregate_test_studies(
    image_scores: pd.DataFrame,
    validation_normalization: dict[str, dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_columns = [validation_pipeline._raw_column(label) for label in LABELS]
    grouped = image_scores.groupby("study_key", sort=True, as_index=False)
    raw_scores = grouped[raw_columns].mean()
    view_counts = grouped.size().rename(columns={"size": "frontal_view_count"})
    view_paths = grouped["dicom_path"].agg(
        lambda values: json.dumps(list(values), separators=(",", ":"))
    ).rename(columns={"dicom_path": "frontal_dicom_paths"})
    raw_scores = view_counts.merge(
        raw_scores, on="study_key", validate="one_to_one"
    )
    raw_scores = raw_scores.merge(
        view_paths, on="study_key", validate="one_to_one"
    )
    raw_scores.insert(0, "model_name", MODEL_NAME)
    raw_scores = raw_scores.loc[
        :,
        [
            "model_name",
            "study_key",
            "frontal_view_count",
            "frontal_dicom_paths",
            *raw_columns,
        ],
    ]

    scores = raw_scores.copy()
    for label in LABELS:
        raw_column = validation_pipeline._raw_column(label)
        mean = float(validation_normalization[label]["raw_mean"])
        std = float(validation_normalization[label]["raw_std"])
        scores[label] = (scores[raw_column].to_numpy(dtype=float) - mean) / std
    if not np.isfinite(scores[list(LABELS)].to_numpy()).all():
        raise RuntimeError("Validation normalization produced non-finite test scores")
    scores = scores.loc[
        :,
        [
            "model_name",
            "study_key",
            "frontal_view_count",
            "frontal_dicom_paths",
            *LABELS,
            *raw_columns,
        ],
    ]
    return raw_scores, scores


def _evaluate_test(
    scores: pd.DataFrame,
    ground_truth: pd.DataFrame,
    thresholds: dict[str, float],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    long_scores = scores.melt(
        id_vars=["study_key"],
        value_vars=list(LABELS),
        var_name="label",
        value_name="score",
    )
    truth = ground_truth.loc[
        :, ["study_key", "label", "ground_truth_status"]
    ].copy()
    joined = long_scores.merge(
        truth,
        on=["study_key", "label"],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if not (joined["_merge"] == "both").all():
        raise RuntimeError(
            "Test scores and ground truth do not align: "
            f"{joined['_merge'].value_counts().to_dict()}"
        )
    joined = joined.drop(columns="_merge")
    joined["ground_truth"] = (
        joined["ground_truth_status"].astype(str) == "present"
    ).astype(int)

    report_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    for label in LABELS:
        rows = joined.loc[joined["label"] == label].copy()
        rows = rows.sort_values("study_key", kind="stable").reset_index(drop=True)
        y_true = rows["ground_truth"].to_numpy(dtype=int)
        label_scores = rows["score"].to_numpy(dtype=float)
        threshold = float(thresholds[label])
        metrics = validation_pipeline._metrics_at_threshold(
            y_true, label_scores, threshold
        )
        metrics.update(
            {
                "label": label,
                "study_count": len(rows),
                "ground_truth_positive": int(y_true.sum()),
                "ground_truth_negative": int((y_true == 0).sum()),
                "auroc": float(roc_auc_score(y_true, label_scores)),
                "average_precision": float(
                    average_precision_score(y_true, label_scores)
                ),
            }
        )
        report_rows.append(metrics)

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
        ],
    ]
    predictions = pd.concat(prediction_frames, ignore_index=True)
    predictions.insert(0, "model_name", MODEL_NAME)

    total_tp = int(report["tp"].sum())
    total_fp = int(report["fp"].sum())
    total_fn = int(report["fn"].sum())
    aggregate = {
        "macro_auroc": float(report["auroc"].mean()),
        "macro_average_precision": float(report["average_precision"].mean()),
        "macro_f1": float(report["f1"].mean()),
        "macro_precision": float(report["precision"].mean()),
        "macro_recall": float(report["recall"].mean()),
        "micro_f1": validation_pipeline._safe_div(
            2 * total_tp, 2 * total_tp + total_fp + total_fn
        ),
        "micro_precision": validation_pipeline._safe_div(
            total_tp, total_tp + total_fp
        ),
        "micro_recall": validation_pipeline._safe_div(
            total_tp, total_tp + total_fn
        ),
    }
    return report, predictions, aggregate


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = build_parser().parse_args()
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be positive")

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    if torch.backends.cudnn.is_available():
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")

    biovil_root = _resolve_directory(args.biovil_root, "BioViL root")
    himl_root = _resolve_directory(biovil_root / "hi-ml", "HI-ML repository")
    himl_source = _resolve_directory(
        himl_root / "hi-ml-multimodal" / "src", "HI-ML source"
    )
    model_dir = _resolve_directory(args.model_dir, "CXR-BERT model directory")
    image_checkpoint = _resolve_file(
        args.image_checkpoint, "BioViL image checkpoint"
    )
    manifest_path = _resolve_file(args.manifest, "test manifest")
    ground_truth_path = _resolve_file(args.ground_truth, "test ground truth")
    image_root = _resolve_directory(args.image_root, "test image root")
    prompt_policy_path = _resolve_file(args.prompt_policy, "prompt policy")
    threshold_policy_path = _resolve_file(
        args.threshold_policy, "threshold policy"
    )
    validation_run_config_path = _resolve_file(
        args.validation_run_config, "validation run config"
    )
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    output_paths = {
        "image_scores": output_dir / "test_image_scores.csv",
        "raw_scores": output_dir / "test_raw_scores.csv",
        "scores": output_dir / "test_scores.csv",
        "predictions": output_dir / "test_predictions.csv",
        "metrics": output_dir / "test_per_label_metrics.csv",
        "summary": output_dir / "test_summary.json",
        "run_config": output_dir / "test_run_config.json",
    }
    existing = [path for path in output_paths.values() if path.exists()]
    if existing and not args.overwrite:
        formatted = "\n".join(str(path) for path in existing)
        raise FileExistsError(
            "Refusing to replace existing test outputs without --overwrite:\n"
            f"{formatted}"
        )

    (
        prompt_policy,
        prompts,
        threshold_policy,
        validation_run_config,
    ) = _load_frozen_policies(
        prompt_policy_path,
        threshold_policy_path,
        validation_run_config_path,
    )
    thresholds = {
        label: float(threshold_policy["selected_thresholds"][label])
        for label in LABELS
    }
    validation_normalization = threshold_policy["validation_normalization"]

    validation_pipeline._verify_hash(
        image_checkpoint,
        validation_pipeline.EXPECTED_IMAGE_CHECKPOINT_SHA256,
        "BioViL image checkpoint",
    )
    manifest_sha256 = _verify_hash(
        manifest_path,
        EXPECTED_TEST_MANIFEST_SHA256,
        "Test manifest",
    )
    ground_truth_sha256 = _verify_hash(
        ground_truth_path,
        EXPECTED_TEST_GROUND_TRUTH_SHA256,
        "Test ground truth",
    )
    himl_revision = validation_pipeline._git_revision(himl_root)
    if himl_revision != validation_pipeline.EXPECTED_HIML_REVISION:
        raise RuntimeError(
            f"Expected HI-ML revision {validation_pipeline.EXPECTED_HIML_REVISION}, "
            f"found {himl_revision}"
        )

    frontal, ground_truth = validation_pipeline._prepare_validation_data(
        manifest_path,
        ground_truth_path,
        image_root,
        args.expected_views,
        args.expected_frontal_images,
        args.expected_studies,
    )
    print(f"Manifest rows: {args.expected_views}")
    print(f"Frontal image rows: {len(frontal)}")
    print(f"Unique studies: {frontal['study_key'].nunique()}")
    print(f"Device: {device}")
    print("Frozen thresholds:")
    for label in LABELS:
        print(f"  {label}: {thresholds[label]}")

    (
        create_transform,
        ImageModel,
        ImageEncoderType,
        CXRBertConfig,
        CXRBertModel,
    ) = validation_pipeline._load_biovil_classes(himl_source)

    print("Loading BioViL image encoder...", flush=True)
    image_model = ImageModel(
        img_encoder_type=ImageEncoderType.RESNET50,
        joint_feature_size=128,
        pretrained_model_path=image_checkpoint,
    ).eval().to(device)
    print("Loading CXR-BERT tokenizer and text encoder...", flush=True)
    tokenizer = BertTokenizer.from_pretrained(
        model_dir, local_files_only=True
    )
    text_config = CXRBertConfig.from_pretrained(
        model_dir, local_files_only=True
    )
    text_model = CXRBertModel.from_pretrained(
        model_dir,
        config=text_config,
        local_files_only=True,
    ).eval().to(device)
    text_embeddings = validation_pipeline._encode_prompts(
        prompts=prompts,
        tokenizer=tokenizer,
        text_model=text_model,
        device=device,
    )
    transform = create_transform(resize=512, center_crop_size=480)
    image_scores = validation_pipeline._score_images(
        frontal=frontal,
        image_model=image_model,
        text_embeddings=text_embeddings,
        transform=transform,
        device=device,
        batch_size=args.batch_size,
    )
    raw_scores, scores = _aggregate_test_studies(
        image_scores, validation_normalization
    )
    if len(raw_scores) != args.expected_studies:
        raise RuntimeError(
            f"Expected {args.expected_studies} test study rows, "
            f"found {len(raw_scores)}"
        )

    report, predictions, aggregate = _evaluate_test(
        scores, ground_truth, thresholds
    )
    if len(predictions) != args.expected_studies * len(LABELS):
        raise RuntimeError("Unexpected number of test study-label predictions")

    multi_view_count = int((raw_scores["frontal_view_count"] > 1).sum())
    summary = {
        "model_name": MODEL_NAME,
        "evaluation_split": "competition_test",
        "study_count": args.expected_studies,
        "study_label_count": len(predictions),
        "label_count": len(LABELS),
        "frontal_image_count": len(image_scores),
        "multi_frontal_study_count": multi_view_count,
        "threshold_policy_version": threshold_policy["policy_version"],
        "threshold_policy_sha256": EXPECTED_THRESHOLD_POLICY_SHA256,
        "threshold_source": "competition_validation_only",
        "normalization_source": "competition_validation_only",
        "prompt_policy_sha256": EXPECTED_PROMPT_POLICY_SHA256,
        "prompt_sha256": prompt_policy["prompt_source"]["prompt_sha256"],
        "test_inference_reused": False,
        **aggregate,
    }
    test_script = Path(__file__).resolve()
    run_config = {
        "model_name": MODEL_NAME,
        "seed": args.seed,
        "device": str(device),
        "batch_size": args.batch_size,
        "image_checkpoint": str(image_checkpoint),
        "image_checkpoint_sha256": validation_pipeline._sha256(
            image_checkpoint
        ),
        "text_model_directory": str(model_dir),
        "hi_ml_repository": str(himl_root),
        "hi_ml_revision": himl_revision,
        "huggingface_revision": prompt_policy["model"]["huggingface_revision"],
        "text_model_class": validation_run_config["text_model_class"],
        "tokenizer_class": validation_run_config["tokenizer_class"],
        "prompt_policy": str(prompt_policy_path),
        "prompt_policy_sha256": EXPECTED_PROMPT_POLICY_SHA256,
        "threshold_policy": str(threshold_policy_path),
        "threshold_policy_sha256": EXPECTED_THRESHOLD_POLICY_SHA256,
        "validation_run_config": str(validation_run_config_path),
        "validation_run_config_sha256": _sha256(validation_run_config_path),
        "validation_script_sha256": EXPECTED_VALIDATION_SCRIPT_SHA256,
        "manifest": str(manifest_path),
        "manifest_sha256": manifest_sha256,
        "ground_truth": str(ground_truth_path),
        "ground_truth_sha256": ground_truth_sha256,
        "image_root": str(image_root),
        "manifest_view_count": args.expected_views,
        "frontal_image_count": len(image_scores),
        "study_count": len(raw_scores),
        "multi_frontal_study_count": multi_view_count,
        "prompts": prompts,
        "image_preprocessing": prompt_policy["image_preprocessing"],
        "scoring": prompt_policy["scoring"],
        "validation_normalization": validation_normalization,
        "selected_thresholds": thresholds,
        "test_tuning_performed": False,
        "script": str(test_script),
        "script_sha256": _sha256(test_script),
        "versions": {
            "python": sys.version.replace("\n", " "),
            "torch": torch.__version__,
            "torchvision": _package_version("torchvision"),
            "transformers": _package_version("transformers"),
            "timm": _package_version("timm"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": _package_version("scikit-learn"),
            "Pillow": _package_version("Pillow"),
        },
    }

    image_scores.to_csv(output_paths["image_scores"], index=False)
    raw_scores.to_csv(output_paths["raw_scores"], index=False)
    scores.to_csv(output_paths["scores"], index=False)
    predictions.to_csv(output_paths["predictions"], index=False)
    report.to_csv(output_paths["metrics"], index=False)
    _write_json(output_paths["summary"], summary)
    _write_json(output_paths["run_config"], run_config)

    print("\nPer-label test metrics:")
    print(report.to_string(index=False))
    print("\nTest summary:")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("\nSaved artifacts:")
    for name, path in output_paths.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
