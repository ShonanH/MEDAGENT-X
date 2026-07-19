from medagentx.paths import CHEXPERT_OUTPUT_DIR, DATA_DIR, FUSION_OUTPUT_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR, SRC_ROOT, VECTOR_DB_DIR

#!/usr/bin/env python3
"""
Extract pretrained RAD-DINO Transformer features for MEDAGENT-X Workflow A.

This is the Transformer/global-context branch.

It does NOT train a model.
It does NOT require quality labels.
It does NOT make quality decisions.

Inputs:
  - CheXpert Plus manifest with dicom_paths
  - Downloaded local DICOM files

Outputs:
  - outputs/chexpert_plus/raddino_features/*.npz
  - outputs/chexpert_plus/raddino_feature_manifest.csv

python -m medagentx.cli.06_extract_raddino_features.py \
  --manifest-path data/processed/chexpert_plus/chexpert_plus_v2_manifest.csv
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from tqdm import tqdm
from transformers import AutoImageProcessor, AutoModel



if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from medagentx.helpers.dicom_loader import load_normalized_dicom_image


DEFAULT_MODEL_NAME = "microsoft/rad-dino"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract RAD-DINO Transformer features from local DICOM files."
    )

    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=PROCESSED_DATA_DIR / "chexpert_plus" / "chexpert_plus_v2_manifest.csv",
    )

    parser.add_argument(
        "--dicom-root",
        type=Path,
        default=RAW_DATA_DIR / "chexpert_plus" / "dicom_train",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=CHEXPERT_OUTPUT_DIR,
    )

    parser.add_argument(
        "--model-name",
        type=str,
        default=DEFAULT_MODEL_NAME,
    )

    parser.add_argument(
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for testing.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Recompute features even if output file already exists.",
    )

    parser.add_argument(
        "--no-save-patch-tokens",
        action="store_true",
        help="Only save CLS/global embedding, not patch/token embeddings.",
    )

    return parser.parse_args()


def clean_dicom_path(path):
    path = str(path).strip()

    if path.startswith("train/"):
        path = path.removeprefix("train/")

    return path


def safe_feature_name(dicom_path):
    path = clean_dicom_path(dicom_path)

    if path.endswith(".dcm"):
        path = path[:-4]

    return path.replace("/", "__") + ".npz"


def collect_manifest_dicoms(manifest):
    records = []

    if "dicom_paths" not in manifest.columns:
        raise KeyError(
            "Manifest must contain a 'dicom_paths' column. "
            f"Found columns: {manifest.columns.tolist()}"
        )

    seen = set()

    for row_index, row in manifest.iterrows():
        dicom_paths = str(row["dicom_paths"]).split("|")

        for dicom_path in dicom_paths:
            dicom_path = clean_dicom_path(dicom_path)

            if not dicom_path or dicom_path in seen:
                continue

            seen.add(dicom_path)

            records.append(
                {
                    "manifest_row_index": row_index,
                    "study_key": row.get("study_key", None),
                    "dicom_path": dicom_path,
                }
            )

    return records


def dicom_to_pil_rgb(local_path):
    image = load_normalized_dicom_image(local_path)

    if isinstance(image, tuple):
        image = image[0]

    image = np.asarray(image, dtype=np.float32)
    image = np.nan_to_num(image, nan=0.0, posinf=1.0, neginf=0.0)

    image_min = float(image.min())
    image_max = float(image.max())

    if image_max > image_min:
        image = (image - image_min) / (image_max - image_min)
    else:
        image = np.zeros_like(image, dtype=np.float32)

    image_uint8 = np.clip(image * 255.0, 0, 255).astype(np.uint8)

    return Image.fromarray(image_uint8, mode="L").convert("RGB")


def extract_raddino_features(model, processor, pil_image, device):
    inputs = processor(images=pil_image, return_tensors="pt")
    inputs = {key: value.to(device) for key, value in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    if not hasattr(outputs, "last_hidden_state"):
        raise RuntimeError("RAD-DINO output does not contain last_hidden_state.")

    tokens = outputs.last_hidden_state[0].detach().cpu().float().numpy()

    cls_embedding = tokens[0]
    patch_embeddings = tokens[1:]

    return cls_embedding, patch_embeddings


def main():
    args = parse_args()

    manifest_path = args.manifest_path.resolve()
    dicom_root = args.dicom_root.resolve()
    output_dir = args.output_dir.resolve()
    feature_dir = output_dir / "raddino_features"
    feature_manifest_path = output_dir / "raddino_feature_manifest.csv"

    output_dir.mkdir(parents=True, exist_ok=True)
    feature_dir.mkdir(parents=True, exist_ok=True)

    manifest = pd.read_csv(manifest_path)
    records = collect_manifest_dicoms(manifest)

    if args.limit is not None:
        records = records[: args.limit]

    print("Manifest:", manifest_path)
    print("DICOM root:", dicom_root)
    print("RAD-DINO model:", args.model_name)
    print("Device:", args.device)
    print("DICOM images:", len(records))
    print("Feature directory:", feature_dir)
    print("Feature manifest:", feature_manifest_path)

    processor = AutoImageProcessor.from_pretrained(args.model_name)
    model = AutoModel.from_pretrained(args.model_name)
    model.to(args.device)
    model.eval()

    status_rows = []

    for record in tqdm(records, desc="Extracting RAD-DINO features"):
        dicom_path = record["dicom_path"]
        local_path = dicom_root / dicom_path
        feature_path = feature_dir / safe_feature_name(dicom_path)

        row = {
            "manifest_row_index": record["manifest_row_index"],
            "study_key": record["study_key"],
            "dicom_path": dicom_path,
            "local_path": str(local_path),
            "feature_path": str(feature_path),
            "model_name": args.model_name,
            "status": None,
            "error": None,
        }

        try:
            if not local_path.exists():
                raise FileNotFoundError(f"Missing local DICOM: {local_path}")

            if feature_path.exists() and not args.overwrite:
                row["status"] = "exists"
                status_rows.append(row)
                continue

            pil_image = dicom_to_pil_rgb(local_path)

            cls_embedding, patch_embeddings = extract_raddino_features(
                model=model,
                processor=processor,
                pil_image=pil_image,
                device=args.device,
            )

            save_payload = {
                "cls_embedding": cls_embedding.astype(np.float32),
                "dicom_path": np.array(dicom_path),
                "local_path": np.array(str(local_path)),
                "model_name": np.array(args.model_name),
            }

            if not args.no_save_patch_tokens:
                save_payload["patch_embeddings"] = patch_embeddings.astype(np.float16)

            np.savez_compressed(feature_path, **save_payload)

            row["status"] = "success"

        except Exception as exc:
            row["status"] = "failed"
            row["error"] = f"{type(exc).__name__}: {exc}"

        status_rows.append(row)

    feature_manifest = pd.DataFrame(status_rows)
    feature_manifest.to_csv(feature_manifest_path, index=False)

    print()
    print("RAD-DINO feature extraction complete.")
    print("Status counts:", feature_manifest["status"].value_counts().to_dict())
    print("Feature manifest:", feature_manifest_path)
    print("Feature directory:", feature_dir)


if __name__ == "__main__":
    main()