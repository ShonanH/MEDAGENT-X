#!/usr/bin/env python3
"""
05_extract_convnext_features.py

Workflow A: ConvNeXt feature extraction for CheXpert Plus DICOMs.

This script:
    1. Reads the CheXpert Plus manifest.
    2. Loads local DICOM files.
    3. Applies DICOM preprocessing through load_normalized_dicom_image().
    4. Converts each image to a 3-channel ConvNeXt tensor.
    5. Runs ConvNeXt-Tiny feature extraction.
    6. Saves spatial feature maps and pooled embeddings.

Outputs:
    outputs/chexpert_plus/convnext_features/
    outputs/chexpert_plus/convnext_feature_manifest.csv

python scripts/05_extract_convnext_features.py \
  --manifest-path data/processed/chexpert_plus/chexpert_plus_v2_manifest.csv \
  --dicom-root data/raw/chexpert_plus/dicom_train \
  --limit 10

python scripts/05_extract_convnext_features.py \
  --manifest-path data/processed/chexpert_plus/chexpert_plus_v2_manifest.csv \
  --dicom-root data/raw/chexpert_plus/dicom_train \
  --pretrained
"""


import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from PIL import Image
from tqdm import tqdm
import timm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.helpers.dicom_loader import load_normalized_dicom_image

DEFAULT_MANIFEST_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "chexpert_plus"
    / "chexpert_plus_v2_manifest.csv"
)

DEFAULT_DICOM_ROOT = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "chexpert_plus"
    / "dicom_train"
)

OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "chexpert_plus"
FEATURE_DIR = OUTPUT_ROOT / "convnext_features"
FEATURE_MANIFEST_PATH = OUTPUT_ROOT / "convnext_feature_manifest.csv"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract ConvNeXt-Tiny features from local CheXpert Plus DICOMs."
    )

    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--dicom-root", type=Path, default=DEFAULT_DICOM_ROOT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--model-name", default="convnext_tiny")
    parser.add_argument("--pretrained", action="store_true")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")

    return parser.parse_args()


def clean_dicom_path(path):
    path = str(path).strip().replace("\\", "/").lstrip("./")

    if "/train/" in path:
        path = path.split("/train/", maxsplit=1)[1]

    for prefix in ("train/", "DICOM_train/", "dicom_train/"):
        if path.startswith(prefix):
            path = path[len(prefix):]

    return path

def collect_manifest_records(manifest_path):
    manifest = pd.read_csv(manifest_path)

    records = []

    for _, row in manifest.iterrows():
        if "dicom_paths" in manifest.columns:
            raw_paths = str(row["dicom_paths"]).split("|")
        else: 
            raw_paths = [row.get("dicom_paths") or row.get("path_to_dcm")]

        for raw_path in raw_paths:
            dicom_path = clean_dicom_path(raw_path)

            if not dicom_path:
                continue

            records.append(
                {
                    "study_key": row.get("study_key", ""),
                    "deid_patient_id": row.get("deid_patient_id", ""),
                    "split": row.get("split", ""),
                    "age": row.get("age", ""),
                    "sex": row.get("sex", ""),
                    "dicom_path": dicom_path,
                }
            )
    seen = set()
    unique_records = []

    for record in records:
        if record["dicom_path"] in seen:
            continue

        seen.add(record["dicom_path"])
        unique_records.append(record)

    return unique_records

def to_uint8(image):
    image = np.asarray(image, dtype=np.float32)
    image = np.clip(image, 0.0, 1.0)
    return (image * 255.0).round().astype(np.uint8)

def make_tensor(image, image_size):
    pil_image = Image.fromarray(to_uint8(image), mode="L")
    pil_image = pil_image.resize((image_size, image_size), resample=Image.BILINEAR)

    array = np.asarray(pil_image, dtype=np.float32) / 255.0
    tensor = np.stack([array, array, array], axis=0)
    tensor = torch.from_numpy(tensor).float()

    mean = torch.tensor([0.485, 0.456, 0.406]).view(3,1,1)
    std = torch.tensor([0.229, 0.224, 0.225]).view(3,1,1)

    tensor = (tensor - mean) / std
    return tensor

