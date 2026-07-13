#!/usr/bin/env python3
"""
04_validate_dicom_preprocessing.py

Validate Workflow A DICOM preprocessing for downloaded CheXpert Plus cases.

This checks:
    downloaded DICOM
    -> DICOM-aware loading
    -> modality LUT
    -> MONOCHROME1 correction
    -> min-max normalization
    -> 3-channel ConvNeXt-ready tensor shape

All outputs go under:
    outputs/chexpert_plus/

python scripts/04_validate_dicom_preprocessing.py \
  --manifest-path data/processed/chexpert_plus/chexpert_plus_v2_manifest.csv \
  --dicom-root data/raw/chexpert_plus/dicom_train \
  --preview-limit 25
"""

import argparse
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.features.artifact_features import compute_artifact_features
from src.medagentx.helpers.dicom_loader import load_normalized_dicom_image


DEFAULT_500_MANIFEST = (
    PROJECT_ROOT / "data" / "processed" / "chexpert_plus_v2_manifest.csv"
)

DEFAULT_50_MANIFEST = (
    PROJECT_ROOT / "data" / "processed" / "chexpert_plus_50_study_manifest.csv"
)

DEFAULT_DICOM_ROOT = (
    PROJECT_ROOT / "data" / "raw" / "chexpert_plus" / "dicom_train"
)

OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "chexpert_plus"
PREVIEW_DIR = OUTPUT_ROOT / "dicom_preprocessing_preview"
METADATA_DIR = OUTPUT_ROOT / "dicom_preprocessing_metadata"
STATUS_PATH = OUTPUT_ROOT / "dicom_preprocessing_status.csv"


def default_manifest_path():
    if DEFAULT_500_MANIFEST.exists():
        return DEFAULT_500_MANIFEST

    return DEFAULT_50_MANIFEST


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate local CheXpert Plus DICOM preprocessing."
    )

    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=default_manifest_path(),
        help="CheXpert Plus study-level or image-level manifest CSV.",
    )

    parser.add_argument(
        "--dicom-root",
        type=Path,
        default=DEFAULT_DICOM_ROOT,
        help="Local root containing downloaded DICOM files.",
    )

    parser.add_argument(
        "--preview-limit",
        type=int,
        default=25,
        help="Maximum number of preview PNGs and metadata text files to write.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of DICOM files to validate.",
    )

    parser.add_argument(
        "--convnext-size",
        type=int,
        default=224,
        help="Square resize target for ConvNeXt-ready tensor validation.",
    )

    return parser.parse_args()


def clean_dicom_path(path):
    path = str(path).strip().replace("\\", "/").lstrip("./")

    if "/train/" in path:
        path = path.split("/train/", maxsplit=1)[1]

    for prefix in ("train/", "DICOM_train/", "dicom_train/"):
        if path.startswith(prefix):
            path = path[len(prefix):]

    return path

def split_manifest_dicom_paths(value):
    if pd.isna(value):
        return []

    paths = []

    for raw_path in str(value).split("|"):
        cleaned = clean_dicom_path(raw_path)

        if cleaned:
            paths.append(cleaned)

    return list(dict.fromkeys(paths))


def extract_manifest_dicom_paths(df):
    if "dicom_paths" in df.columns:
        paths = []

        for value in df["dicom_paths"]:
            paths.extend(split_manifest_dicom_paths(value))

        return list(dict.fromkeys(paths))

    for column in ("dicom_path", "path_to_dcm", "dicom_path_original"):
        if column in df.columns:
            paths = []

            for value in df[column]:
                paths.extend(split_manifest_dicom_paths(value))

            return list(dict.fromkeys(paths))

    raise ValueError(
        "Manifest must contain `dicom_paths`, `dicom_path`, "
        "`path_to_dcm`, or `dicom_path_original`."
    )


def safe_stem(dicom_path):
    return (
        dicom_path
        .replace("/", "_")
        .replace("\\", "_")
        .replace(".dcm", "")
        .replace(".", "_")
    )


def to_uint8(image):
    image = np.asarray(image, dtype=np.float32)
    image = np.clip(image, 0.0, 1.0)

    return (image * 255.0).round().astype(np.uint8)


def make_convnext_tensor(image, size):
    pil_image = Image.fromarray(to_uint8(image), mode="L")
    pil_image = pil_image.resize((size, size), resample=Image.BILINEAR)

    array = np.asarray(pil_image, dtype=np.float32) / 255.0
    tensor = np.stack([array, array, array], axis=0)

    return tensor


def write_preview(image, preview_path):
    preview_path.parent.mkdir(parents=True, exist_ok=True)

    Image.fromarray(to_uint8(image), mode="L").save(preview_path)


