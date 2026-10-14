"""Run GLoRIA zero-shot inference on the CheXpert validation cohort.

Every frontal image is scored independently. When a study has more than one
frontal image, the label scores are averaged so the final output contains one
row per study. The image-level scores are retained as an audit artifact.
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


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GLORIA_ROOT = PROJECT_ROOT / "external" / "gloria"
DEFAULT_CHECKPOINT = (
    DEFAULT_GLORIA_ROOT / "pretrained" / "chexpert_resnet50.ckpt"
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
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "v2" / "experiments" / "gloria_zero_shot_comparison"
)

LABELS: tuple[str, ...] = (
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
)
MODEL_NAME = "gloria_resnet50_zero_shot"
PROMPT_SEED = 6


def _raw_column(label: str) -> str:
    return f"raw_{label}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Score CheXpert validation frontal images with GLoRIA and average "
            "multiple frontal views into one row per study."
        )
    )
    parser.add_argument("--gloria-root", type=Path, default=DEFAULT_GLORIA_ROOT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--expected-studies", type=int, default=200)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--seed", type=int, default=20260916)
    return parser


def _require_file(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Missing {description}: {resolved}")
    return resolved


def _load_gloria(gloria_root: Path) -> Any:
    root = gloria_root.expanduser().resolve()
    if not (root / "gloria" / "__init__.py").is_file():
        raise FileNotFoundError(f"GLoRIA source package not found under: {root}")
    sys.path.insert(0, str(root))
    try:
        import gloria  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError(
            "Unable to import the local GLoRIA package. Confirm that the "
            "Python-3.12 compatibility patches have been applied."
        ) from exc
    return gloria


def _prepare_frontal_manifest(manifest_path: Path, image_root: Path) -> pd.DataFrame:
    frame = pd.read_csv(manifest_path)
    required = {"study_key", "dicom_path"}
    missing_columns = sorted(required - set(frame.columns))
    if missing_columns:
        raise ValueError(f"Manifest is missing columns: {missing_columns}")

    frontal_mask = frame["dicom_path"].astype(str).str.contains(
        r"_frontal\.(?:jpg|jpeg|png)$",
        case=False,
        regex=True,
        na=False,
    )
    frontal = frame.loc[frontal_mask].copy()
    frontal = frontal.sort_values(
        ["study_key", "dicom_path"], kind="stable"
    ).reset_index(drop=True)
    if frontal.empty:
        raise ValueError("Manifest contains no frontal JPG/PNG images")

    frontal["image_path"] = frontal["dicom_path"].map(
        lambda value: str((image_root / str(value)).resolve())
    )
    missing_images = [
        path for path in frontal["image_path"] if not Path(path).is_file()
    ]
    if missing_images:
        raise FileNotFoundError(
            f"Missing {len(missing_images)} images; first missing: {missing_images[0]}"
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
                # Match GLoRIA's official zero-shot implementation: use the
                # strongest matching prompt for each image and class.
                raw_by_label[_raw_column(label)] = similarities.max(axis=1)

        missing_labels = [
            label for label in LABELS if _raw_column(label) not in raw_by_label
        ]
        if missing_labels:
            raise RuntimeError(f"GLoRIA output is missing labels: {missing_labels}")

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
    if result.loc[:, raw_columns].isna().any().any():
        raise RuntimeError("GLoRIA produced missing scores")
    # This image-level normalization is saved for audit only. The final
    # comparison uses study-level normalization after multi-view averaging.
    normalized = gloria.utils.normalize(result.loc[:, raw_columns].to_numpy())
    result.loc[:, list(LABELS)] = normalized
    return result


def _aggregate_studies(gloria: Any, image_scores: pd.DataFrame) -> pd.DataFrame:
    grouped = image_scores.groupby("study_key", sort=True, as_index=False)
    raw_columns = [_raw_column(label) for label in LABELS]
    study_scores = grouped[raw_columns].mean()
    normalized = gloria.utils.normalize(
        study_scores.loc[:, raw_columns].to_numpy()
    )
    study_scores.loc[:, list(LABELS)] = normalized
    view_counts = grouped.size().rename(columns={"size": "frontal_view_count"})
    view_paths = grouped["dicom_path"].agg(
        lambda values: json.dumps(list(values), separators=(",", ":"))
    ).rename(columns={"dicom_path": "frontal_dicom_paths"})

    study_scores = view_counts.merge(study_scores, on="study_key", validate="one_to_one")
    study_scores = study_scores.merge(view_paths, on="study_key", validate="one_to_one")
    study_scores.insert(0, "model_name", MODEL_NAME)
    ordered = [
        "model_name",
        "study_key",
        "frontal_view_count",
        "frontal_dicom_paths",
        *LABELS,
        *raw_columns,
    ]
    return study_scores.loc[:, ordered]


def main() -> None:
    args = build_parser().parse_args()
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be positive")
    if args.expected_studies <= 0:
        raise ValueError("--expected-studies must be positive")

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    manifest_path = _require_file(args.manifest, "validation manifest")
    checkpoint_path = _require_file(args.checkpoint, "GLoRIA checkpoint")
    image_root = args.image_root.expanduser().resolve()
    if not image_root.is_dir():
        raise FileNotFoundError(f"Missing validation image directory: {image_root}")

    gloria = _load_gloria(args.gloria_root)
    frontal = _prepare_frontal_manifest(manifest_path, image_root)
    study_count = frontal["study_key"].nunique()
    print(f"Manifest rows: {len(pd.read_csv(manifest_path))}")
    print(f"Frontal image rows: {len(frontal)}")
    print(f"Unique studies: {study_count}")
    if study_count != args.expected_studies:
        raise RuntimeError(
            f"Expected {args.expected_studies} studies, found {study_count}"
        )

    print(f"Device: {args.device}")
    print("Loading GLoRIA checkpoint...", flush=True)
    model = gloria.load_gloria(name=str(checkpoint_path), device=args.device)
    model.eval()
    # Match the official package's fixed prompt sampling seed and make it
    # explicit so validation and test use exactly the same prompt set.
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
    study_scores = _aggregate_studies(gloria, image_scores)
    if len(study_scores) != args.expected_studies:
        raise RuntimeError(
            f"Expected {args.expected_studies} study rows, found {len(study_scores)}"
        )

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    image_output = output_dir / "validation_image_scores.csv"
    study_output = output_dir / "validation_scores.csv"
    image_scores.to_csv(image_output, index=False)
    study_scores.to_csv(study_output, index=False)

    multi_view = int((study_scores["frontal_view_count"] > 1).sum())
    print(f"Saved image scores: {image_output}")
    print(f"Saved study scores: {study_output}")
    print(f"Image rows: {len(image_scores)}")
    print(f"Study rows: {len(study_scores)}")
    print(f"Studies with multiple frontal views: {multi_view}")
    print(study_scores.loc[:, LABELS].describe().to_string())


if __name__ == "__main__":
    main()
