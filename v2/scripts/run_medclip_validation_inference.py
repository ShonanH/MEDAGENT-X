"""Generate validation-only, study-level MedCLIP zero-shot scores.

The command deliberately does not accept the held-out test manifest or test
labels.  It scores every eligible frontal validation image with MedCLIP's
official CheXpert prompt classifier, averages continuous image scores within a
study, and z-normalizes those study scores using validation data only.  Run
``tune_gloria_validation_thresholds.py`` afterwards with ``--model-name`` set
to ``medclip_vit_zero_shot`` to create the frozen threshold policy.
"""

from __future__ import annotations

import argparse
import gc
import importlib.metadata
import json
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
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
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "v2" / "experiments" / "medclip_zero_shot_comparison"

LABELS: tuple[str, ...] = (
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
)
MODEL_NAME = "medclip_vit_zero_shot"
PROMPT_COUNT = 10


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Score the locked CheXpert validation cohort with the official "
            "MedCLIP CheXpert prompt classifier."
        )
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--expected-views", type=int, default=234)
    parser.add_argument("--expected-frontal-images", type=int, default=202)
    parser.add_argument("--expected-studies", type=int, default=200)
    parser.add_argument("--prompt-count", type=int, default=PROMPT_COUNT)
    parser.add_argument("--seed", type=int, default=20261019)
    parser.add_argument(
        "--device", default="cuda:0" if torch.cuda.is_available() else "cpu"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace existing output artifacts."
    )
    return parser


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


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def raw_column(label: str) -> str:
    return f"raw_{label}"


