"""Run a read-only, single-image smoke test for the Exp20 BioViL policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

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
DEFAULT_POLICY = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp20_biovil_native_zero_shot_comparison"
    / "prompt_policy.json"
)
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
EXPECTED_LABELS = (
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Load one validation image and all frozen Exp20 prompts, then "
            "verify BioViL embeddings and positive-negative margins."
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
    parser.add_argument(
        "--study-key",
        default="patient64541/study1",
        help="Validation study used for the read-only smoke test.",
    )
    parser.add_argument(
        "--device",
        default="cuda:0" if torch.cuda.is_available() else "cpu",
    )
    parser.add_argument(
        "--repeat-tolerance",
        type=float,
        default=1e-6,
        help="Maximum embedding difference allowed across repeated forwards.",
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
    print(f"{description} SHA-256: {observed}")
    return observed


def git_output(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def verify_source(repository: Path) -> None:
    revision = git_output(repository, "rev-parse", "HEAD")
    status = git_output(repository, "status", "--short")
    print("Microsoft HI-ML revision:", revision)
    print("Microsoft HI-ML working tree clean:", not bool(status))
    if revision != EXPECTED_HIML_REVISION:
        raise RuntimeError(
            f"Expected HI-ML revision {EXPECTED_HIML_REVISION}, "
            f"found {revision}"
        )
    if status:
        raise RuntimeError(
            "Microsoft HI-ML repository has uncommitted changes:\n" + status
        )


def load_policy(path: Path) -> tuple[dict[str, Any], str]:
    checksum_path = resolve_file(
        path.with_name("prompt_policy.sha256"), "prompt-policy checksum"
    )
    fields = checksum_path.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[1] != path.name:
        raise RuntimeError(f"Malformed checksum file: {checksum_path}")
    expected_hash = fields[0]
    observed_hash = sha256(path)
    print("Prompt-policy SHA-256:", observed_hash)
    print("Prompt-policy checksum matches:", observed_hash == expected_hash)
    if observed_hash != expected_hash:
        raise RuntimeError("Exp20 prompt-policy checksum mismatch")

    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("policy_version") != POLICY_VERSION:
        raise RuntimeError(
            f"Expected policy version {POLICY_VERSION!r}, "
            f"found {policy.get('policy_version')!r}"
        )
    if tuple(policy.get("labels", ())) != EXPECTED_LABELS:
        raise RuntimeError("Exp20 prompt-policy labels or order changed")
    prompts = policy.get("prompts")
    if not isinstance(prompts, dict) or tuple(prompts) != EXPECTED_LABELS:
        raise RuntimeError("Exp20 prompt mapping is invalid")
    for label in EXPECTED_LABELS:
        pair = prompts[label]
        if set(pair) != {"positive", "negative"}:
            raise RuntimeError(f"Invalid positive-negative pair for {label}")
        if not all(isinstance(pair[key], str) for key in pair):
            raise RuntimeError(f"Non-string prompt found for {label}")
    expected_formula = "positive_similarity - negative_similarity"
    observed_formula = policy.get("inference", {}).get("image_raw_score")
    if observed_formula != expected_formula:
        raise RuntimeError(
            f"Expected score formula {expected_formula!r}, "
            f"found {observed_formula!r}"
        )
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


def resolve_smoke_image(
    manifest_path: Path, image_root: Path, study_key: str
) -> tuple[str, Path]:
    manifest = pd.read_csv(manifest_path)
    required = {"study_key", "dicom_path"}
    missing = sorted(required - set(manifest.columns))
    if missing:
        raise ValueError(f"Manifest is missing columns: {missing}")
    rows = manifest.loc[
        manifest["study_key"].astype(str).eq(study_key)
        & manifest["dicom_path"].astype(str).str.contains(
            r"_frontal\.(?:jpg|jpeg|png)$",
            case=False,
            regex=True,
            na=False,
        )
    ].copy()
    rows = rows.sort_values("dicom_path", kind="stable")
    if rows.empty:
        raise RuntimeError(
            f"No frontal validation image found for study {study_key!r}"
        )
    dicom_path = str(rows.iloc[0]["dicom_path"])
    image_path = resolve_file(
        image_root / dicom_path,
        f"frontal image for study {study_key}",
    )
    return dicom_path, image_path


def validate_normalized(
    embeddings: torch.Tensor, description: str, tolerance: float = 1e-5
) -> torch.Tensor:
    if not torch.isfinite(embeddings).all():
        raise RuntimeError(f"{description} contains non-finite values")
    norms = torch.linalg.vector_norm(embeddings, dim=1)
    if not torch.allclose(norms, torch.ones_like(norms), atol=tolerance):
        raise RuntimeError(
            f"{description} is not L2-normalized; norms={norms.tolist()}"
        )
    return norms


def main() -> None:
    args = build_parser().parse_args()
    torch.manual_seed(0)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(0)

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
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(f"Requested {device}, but CUDA is unavailable")

    print("=== VERIFYING FROZEN INPUTS ===")
    policy, policy_hash_before = load_policy(policy_path)
    verify_hash(
        image_checkpoint,
        EXPECTED_IMAGE_CHECKPOINT_SHA256,
        "BioViL image checkpoint",
    )
    verify_hash(
        text_checkpoint,
        EXPECTED_TEXT_CHECKPOINT_SHA256,
        "CXR-BERT checkpoint",
    )
    verify_hash(
        manifest_path,
        EXPECTED_MANIFEST_SHA256,
        "Validation manifest",
    )
    verify_source(hi_ml_root)

    dicom_path, image_path = resolve_smoke_image(
        manifest_path, image_root, args.study_key
    )
    print("Study:", args.study_key)
    print("Manifest image:", dicom_path)
    print("Resolved image:", image_path)
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
    print(
        "Image parameters:",
        f"{sum(parameter.numel() for parameter in image_model.parameters()):,}",
    )
    print(
        "Text parameters:",
        f"{sum(parameter.numel() for parameter in text_model.parameters()):,}",
    )

    transform = create_transform(resize=512, center_crop_size=480)
    with Image.open(image_path) as image:
        image_tensor = transform(image.convert("L")).unsqueeze(0).to(device)
    if tuple(image_tensor.shape) != (1, 3, 480, 480):
        raise RuntimeError(
            "Expected image tensor shape (1, 3, 480, 480), "
            f"found {tuple(image_tensor.shape)}"
        )

    prompt_texts: list[str] = []
    prompt_index: list[tuple[str, str]] = []
    for label in EXPECTED_LABELS:
        for polarity in ("positive", "negative"):
            prompt_texts.append(policy["prompts"][label][polarity])
            prompt_index.append((label, polarity))
    tokens = tokenizer(
        prompt_texts,
        add_special_tokens=True,
        padding=True,
        return_tensors="pt",
    )
    tokens = {name: value.to(device) for name, value in tokens.items()}

    print("\n=== ENCODING IMAGE AND PROMPTS ===", flush=True)
    with torch.inference_mode():
        first_output = image_model(image_tensor)
        second_output = image_model(image_tensor)
        first_image_embedding = F.normalize(
            first_output.projected_global_embedding, dim=1
        )
        second_image_embedding = F.normalize(
            second_output.projected_global_embedding, dim=1
        )
        text_embeddings = text_model.get_projected_text_embeddings(
            input_ids=tokens["input_ids"],
            attention_mask=tokens["attention_mask"],
            normalize_embeddings=True,
        )

    if tuple(first_image_embedding.shape) != (1, 128):
        raise RuntimeError(
            f"Unexpected image embedding shape: {first_image_embedding.shape}"
        )
    if tuple(text_embeddings.shape) != (10, 128):
        raise RuntimeError(
            f"Unexpected text embedding shape: {text_embeddings.shape}"
        )
    image_norms = validate_normalized(
        first_image_embedding, "Image embedding"
    )
    text_norms = validate_normalized(text_embeddings, "Text embeddings")
    repeat_difference = float(
        torch.max(
            torch.abs(first_image_embedding - second_image_embedding)
        ).item()
    )
    if repeat_difference > args.repeat_tolerance:
        raise RuntimeError(
            "Repeated image forwards were not deterministic enough: "
            f"difference={repeat_difference}, "
            f"tolerance={args.repeat_tolerance}"
        )

    similarities = (first_image_embedding @ text_embeddings.T).reshape(5, 2)
    margins = similarities[:, 0] - similarities[:, 1]
    if not torch.isfinite(similarities).all() or not torch.isfinite(margins).all():
        raise RuntimeError("Non-finite similarity or margin detected")

    print("Image tensor shape:", tuple(image_tensor.shape))
    print("Image embedding shape:", tuple(first_image_embedding.shape))
    print("Text embedding shape:", tuple(text_embeddings.shape))
    print("Image embedding norm:", float(image_norms[0].item()))
    print(
        "Text norm range:",
        float(text_norms.min().item()),
        float(text_norms.max().item()),
    )
    print("Repeated-forward maximum difference:", repeat_difference)

    print("\n=== POSITIVE-NEGATIVE SCORES ===")
    print(
        f"{'Label':<20} {'Positive':>12} {'Negative':>12} {'Margin':>12}"
    )
    for index, label in enumerate(EXPECTED_LABELS):
        positive = float(similarities[index, 0].item())
        negative = float(similarities[index, 1].item())
        margin = float(margins[index].item())
        print(f"{label:<20} {positive:>12.6f} {negative:>12.6f} {margin:>12.6f}")

    policy_hash_after = sha256(policy_path)
    if policy_hash_after != policy_hash_before:
        raise RuntimeError("Prompt policy changed during the smoke test")
    print("\nPrompt policy unchanged:", True)
    if device.type == "cuda":
        print(
            "GPU allocated:",
            f"{torch.cuda.memory_allocated(device) / (1024 ** 3):.3f} GiB",
        )
    print("No experiment outputs were written.")
    print("STEP 3 SMOKE TEST SUCCEEDED")


if __name__ == "__main__":
    main()
