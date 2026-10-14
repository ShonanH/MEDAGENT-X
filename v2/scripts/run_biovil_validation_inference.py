"""Run and tune BioViL zero-shot inference on CheXpert validation data.

This script intentionally reads only the competition-validation manifest and
ground truth. It scores every frontal image, averages raw scores across
frontal views at study level, fits population z-score parameters on validation
only, and selects one threshold per label by maximum F1 subject to a minimum
specificity constraint.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import json
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from PIL import Image
from sklearn.metrics import average_precision_score, roc_auc_score
from transformers import BertTokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BIOVIL_ROOT = PROJECT_ROOT / "external" / "biovil"
DEFAULT_HIML_ROOT = DEFAULT_BIOVIL_ROOT / "hi-ml"
DEFAULT_HIML_SOURCE = (
    DEFAULT_HIML_ROOT / "hi-ml-multimodal" / "src"
)
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
    / "exp16_chexpert_competition_val_thresholds"
    / "competition_val_manifest.csv"
)
DEFAULT_GROUND_TRUTH = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp16_chexpert_competition_val_thresholds"
    / "competition_val_ground_truth.csv"
)
DEFAULT_IMAGE_ROOT = (
    PROJECT_ROOT
    / "v2"
    / "data"
    / "chexpert_competition_test"
    / "chexlocalize"
    / "CheXpert"
    / "val"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "v2" / "experiments" / "biovil_zero_shot_comparison"
)
DEFAULT_PROMPT_POLICY = DEFAULT_OUTPUT_DIR / "prompt_policy.json"

LABELS: tuple[str, ...] = (
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
)
MODEL_NAME = "biovil_resnet50_zero_shot"
POLICY_VERSION = "biovil_zero_shot_max_f1_specificity_floor_v1"
EXPECTED_PROMPT_POLICY_VERSION = "biovil_gloria_prompt_match_v1"
EXPECTED_IMAGE_CHECKPOINT_SHA256 = (
    "118c4bb1c16d4e69b7c9b7f2ff5b2c0a79242059acf20bd2ed3068045b8f6b98"
)
EXPECTED_HIML_REVISION = "b67c1d27c6b17d8e8ff01f8c507f3cabdb307388"
EXPECTED_MANIFEST_SHA256 = (
    "684f12cc181a6fb987436e0ef01ccc7ddfd8b86f60669c78e564ff39ebb306be"
)
EXPECTED_GROUND_TRUTH_SHA256 = (
    "1caf1a4639711f32a1566ab514aed4d79f45f6f3477152c19811370586453026"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run BioViL zero-shot validation inference and select thresholds "
            "without reading the test cohort."
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
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--expected-views", type=int, default=234)
    parser.add_argument("--expected-frontal-images", type=int, default=202)
    parser.add_argument("--expected-studies", type=int, default=200)
    parser.add_argument("--minimum-specificity", type=float, default=0.60)
    parser.add_argument(
        "--device", default="cuda:0" if torch.cuda.is_available() else "cpu"
    )
    parser.add_argument("--seed", type=int, default=20260916)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing validation output artifacts.",
    )
    return parser


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_revision(repository: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _raw_column(label: str) -> str:
    return f"raw_{label}"


def _verify_hash(path: Path, expected: str, description: str) -> str:
    observed = _sha256(path)
    if observed != expected:
        raise RuntimeError(
            f"{description} SHA-256 mismatch: expected {expected}, "
            f"observed {observed}"
        )
    return observed


def _load_prompt_policy(path: Path) -> tuple[dict[str, Any], dict[str, list[str]]]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("policy_version") != EXPECTED_PROMPT_POLICY_VERSION:
        raise RuntimeError(
            "Unexpected prompt-policy version: "
            f"{policy.get('policy_version')!r}"
        )
    if policy.get("labels") != list(LABELS):
        raise RuntimeError(f"Prompt-policy labels differ from {list(LABELS)}")

    prompts = policy.get("prompts")
    if not isinstance(prompts, dict) or list(prompts) != list(LABELS):
        raise RuntimeError("Prompt-policy prompt labels or order are invalid")
    for label in LABELS:
        values = prompts[label]
        if not isinstance(values, list) or len(values) != 5:
            raise RuntimeError(f"{label} must contain exactly five prompts")
        if not all(isinstance(value, str) for value in values):
            raise RuntimeError(f"{label} contains a non-string prompt")

    expected_prompt_hash = policy["prompt_source"]["prompt_sha256"]
    observed_prompt_hash = _canonical_json_sha256(prompts)
    if observed_prompt_hash != expected_prompt_hash:
        raise RuntimeError(
            "Prompt content hash mismatch: "
            f"expected {expected_prompt_hash}, observed {observed_prompt_hash}"
        )
    return policy, prompts


def _prepare_validation_data(
    manifest_path: Path,
    ground_truth_path: Path,
    image_root: Path,
    expected_views: int,
    expected_frontal_images: int,
    expected_studies: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest = pd.read_csv(manifest_path)
    required_manifest = {"study_key", "dicom_path"}
    missing_manifest = sorted(required_manifest - set(manifest.columns))
    if missing_manifest:
        raise ValueError(f"Manifest is missing columns: {missing_manifest}")
    if len(manifest) != expected_views:
        raise RuntimeError(
            f"Expected {expected_views} validation views, found {len(manifest)}"
        )
    if manifest["dicom_path"].duplicated().any():
        raise RuntimeError("Validation manifest contains duplicate image paths")

    frontal_mask = manifest["dicom_path"].astype(str).str.contains(
        r"_frontal\.(?:jpg|jpeg|png)$",
        case=False,
        regex=True,
        na=False,
    )
    frontal = manifest.loc[frontal_mask].copy()
    frontal = frontal.sort_values(
        ["study_key", "dicom_path"], kind="stable"
    ).reset_index(drop=True)
    if len(frontal) != expected_frontal_images:
        raise RuntimeError(
            f"Expected {expected_frontal_images} frontal images, "
            f"found {len(frontal)}"
        )
    if frontal["study_key"].nunique() != expected_studies:
        raise RuntimeError(
            f"Expected {expected_studies} frontal-image studies, "
            f"found {frontal['study_key'].nunique()}"
        )

    frontal["image_path"] = frontal["dicom_path"].map(
        lambda value: str((image_root / str(value)).resolve())
    )
    missing_images = [
        value for value in frontal["image_path"] if not Path(value).is_file()
    ]
    if missing_images:
        raise FileNotFoundError(
            f"Missing {len(missing_images)} frontal images; "
            f"first missing: {missing_images[0]}"
        )

    ground_truth = pd.read_csv(ground_truth_path)
    required_ground_truth = {
        "study_key",
        "label",
        "ground_truth_status",
    }
    missing_ground_truth = sorted(
        required_ground_truth - set(ground_truth.columns)
    )
    if missing_ground_truth:
        raise ValueError(
            f"Ground truth is missing columns: {missing_ground_truth}"
        )
    ground_truth = ground_truth.loc[
        ground_truth["label"].isin(LABELS)
    ].copy()
    if ground_truth.duplicated(["study_key", "label"]).any():
        raise RuntimeError("Ground truth contains duplicate study-label rows")
    if len(ground_truth) != expected_studies * len(LABELS):
        raise RuntimeError(
            f"Expected {expected_studies * len(LABELS)} ground-truth rows, "
            f"found {len(ground_truth)}"
        )
    if ground_truth["study_key"].nunique() != expected_studies:
        raise RuntimeError("Unexpected validation ground-truth study count")
    if set(ground_truth["label"]) != set(LABELS):
        raise RuntimeError("Validation ground-truth labels do not match policy")
    observed_statuses = set(ground_truth["ground_truth_status"].astype(str))
    if observed_statuses != {"absent", "present"}:
        raise RuntimeError(
            f"Ground truth is not fully binary: {sorted(observed_statuses)}"
        )
    if "binary_scoreable" in ground_truth.columns:
        scoreable = (
            ground_truth["binary_scoreable"]
            .astype(str)
            .str.lower()
            .eq("true")
        )
        if not scoreable.all():
            raise RuntimeError("Ground truth contains non-scoreable rows")

    manifest_studies = set(frontal["study_key"].astype(str))
    truth_studies = set(ground_truth["study_key"].astype(str))
    if manifest_studies != truth_studies:
        raise RuntimeError("Frontal-image and ground-truth studies differ")
    return frontal, ground_truth


def _load_biovil_classes(source_root: Path) -> tuple[Any, Any, Any, Any, Any]:
    source = str(source_root)
    if source not in sys.path:
        sys.path.insert(0, source)
    try:
        from health_multimodal.image.data.transforms import (
            create_chest_xray_transform_for_inference,
        )
        from health_multimodal.image.model.model import ImageModel
        from health_multimodal.image.model.types import ImageEncoderType
        from health_multimodal.text.model.configuration_cxrbert import (
            CXRBertConfig,
        )
        from health_multimodal.text.model.modelling_cxrbert import CXRBertModel
    except Exception as error:
        raise RuntimeError(
            f"Unable to import BioViL from pinned source {source_root}"
        ) from error
    return (
        create_chest_xray_transform_for_inference,
        ImageModel,
        ImageEncoderType,
        CXRBertConfig,
        CXRBertModel,
    )


def _encode_prompts(
    *,
    prompts: dict[str, list[str]],
    tokenizer: BertTokenizer,
    text_model: Any,
    device: torch.device,
) -> torch.Tensor:
    flattened = [prompt for label in LABELS for prompt in prompts[label]]
    tokens = tokenizer(
        flattened,
        add_special_tokens=True,
        padding=True,
        return_tensors="pt",
    )
    tokens = {name: value.to(device) for name, value in tokens.items()}
    with torch.inference_mode():
        embeddings = text_model.get_projected_text_embeddings(
            input_ids=tokens["input_ids"],
            attention_mask=tokens["attention_mask"],
            normalize_embeddings=True,
        )
    expected_shape = (len(LABELS) * 5, 128)
    if tuple(embeddings.shape) != expected_shape:
        raise RuntimeError(
            f"Expected prompt embedding shape {expected_shape}, "
            f"found {tuple(embeddings.shape)}"
        )
    if not torch.isfinite(embeddings).all():
        raise RuntimeError("Text encoder produced non-finite prompt embeddings")
    return embeddings


def _score_images(
    *,
    frontal: pd.DataFrame,
    image_model: Any,
    text_embeddings: torch.Tensor,
    transform: Any,
    device: torch.device,
    batch_size: int,
) -> pd.DataFrame:
    batches: list[pd.DataFrame] = []
    for start in range(0, len(frontal), batch_size):
        stop = min(start + batch_size, len(frontal))
        batch = frontal.iloc[start:stop].reset_index(drop=True)
        tensors: list[torch.Tensor] = []
        for image_path in batch["image_path"]:
            with Image.open(image_path) as image:
                tensors.append(transform(image.convert("L")))
        image_tensor = torch.stack(tensors).to(device)

        with torch.inference_mode():
            outputs = image_model(image_tensor)
            image_embeddings = F.normalize(
                outputs.projected_global_embedding, dim=1
            )
            similarities = image_embeddings @ text_embeddings.T
            similarities = similarities.reshape(len(batch), len(LABELS), 5)
            scores = similarities.max(dim=2).values.cpu().numpy()

        if not np.isfinite(scores).all():
            raise RuntimeError("BioViL produced non-finite image scores")
        output = pd.DataFrame(
            scores,
            columns=[_raw_column(label) for label in LABELS],
        )
        output.insert(0, "image_path", batch["image_path"].astype(str))
        output.insert(0, "dicom_path", batch["dicom_path"].astype(str))
        output.insert(0, "study_key", batch["study_key"].astype(str))
        output.insert(0, "model_name", MODEL_NAME)
        batches.append(output)
        print(f"Processed {stop}/{len(frontal)} frontal images", flush=True)

        del image_tensor, outputs, image_embeddings, similarities, scores
        gc.collect()
        if device.type == "cuda":
            torch.cuda.empty_cache()

    return pd.concat(batches, ignore_index=True)


def _aggregate_studies(
    image_scores: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, Any]]]:
    raw_columns = [_raw_column(label) for label in LABELS]
    grouped = image_scores.groupby("study_key", sort=True, as_index=False)
    raw_scores = grouped[raw_columns].mean()
    view_counts = grouped.size().rename(columns={"size": "frontal_view_count"})
    view_paths = grouped["dicom_path"].agg(
        lambda values: json.dumps(list(values), separators=(",", ":"))
    ).rename(columns={"dicom_path": "frontal_dicom_paths"})
    raw_scores = view_counts.merge(raw_scores, on="study_key", validate="one_to_one")
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
    normalization: dict[str, dict[str, Any]] = {}
    for label in LABELS:
        raw_column = _raw_column(label)
        raw = raw_scores[raw_column].to_numpy(dtype=float)
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
            "fit_split": "competition_validation_only",
        }
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
    return raw_scores, scores, normalization


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
    return {
        "threshold": float(threshold),
        "predicted_positive": int(predicted.sum()),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": _safe_div(tp, tp + fp),
        "recall": _safe_div(tp, tp + fn),
        "f1": _safe_div(2 * tp, 2 * tp + fp + fn),
        "specificity": _safe_div(tn, tn + fp),
        "accuracy": _safe_div(tp + tn, len(y_true)),
    }


def _select_threshold(
    y_true: np.ndarray,
    scores: np.ndarray,
    minimum_specificity: float,
) -> dict[str, Any]:
    candidates = np.unique(scores.astype(float))
    rows = [
        _metrics_at_threshold(y_true, scores, float(threshold))
        for threshold in candidates
    ]
    eligible = [
        row for row in rows if row["specificity"] >= minimum_specificity
    ]
    if not eligible:
        raise RuntimeError(
            "No threshold satisfies the validation specificity floor of "
            f"{minimum_specificity}"
        )
    return max(
        eligible,
        key=lambda row: (row["f1"], row["precision"], row["threshold"]),
    )


def _tune_thresholds(
    scores: pd.DataFrame,
    ground_truth: pd.DataFrame,
    minimum_specificity: float,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float], dict[str, float]]:
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
            "Validation scores and ground truth do not align: "
            f"{joined['_merge'].value_counts().to_dict()}"
        )
    joined = joined.drop(columns="_merge")
    joined["ground_truth"] = (
        joined["ground_truth_status"].astype(str) == "present"
    ).astype(int)

    report_rows: list[dict[str, Any]] = []
    prediction_frames: list[pd.DataFrame] = []
    thresholds: dict[str, float] = {}
    for label in LABELS:
        rows = joined.loc[joined["label"] == label].copy()
        rows = rows.sort_values("study_key", kind="stable").reset_index(drop=True)
        y_true = rows["ground_truth"].to_numpy(dtype=int)
        label_scores = rows["score"].to_numpy(dtype=float)
        if set(np.unique(y_true)) != {0, 1}:
            raise RuntimeError(f"{label} lacks both binary classes")
        selected = _select_threshold(
            y_true, label_scores, minimum_specificity
        )
        threshold = float(selected["threshold"])
        thresholds[label] = threshold
        selected.update(
            {
                "label": label,
                "study_count": len(rows),
                "ground_truth_positive": int(y_true.sum()),
                "ground_truth_negative": int((y_true == 0).sum()),
                "auroc": float(roc_auc_score(y_true, label_scores)),
                "average_precision": float(
                    average_precision_score(y_true, label_scores)
                ),
                "selection_metric": "f1",
                "minimum_specificity": minimum_specificity,
                "tie_breaker": "precision_then_higher_threshold",
            }
        )
        report_rows.append(selected)

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
            "selection_metric",
            "minimum_specificity",
            "tie_breaker",
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
        "micro_f1": _safe_div(
            2 * total_tp, 2 * total_tp + total_fp + total_fn
        ),
        "micro_precision": _safe_div(total_tp, total_tp + total_fp),
        "micro_recall": _safe_div(total_tp, total_tp + total_fn),
    }
    return report, predictions, thresholds, aggregate


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
    if not 0.0 <= args.minimum_specificity <= 1.0:
        raise ValueError("--minimum-specificity must be between 0 and 1")

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
    manifest_path = _resolve_file(args.manifest, "validation manifest")
    ground_truth_path = _resolve_file(
        args.ground_truth, "validation ground truth"
    )
    image_root = _resolve_directory(args.image_root, "validation image root")
    prompt_policy_path = _resolve_file(args.prompt_policy, "prompt policy")
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    output_paths = {
        "image_scores": output_dir / "validation_image_scores.csv",
        "raw_scores": output_dir / "validation_raw_scores.csv",
        "scores": output_dir / "validation_scores.csv",
        "threshold_report": output_dir / "validation_threshold_report.csv",
        "predictions": output_dir / "validation_predictions.csv",
        "threshold_policy": output_dir / "threshold_policy.json",
        "run_config": output_dir / "validation_run_config.json",
    }
    existing = [path for path in output_paths.values() if path.exists()]
    if existing and not args.overwrite:
        formatted = "\n".join(str(path) for path in existing)
        raise FileExistsError(
            "Refusing to replace existing outputs without --overwrite:\n"
            f"{formatted}"
        )

    prompt_policy, prompts = _load_prompt_policy(prompt_policy_path)
    prompt_policy_sha256 = _sha256(prompt_policy_path)
    prompt_sha256 = _canonical_json_sha256(prompts)

    image_checkpoint_sha256 = _verify_hash(
        image_checkpoint,
        EXPECTED_IMAGE_CHECKPOINT_SHA256,
        "BioViL image checkpoint",
    )
    manifest_sha256 = _verify_hash(
        manifest_path,
        EXPECTED_MANIFEST_SHA256,
        "Validation manifest",
    )
    ground_truth_sha256 = _verify_hash(
        ground_truth_path,
        EXPECTED_GROUND_TRUTH_SHA256,
        "Validation ground truth",
    )
    himl_revision = _git_revision(himl_root)
    if himl_revision != EXPECTED_HIML_REVISION:
        raise RuntimeError(
            f"Expected HI-ML revision {EXPECTED_HIML_REVISION}, "
            f"found {himl_revision}"
        )

    frontal, ground_truth = _prepare_validation_data(
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

    (
        create_transform,
        ImageModel,
        ImageEncoderType,
        CXRBertConfig,
        CXRBertModel,
    ) = _load_biovil_classes(himl_source)

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

    text_embeddings = _encode_prompts(
        prompts=prompts,
        tokenizer=tokenizer,
        text_model=text_model,
        device=device,
    )
    transform = create_transform(resize=512, center_crop_size=480)
    image_scores = _score_images(
        frontal=frontal,
        image_model=image_model,
        text_embeddings=text_embeddings,
        transform=transform,
        device=device,
        batch_size=args.batch_size,
    )
    raw_scores, scores, normalization = _aggregate_studies(image_scores)
    if len(raw_scores) != args.expected_studies:
        raise RuntimeError(
            f"Expected {args.expected_studies} study scores, "
            f"found {len(raw_scores)}"
        )

    report, predictions, thresholds, aggregate = _tune_thresholds(
        scores,
        ground_truth,
        args.minimum_specificity,
    )
    if not (report["specificity"] >= args.minimum_specificity).all():
        raise RuntimeError("At least one selected threshold violates the floor")

    multi_view_count = int((raw_scores["frontal_view_count"] > 1).sum())
    threshold_policy = {
        "model_name": MODEL_NAME,
        "policy_version": POLICY_VERSION,
        "selection_split": "competition_val",
        "selection_metric": "per_label_maximum_f1_with_specificity_floor",
        "minimum_specificity": args.minimum_specificity,
        "tie_breaker": "maximum_precision_then_higher_threshold",
        "study_count": args.expected_studies,
        "study_label_count": args.expected_studies * len(LABELS),
        "selected_thresholds": thresholds,
        "validation_normalization": normalization,
        "prompt_policy": str(prompt_policy_path),
        "prompt_policy_sha256": prompt_policy_sha256,
        "prompt_sha256": prompt_sha256,
        "manifest": str(manifest_path),
        "manifest_sha256": manifest_sha256,
        "ground_truth": str(ground_truth_path),
        "ground_truth_sha256": ground_truth_sha256,
        **aggregate,
    }
    run_config = {
        "model_name": MODEL_NAME,
        "seed": args.seed,
        "device": str(device),
        "batch_size": args.batch_size,
        "image_checkpoint": str(image_checkpoint),
        "image_checkpoint_sha256": image_checkpoint_sha256,
        "text_model_directory": str(model_dir),
        "huggingface_revision": prompt_policy["model"]["huggingface_revision"],
        "hi_ml_repository": str(himl_root),
        "hi_ml_revision": himl_revision,
        "text_model_class": (
            "health_multimodal.text.model.modelling_cxrbert.CXRBertModel"
        ),
        "tokenizer_class": "transformers.BertTokenizer",
        "compatibility_reason": prompt_policy["compatibility"]["reason"],
        "prompt_policy": str(prompt_policy_path),
        "prompt_policy_sha256": prompt_policy_sha256,
        "prompt_sha256": prompt_sha256,
        "prompts": prompts,
        "manifest": str(manifest_path),
        "manifest_sha256": manifest_sha256,
        "ground_truth": str(ground_truth_path),
        "ground_truth_sha256": ground_truth_sha256,
        "image_root": str(image_root),
        "manifest_view_count": args.expected_views,
        "frontal_image_count": len(frontal),
        "study_count": len(raw_scores),
        "multi_frontal_study_count": multi_view_count,
        "image_preprocessing": prompt_policy["image_preprocessing"],
        "scoring": prompt_policy["scoring"],
        "minimum_specificity": args.minimum_specificity,
        "normalization": normalization,
        "selected_thresholds": thresholds,
        "script": str(Path(__file__).resolve()),
        "script_sha256": _sha256(Path(__file__).resolve()),
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
    report.to_csv(output_paths["threshold_report"], index=False)
    predictions.to_csv(output_paths["predictions"], index=False)
    _write_json(output_paths["threshold_policy"], threshold_policy)
    _write_json(output_paths["run_config"], run_config)

    print("\nPer-label validation metrics:")
    print(report.to_string(index=False))
    print("\nValidation summary:")
    print(json.dumps(threshold_policy, indent=2, sort_keys=True))
    print("\nSaved artifacts:")
    for name, path in output_paths.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