def safe_stem(dicom_path):
    return(
        dicom_path
        .replace("/", "_")
        .replace("\\", "_")
        .replace(".dcm", "")
        .replace(".", "_")    
    )
    

def build_convnext(model_name, pretrained, device):
    model = timm.create_model(
        model_name,
        pretrained=pretrained,
        features_only=True,
        out_indices=(3,),
    )

    model.eval()
    model.to(device)

    return model

def main():
    args = parse_args()

    FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    FEATURE_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    records = collect_manifest_records(args.manifest_path)

    if args.limit is not None:
        records = records[:args.limit]

    print(f"Manifest: {args.manifest_path}")
    print(f"DICOM root: {args.dicom_root}")
    print(f"Feature directory: {FEATURE_DIR}")
    print(f"Feature manifest: {FEATURE_MANIFEST_PATH}")
    print(f"Records to process: {len(records)}")
    print(f"Device: {args.device}")
    print(f"Model: {args.model_name}")
    print(f"Pretrained: {args.pretrained}")

    model = build_convnext(
        model_name = args.model_name,
        pretrained = args.pretrained,
        device=args.device
    )

    output_records = []

    for record in tqdm(records, desc="Extracting ConvNeXT features"):
        dicom_path = record["dicom_path"]
        local_path = args.dicom_root / dicom_path
        feature_path = FEATURE_DIR / f"{safe_stem(dicom_path)}.npz"

        if not local_path.exists():
            output_records.append(
                {
                    **record,
                    "local_path": str(local_path),
                    "feature_path": "",
                    "status": "missing_dicom",
                    "error": "",
                }
            )
            continue

        try:
            with local_path.open("rb") as file_obj:
                image, ds = load_normalized_dicom_image(file_obj)

            tensor = make_tensor(image, args.image_size)
            tensor = tensor.unsqueeze(0).to(args.device)

            with torch.no_grad():
                feature_map = model(tensor)[0]
                pooled = F.adaptive_avg_pool2d(feature_map, output_size=1)
                pooled = pooled.flatten(1)

            feature_map_np = feature_map.squeeze(0).cpu().numpy().astype(np.float32)
            pooled_np = pooled.squeeze(0).cpu().numpy().astype(np.float32)

            np.savez_compressed(
                feature_path,
                feature_map=feature_map_np,
                pooled_embedding=pooled_np,
                dicom_path=dicom_path,
                rows=getattr(ds, "Rows", None),
                columns=getattr(ds, "Columns", None),
                photometric=str(getattr(ds, "PhotometricInterpretation", "")),
                view_position = str(getattr(ds, "ViewPosition", "")),
            )

            output_records.append(
                {
                    **record,
                    "local_path": str(local_path),
                    "feature_path": str(feature_path),
                    "status": "ok",
                    "error": "",
                    "rows": getattr(ds, "Rows", None),
                    "columns": getattr(ds, "Columns", None),
                    "photometric": getattr(ds, "PhotometricInterpretation", None),
                    "view_position": getattr(ds, "ViewPosition", None),
                    "feature_map_shape": str(tuple(feature_map_np.shape)),
                    "pooled_embedding_shape": str(tuple(pooled_np.shape)),
                }
            )

        except Exception as error:
            output_records.append(
                {
                    **record,
                    "local_path": str(local_path),
                    "feature_path": "",
                    "status": "failed",
                    "error": f"{type(error).__name__}: {error}",
                }
            )
        pd.DataFrame(output_records).to_csv(FEATURE_MANIFEST_PATH, index=False)

    status = pd.DataFrame(output_records)
    print()
    print("ConvNeXt feature extraction complete.")
    print("Status counts:", status["status"].value_counts().to_dict())
    print(f"Feature manifest: {FEATURE_MANIFEST_PATH}")
    print(f"Feature directory: {FEATURE_DIR}")


if __name__ == "__main__":
    main()















































