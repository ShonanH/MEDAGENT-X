#!/usr/bin/env python3
"""
05_download_manifest_dicoms.py

Download CheXpert Plus DICOM files listed in a MEDAGENT-X manifest.

This script avoids Redivis Python file-directory helpers:
    table.to_directory()
    table.file(...)

Those can fail on NRP with Arrow stream / timeout errors.

Instead, it uses:
    manifest dicom_path
    -> lookup file_id from local Redivis DICOM index CSV
    -> Redivis REST API rawFiles/{file_id}
    -> local DICOM file

DICOM output:
    data/raw/chexpert_plus/dicom_train/

Status output:
    outputs/chexpert_plus/dicom_download_status.csv

TEST:
python -m medagentx.cli.05_download_manifest_dicoms \
  --manifest-path data/processed/chexpert_plus/chexpert_plus_500_study_manifest.csv \
  --limit 5

RUN:

python -m medagentx.cli.05_download_manifest_dicoms \
  --manifest-path data/processed/chexpert_plus/chexpert_plus_500_study_manifest.csv \
  --workers 4
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from tqdm import tqdm


from medagentx._bootstrap import ensure_src_on_path
from medagentx.paths import CHEXPERT_OUTPUT_DIR, DATA_DIR, FUSION_OUTPUT_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR, SRC_ROOT, VECTOR_DB_DIR

ensure_src_on_path()

from medagentx.helpers.redivis_rest_client import RedivisRestClient


DEFAULT_MANIFEST_PATH = (
    PROCESSED_DATA_DIR
    / "chexpert_plus"
    / "chexpert_plus_500_study_manifest.csv"
)

DEFAULT_INDEX_DIR = (
    RAW_DATA_DIR
    / "chexpert_plus"
    / "dicom_train_index"
)

DEFAULT_OUTPUT_DIR = (
    RAW_DATA_DIR
    / "chexpert_plus"
    / "dicom_train"
)

DEFAULT_STATUS_PATH = CHEXPERT_OUTPUT_DIR / "dicom_download_status.csv"

FILE_ID_COLUMNS = [
    "file_id",
    "id",
    "_id",
    "fileId",
    "file_id_",
]

PATH_COLUMNS = [
    "path",
    "file_path",
    "file_name",
    "filename",
    "name",
    "dicom_path",
    "path_to_dcm",
    "uri",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download manifest DICOMs using Redivis REST rawFiles API."
    )

    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to CheXpert Plus manifest CSV.",
    )

    parser.add_argument(
        "--index-dir",
        type=Path,
        default=DEFAULT_INDEX_DIR,
        help="Directory containing Redivis DICOM_train index CSV.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Local directory where DICOM files will be saved.",
    )

    parser.add_argument(
        "--status-path",
        type=Path,
        default=DEFAULT_STATUS_PATH,
        help="CSV file where download status will be written.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of DICOM files to download.",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel download workers. Start with 1; try 4 if stable.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite local files that already exist.",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="HTTP read timeout in seconds.",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Retry count per file.",
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


def collect_manifest_dicom_paths(manifest_path):
    manifest = pd.read_csv(manifest_path)

    if "dicom_paths" in manifest.columns:
        source_columns = ["dicom_paths"]
    else:
        source_columns = [
            column
            for column in ("dicom_path", "path_to_dcm", "dicom_path_original")
            if column in manifest.columns
        ]

    if not source_columns:
        raise ValueError(
            "Manifest must contain `dicom_paths`, `dicom_path`, "
            "`path_to_dcm`, or `dicom_path_original`."
        )

    paths = []

    for column in source_columns:
        for value in manifest[column]:
            if pd.isna(value):
                continue

            for raw_path in str(value).split("|"):
                cleaned = clean_dicom_path(raw_path)

                if cleaned:
                    paths.append(cleaned)

    return list(dict.fromkeys(paths))


def get_first_existing_csv(index_dir):
    csv_paths = sorted(index_dir.glob("*.csv"))

    if not csv_paths:
        raise FileNotFoundError(f"No CSV files found in: {index_dir}")

    return csv_paths[0]


def find_column(columns, candidates):
    lower_to_actual = {column.lower(): column for column in columns}

    for candidate in candidates:
        if candidate.lower() in lower_to_actual:
            return lower_to_actual[candidate.lower()]

    return None


def find_matching_path_column(csv_path, target_paths, sample_rows=5000):
    header = pd.read_csv(csv_path, nrows=0).columns.tolist()
    candidate_columns = [
        column
        for column in header
        if column.lower() in {candidate.lower() for candidate in PATH_COLUMNS}
    ]

    if not candidate_columns:
        raise ValueError(
            f"No candidate path columns found in {csv_path}. "
            f"Available columns: {header}"
        )

    sample = pd.read_csv(csv_path, nrows=sample_rows, usecols=candidate_columns)

    best_column = None
    best_matches = -1

    for column in candidate_columns:
        normalized = sample[column].dropna().map(clean_dicom_path)
        matches = normalized.isin(target_paths).sum()

        if matches > best_matches:
            best_matches = matches
            best_column = column

    if best_column is None:
        raise ValueError("Could not determine DICOM path column.")

    return best_column


def build_file_id_lookup(index_dir, manifest_paths):
    csv_path = get_first_existing_csv(index_dir)
    target_paths = set(manifest_paths)

    header = pd.read_csv(csv_path, nrows=0).columns.tolist()

    file_id_column = find_column(header, FILE_ID_COLUMNS)
    if file_id_column is None:
        raise ValueError(
            f"Could not identify file ID column in {csv_path}. "
            f"Available columns: {header}"
        )

    path_column = find_matching_path_column(
        csv_path=csv_path,
        target_paths=target_paths,
    )

    print(f"DICOM index CSV: {csv_path}")
    print(f"Using file ID column: {file_id_column}")
    print(f"Using path column: {path_column}")

    lookup = {}

    for chunk in pd.read_csv(
        csv_path,
        usecols=[file_id_column, path_column],
        chunksize=50000,
    ):
        chunk = chunk.dropna(subset=[file_id_column, path_column]).copy()
        chunk["clean_dicom_path"] = chunk[path_column].map(clean_dicom_path)
        chunk = chunk[chunk["clean_dicom_path"].isin(target_paths)]

        for _, row in chunk.iterrows():
            clean_path = row["clean_dicom_path"]
            file_id = str(row[file_id_column]).strip()

            if clean_path and file_id:
                lookup[clean_path] = file_id

    return lookup


def download_one(client, dicom_path, file_id, output_dir, overwrite):
    output_path = output_dir / dicom_path

    result = client.download_raw_file(
        file_id=file_id,
        output_path=output_path,
        overwrite=overwrite,
        resume=True,
    )

    return {
        "dicom_path": dicom_path,
        "file_id": file_id,
        "local_path": result.output_path,
        "download_status": result.status,
        "bytes_written": result.bytes_written,
        "error": result.error,
    }


def write_status(records, status_path):
    status_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(status_path, index=False)


def main():
    args = parse_args()

    if not args.manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {args.manifest_path}")

    if not args.index_dir.exists():
        raise FileNotFoundError(f"DICOM index directory not found: {args.index_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.status_path.parent.mkdir(parents=True, exist_ok=True)

    manifest_paths = collect_manifest_dicom_paths(args.manifest_path)

    if args.limit is not None:
        manifest_paths = manifest_paths[:args.limit]

    print(f"Manifest: {args.manifest_path}")
    print(f"Manifest DICOM paths: {len(manifest_paths)}")
    print(f"Output directory: {args.output_dir}")
    print(f"Status path: {args.status_path}")

    file_id_lookup = build_file_id_lookup(
        index_dir=args.index_dir,
        manifest_paths=manifest_paths,
    )

    matched = []
    missing_from_index = []

    for dicom_path in manifest_paths:
        file_id = file_id_lookup.get(dicom_path)

        if file_id:
            matched.append((dicom_path, file_id))
        else:
            missing_from_index.append(dicom_path)

    print(f"Matched DICOM paths to file IDs: {len(matched)}")
    print(f"Missing from index: {len(missing_from_index)}")

    client = RedivisRestClient.from_env(
        timeout=args.timeout,
        max_retries=args.max_retries,
    )

    status_records = []

    for dicom_path in missing_from_index:
        status_records.append(
            {
                "dicom_path": dicom_path,
                "file_id": "",
                "local_path": str(args.output_dir / dicom_path),
                "download_status": "missing_from_index",
                "bytes_written": 0,
                "error": "",
            }
        )

    if args.workers <= 1:
        for dicom_path, file_id in tqdm(matched, desc="Downloading DICOMs"):
            record = download_one(
                client=client,
                dicom_path=dicom_path,
                file_id=file_id,
                output_dir=args.output_dir,
                overwrite=args.overwrite,
            )

            status_records.append(record)
            write_status(status_records, args.status_path)

    else:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    download_one,
                    client,
                    dicom_path,
                    file_id,
                    args.output_dir,
                    args.overwrite,
                ): dicom_path
                for dicom_path, file_id in matched
            }

            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Downloading DICOMs",
            ):
                record = future.result()
                status_records.append(record)
                write_status(status_records, args.status_path)

    status = pd.DataFrame(status_records)
    counts = status["download_status"].value_counts().to_dict()

    print()
    print("Download complete.")
    print(f"Status counts: {counts}")
    print(f"Status CSV: {args.status_path}")
    print(f"Saved under: {args.output_dir}")


if __name__ == "__main__":
    main()