def write_metadata_summary(metadata_path, dicom_path, local_path, ds, image, tensor):
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "MEDAGENT-X CheXpert Plus DICOM Preprocessing Validation",
        "",
        f"Manifest DICOM path: {dicom_path}",
        f"Local DICOM path: {local_path}",
        "",
        "DICOM metadata",
        f"Rows: {getattr(ds, 'Rows', '')}",
        f"Columns: {getattr(ds, 'Columns', '')}",
        f"PhotometricInterpretation: {getattr(ds, 'PhotometricInterpretation', '')}",
        f"ViewPosition: {getattr(ds, 'ViewPosition', '')}",
        f"BitsStored: {getattr(ds, 'BitsStored', '')}",
        f"BitsAllocated: {getattr(ds, 'BitsAllocated', '')}",
        f"PixelRepresentation: {getattr(ds, 'PixelRepresentation', '')}",
        f"Modality: {getattr(ds, 'Modality', '')}",
        "",
        "Preprocessed image",
        f"normalized_shape: {tuple(image.shape)}",
        f"normalized_min: {float(np.min(image)):.6f}",
        f"normalized_max: {float(np.max(image)):.6f}",
        f"normalized_mean: {float(np.mean(image)):.6f}",
        f"normalized_std: {float(np.std(image)):.6f}",
        f"convnext_tensor_shape: {tuple(tensor.shape)}",
    ]

    metadata_path.write_text("\n".join(lines) + "\n")


def validate_one(dicom_path, local_path, args, preview_count):
    if not local_path.exists():
        return {
            "dicom_path": dicom_path,
            "local_path": str(local_path),
            "status": "missing_file",
            "error": "",
        }, preview_count

    try:
        with local_path.open("rb") as file_obj:
            image, ds = load_normalized_dicom_image(file_obj)

        tensor = make_convnext_tensor(image, args.convnext_size)
        artifact_features = compute_artifact_features(image)

        preview_path = ""
        metadata_path = ""

        if preview_count < args.preview_limit:
            stem = safe_stem(dicom_path)

            preview_path = PREVIEW_DIR / f"{stem}.png"
            metadata_path = METADATA_DIR / f"{stem}.txt"

            write_preview(image, preview_path)
            write_metadata_summary(
                metadata_path=metadata_path,
                dicom_path=dicom_path,
                local_path=local_path,
                ds=ds,
                image=image,
                tensor=tensor,
            )

            preview_count += 1

        record = {
            "dicom_path": dicom_path,
            "local_path": str(local_path),
            "status": "ok",
            "error": "",
            "preview_path": str(preview_path) if preview_path else "",
            "metadata_path": str(metadata_path) if metadata_path else "",
            "rows": getattr(ds, "Rows", None),
            "columns": getattr(ds, "Columns", None),
            "photometric": getattr(ds, "PhotometricInterpretation", None),
            "view_position": getattr(ds, "ViewPosition", None),
            "bits_stored": getattr(ds, "BitsStored", None),
            "bits_allocated": getattr(ds, "BitsAllocated", None),
            "pixel_representation": getattr(ds, "PixelRepresentation", None),
            "modality": getattr(ds, "Modality", None),
            "normalized_shape": str(tuple(image.shape)),
            "convnext_tensor_shape": str(tuple(tensor.shape)),
        }

        record.update(artifact_features)

        return record, preview_count

    except Exception as error:
        return {
            "dicom_path": dicom_path,
            "local_path": str(local_path),
            "status": "preprocess_failed",
            "error": f"{type(error).__name__}: {error}",
        }, preview_count


def main():
    args = parse_args()

    if not args.manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {args.manifest_path}")

    df = pd.read_csv(args.manifest_path)
    dicom_paths = extract_manifest_dicom_paths(df)

    if args.limit is not None:
        dicom_paths = dicom_paths[:args.limit]

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Manifest: {args.manifest_path}")
    print(f"DICOM root: {args.dicom_root}")
    print(f"Output root: {OUTPUT_ROOT}")
    print(f"DICOM files to validate: {len(dicom_paths)}")

    records = []
    preview_count = 0

    for dicom_path in tqdm(dicom_paths, desc="Validating DICOM preprocessing"):
        local_path = args.dicom_root / dicom_path

        record, preview_count = validate_one(
            dicom_path=dicom_path,
            local_path=local_path,
            args=args,
            preview_count=preview_count,
        )

        records.append(record)

    status_df = pd.DataFrame(records)
    status_df.to_csv(STATUS_PATH, index=False)

    status_counts = status_df["status"].value_counts().to_dict()

    print(f"Status counts: {status_counts}")
    print(f"Status CSV: {STATUS_PATH}")
    print(f"Preview directory: {PREVIEW_DIR}")
    print(f"Metadata directory: {METADATA_DIR}")


if __name__ == "__main__":
    main()