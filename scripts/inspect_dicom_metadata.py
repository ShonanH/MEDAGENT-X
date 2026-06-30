import argparse
from pathlib import Path

import pandas as pd
import pydicom
import redivis


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DICOM_TRAIN_TABLE = "aimi.chexpert_plus:5yyj:v1_0.dicom_train:1934"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Inspect all readable metadata from one CheXpert Plus DICOM."
    )

    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=PROJECT_ROOT
        / "data"
        / "processed"
        / "chexpert_plus_50_study_manifest.csv",
        help="Path to the study-level manifest CSV.",
    )

    parser.add_argument(
        "--row-index",
        type=int,
        default=0,
        help="Manifest row index to inspect.",
    )

    parser.add_argument(
        "--output-path",
        type=Path,
        default=PROJECT_ROOT
        / "outputs"
        / "chexpert_plus_dicom_metadata"
        / "dicom_metadata_row0.txt",
        help="Where to save the metadata text output.",
    )

    return parser.parse_args()


def get_first_dicom_path(dicom_paths):
    first_path = str(dicom_paths).split("|")[0]

    if first_path.startswith("train/"):
        first_path = first_path.removeprefix("train/")

    return first_path


def format_data_element(element):
    tag = str(element.tag)
    keyword = element.keyword or ""
    name = element.name
    vr = element.VR

    if element.VR == "SQ":
        value = f"<Sequence with {len(element.value)} item(s)>"
    elif element.keyword == "PixelData":
        value = "<PixelData skipped>"
    else:
        value = str(element.value)

    return f"{tag} | {keyword} | {name} | {vr} | {value}"


def main():
    args = parse_args()

    manifest = pd.read_csv(args.manifest_path)

    if args.row_index < 0 or args.row_index >= len(manifest):
        raise IndexError(
            f"row-index must be between 0 and {len(manifest) - 1}."
        )

    row = manifest.iloc[args.row_index]
    redivis_dicom_path = get_first_dicom_path(row["dicom_paths"])

    table = redivis.table(DICOM_TRAIN_TABLE)
    dicom_file = table.file(redivis_dicom_path)

    with dicom_file.open("rb") as f:
        ds = pydicom.dcmread(f, stop_before_pixels=True)

    output_lines = []

    output_lines.append("MEDAGENT-X CheXpert Plus DICOM Metadata Inspection")
    output_lines.append("=" * 70)
    output_lines.append(f"Study key: {row['study_key']}")
    output_lines.append(f"Manifest DICOM path: {row['dicom_paths']}")
    output_lines.append(f"Redivis DICOM path: {redivis_dicom_path}")
    output_lines.append("")
    output_lines.append("FILE META")
    output_lines.append("-" * 70)

    if hasattr(ds, "file_meta"):
        for element in ds.file_meta:
            output_lines.append(format_data_element(element))
    else:
        output_lines.append("No file_meta found.")

    output_lines.append("")
    output_lines.append("DATASET METADATA")
    output_lines.append("-" * 70)

    for element in ds:
        if element.keyword == "PixelData":
            continue

        output_lines.append(format_data_element(element))

    args.output_path.parent.mkdir(parents=True, exist_ok=True)

    text = "\n".join(output_lines)

    args.output_path.write_text(text, encoding="utf-8")

    print(text)
    print()
    print(f"Saved metadata to: {args.output_path}")


if __name__ == "__main__":
    main()


# python scripts/inspect_dicom_metadata.py \
#   --manifest-path data/processed/chexpert_plus_50_study_manifest.csv \
#   --row-index 0