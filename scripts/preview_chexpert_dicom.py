import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pydicom
import redivis
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DICOM_TRAIN_TABLE = "aimi.chexpert_plus:5yyj:v1_0.dicom_train:1934"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Load one CheXpert Plus DICOM pixel array and save a PNG preview."
    )

    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=PROJECT_ROOT
        / "data"
        / "processed"
        / "chexpert_plus_50_study_manifest.csv",
    )

    parser.add_argument(
        "--row-index",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "chexpert_plus_dicom_preview",
    )

    return parser.parse_args()


def get_first_dicom_path(dicom_paths):
    first_path = str(dicom_paths).split("|")[0]

    if first_path.startswith("train/"):
        first_path = first_path.removeprefix("train/")

    return first_path


def normalize_to_uint8(image):
   image = image.astype(np.float32)

   image_min = float(np.min(image))
   image_max = float(np.max(image))

   if image_max <= image_min:
      return np.zeros(image.shape, dtype=np.uint8)

   image = (image - image_min) / (image_max - image_min)
   image = image * 255.0

   return image.astype(np.uint8)

def main():
   args = parse_args()

   manifest = pd.read_csv(args.manifest_path)

   if args.row_index < 0 or args.row_index >= len(manifest):
      raise IndexError(f"Row index must be between 0 and {len(manifest) - 1}")

   row = manifest.iloc[args.row_index]
   redivis_dicom_path = get_first_dicom_path(row['dicom_paths'])
   
   print("Study key:", row["study_key"])
   print("Redivis DICOM path:", redivis_dicom_path)

   table = redivis.table(DICOM_TRAIN_TABLE)
   dicom_file = table.file(redivis_dicom_path)

   with dicom_file.open("rb") as f:
      ds = pydicom.dcmread(f)
   
   pixel_array = ds.pixel_array.astype(np.float32)

   slope = float(getattr(ds, "RescaleSlope", 1))
   intercept = float(getattr(ds, "RescaleIntercept", 0))
   pixel_array = pixel_array * slope + intercept

   photometric = getattr(ds, "PhotometricInterpretation", "")

   normalized = normalize_to_uint8(pixel_array)

   if photometric == "MONOCHROME":
      normalized = 255 - normalized
   
   args.output_dir.mkdir(parents=True, exist_ok=True)

   output_path = args.output_dir / f"row_{args.row_index}_preview.png"

   Image.fromarray(normalized).save(output_path)

   print()
   print("Pixel loading passed.")
   print("Pixel metadata:")
   print("  shape:", pixel_array.shape)
   print("  dtype:", pixel_array.dtype)
   print("  min:", float(np.min(pixel_array)))
   print("  max:", float(np.max(pixel_array)))
   print("  mean:", float(np.mean(pixel_array)))
   print("  std:", float(np.std(pixel_array)))
   print("  photometric:", photometric)
   print()
   print("Saved preview to:", output_path)


if __name__ == "__main__":
    main()