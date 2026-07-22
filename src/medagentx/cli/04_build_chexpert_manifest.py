import argparse
import csv
import sys
from pathlib import Path

import pandas as pd
import redivis


from medagentx._bootstrap import ensure_src_on_path
from medagentx.paths import PROCESSED_DATA_DIR, RAW_DATA_DIR

ensure_src_on_path()

from medagentx.helpers.chexpert_plus_manifest import (
    MANIFEST_COLUMNS,
    build_study_manifest_records,
)


DATASET_REF = "chexpert_plus:5yyj"
MAIN_TABLE_REF = "df_chexpert_plus_240401:bavj"
DICOM_TRAIN_TABLE = "aimi.chexpert_plus:5yyj:v1_0.dicom_train:1934"

DICOM_INDEX_PATH_COLUMNS = [
    "file_name",
    "name",
    "path",
    "file_path",
    "filename",
    "dicom_path",
    "path_to_dcm",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build a CheXpert Plus study-level manifest from Redivis CSV downloads."
    )

    parser.add_argument(
        "--row-limit",
        type=int,
        default=None,
        help=(
            "Optional cap on image-level metadata rows to scan. "
            "Default: scan the full train split (use this only for quick tests)."
        ),
    )
    parser.add_argument(
        "--study-limit",
        type=int,
        default=25000,
        help="Maximum number of studies to include in the manifest.",
    )

    parser.add_argument(
        "--metadata-cache-dir",
        type=Path,
        default=RAW_DATA_DIR / "chexpert_plus" / "metadata_table",
    )

    parser.add_argument(
        "--dicom-index-cache-dir",
        type=Path,
        default=RAW_DATA_DIR / "chexpert_plus" / "dicom_train_index",
    )

    parser.add_argument("--overwrite-metadata-download", action="store_true")
    parser.add_argument("--overwrite-dicom-index-download", action="store_true")

    parser.add_argument(
        "--output-path",
        type=Path,
        default=PROCESSED_DATA_DIR
        / "chexpert_plus"
        / "chexpert_plus_study_manifest.csv",
    )

    return parser.parse_args()


def clean_redivis_dicom_path(path):
    path = str(path).strip().replace("\\", "/").lstrip("./")

    if "/train/" in path:
        path = path.split("/train/", maxsplit=1)[1]

    for prefix in ["train/", "DICOM_train/", "dicom_train/"]:
        if path.startswith(prefix):
            path = path[len(prefix):]

    return path


def get_first_csv(directory):
    csv_paths = sorted(Path(directory).glob("*.csv"))

    if not csv_paths:
        raise FileNotFoundError(f"No CSV files found in: {directory}")

    return csv_paths[0]


def download_metadata_table(args):
    args.metadata_cache_dir.mkdir(parents=True, exist_ok=True)

    existing_csvs = sorted(args.metadata_cache_dir.glob("*.csv"))
    if existing_csvs and not args.overwrite_metadata_download:
        print(f"Using cached metadata CSV: {existing_csvs[0]}")
        return existing_csvs[0]

    print("Downloading CheXpert Plus metadata table as CSV...")

    dataset = redivis.organization("AIMI").dataset(DATASET_REF)
    table = dataset.table(MAIN_TABLE_REF)

    table.download(
        path=str(args.metadata_cache_dir),
        format="csv",
        overwrite=args.overwrite_metadata_download,
        progress=True,
    )

    return get_first_csv(args.metadata_cache_dir)


def download_dicom_index_table(args):
    args.dicom_index_cache_dir.mkdir(parents=True, exist_ok=True)

    existing_csvs = sorted(args.dicom_index_cache_dir.glob("*.csv"))
    if existing_csvs and not args.overwrite_dicom_index_download:
        print(f"Using cached DICOM index CSV: {existing_csvs[0]}")
        return existing_csvs[0]

    print("Downloading DICOM_train index table as CSV...")

    dicom_table = redivis.table(DICOM_TRAIN_TABLE)

    dicom_table.download(
        path=str(args.dicom_index_cache_dir),
        format="csv",
        overwrite=args.overwrite_dicom_index_download,
        progress=True,
    )

    return get_first_csv(args.dicom_index_cache_dir)


