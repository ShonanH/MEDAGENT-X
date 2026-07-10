"""
Download CheXpert Plus DICOM files from Redivis to local NRP storage.

This script reads a MEDAGENT-X CheXpert manifest, extracts the DICOM paths,
checks each path against the Redivis DICOM_train file index, and saves the
files locally while preserving the patient/study folder structure.

Use this before training so ConvNeXt reads local files instead of streaming
DICOMs from Redivis every epoch.
"""

import argparse
import shutil
from pathlib import Path

import pandas as pd
import redivis


DICOM_TRAIN_TABLE = "aimi.chexpert_plus:5yyj:v1_0.dicom_train:1934"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download CheXpert Plus DICOMs listed in a manifest."
    )

    parser.add_argument(
        "--manifest-path",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw/chexpert_plus/dicom_train"),
    )

    return parser.parse_args()


def clean_redivis_dicom_path(path):
    path = str(path).strip()

    if path.startswith("train/"):
        path = path.removeprefix("train/")

    return path


def collect_dicom_paths(manifest):
    paths = []

    for _, row in manifest.iterrows():
        for path in str(row["dicom_paths"]).split("|"):
            path = clean_redivis_dicom_path(path)

            if path:
                paths.append(path)

    return sorted(set(paths))


def main():
    args = parse_args()

    manifest = pd.read_csv(args.manifest_path)
    dicom_paths = collect_dicom_paths(manifest)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Manifest:", args.manifest_path)
    print("Unique DICOM paths:", len(dicom_paths))
    print("Output directory:", args.output_dir)

    dicom_table = redivis.table(DICOM_TRAIN_TABLE)
    dicom_dir = dicom_table.to_directory()

    downloaded = 0
    already_exists = 0
    missing = 0

    for index, dicom_path in enumerate(dicom_paths, start=1):
        output_path = args.output_dir / dicom_path

        if output_path.exists():
            already_exists += 1
            print(f"[{index}/{len(dicom_paths)}] exists: {dicom_path}")
            continue

        redivis_file = dicom_dir.get(dicom_path)

        if redivis_file is None:
            missing += 1
            print(f"[{index}/{len(dicom_paths)}] missing in Redivis: {dicom_path}")
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with redivis_file.open("rb") as source:
            with output_path.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)

        downloaded += 1
        print(f"[{index}/{len(dicom_paths)}] downloaded: {dicom_path}")

    print()
    print("Download complete.")
    print("Downloaded:", downloaded)
    print("Already existed:", already_exists)
    print("Missing:", missing)
    print("Saved under:", args.output_dir)


if __name__ == "__main__":
    main()