def prepare_frontal_manifest(
    manifest_path: Path,
    image_root: Path,
    *,
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
        raise RuntimeError(f"Expected {expected_views} views, found {len(manifest)}")
    if manifest["dicom_path"].duplicated().any():
        raise ValueError("Manifest contains duplicate image paths")

    frontal = manifest.loc[
        manifest["dicom_path"].astype(str).str.contains(
            r"_frontal\.(?:jpg|jpeg|png)$", case=False, regex=True, na=False
        )
    ].copy()
    frontal = frontal.sort_values(["study_key", "dicom_path"], kind="stable").reset_index(
        drop=True
    )
    if len(frontal) != expected_frontal_images:
        raise RuntimeError(
            f"Expected {expected_frontal_images} frontal images, found {len(frontal)}"
        )
    if frontal["study_key"].nunique() != expected_studies:
        raise RuntimeError(
            f"Expected {expected_studies} frontal studies, found "
            f"{frontal['study_key'].nunique()}"
        )
    frontal["image_path"] = frontal["dicom_path"].map(
        lambda value: str((image_root / str(value)).resolve())
    )
    missing_images = [path for path in frontal["image_path"] if not Path(path).is_file()]
    if missing_images:
        raise FileNotFoundError(
            f"Missing {len(missing_images)} images; first missing: {missing_images[0]}"
        )
    return frontal


def load_medclip(device: torch.device, prompt_count: int) -> tuple[Any, Any, Any, Any]:
    """Load the official MedCLIP ViT model and its CheXpert prompt classifier."""
    try:
        from medclip import (  # type: ignore[import-not-found]
            MedCLIPModel,
            MedCLIPProcessor,
            MedCLIPVisionModelViT,
            PromptClassifier,
        )
        from medclip import constants as medclip_constants  # type: ignore[import-not-found]
        from medclip.prompts import (  # type: ignore[import-not-found]
            generate_chexpert_class_prompts,
            process_class_prompts,
        )
    except ImportError as exc:
        raise RuntimeError(
            "MedCLIP is not installed. Install the official package in this "
            "baseline's isolated environment (for example: pip install medclip)."
        ) from exc

    model = MedCLIPModel(vision_cls=MedCLIPVisionModelViT)
    try:
        model.from_pretrained()
    except RuntimeError as exc:
        # Older MedCLIP releases save this legacy, non-learned BERT buffer.
        # It is absent in newer Transformers models, producing the exact
        # ``Unexpected key(s) ... position_ids`` error. Do not use a blanket
        # ``strict=False`` fallback: all learned weights must still match.
        legacy_key = "text_model.model.embeddings.position_ids"
        if legacy_key not in str(exc):
            raise
        checkpoint_path = (
            Path.cwd()
            / "pretrained"
            / "medclip-vit"
            / medclip_constants.WEIGHTS_NAME
        )
        if not checkpoint_path.is_file():
            raise RuntimeError(
                "MedCLIP downloaded a checkpoint but it was not found at "
                f"{checkpoint_path}. Install MedCLIP from its GitHub source "
                "or pass a compatible environment."
            ) from exc
        state_dict = torch.load(checkpoint_path, map_location="cpu")
        if state_dict.pop(legacy_key, None) is None:
            raise RuntimeError(
                "MedCLIP failed to load for a reason other than its known "
                "legacy position_ids checkpoint buffer."
            ) from exc
        model.load_state_dict(state_dict, strict=True)
    model = model.eval().to(device)
    classifier = PromptClassifier(model, ensemble=True).eval().to(device)
    processor = MedCLIPProcessor()
    prompts = generate_chexpert_class_prompts(n=prompt_count)
    prompt_inputs = process_class_prompts(prompts)
    return classifier, processor, prompt_inputs, prompts


def _move_to_device(value: Any, device: torch.device) -> Any:
    if isinstance(value, torch.Tensor):
        return value.to(device)
    if isinstance(value, dict):
        return {key: _move_to_device(item, device) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return type(value)(_move_to_device(item, device) for item in value)
    return value


def score_images(
    *,
    classifier: Any,
    processor: Any,
    prompt_inputs: Any,
    frontal: pd.DataFrame,
    device: torch.device,
    batch_size: int,
) -> pd.DataFrame:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required to load CXR images. Install it in the isolated "
            "MedCLIP environment."
        ) from exc
    batches: list[pd.DataFrame] = []
    for start in range(0, len(frontal), batch_size):
        stop = min(start + batch_size, len(frontal))
        batch = frontal.iloc[start:stop].reset_index(drop=True)
        images: list[Any] = []
        try:
            for image_path in batch["image_path"]:
                with Image.open(image_path) as image:
                    images.append(image.convert("RGB"))
            inputs = _move_to_device(
                processor(images=images, return_tensors="pt"), device
            )
            inputs["prompt_inputs"] = _move_to_device(prompt_inputs, device)
            with torch.inference_mode():
                output = classifier(**inputs)
        finally:
            for image in images:
                image.close()

        if not isinstance(output, dict) or "logits" not in output:
            raise RuntimeError("MedCLIP PromptClassifier did not return logits")
        class_names = list(output.get("class_names", []))
        if set(class_names) != set(LABELS) or len(class_names) != len(LABELS):
            raise RuntimeError(
                "Unexpected MedCLIP class names. Expected "
                f"{list(LABELS)}, received {class_names}"
            )
        logits = output["logits"]
        if not isinstance(logits, torch.Tensor) or tuple(logits.shape) != (
            len(batch),
            len(LABELS),
        ):
            raise RuntimeError(
                "Unexpected MedCLIP logits shape: "
                f"{getattr(logits, 'shape', None)}"
            )
        ordered = logits.detach().float().cpu().numpy()[:, [class_names.index(label) for label in LABELS]]
        if not np.isfinite(ordered).all():
            raise RuntimeError("MedCLIP produced non-finite image scores")
        score_frame = pd.DataFrame(
            {raw_column(label): ordered[:, index] for index, label in enumerate(LABELS)}
        )
        score_frame.insert(0, "image_path", batch["image_path"])
        score_frame.insert(0, "dicom_path", batch["dicom_path"].astype(str))
        score_frame.insert(0, "study_key", batch["study_key"].astype(str))
        score_frame.insert(0, "model_name", MODEL_NAME)
        batches.append(score_frame)
        print(f"Processed {stop}/{len(frontal)} frontal images", flush=True)
        del inputs, output
        gc.collect()
        if device.type == "cuda":
            torch.cuda.empty_cache()

    scores = pd.concat(batches, ignore_index=True)
    if scores[[raw_column(label) for label in LABELS]].isna().any().any():
        raise RuntimeError("MedCLIP produced missing image scores")
    return scores


def aggregate_and_normalize(image_scores: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    raw_columns = [raw_column(label) for label in LABELS]
    grouped = image_scores.groupby("study_key", sort=True, as_index=False)
    studies = grouped[raw_columns].mean()
    view_counts = grouped.size().rename(columns={"size": "frontal_view_count"})
    view_paths = grouped["dicom_path"].agg(
        lambda values: json.dumps(list(values), separators=(",", ":"))
    ).rename(columns={"dicom_path": "frontal_dicom_paths"})
    studies = view_counts.merge(studies, on="study_key", validate="one_to_one")
    studies = studies.merge(view_paths, on="study_key", validate="one_to_one")

    normalization: dict[str, dict[str, float]] = {}
    for label in LABELS:
        raw = studies[raw_column(label)].to_numpy(dtype=float)
        mean = float(np.mean(raw))
        std = float(np.std(raw, ddof=0))
        if not np.isfinite(std) or std <= 0:
            raise RuntimeError(f"Invalid validation standard deviation for {label}: {std}")
        studies[label] = (raw - mean) / std
        normalization[label] = {
            "raw_mean": mean,
            "raw_std": std,
            "method": "zscore_population",
        }
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
    ], normalization


def main() -> None:
    args = build_parser().parse_args()
    if args.batch_size <= 0 or args.prompt_count <= 0:
        raise ValueError("--batch-size and --prompt-count must be positive")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True

    manifest = resolve_file(args.manifest, "validation manifest")
    image_root = resolve_directory(args.image_root, "validation image directory")
    output_dir = args.output_dir.expanduser().resolve()
    paths = {
        "image_scores": output_dir / "validation_image_scores.csv",
        "scores": output_dir / "validation_scores.csv",
        "run_config": output_dir / "validation_inference_run_config.json",
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing and not args.overwrite:
        raise FileExistsError(
            "Refusing to overwrite existing MedCLIP validation outputs:\n"
            + "\n".join(str(path) for path in existing)
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(f"Requested {device}, but CUDA is unavailable")
    frontal = prepare_frontal_manifest(
        manifest,
        image_root,
        expected_views=args.expected_views,
        expected_frontal_images=args.expected_frontal_images,
        expected_studies=args.expected_studies,
    )
    classifier, processor, prompt_inputs, prompts = load_medclip(device, args.prompt_count)
    image_scores = score_images(
        classifier=classifier,
        processor=processor,
        prompt_inputs=prompt_inputs,
        frontal=frontal,
        device=device,
        batch_size=args.batch_size,
    )
    study_scores, normalization = aggregate_and_normalize(image_scores)
    if len(study_scores) != args.expected_studies:
        raise RuntimeError(f"Expected {args.expected_studies} studies, found {len(study_scores)}")
    image_scores.to_csv(paths["image_scores"], index=False)
    study_scores.to_csv(paths["scores"], index=False)
    config = {
        "model_name": MODEL_NAME,
        "model_variant": "MedCLIP ViT official pretrained checkpoint",
        "score_definition": "official_MedCLIP_PromptClassifier_logits",
        "study_aggregation": "mean_of_frontal_image_continuous_scores",
        "normalization_source": "competition_validation_only",
        "manifest": str(manifest),
        "image_root": str(image_root),
        "labels": list(LABELS),
        "prompts": prompts,
        "prompt_count": args.prompt_count,
        "validation_normalization": normalization,
        "frontal_image_count": len(image_scores),
        "study_count": len(study_scores),
        "execution": {
            "device": str(device),
            "batch_size": args.batch_size,
            "seed": args.seed,
            "python": sys.version,
            "torch": torch.__version__,
            "medclip": package_version("medclip"),
            "cuda_runtime": torch.version.cuda,
            "gpu_name": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
        },
    }
    paths["run_config"].write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    for name, path in paths.items():
        print(f"Saved {name}: {path}")


if __name__ == "__main__":
    main()