def find_dicom_index_path_column(dicom_index_csv_path):
    header = pd.read_csv(dicom_index_csv_path, nrows=0).columns.tolist()
    lower_to_actual = {column.lower(): column for column in header}

    for candidate in DICOM_INDEX_PATH_COLUMNS:
        if candidate.lower() in lower_to_actual:
            return lower_to_actual[candidate.lower()]

    raise ValueError(
        "Could not identify DICOM path column in DICOM index CSV. "
        f"Available columns: {header}"
    )


def load_available_dicom_paths(dicom_index_csv_path):
    path_column = find_dicom_index_path_column(dicom_index_csv_path)

    print(f"Reading DICOM index CSV: {dicom_index_csv_path}")
    print(f"Using DICOM path column: {path_column}")

    available_paths = set()

    for chunk in pd.read_csv(dicom_index_csv_path, usecols=[path_column], chunksize=50000):
        for value in chunk[path_column].dropna().astype(str):
            cleaned_path = clean_redivis_dicom_path(value)

            if cleaned_path and cleaned_path.lower() != "nan":
                available_paths.add(cleaned_path)

    print("Available DICOM paths in index:", len(available_paths))
    return available_paths


def read_metadata_rows(metadata_csv_path, row_limit=None):
    print(f"Reading metadata CSV: {metadata_csv_path}")
    if row_limit is None:
        print("Row scan limit: none (full train split)")
    else:
        print(f"Row scan limit: {row_limit}")

    header = pd.read_csv(metadata_csv_path, nrows=0).columns.tolist()
    usecols = [column for column in MANIFEST_COLUMNS if column in header]

    if "path_to_dcm" not in usecols:
        raise ValueError(f"path_to_dcm column not found. Available columns: {header}")

    rows = []
    rows_scanned = 0

    for chunk in pd.read_csv(metadata_csv_path, usecols=usecols, chunksize=5000):
        chunk = chunk[chunk["path_to_dcm"].notna()].copy()

        if "split" in chunk.columns:
            chunk = chunk[chunk["split"].astype(str).str.strip() == "train"]

        if chunk.empty:
            continue

        for row in chunk.to_dict(orient="records"):
            rows_scanned += 1
            rows.append(row)

            if row_limit is not None and rows_scanned >= row_limit:
                return rows

    return rows


def filter_rows_with_available_dicoms(rows, available_dicom_paths):
    print("Checking DICOM availability using downloaded DICOM_train index...")

    available_rows = []
    skipped_rows = 0

    for row in rows:
        dicom_path = row.get("path_to_dcm")

        if not dicom_path:
            skipped_rows += 1
            continue

        cleaned_path = clean_redivis_dicom_path(dicom_path)

        if cleaned_path not in available_dicom_paths:
            skipped_rows += 1
            continue

        available_rows.append(row)

    print("Rows with available DICOMs:", len(available_rows))
    print("Rows skipped because DICOM was missing:", skipped_rows)

    return available_rows


def write_manifest_csv(records, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(records) == 0:
        raise ValueError("No manifest records were created.")

    fieldnames = list(records[0].keys())

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main():
    args = parse_args()

    print("Connecting to Redivis dataset: AIMI / chexpert_plus")

    metadata_csv_path = download_metadata_table(args)
    dicom_index_csv_path = download_dicom_index_table(args)

    available_dicom_paths = load_available_dicom_paths(dicom_index_csv_path)

    rows = read_metadata_rows(
        metadata_csv_path=metadata_csv_path,
        row_limit=args.row_limit,
    )

    print(f"Image-level rows read from metadata CSV: {len(rows)}")

    rows = filter_rows_with_available_dicoms(
        rows=rows,
        available_dicom_paths=available_dicom_paths,
    )

    print(f"Building manifest with up to {args.study_limit} studies...")
    manifest_records = build_study_manifest_records(
        rows=rows,
        study_limit=args.study_limit,
    )

    print(f"Studies created: {len(manifest_records)}")

    write_manifest_csv(
        records=manifest_records,
        output_path=args.output_path,
    )

    print(f"Saved manifest to: {args.output_path}")

    if len(manifest_records) > 0:
        first_record = manifest_records[0]
        print("First study preview:")
        print(f"  study_key: {first_record['study_key']}")
        print(f"  image_count: {first_record['image_count']}")
        print(f"  split: {first_record['split']}")


if __name__ == "__main__":
    main()