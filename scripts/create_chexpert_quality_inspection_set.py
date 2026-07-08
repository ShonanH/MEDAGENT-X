import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.helpers.chexpert_plus_dataset import CheXpertPlusDicomDataset


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create low/mid/high pseudo-quality inspection previews."
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
        "--pseudo-score-path",
        type=Path,
        default=PROJECT_ROOT
        / "outputs"
        / "chexpert_plus"
        / "chexpert_plus_50_pseudo_quality_scores.csv",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT
        / "outputs"
        / "chexpert_plus"
        / "pseudo_quality_inspection",
    )

    parser.add_argument(
        "--cases-per-group",
        type=int,
        default=5,
    )

    return parser.parse_args()


def image_to_uint8(image):
    image = np.asarray(image, dtype=np.float32)

    image_min = float(np.min(image))
    image_max = float(np.max(image))

    if image_max <= image_min:
        return np.zeros(image.shape, dtype=np.uint8)

    image = (image - image_min) / (image_max - image_min)
    image = image * 255.0

    return image.astype(np.uint8)


def select_inspection_cases(df, cases_per_group):
    score_col = "recommended_pseudo_quality_score_0_5"

    low = df.sort_values(score_col, ascending=True).head(cases_per_group).copy()
    low["inspection_group"] = "low"

    high = df.sort_values(score_col, ascending=False).head(cases_per_group).copy()
    high["inspection_group"] = "high"

    median_score = float(df[score_col].median())
    mid = df.copy()
    mid["distance_from_median"] = (mid[score_col] - median_score).abs()
    mid = mid.sort_values("distance_from_median", ascending=True).head(cases_per_group)
    mid = mid.copy()
    mid["inspection_group"] = "middle"

    selected = pd.concat([low, mid, high], ignore_index=True)

    selected = selected.drop_duplicates(subset=["study_key"], keep="first")

    return selected


def main():
    args = parse_args()

    scores_df = pd.read_csv(args.pseudo_score_path)

    required_columns = [
        "study_key",
        "dicom_path",
        "recommended_pseudo_quality_score_0_5",
        "recommended_quality_gate",
        "normalized_quality_hints",
        "sharpness_score",
        "contrast_score",
        "noise_score",
        "exposure_score",
    ]

    missing_columns = [
        column for column in required_columns if column not in scores_df.columns
    ]

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    selected = select_inspection_cases(
        df=scores_df,
        cases_per_group=args.cases_per_group,
    )

    dataset = CheXpertPlusDicomDataset(
        manifest_path=args.manifest_path,
        transform=None,
    )

    study_to_index = {}

    for idx in range(len(dataset.manifest)):
        row = dataset.manifest.iloc[idx]
        study_to_index[row["study_key"]] = idx

    preview_dir = args.output_dir / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)

    inspection_rows = []

    for _, row in selected.iterrows():
        study_key = row["study_key"]

        if study_key not in study_to_index:
            raise ValueError(f"Study key not found in manifest: {study_key}")

        sample = dataset[study_to_index[study_key]]

        image = sample["image"].squeeze(0).numpy()
        image_uint8 = image_to_uint8(image)

        safe_study_key = study_key.replace("/", "_")
        preview_path = preview_dir / f"{row['inspection_group']}_{safe_study_key}.png"

        Image.fromarray(image_uint8).save(preview_path)

        inspection_row = {
            "inspection_group": row["inspection_group"],
            "study_key": study_key,
            "dicom_path": sample["dicom_path"],
            "preview_path": str(preview_path),
            "recommended_pseudo_quality_score_0_5": row[
                "recommended_pseudo_quality_score_0_5"
            ],
            "recommended_quality_gate": row["recommended_quality_gate"],
            "normalized_quality_hints": row.get("normalized_quality_hints", ""),
            "sharpness_score": row["sharpness_score"],
            "contrast_score": row["contrast_score"],
            "noise_score": row["noise_score"],
            "exposure_score": row["exposure_score"],
            "view_position": sample["view_position"],
            "photometric": sample["photometric"],
        }

        inspection_rows.append(inspection_row)

        print(
            f"Saved {row['inspection_group']} preview:",
            study_key,
            "score:",
            row["recommended_pseudo_quality_score_0_5"],
        )

    inspection_df = pd.DataFrame(inspection_rows)

    inspection_csv_path = args.output_dir / "inspection_cases.csv"
    inspection_df.to_csv(inspection_csv_path, index=False)

    print()
    print("Inspection set created.")
    print("Rows:", len(inspection_df))
    print("CSV:", inspection_csv_path)
    print("Preview folder:", preview_dir)
    print()
    print(
        inspection_df[
            [
                "inspection_group",
                "study_key",
                "recommended_pseudo_quality_score_0_5",
                "recommended_quality_gate",
                "normalized_quality_hints",
                "preview_path",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()