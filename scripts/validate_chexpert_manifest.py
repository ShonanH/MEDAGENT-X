import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


REQUIRED_COLUMNS = [
    "study_key",
    "deid_patient_id",
    "split",
    "age",
    "sex",
    "dicom_paths",
    "image_paths",
    "frontal_lateral_views",
    "ap_pa_views",
    "report",
    "section_impression",
    "image_count",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate a CheXpert Plus study-level manifest."
    )

    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=PROJECT_ROOT
        / "data"
        / "processed"
        / "chexpert_plus_50_study_manifest.csv",
        help="Path to the manifest CSV.",
    )

    parser.add_argument(
        "--expected-studies",
        type=int,
        default=50,
        help="Expected number of study-level rows.",
    )

    return parser.parse_args()


def fail_if(condition, message):
    if condition:
        raise ValueError(message)


def validate_required_columns(df):
    missing_columns = []

    for column in REQUIRED_COLUMNS:
        if column not in df.columns:
            missing_columns.append(column)

    fail_if(
        len(missing_columns) > 0,
        f"Missing required columns: {missing_columns}",
    )


def validate_manifest(df, expected_studies):
    validate_required_columns(df)

    fail_if(
        len(df) != expected_studies,
        f"Expected {expected_studies} studies, but found {len(df)}.",
    )

    fail_if(
        df["study_key"].duplicated().any(),
        "Duplicate study_key values found.",
    )

    fail_if(
        df["study_key"].isna().any(),
        "Missing study_key values found.",
    )

    fail_if(
        df["dicom_paths"].isna().any(),
        "Missing dicom_paths values found.",
    )

    fail_if(
        (df["image_count"] < 1).any(),
        "Every study must have at least one image.",
    )

    fail_if(
        df["section_impression"].isna().any(),
        "Every study must have a section_impression value.",
    )


def print_summary(df):
    print("Manifest validation passed.")
    print()
    print(f"Study rows: {len(df)}")
    print(f"Unique studies: {df['study_key'].nunique()}")
    print()
    print("Split counts:")
    print(df["split"].value_counts(dropna=False).to_string())
    print()
    print("Image count distribution:")
    print(df["image_count"].value_counts(dropna=False).sort_index().to_string())
    print()
    print("Missing report fields:")
    print(f"  report: {df['report'].isna().sum()}")
    print(f"  section_impression: {df['section_impression'].isna().sum()}")

    if "section_findings" in df.columns:
        print(f"  section_findings: {df['section_findings'].isna().sum()}")

    print()
    print("First 5 studies:")
    print(
        df[
            [
                "study_key",
                "deid_patient_id",
                "split",
                "age",
                "sex",
                "image_count",
            ]
        ]
        .head()
        .to_string(index=False)
    )


def main():
    args = parse_args()

    df = pd.read_csv(args.manifest_path)

    validate_manifest(
        df=df,
        expected_studies=args.expected_studies,
    )

    print_summary(df)


if __name__ == "__main__":
    main()

