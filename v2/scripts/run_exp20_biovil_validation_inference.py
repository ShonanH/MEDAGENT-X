"""Run validation-only BioViL inference for the frozen Exp20 protocol.

This command never reads ground truth and never selects thresholds. It scores
all eligible frontal validation images, averages continuous scores at study
level, and writes auditable inference artifacts without overwriting files.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import json
import os
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


sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[2]
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
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp20_biovil_native_zero_shot_comparison"
)
DEFAULT_POLICY = DEFAULT_OUTPUT_DIR / "prompt_policy.json"
DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp16_chexpert_competition_val_thresholds"
    / "competition_val_manifest.csv"
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

POLICY_VERSION = "biovil_native_positive_negative_margin_exp20_v1"
MODEL_NAME = "biovil_resnet50_native_zero_shot"
EXPECTED_HIML_REVISION = "b67c1d27c6b17d8e8ff01f8c507f3cabdb307388"
EXPECTED_IMAGE_CHECKPOINT_SHA256 = (
    "118c4bb1c16d4e69b7c9b7f2ff5b2c0"
    "a79242059acf20bd2ed3068045b8f6b98"
)
EXPECTED_TEXT_CHECKPOINT_SHA256 = (
    "a41d2f4b33e5bdbacabecb8d34c44201"
    "63e2165b9fdc6915014e8263a0d0782b"
)
EXPECTED_MANIFEST_SHA256 = (
    "684f12cc181a6fb987436e0ef01ccc7d"
    "dfd8b86f60669c78e564ff39ebb306be"
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
            "Generate Exp20 BioViL positive-negative margin scores on the "
            "competition-validation cohort without reading ground truth."
        )
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument(
        "--image-checkpoint", type=Path, default=DEFAULT_IMAGE_CHECKPOINT
    )
    parser.add_argument("--hi-ml-root", type=Path, default=DEFAULT_HIML_ROOT)
    parser.add_argument(
        "--hi-ml-source", type=Path, default=DEFAULT_HIML_SOURCE
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--expected-views", type=int, default=234)
    parser.add_argument("--expected-frontal-images", type=int, default=202)
    parser.add_argument("--expected-studies", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260923)
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


def git_output(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


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


def load_policy(path: Path) -> tuple[dict[str, Any], str]:
    checksum_path = resolve_file(
        path.with_name("prompt_policy.sha256"), "prompt-policy checksum"
    )
    checksum_fields = checksum_path.read_text(encoding="utf-8").strip().split()
    if len(checksum_fields) != 2 or checksum_fields[1] != path.name:
        raise RuntimeError(f"Malformed checksum file: {checksum_path}")
    observed_hash = sha256(path)
    if observed_hash != checksum_fields[0]:
        raise RuntimeError("Exp20 prompt-policy checksum mismatch")
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("policy_version") != POLICY_VERSION:
        raise RuntimeError(
            f"Expected policy version {POLICY_VERSION!r}, "
            f"found {policy.get('policy_version')!r}"
        )
    if tuple(policy.get("labels", ())) != LABELS:
        raise RuntimeError("Exp20 prompt-policy labels or order changed")
    prompts = policy.get("prompts")
    if not isinstance(prompts, dict) or tuple(prompts) != LABELS:
        raise RuntimeError("Exp20 prompt mapping is invalid")
    for label in LABELS:
        prompt_pair = prompts[label]
        if set(prompt_pair) != {"positive", "negative"}:
            raise RuntimeError(f"Invalid prompt pair for {label}")
        if not all(
            isinstance(prompt_pair[polarity], str)
            for polarity in ("positive", "negative")
        ):
            raise RuntimeError(f"Non-string prompt found for {label}")
    formula = policy.get("inference", {}).get("image_raw_score")
    if formula != "positive_similarity - negative_similarity":
        raise RuntimeError(f"Unexpected score formula: {formula!r}")
    return policy, observed_hash


def load_biovil_classes(
    source_root: Path,
) -> tuple[Any, Any, Any, Any, Any, Any]:
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
            CXRBertTokenizer,
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
        CXRBertTokenizer,
        CXRBertModel,
    )


def prepare_manifest(
    manifest_path: Path,
    image_root: Path,
    expected_views: int,
    expected_frontal_images: int,
    expected_studies: int,
) -> pd.DataFrame:
    manifest = pd.read_csv(manifest_path)
    required = {"study_key", "dicom_path"}
    missing = sorted(required - set(manifest.columns))
    if missing:
        raise ValueError(f"Manifest is missing columns: {missing}")
    if len(manifest) != expected_views:
        raise RuntimeError(
            f"Expected {expected_views} validation views, found {len(manifest)}"
        )
    if manifest["dicom_path"].duplicated().any():
        raise RuntimeError("Validation manifest contains duplicate image paths")

    frontal = manifest.loc[
        manifest["dicom_path"].astype(str).str.contains(
            r"_frontal\.(?:jpg|jpeg|png)$",
            case=False,
            regex=True,
            na=False,
        )
    ].copy()
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
            f"Expected {expected_studies} studies with frontal images, "
            f"found {frontal['study_key'].nunique()}"
        )
    frontal["image_path"] = frontal["dicom_path"].map(
        lambda value: str((image_root / str(value)).resolve())
    )
    missing_images = [
        path for path in frontal["image_path"] if not Path(path).is_file()
    ]
    if missing_images:
        raise FileNotFoundError(
            f"Missing {len(missing_images)} validation frontal images; "
            f"first missing: {missing_images[0]}"
        )
    return frontal


def encode_prompts(
    *,
    policy: dict[str, Any],
    tokenizer: Any,
    text_model: Any,
    device: torch.device,
) -> torch.Tensor:
    prompt_texts = [
        policy["prompts"][label][polarity]
        for label in LABELS
        for polarity in ("positive", "negative")
    ]
    tokens = tokenizer(
        prompt_texts,
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
    if tuple(embeddings.shape) != (len(LABELS) * 2, 128):
        raise RuntimeError(
            "Expected text embedding shape (10, 128), "
            f"found {tuple(embeddings.shape)}"
        )
    if not torch.isfinite(embeddings).all():
        raise RuntimeError("Text embeddings contain non-finite values")
    norms = torch.linalg.vector_norm(embeddings, dim=1)
    if not torch.allclose(norms, torch.ones_like(norms), atol=1e-5):
        raise RuntimeError(
            f"Text embeddings are not L2-normalized: {norms.tolist()}"
        )
    return embeddings.reshape(len(LABELS), 2, 128)


def score_images(
    *,
    frontal: pd.DataFrame,
    image_model: Any,
    text_embeddings: torch.Tensor,
    transform: Any,
    device: torch.device,
    batch_size: int,
) -> pd.DataFrame:
    if batch_size <= 0:
        raise ValueError("--batch-size must be positive")
    output_frames: list[pd.DataFrame] = []
    flattened_text = text_embeddings.reshape(len(LABELS) * 2, 128)

    for start in range(0, len(frontal), batch_size):
        stop = min(start + batch_size, len(frontal))
        batch = frontal.iloc[start:stop].reset_index(drop=True)
        tensors: list[torch.Tensor] = []
        for image_path in batch["image_path"]:
            with Image.open(image_path) as image:
                tensors.append(transform(image.convert("L")))
        image_tensor = torch.stack(tensors).to(device)
        if tuple(image_tensor.shape[1:]) != (3, 480, 480):
            raise RuntimeError(
                "Expected transformed image shape (3, 480, 480), "
                f"found {tuple(image_tensor.shape[1:])}"
            )

        with torch.inference_mode():
            model_output = image_model(image_tensor)
            image_embeddings = F.normalize(
                model_output.projected_global_embedding, dim=1
            )
            similarities = image_embeddings @ flattened_text.T
            similarities = similarities.reshape(len(batch), len(LABELS), 2)
            margins = similarities[:, :, 0] - similarities[:, :, 1]

        if tuple(image_embeddings.shape) != (len(batch), 128):
            raise RuntimeError(
                f"Unexpected image embedding shape: {image_embeddings.shape}"
            )
        if not torch.isfinite(image_embeddings).all():
            raise RuntimeError("Image embeddings contain non-finite values")
        norms = torch.linalg.vector_norm(image_embeddings, dim=1)
        if not torch.allclose(norms, torch.ones_like(norms), atol=1e-5):
            raise RuntimeError("Image embeddings are not L2-normalized")
        if not torch.isfinite(similarities).all() or not torch.isfinite(
            margins
        ).all():
            raise RuntimeError("Non-finite BioViL score detected")

        similarity_values = similarities.detach().cpu().numpy()
        margin_values = margins.detach().cpu().numpy()
        output = pd.DataFrame(
            {
                "model_name": MODEL_NAME,
                "policy_version": POLICY_VERSION,
                "study_key": batch["study_key"].astype(str),
                "dicom_path": batch["dicom_path"].astype(str),
                "image_path": batch["image_path"].astype(str),
            }
        )
        for label_index, label in enumerate(LABELS):
            output[positive_column(label)] = similarity_values[:, label_index, 0]
            output[negative_column(label)] = similarity_values[:, label_index, 1]
            output[raw_column(label)] = margin_values[:, label_index]
        output_frames.append(output)
        print(f"Processed {stop}/{len(frontal)} frontal images", flush=True)

        del (
            image_tensor,
            model_output,
            image_embeddings,
            similarities,
            margins,
        )
        gc.collect()
        if device.type == "cuda":
            torch.cuda.empty_cache()

    scores = pd.concat(output_frames, ignore_index=True)
    if len(scores) != len(frontal):
        raise RuntimeError("Image-score row count changed during inference")
    return scores


def aggregate_studies(image_scores: pd.DataFrame) -> pd.DataFrame:
    score_columns = [
        column
        for label in LABELS
        for column in (
            positive_column(label),
            negative_column(label),
            raw_column(label),
        )
    ]
    grouped = image_scores.groupby("study_key", sort=True, as_index=False)
    study_scores = grouped[score_columns].mean()
    view_counts = grouped.size().rename(columns={"size": "frontal_view_count"})
    view_paths = grouped["dicom_path"].agg(
        lambda values: json.dumps(list(values), separators=(",", ":"))
    ).rename(columns={"dicom_path": "frontal_dicom_paths"})
    study_scores = view_counts.merge(
        study_scores, on="study_key", validate="one_to_one"
    )
    study_scores = study_scores.merge(
        view_paths, on="study_key", validate="one_to_one"
    )
    study_scores.insert(0, "policy_version", POLICY_VERSION)
    study_scores.insert(0, "model_name", MODEL_NAME)

    for label in LABELS:
        reconstructed = (
            study_scores[positive_column(label)]
            - study_scores[negative_column(label)]
        )
        if not np.allclose(
            reconstructed,
            study_scores[raw_column(label)],
            rtol=0.0,
            atol=1e-6,
        ):
            raise RuntimeError(
                f"Study-level margin identity failed for {label}"
            )
    return study_scores


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
        "image_scores": output_dir / "validation_image_scores.csv",
        "raw_scores": output_dir / "validation_raw_scores.csv",
        "run_config": output_dir / "validation_inference_run_config.json",
    }
    existing = [path for path in output_paths.values() if path.exists()]
    if existing:
        formatted = "\n".join(str(path) for path in existing)
        raise FileExistsError(
            "Refusing to overwrite existing validation inference outputs:\n"
            + formatted
        )

    policy_path = resolve_file(args.policy, "Exp20 prompt policy")
    model_dir = resolve_directory(args.model_dir, "CXR-BERT model directory")
    image_checkpoint = resolve_file(
        args.image_checkpoint, "BioViL image checkpoint"
    )
    text_checkpoint = resolve_file(
        model_dir / "pytorch_model.bin", "CXR-BERT checkpoint"
    )
    hi_ml_root = resolve_directory(args.hi_ml_root, "Microsoft HI-ML repository")
    hi_ml_source = resolve_directory(args.hi_ml_source, "HI-ML Python source")
    manifest_path = resolve_file(args.manifest, "validation manifest")
    image_root = resolve_directory(args.image_root, "validation image root")
    script_path = Path(__file__).resolve()
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(f"Requested {device}, but CUDA is unavailable")

    print("=== VERIFYING EXP20 VALIDATION INPUTS ===")
    policy, policy_hash = load_policy(policy_path)
    image_checkpoint_hash = verify_hash(
        image_checkpoint,
        EXPECTED_IMAGE_CHECKPOINT_SHA256,
        "BioViL image checkpoint",
    )
    text_checkpoint_hash = verify_hash(
        text_checkpoint,
        EXPECTED_TEXT_CHECKPOINT_SHA256,
        "CXR-BERT checkpoint",
    )
    manifest_hash = verify_hash(
        manifest_path,
        EXPECTED_MANIFEST_SHA256,
        "Validation manifest",
    )
    hi_ml_revision = git_output(hi_ml_root, "rev-parse", "HEAD")
    hi_ml_status = git_output(hi_ml_root, "status", "--short")
    if hi_ml_revision != EXPECTED_HIML_REVISION:
        raise RuntimeError(
            f"Expected HI-ML revision {EXPECTED_HIML_REVISION}, "
            f"found {hi_ml_revision}"
        )
    if hi_ml_status:
        raise RuntimeError(
            "Microsoft HI-ML repository has uncommitted changes:\n"
            + hi_ml_status
        )

    frontal = prepare_manifest(
        manifest_path,
        image_root,
        args.expected_views,
        args.expected_frontal_images,
        args.expected_studies,
    )
    print("Prompt-policy SHA-256:", policy_hash)
    print("Manifest rows:", args.expected_views)
    print("Frontal images:", len(frontal))
    print("Studies:", frontal["study_key"].nunique())
    print(
        "Studies with multiple frontal views:",
        int((frontal.groupby("study_key").size() > 1).sum()),
    )
    print("Ground truth read:", False)
    print("Device:", device)

    (
        create_transform,
        ImageModel,
        ImageEncoderType,
        CXRBertConfig,
        CXRBertTokenizer,
        CXRBertModel,
    ) = load_biovil_classes(hi_ml_source)

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
    text_embeddings = encode_prompts(
        policy=policy,
        tokenizer=tokenizer,
        text_model=text_model,
        device=device,
    )
    transform = create_transform(resize=512, center_crop_size=480)

    print("\n=== RUNNING VALIDATION INFERENCE ===", flush=True)
    image_scores = score_images(
        frontal=frontal,
        image_model=image_model,
        text_embeddings=text_embeddings,
        transform=transform,
        device=device,
        batch_size=args.batch_size,
    )
    study_scores = aggregate_studies(image_scores)
    if len(study_scores) != args.expected_studies:
        raise RuntimeError(
            f"Expected {args.expected_studies} study rows, "
            f"found {len(study_scores)}"
        )
    if not np.isfinite(
        study_scores[
            [raw_column(label) for label in LABELS]
        ].to_numpy(dtype=float)
    ).all():
        raise RuntimeError("Study scores contain non-finite values")
    multi_view_count = int((study_scores["frontal_view_count"] > 1).sum())
    if multi_view_count != 2:
        raise RuntimeError(
            f"Expected 2 multi-frontal validation studies, "
            f"found {multi_view_count}"
        )

    if sha256(policy_path) != policy_hash:
        raise RuntimeError("Prompt policy changed during validation inference")
    for path in output_paths.values():
        if path.exists():
            raise FileExistsError(f"Output appeared during inference: {path}")

    write_csv_atomic(image_scores, output_paths["image_scores"])
    write_csv_atomic(study_scores, output_paths["raw_scores"])
    output_hashes = {
        "validation_image_scores.csv": sha256(output_paths["image_scores"]),
        "validation_raw_scores.csv": sha256(output_paths["raw_scores"]),
    }
    auxiliary_model_files = [
        "config.json",
        "configuration_cxrbert.py",
        "modeling_cxrbert.py",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "vocab.txt",
    ]
    model_file_hashes = {
        name: sha256(resolve_file(model_dir / name, name))
        for name in auxiliary_model_files
    }
    run_config = {
        "experiment_id": "exp20",
        "model_name": MODEL_NAME,
        "policy_version": POLICY_VERSION,
        "prompt_policy_path": str(policy_path),
        "prompt_policy_sha256": policy_hash,
        "script_path": str(script_path),
        "script_sha256": sha256(script_path),
        "ground_truth_read": False,
        "split": "competition_validation",
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_hash,
        "image_root": str(image_root),
        "manifest_rows": args.expected_views,
        "frontal_image_count": len(image_scores),
        "study_count": len(study_scores),
        "multi_frontal_study_count": multi_view_count,
        "labels": list(LABELS),
        "prompts": policy["prompts"],
        "image_score": "positive_similarity - negative_similarity",
        "study_aggregation": "mean_of_frontal_image_continuous_scores",
        "normalization_applied": False,
        "thresholds_applied": False,
        "image_preprocessing": {
            "transform": "official_hi_ml_inference_transform",
            "resize": 512,
            "center_crop_size": 480,
            "input_mode": "grayscale_converted_by_official_transform",
        },
        "model": {
            "image_checkpoint": str(image_checkpoint),
            "image_checkpoint_sha256": image_checkpoint_hash,
            "text_checkpoint": str(text_checkpoint),
            "text_checkpoint_sha256": text_checkpoint_hash,
            "model_file_sha256": model_file_hashes,
            "hi_ml_root": str(hi_ml_root),
            "hi_ml_revision": hi_ml_revision,
            "hi_ml_working_tree_clean": True,
            "tokenizer_class": "CXRBertTokenizer",
            "embedding_dimension": 128,
        },
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
            "cuda_available": torch.cuda.is_available(),
            "cuda_runtime": torch.version.cuda,
            "gpu_name": (
                torch.cuda.get_device_name(device)
                if device.type == "cuda"
                else None
            ),
        },
        "outputs": {
            "validation_image_scores": str(output_paths["image_scores"]),
            "validation_raw_scores": str(output_paths["raw_scores"]),
            "sha256": output_hashes,
        },
    }
    write_json_atomic(run_config, output_paths["run_config"])

    print("\n=== VALIDATION INFERENCE COMPLETE ===")
    print("Image rows:", len(image_scores))
    print("Study rows:", len(study_scores))
    print("Studies with multiple frontal views:", multi_view_count)
    print("Saved:", output_paths["image_scores"])
    print("SHA-256:", output_hashes["validation_image_scores.csv"])
    print("Saved:", output_paths["raw_scores"])
    print("SHA-256:", output_hashes["validation_raw_scores.csv"])
    print("Saved:", output_paths["run_config"])
    print("Prompt policy unchanged:", sha256(policy_path) == policy_hash)
    print("Ground truth read:", False)
    print("STEP 4 VALIDATION INFERENCE SUCCEEDED")


if __name__ == "__main__":
    main()
