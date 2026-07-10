#!/usr/bin/env python3
"""
02_download_chexpert_dicoms.py

Download DICOM files listed in the MEDAGENT-X v2 manifest.

This prepares Workflow A:
DICOM input -> preprocessing -> ConvNeXt feature extraction.
"""

from pathlib import Path
import pandas as pd
import redivis
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parents[1]



DICOM_TABLE = "aimi.chexpert_plus:5yyj:v1_0.dicom_train:1934"

MANIFEST_PATH = Path("data/processed/chexpert_plus/chexpert_plus_v2_manifest.csv")
OUTPUT_ROOT = PROJECT_ROOT/ "data/raw/chexpert_plus/DICOM_train")


def candidate_redivis_paths(row):
    paths = []

    for column in ["dicom_path_original", "path_to_dcm", "dicom_path"]:
        if column in row and pd.notna(row[column]):
            value = str(row[column]).strip()
            if value:
                paths.append(value)

    # Some Redivis file paths may include train/, while your normalized
    # manifest path may not. Try both forms.
    expanded = []
    for path in paths:
        expanded.append(path)
        if path.startswith("train/"):
            expanded.append(path[len("train/"):])
        else:
            expanded.append(f"train/{path}")

    return list(dict.fromkeys(expanded))


def main():
    df = pd.read_csv(MANIFEST_PATH)
    table = redivis.table(DICOM_TABLE)

    downloaded = []
    missing = []

    for _, row in tqdm(df.iterrows(), total=len(df)):
        local_rel_path = str(row["dicom_path"]).strip()
        local_path = OUTPUT_ROOT / local_rel_path

        if local_path.exists():
            downloaded.append(local_rel_path)
            continue

        local_path.parent.mkdir(parents=True, exist_ok=True)

        file_obj = None
        used_redivis_path = None

        for redivis_path in candidate_redivis_paths(row):
            try:
                file_obj = table.file(redivis_path)
                # download() will fail if this path is not valid
                file_obj.download(local_path, overwrite=False, progress=False)
                used_redivis_path = redivis_path
                break
            except Exception:
                file_obj = None

        if used_redivis_path is None:
            missing.append(local_rel_path)
        else:
            downloaded.append(local_rel_path)

    status = pd.DataFrame(
        {
            "dicom_path": downloaded + missing,
            "download_status": ["downloaded"] * len(downloaded) + ["missing"] * len(missing),
        }
    )

    status_path = OUTPUT_ROOT.parent / "dicom_download_status.csv"
    status.to_csv(status_path, index=False)

    print(f"Downloaded: {len(downloaded)}")
    print(f"Missing: {len(missing)}")
    print(f"Status CSV: {status_path}")


if __name__ == "__main__":
    main()