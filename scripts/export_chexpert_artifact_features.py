import argparse
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.features.artifact_features import compute_artifact_features
from src.medagentx.helpers.chexpert_plus_dataset import CheXpertPlusDicomDataset


QUALITY_HINT_TERMS = [
    "limited",
    "suboptimal",
    "motion",
    "rotated",
    "rotation",
    "low volume",
    "low lung volume",
    "poor inspiration",
    "shallow inspiration",
    "expiratory",
    "underpenetrated",
    "overpenetrated",
    "portable",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export artifact features for CheXpert Plus DICOM images."
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
        "--output-path",
        type=Path,
        default=PROJECT_ROOT
        / "outputs"
        / "chexpert_plus"
        / "chexpert_plus_50_artifact_features.csv",
    )

    return parser.parse_args()

def find_quality_hints(*texts):
    combined_text = "".join(str(text) for text in texts if text is not None)
    combined_text = combined_text.lower()

    found_terms = []

    for term in QUALITY_HINT_TERMS:
        if term in combined_text:
            found_terms.append(term)

    return found_terms

def main():
    args = parse_args()
    dataset = CheXpertPlusDicomDataset(
        manifest_path = args.manifest_path,
        transform=None,
    )

    output_rows = []

    print("Dataset length: ", len(dataset))

    for idx in range(len(dataset)):
        sample = dataset[idx]

        image = sample["image"].squeeze(0).numpy()
        features = compute_artifact_features(image)

        quality_hints = find_quality_hints(
            sample.get("report", ""),
            sample.get("section_findings", ""),
            sample.get("section_impression",""),
        )

        row = {
            "study_key": sample["study_key"],
            "dicom_path": sample["dicom_path"],
            "deid_patient_id": sample["deid_patient_id"],
            "age": sample["age"],
            "sex": sample["sex"],
            "split": sample["split"],
            "image_count": sample["image_count"],
            "view_position": sample["view_position"],
            "photometric": sample["photometric"],
            "rows": sample["rows"],
            "columns": sample["columns"],
            "quality_hint_count": len(quality_hints),
            "quality_hints": "|".join(quality_hints),
        }

        row.update(features)
        output_rows.append(row)

        print(f"Processed {idx + 1}/{len(dataset)}: {sample['study_key']}")

    output_df = pd.DataFrame(output_rows)

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(args.output_path, index=False)

    print()
    print("Artifact feature export complete.")
    print("Rows exported:", len(output_df))
    print("Saved to:", args.output_path)
    print()
    print("Feature summary:")
    feature_columns = [
        "contrast_proxy",
        "noise_proxy",
        "blur_proxy",
        "sharpness_proxy",
        "edge_density",
        "entropy",
    ]
    print(output_df[feature_columns].describe())


if __name__ == "__main__":
    main()