import argparse
import csv
import sys
from pathlib import Path

import redivis


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.helpers.chexpert_plus_manifest import (
    build_query,
    build_study_manifest_records,
)
DICOM_TRAIN_TABLE = "aimi.chexpert_plus:5yyj:v1_0.dicom_train:1934"

def clean_redivis_dicom_path(path):
    path = str(path).strip()

    if path.startswith("train/"):
        path = path.removeprefix("train/")

    return path


def filter_rows_with_available_dicoms(rows):
    print("Checking DICOM availability in Redivis DICOM_train...")

    dicom_table = redivis.table(DICOM_TRAIN_TABLE)
    dicom_dir = dicom_table.to_directory()

    available_rows = []
    skipped_rows = 0

    for row in rows:
        dicom_path = row.get("path_to_dcm")

        if not dicom_path:
            skipped_rows += 1
            continue

        redivis_path = clean_redivis_dicom_path(dicom_path)

        if dicom_dir.get(redivis_path) is None:
            skipped_rows += 1
            continue

        available_rows.append(row)

    print("Rows with available DICOMs:", len(available_rows))
    print("Rows skipped because DICOM was missing:", skipped_rows)

    return available_rows
    
def parse_args():
    parser = argparse.ArgumentParser(
        description="Build a small CheXpert Plus study-level manifest from Redivis."
    )

    parser.add_argument(
        "--row-limit",
        type=int,
        default=1000,
        help="Maximum image-level rows to query from Redivis.",
    )

    parser.add_argument(
        "--study-limit",
        type=int,
        default=50,
        help="Maximum study-level cases to keep in the manifest.",
    )

    parser.add_argument(
        "--output-path",
        type=Path,
        default=PROJECT_ROOT
        / "data"
        / "processed"
        / "chexpert_plus_50_study_manifest.csv",
        help="Where to save the study-level manifest CSV.",
    )

    return parser.parse_args()


def dataframe_to_records(df):
   records = []

   for row in df.to_dict(orient="records"):
      records.append(row)

   return records


def write_manifest_csv(records, output_path):
   output_path.parent.mkdir(parents=True, exist_ok=True)

   if len(records) == 0:
      raise ValueError("No manifest records were created")

   fieldnames = list(records[0].keys())

   with output_path.open("w", newline="", encoding="utf-8") as f:
      writer = csv.DictWriter(f, fieldnames=fieldnames)
      writer.writeheader()
      writer.writerows(records)

def main():
    args = parse_args()

    print("Connecting to Redivis dataset: AIMI CheXpert Plus")

    organization = redivis.organization("AIMI")
    dataset = organization.dataset("chexpert_plus")

    query = build_query(row_limit=args.row_limit)

    print(f"Querying up to {args.row_limit} image-level rows.....")
    df_rows = dataset.query(query).to_pandas_dataframe(dtype_backend="numpy")

    print(f"Rows returned: {len(df_rows)}")
    rows = dataframe_to_records(df_rows)
    rows = filter_rows_with_available_dicoms(rows)
    
    print(f"Building manifest with up to {args.study_limit} studies.....")
    manifest_records = build_study_manifest_records(
       rows=rows,
       study_limit=args.study_limit,
    )

    print(f"Studies created: {len(manifest_records)}")

    write_manifest_csv(
       records=manifest_records,
       output_path=args.output_path
    )

    print(f"Saved manifest to: {args.output_path}")

    if len(manifest_records) > 0:
       first_record = manifest_records[0]
       print("First study preview: ")
       print(f"    study_key: {first_record['study_key']}")
       print(f"  image_count: {first_record['image_count']}")
       print(f"  split: {first_record['split']}")


if __name__ == "__main__":
    main()
