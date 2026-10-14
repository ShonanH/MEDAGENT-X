"""Run the locked Exp20 BioViL evaluation on the CheXpert test cohort.

Prediction-only artifacts are written and checksummed before this command opens
the test ground-truth CSV. The command only applies validation-frozen
normalization and thresholds; it contains no threshold-selection procedure.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

import run_exp20_biovil_validation_inference as inference_pipeline


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp20_biovil_native_zero_shot_comparison"
)
DEFAULT_PROMPT_POLICY = DEFAULT_OUTPUT_DIR / "prompt_policy.json"
DEFAULT_THRESHOLD_POLICY = DEFAULT_OUTPUT_DIR / "threshold_policy.json"
DEFAULT_VALIDATION_INFERENCE_CONFIG = (
    DEFAULT_OUTPUT_DIR / "validation_inference_run_config.json"
)
DEFAULT_BIOVIL_ROOT = PROJECT_ROOT / "external" / "biovil"
DEFAULT_HIML_ROOT = DEFAULT_BIOVIL_ROOT / "hi-ml"
DEFAULT_HIML_SOURCE = DEFAULT_HIML_ROOT / "hi-ml-multimodal" / "src"
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

PROMPT_POLICY_VERSION = "biovil_native_positive_negative_margin_exp20_v1"
THRESHOLD_POLICY_VERSION = (
    "biovil_native_max_f1_specificity_floor_exp20_v1"
)
MODEL_NAME = "biovil_resnet50_native_zero_shot"
EXPECTED_PROMPT_POLICY_SHA256 = (
    "086297ab423635da83acac73752c7a21"
    "a610f17a4be6bfda0d34f7214ec44a82"
)
EXPECTED_THRESHOLD_POLICY_SHA256 = (
    "048f8f06857ebe9d47d0d0e1e5ee88e"
    "49eca7ff726a48660314d8258781775e5"
)
EXPECTED_TEST_MANIFEST_SHA256 = (
    "fe4084cbb7acb349ffe9aa45f5e56074"
    "0562f76ce6496c3436918fee6444f6aa"
)
EXPECTED_TEST_GROUND_TRUTH_SHA256 = (
    "9bab723d2051e2c35b3869e8d659c71"
    "c9c3da78ea21814d3a337120e4150f489"
)
LABELS = inference_pipeline.LABELS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Apply the frozen Exp20 BioViL policy to the 500-study test "
            "cohort, locking predictions before opening test labels."
        )
    )
    parser.add_argument(
        "--prompt-policy", type=Path, default=DEFAULT_PROMPT_POLICY
    )
    parser.add_argument(
        "--threshold-policy", type=Path, default=DEFAULT_THRESHOLD_POLICY
    )
    parser.add_argument(
        "--validation-inference-config",
        type=Path,
        default=DEFAULT_VALIDATION_INFERENCE_CONFIG,
    )
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument(
        "--image-checkpoint", type=Path, default=DEFAULT_IMAGE_CHECKPOINT
    )
    parser.add_argument("--hi-ml-root", type=Path, default=DEFAULT_HIML_ROOT)
    parser.add_argument(
        "--hi-ml-source", type=Path, default=DEFAULT_HIML_SOURCE
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH
    )
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--expected-views", type=int, default=668)
    parser.add_argument("--expected-frontal-images", type=int, default=518)
    parser.add_argument("--expected-studies", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260923)
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help=(
            "Verify the locked policies, test manifest, and image inventory, "
            "then exit without loading models, opening labels, or writing."
        ),
    )
    parser.add_argument(
        "--device",
        default="cuda:0" if torch.cuda.is_available() else "cpu",
    )
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


def verify_hash(path: Path, expected: str, description: str) -> str:
    observed = sha256(path)
    if observed != expected:
        raise RuntimeError(
            f"{description} SHA-256 mismatch: expected {expected}, "
            f"observed {observed}"
        )
    return observed


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def load_checksum_policy(
    policy_path: Path,
    checksum_name: str,
    expected_hash: str,
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
    if observed != expected_hash:
        raise RuntimeError(
            f"Frozen hash mismatch for {policy_path}: expected "
            f"{expected_hash}, observed {observed}"
        )
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("policy_version") != expected_version:
        raise RuntimeError(
            f"Expected policy version {expected_version!r}, "
            f"found {policy.get('policy_version')!r}"
        )
    return policy, observed


def validate_frozen_policies(
    *,
    prompt_policy_path: Path,
    threshold_policy_path: Path,
    validation_inference_config_path: Path,
) -> tuple[
    dict[str, Any],
    str,
    dict[str, Any],
    str,
    dict[str, Any],
    str,
]:
    prompt_policy, prompt_policy_hash = load_checksum_policy(
        prompt_policy_path,
        "prompt_policy.sha256",
        EXPECTED_PROMPT_POLICY_SHA256,
        PROMPT_POLICY_VERSION,
    )
    threshold_policy, threshold_policy_hash = load_checksum_policy(
        threshold_policy_path,
        "threshold_policy.sha256",
        EXPECTED_THRESHOLD_POLICY_SHA256,
        THRESHOLD_POLICY_VERSION,
    )
    validation_config = json.loads(
        validation_inference_config_path.read_text(encoding="utf-8")
    )
    validation_config_hash = sha256(validation_inference_config_path)

    if tuple(prompt_policy.get("labels", ())) != LABELS:
        raise RuntimeError("Prompt-policy labels or order changed")
    if threshold_policy.get("experiment_id") != "exp20":
        raise RuntimeError("Threshold policy is not from Exp20")
    if threshold_policy.get("model_name") != MODEL_NAME:
        raise RuntimeError("Threshold policy belongs to another model")
    if threshold_policy.get("source_prompt_policy_sha256") != (
        prompt_policy_hash
    ):
        raise RuntimeError("Threshold and prompt policies are not linked")
    if threshold_policy.get("selection_split") != "competition_validation":
        raise RuntimeError("Thresholds were not selected on validation")
    if threshold_policy.get("minimum_specificity") != 0.60:
        raise RuntimeError("Threshold policy lacks specificity >= 0.60")
    if threshold_policy.get("test_data_used_for_selection") is not False:
        raise RuntimeError("Threshold policy indicates test-data selection")
    if threshold_policy.get("prompts") != prompt_policy.get("prompts"):
        raise RuntimeError("Threshold-policy prompts differ from prompt policy")

    thresholds = threshold_policy.get("selected_thresholds")
    raw_thresholds = threshold_policy.get("selected_raw_margin_thresholds")
    normalization = threshold_policy.get("validation_normalization")
    for name, value in (
        ("selected_thresholds", thresholds),
        ("selected_raw_margin_thresholds", raw_thresholds),
        ("validation_normalization", normalization),
    ):
        if not isinstance(value, dict) or set(value) != set(LABELS):
            raise RuntimeError(f"Threshold policy has invalid {name}")
    for label in LABELS:
        threshold = float(thresholds[label])
        raw_threshold = float(raw_thresholds[label])
        normalizer = normalization[label]
        mean = float(normalizer["raw_mean"])
        std = float(normalizer["raw_std"])
        if not all(np.isfinite(value) for value in (threshold, raw_threshold, mean, std)):
            raise RuntimeError(f"Non-finite policy value for {label}")
        if std <= 0:
            raise RuntimeError(f"Non-positive validation std for {label}")
        if normalizer.get("method") != "zscore_population":
            raise RuntimeError(f"Unexpected normalization for {label}")
        if normalizer.get("fit_split") != "competition_validation_only":
            raise RuntimeError(f"Non-validation normalizer for {label}")
        reconstructed = mean + threshold * std
        if not np.isclose(reconstructed, raw_threshold, atol=1e-6, rtol=0.0):
            raise RuntimeError(f"Raw threshold identity failed for {label}")

    frozen_inputs = threshold_policy.get("frozen_inputs", {})
    expected_validation_config_hash = frozen_inputs.get(
        "validation_inference_run_config", {}
    ).get("sha256")
    if validation_config_hash != expected_validation_config_hash:
        raise RuntimeError(
            "Validation inference config differs from threshold policy"
        )
    if validation_config.get("prompt_policy_sha256") != prompt_policy_hash:
        raise RuntimeError("Validation inference used another prompt policy")
    if validation_config.get("ground_truth_read") is not False:
        raise RuntimeError("Validation inference was not ground-truth blind")

    validation_script_path = resolve_file(
        Path(inference_pipeline.__file__), "validation inference script"
    )
    if sha256(validation_script_path) != validation_config.get("script_sha256"):
        raise RuntimeError(
            "Validation inference script changed after validation scoring"
        )

    for input_name in (
        "validation_raw_scores",
        "validation_ground_truth",
        "prompt_policy",
    ):
        item = frozen_inputs.get(input_name)
        if not isinstance(item, dict):
            raise RuntimeError(f"Threshold policy lacks {input_name}")
        frozen_path = resolve_file(Path(item["path"]), input_name)
        if sha256(frozen_path) != item.get("sha256"):
            raise RuntimeError(f"Frozen validation input changed: {input_name}")

    return (
        prompt_policy,
        prompt_policy_hash,
        threshold_policy,
        threshold_policy_hash,
        validation_config,
        validation_config_hash,
    )


def apply_validation_policy(
    study_scores: pd.DataFrame,
    threshold_policy: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scores = study_scores.copy()
    prediction_frames: list[pd.DataFrame] = []
    normalization = threshold_policy["validation_normalization"]
    thresholds = threshold_policy["selected_thresholds"]
    for label in LABELS:
        raw = scores[inference_pipeline.raw_column(label)].to_numpy(dtype=float)
        mean = float(normalization[label]["raw_mean"])
        std = float(normalization[label]["raw_std"])
        normalized = (raw - mean) / std
        if not np.isfinite(normalized).all():
            raise RuntimeError(f"Non-finite normalized test score for {label}")
        scores[label] = normalized
        threshold = float(thresholds[label])
        prediction_frames.append(
            pd.DataFrame(
                {
                    "model_name": MODEL_NAME,
                    "policy_version": THRESHOLD_POLICY_VERSION,
                    "study_key": scores["study_key"].astype(str),
                    "label": label,
                    "raw_score": raw,
                    "score": normalized,
                    "threshold": threshold,
                    "predicted_positive": (normalized >= threshold).astype(int),
                }
            )
        )
    predictions = pd.concat(prediction_frames, ignore_index=True)
    predictions["predicted_status"] = predictions["predicted_positive"].map(
        {1: "present", 0: "absent"}
    )
    scores = scores.loc[
        :,
        [
            "model_name",
            "policy_version",
            "study_key",
            "frontal_view_count",
            "frontal_dicom_paths",
            *LABELS,
            *(
                column
                for label in LABELS
                for column in (
                    inference_pipeline.positive_column(label),
                    inference_pipeline.negative_column(label),
                    inference_pipeline.raw_column(label),
                )
            ),
        ],
    ]
    predictions = predictions.loc[
        :,
        [
            "model_name",
            "policy_version",
            "study_key",
            "label",
            "raw_score",
            "score",
            "threshold",
            "predicted_positive",
            "predicted_status",
        ],
    ]
    return scores, predictions


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


def safe_divide(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def load_and_validate_ground_truth(
    ground_truth_path: Path,
    expected_studies: int,
    prediction_studies: set[str],
) -> tuple[pd.DataFrame, str]:
    ground_truth_hash = verify_hash(
        ground_truth_path,
        EXPECTED_TEST_GROUND_TRUTH_SHA256,
        "Test ground truth",
    )
    ground_truth = pd.read_csv(ground_truth_path)
    required = {"study_key", "label", "ground_truth_status"}
    missing = sorted(required - set(ground_truth.columns))
    if missing:
        raise ValueError(f"Ground truth is missing columns: {missing}")
    ground_truth = ground_truth.loc[
        ground_truth["label"].isin(LABELS)
    ].copy()
    if len(ground_truth) != expected_studies * len(LABELS):
        raise RuntimeError(
            f"Expected {expected_studies * len(LABELS)} test labels, "
            f"found {len(ground_truth)}"
        )
    if ground_truth.duplicated(["study_key", "label"]).any():
        raise RuntimeError("Test ground truth has duplicate study-label rows")
    if ground_truth["study_key"].nunique() != expected_studies:
        raise RuntimeError("Unexpected test ground-truth study count")
    if set(ground_truth["study_key"].astype(str)) != prediction_studies:
        raise RuntimeError("Test prediction and ground-truth studies differ")
    if set(ground_truth["label"].astype(str)) != set(LABELS):
        raise RuntimeError("Test ground-truth labels differ")
    statuses = set(ground_truth["ground_truth_status"].astype(str))
    if statuses != {"absent", "present"}:
        raise RuntimeError(f"Test ground truth is not binary: {statuses}")
    if "binary_scoreable" in ground_truth.columns:
        scoreable = (
            ground_truth["binary_scoreable"]
            .astype(str)
            .str.lower()
            .isin({"true", "1"})
        )
        if not scoreable.all():
            raise RuntimeError("Test ground truth contains non-scoreable rows")
    return ground_truth, ground_truth_hash


def evaluate_predictions(
    predictions: pd.DataFrame,
    ground_truth: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    truth = ground_truth.loc[
        :, ["study_key", "label", "ground_truth_status"]
    ].copy()
    rows = predictions.merge(
        truth,
        on=["study_key", "label"],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if not rows["_merge"].eq("both").all():
        raise RuntimeError(
            "Test predictions and ground truth do not align: "
            f"{rows['_merge'].value_counts().to_dict()}"
        )
    rows = rows.drop(columns="_merge")
    rows["ground_truth"] = (
        rows["ground_truth_status"].astype(str).eq("present").astype(int)
    )
    metric_rows: list[dict[str, Any]] = []
    for label in LABELS:
        label_rows = rows.loc[rows["label"].eq(label)].copy()
        label_rows = label_rows.sort_values(
            "study_key", kind="stable"
        ).reset_index(drop=True)
        y_true = label_rows["ground_truth"].to_numpy(dtype=int)
        y_pred = label_rows["predicted_positive"].to_numpy(dtype=int)
        label_scores = label_rows["score"].to_numpy(dtype=float)
        if set(np.unique(y_true)) != {0, 1}:
            raise RuntimeError(f"{label} lacks both test classes")
        tp = int(np.sum((y_pred == 1) & (y_true == 1)))
        tn = int(np.sum((y_pred == 0) & (y_true == 0)))
        fp = int(np.sum((y_pred == 1) & (y_true == 0)))
        fn = int(np.sum((y_pred == 0) & (y_true == 1)))
        metric_rows.append(
            {
                "label": label,
                "threshold": float(label_rows["threshold"].iloc[0]),
                "study_count": len(label_rows),
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
                "auroc": float(roc_auc_score(y_true, label_scores)),
                "average_precision": float(
                    average_precision_score(y_true, label_scores)
                ),
            }
        )
    metrics = pd.DataFrame(metric_rows)
    y_true_all = rows["ground_truth"].to_numpy(dtype=int)
    y_pred_all = rows["predicted_positive"].to_numpy(dtype=int)
    tp = int(np.sum((y_pred_all == 1) & (y_true_all == 1)))
    tn = int(np.sum((y_pred_all == 0) & (y_true_all == 0)))
    fp = int(np.sum((y_pred_all == 1) & (y_true_all == 0)))
    fn = int(np.sum((y_pred_all == 0) & (y_true_all == 1)))
    aggregate = {
        "macro_auroc": float(metrics["auroc"].mean()),
        "macro_average_precision": float(
            metrics["average_precision"].mean()
        ),
        "macro_precision": float(metrics["precision"].mean()),
        "macro_recall": float(metrics["recall"].mean()),
        "macro_f1": float(metrics["f1"].mean()),
        "macro_specificity": float(metrics["specificity"].mean()),
        "macro_accuracy": float(metrics["accuracy"].mean()),
        "micro_precision": safe_divide(tp, tp + fp),
        "micro_recall": safe_divide(tp, tp + fn),
        "micro_f1": safe_divide(2 * tp, 2 * tp + fp + fn),
        "micro_specificity": safe_divide(tn, tn + fp),
        "micro_accuracy": safe_divide(tp + tn, len(y_true_all)),
    }
    rows = rows.sort_values(["study_key", "label"], kind="stable")
    return rows.reset_index(drop=True), metrics, aggregate


def main() -> None:
    args = build_parser().parse_args()
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be positive")

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True

    output_dir = resolve_directory(args.output_dir, "Exp20 output directory")
    output_paths = {
        "image_scores": output_dir / "test_image_scores.csv",
        "raw_scores": output_dir / "test_raw_scores.csv",
        "scores": output_dir / "test_scores.csv",
        "predictions": output_dir / "test_predictions.csv",
        "prediction_lock": output_dir / "test_prediction_lock.json",
        "evaluation_rows": output_dir / "test_evaluation_rows.csv",
        "metrics": output_dir / "test_per_label_metrics.csv",
        "summary": output_dir / "test_summary.json",
        "run_config": output_dir / "test_run_config.json",
    }
    existing = [path for path in output_paths.values() if path.exists()]
    if existing:
        formatted = "\n".join(str(path) for path in existing)
        raise FileExistsError(
            "Refusing to overwrite existing Exp20 test outputs:\n" + formatted
        )

    prompt_policy_path = resolve_file(
        args.prompt_policy, "Exp20 prompt policy"
    )
    threshold_policy_path = resolve_file(
        args.threshold_policy, "Exp20 threshold policy"
    )
    validation_config_path = resolve_file(
        args.validation_inference_config,
        "validation inference run config",
    )
    model_dir = resolve_directory(args.model_dir, "CXR-BERT model directory")
    image_checkpoint = resolve_file(
        args.image_checkpoint, "BioViL image checkpoint"
    )
    text_checkpoint = resolve_file(
        model_dir / "pytorch_model.bin", "CXR-BERT checkpoint"
    )
    hi_ml_root = resolve_directory(args.hi_ml_root, "Microsoft HI-ML repository")
    hi_ml_source = resolve_directory(args.hi_ml_source, "HI-ML Python source")
    manifest_path = resolve_file(args.manifest, "test manifest")
    image_root = resolve_directory(args.image_root, "test image root")
    ground_truth_path = args.ground_truth.expanduser().resolve()
    if not ground_truth_path.is_file():
        raise FileNotFoundError(f"Missing test ground truth: {ground_truth_path}")
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(f"Requested {device}, but CUDA is unavailable")

    print("=== VERIFYING FROZEN TEST INPUTS ===")
    (
        prompt_policy,
        prompt_policy_hash,
        threshold_policy,
        threshold_policy_hash,
        validation_config,
        validation_config_hash,
    ) = validate_frozen_policies(
        prompt_policy_path=prompt_policy_path,
        threshold_policy_path=threshold_policy_path,
        validation_inference_config_path=validation_config_path,
    )
    image_checkpoint_hash = verify_hash(
        image_checkpoint,
        inference_pipeline.EXPECTED_IMAGE_CHECKPOINT_SHA256,
        "BioViL image checkpoint",
    )
    text_checkpoint_hash = verify_hash(
        text_checkpoint,
        inference_pipeline.EXPECTED_TEXT_CHECKPOINT_SHA256,
        "CXR-BERT checkpoint",
    )
    manifest_hash = verify_hash(
        manifest_path,
        EXPECTED_TEST_MANIFEST_SHA256,
        "Test manifest",
    )
    hi_ml_revision = inference_pipeline.git_output(
        hi_ml_root, "rev-parse", "HEAD"
    )
    hi_ml_status = inference_pipeline.git_output(
        hi_ml_root, "status", "--short"
    )
    if hi_ml_revision != inference_pipeline.EXPECTED_HIML_REVISION:
        raise RuntimeError("Microsoft HI-ML revision changed")
    if hi_ml_status:
        raise RuntimeError(
            "Microsoft HI-ML repository has uncommitted changes:\n"
            + hi_ml_status
        )
    frontal = inference_pipeline.prepare_manifest(
        manifest_path,
        image_root,
        args.expected_views,
        args.expected_frontal_images,
        args.expected_studies,
    )
    print("Prompt-policy SHA-256:", prompt_policy_hash)
    print("Threshold-policy SHA-256:", threshold_policy_hash)
    print("Validation-config SHA-256:", validation_config_hash)
    print("Test-manifest SHA-256:", manifest_hash)
    print("Views:", args.expected_views)
    print("Frontal images:", len(frontal))
    print("Studies:", frontal["study_key"].nunique())
    print("Test ground truth opened:", False)
    print("Device:", device)

    if args.preflight_only:
        print("Test evaluator script SHA-256:", sha256(Path(__file__).resolve()))
        print("Model loaded:", False)
        print("Test ground truth opened:", False)
        print("Outputs written:", False)
        print("STEP 6 LOCKED TEST PREFLIGHT SUCCEEDED")
        return

    (
        create_transform,
        ImageModel,
        ImageEncoderType,
        CXRBertConfig,
        CXRBertTokenizer,
        CXRBertModel,
    ) = inference_pipeline.load_biovil_classes(hi_ml_source)
    print("\n=== LOADING BIOVIL ===", flush=True)
    image_model = ImageModel(
        img_encoder_type=ImageEncoderType.RESNET50,
        joint_feature_size=128,
        pretrained_model_path=image_checkpoint,
    ).eval().to(device)
    tokenizer = CXRBertTokenizer.from_pretrained(
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
    text_embeddings = inference_pipeline.encode_prompts(
        policy=prompt_policy,
        tokenizer=tokenizer,
        text_model=text_model,
        device=device,
    )
    transform = create_transform(resize=512, center_crop_size=480)

    print("\n=== GENERATING LABEL-BLIND TEST PREDICTIONS ===", flush=True)
    image_scores = inference_pipeline.score_images(
        frontal=frontal,
        image_model=image_model,
        text_embeddings=text_embeddings,
        transform=transform,
        device=device,
        batch_size=args.batch_size,
    )
    study_scores = inference_pipeline.aggregate_studies(image_scores)
    if len(study_scores) != args.expected_studies:
        raise RuntimeError(
            f"Expected {args.expected_studies} test studies, "
            f"found {len(study_scores)}"
        )
    multi_view_count = int((study_scores["frontal_view_count"] > 1).sum())
    if multi_view_count != 18:
        raise RuntimeError(
            f"Expected 18 multi-frontal test studies, found {multi_view_count}"
        )
    scores, predictions = apply_validation_policy(
        study_scores, threshold_policy
    )
    if len(predictions) != args.expected_studies * len(LABELS):
        raise RuntimeError("Unexpected test prediction count")
    if predictions.duplicated(["study_key", "label"]).any():
        raise RuntimeError("Duplicate test study-label prediction")

    for path in output_paths.values():
        if path.exists():
            raise FileExistsError(f"Output appeared during inference: {path}")
    write_csv_atomic(image_scores, output_paths["image_scores"])
    write_csv_atomic(study_scores, output_paths["raw_scores"])
    write_csv_atomic(scores, output_paths["scores"])
    write_csv_atomic(predictions, output_paths["predictions"])
    prediction_hashes = {
        output_paths[key].name: sha256(output_paths[key])
        for key in ("image_scores", "raw_scores", "scores", "predictions")
    }
    prediction_lock = {
        "experiment_id": "exp20",
        "model_name": MODEL_NAME,
        "prompt_policy_sha256": prompt_policy_hash,
        "threshold_policy_sha256": threshold_policy_hash,
        "test_manifest_sha256": manifest_hash,
        "test_ground_truth_opened_before_prediction_lock": False,
        "normalization_source": "competition_validation_only",
        "threshold_source": "competition_validation_only",
        "test_time_tuning": False,
        "frontal_image_count": len(image_scores),
        "study_count": len(scores),
        "study_label_prediction_count": len(predictions),
        "artifact_sha256": prediction_hashes,
    }
    write_json_atomic(prediction_lock, output_paths["prediction_lock"])
    prediction_lock_hash = sha256(output_paths["prediction_lock"])
    print("Prediction lock SHA-256:", prediction_lock_hash)
    print("Test ground truth opened before prediction lock:", False)

    for filename, expected_hash in prediction_hashes.items():
        path = output_dir / filename
        if sha256(path) != expected_hash:
            raise RuntimeError(f"Prediction artifact changed after lock: {path}")

    print("\n=== LOADING TEST LABELS FOR METRICS ===")
    ground_truth, ground_truth_hash = load_and_validate_ground_truth(
        ground_truth_path,
        args.expected_studies,
        set(predictions["study_key"].astype(str)),
    )
    evaluation_rows, metrics, aggregate = evaluate_predictions(
        predictions, ground_truth
    )
    write_csv_atomic(evaluation_rows, output_paths["evaluation_rows"])
    write_csv_atomic(metrics, output_paths["metrics"])
    summary = {
        "experiment_id": "exp20",
        "model_name": MODEL_NAME,
        "evaluation_split": "competition_test",
        "study_count": args.expected_studies,
        "study_label_count": args.expected_studies * len(LABELS),
        "label_count": len(LABELS),
        "prompt_policy_version": PROMPT_POLICY_VERSION,
        "prompt_policy_sha256": prompt_policy_hash,
        "threshold_policy_version": THRESHOLD_POLICY_VERSION,
        "threshold_policy_sha256": threshold_policy_hash,
        "normalization_source": "competition_validation_only",
        "threshold_source": "competition_validation_only",
        "minimum_validation_specificity": 0.60,
        "test_time_tuning": False,
        "predictions_locked_before_ground_truth": True,
        "prediction_lock_sha256": prediction_lock_hash,
        **aggregate,
    }
    write_json_atomic(summary, output_paths["summary"])

    final_hashes = {
        path.name: sha256(path)
        for key, path in output_paths.items()
        if key != "run_config"
    }
    run_config = {
        "experiment_id": "exp20",
        "model_name": MODEL_NAME,
        "script_path": str(Path(__file__).resolve()),
        "script_sha256": sha256(Path(__file__).resolve()),
        "prompt_policy": str(prompt_policy_path),
        "prompt_policy_sha256": prompt_policy_hash,
        "threshold_policy": str(threshold_policy_path),
        "threshold_policy_sha256": threshold_policy_hash,
        "validation_inference_config": str(validation_config_path),
        "validation_inference_config_sha256": validation_config_hash,
        "test_manifest": str(manifest_path),
        "test_manifest_sha256": manifest_hash,
        "test_ground_truth": str(ground_truth_path),
        "test_ground_truth_sha256": ground_truth_hash,
        "image_root": str(image_root),
        "image_checkpoint": str(image_checkpoint),
        "image_checkpoint_sha256": image_checkpoint_hash,
        "text_checkpoint": str(text_checkpoint),
        "text_checkpoint_sha256": text_checkpoint_hash,
        "hi_ml_revision": hi_ml_revision,
        "labels": list(LABELS),
        "prompts": prompt_policy["prompts"],
        "validation_normalization": threshold_policy[
            "validation_normalization"
        ],
        "selected_thresholds": threshold_policy["selected_thresholds"],
        "score_definition": "positive_similarity - negative_similarity",
        "study_aggregation": "mean_of_frontal_image_continuous_scores",
        "predictions_locked_before_ground_truth": True,
        "prediction_lock_sha256": prediction_lock_hash,
        "test_time_tuning": False,
        "execution": {
            "device": str(device),
            "batch_size": args.batch_size,
            "seed": args.seed,
            "python": sys.version,
            "torch": torch.__version__,
            "torchvision": package_version("torchvision"),
            "transformers": package_version("transformers"),
            "timm": package_version("timm"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": package_version("scikit-learn"),
            "cuda_runtime": torch.version.cuda,
            "gpu_name": (
                torch.cuda.get_device_name(device)
                if device.type == "cuda"
                else None
            ),
        },
        "artifact_sha256": final_hashes,
    }
    write_json_atomic(run_config, output_paths["run_config"])

    print("\n=== PER-LABEL TEST METRICS ===")
    print(metrics.to_string(index=False))
    print("\n=== TEST SUMMARY ===")
    print(json.dumps(summary, indent=2, sort_keys=True))
    for path in output_paths.values():
        print("Saved:", path)
    print("Test-time tuning:", False)
    print("Predictions locked before ground truth:", True)
    print("STEP 7 TEST EVALUATION SUCCEEDED")


if __name__ == "__main__":
    main()
