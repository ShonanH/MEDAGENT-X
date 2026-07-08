import argparse
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


LABEL_TO_SCORE = {
    "good": 4.25,
    "usable": 3.25,
    "review": 2.25,
    "uncertain": 3.00,
}


LABEL_TO_GATE = {
    "good": "proceed",
    "usable": "review",
    "review": "review",
    "uncertain": "review",
}


SEVERE_HINTS = {
    "limited",
    "suboptimal",
    "motion",
    "underpenetrated",
    "overpenetrated",
}


MODERATE_HINTS = {
    "rotation",
    "rotated",
    "low_lung_volume",
    "low lung volume",
    "low lung volumes",
    "poor_inspiration",
    "poor inspiration",
    "shallow inspiration",
    "expiratory",
}


MILD_HINTS = {
    "portable",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create image quality labels and 0-5 scores from CheXpert Plus artifact features."
    )

    parser.add_argument(
        "--artifact-path",
        type=Path,
        default=PROJECT_ROOT
        / "outputs"
        / "chexpert_plus"
        / "chexpert_plus_50_artifact_features.csv",
    )

    parser.add_argument(
        "--output-path",
        type=Path,
        default=PROJECT_ROOT
        / "outputs"
        / "chexpert_plus"
        / "chexpert_plus_50_image_quality_scores.csv",
    )

    return parser.parse_args()


def clip01(values):
    return np.clip(values, 0.0, 1.0)


def percentile_score(series, higher_is_better=True):
    lower = float(series.quantile(0.05))
    upper = float(series.quantile(0.95))

    if upper <= lower:
        return pd.Series(np.ones(len(series)), index=series.index)

    score = (series - lower) / (upper - lower)
    score = clip01(score)

    if not higher_is_better:
        score = 1.0 - score

    return score


def centered_score(series):
    lower = float(series.quantile(0.05))
    upper = float(series.quantile(0.95))
    center = float(series.median())

    radius = max(abs(center - lower), abs(upper - center))

    if radius <= 0:
        return pd.Series(np.ones(len(series)), index=series.index)

    score = 1.0 - (abs(series - center) / radius)

    return clip01(score)


def normalize_hints(value):
    if pd.isna(value) or str(value).strip() == "":
        return []

    hints = []

    for hint in str(value).split("|"):
        hint = hint.strip().lower()

        if hint in ("low lung volume", "low lung volumes"):
            hint = "low_lung_volume"

        if hint in ("rotated", "rotation"):
            hint = "rotation"

        if hint in ("poor inspiration", "shallow inspiration"):
            hint = "poor_inspiration"

        if hint:
            hints.append(hint)

    return sorted(set(hints))


def tier_from_score(score):
    if score >= 0.67:
        return "good"

    if score >= 0.34:
        return "usable"

    return "review"


def report_tier_from_hints(hints):
    if any(hint in SEVERE_HINTS for hint in hints):
        return "review"

    if any(hint in MODERATE_HINTS for hint in hints):
        return "usable"

    return "good"


def acquisition_tier(row):
    min_dimension = min(float(row["rows"]), float(row["columns"]))
    view_position = str(row.get("view_position", "")).upper()
    hints = row["normalized_quality_hints_list"]

    if min_dimension < 1000:
        return "review"

    if view_position not in ("AP", "PA"):
        return "review"

    if "portable" in hints:
        return "usable"

    return "good"


def final_quality_label(pixel_tier, report_tier, acquisition_tier_value):
    signals = [pixel_tier, report_tier, acquisition_tier_value]
    counts = Counter(signals)

    if counts["review"] >= 2:
        return "review"

    if counts["good"] >= 2 and counts["review"] == 0:
        return "good"

    if counts["usable"] >= 2 and counts["review"] == 0:
        return "usable"

    if "review" in signals and "good" in signals:
        return "uncertain"

    if "review" in signals:
        return "review"

    return "usable"


def confidence_from_signals(pixel_tier, report_tier, acquisition_tier_value):
    signals = [pixel_tier, report_tier, acquisition_tier_value]
    most_common_count = Counter(signals).most_common(1)[0][1]

    return round(most_common_count / len(signals), 4)


def main():
    args = parse_args()

    df = pd.read_csv(args.artifact_path)

    required_columns = [
        "study_key",
        "dicom_path",
        "view_position",
        "rows",
        "columns",
        "contrast_proxy",
        "noise_proxy",
        "sharpness_proxy",
        "intensity_mean",
        "entropy",
        "quality_hints",
    ]

    missing_columns = [column for column in required_columns if column not in df.columns]

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    df["sharpness_score"] = percentile_score(
        df["sharpness_proxy"],
        higher_is_better=True,
    )

    df["contrast_score"] = percentile_score(
        df["contrast_proxy"],
        higher_is_better=True,
    )

    df["noise_score"] = percentile_score(
        df["noise_proxy"],
        higher_is_better=False,
    )

    df["exposure_score"] = centered_score(
        df["intensity_mean"],
    )

    df["entropy_score"] = percentile_score(
        df["entropy"],
        higher_is_better=True,
    )

    df["pixel_quality_score"] = (
        0.30 * df["sharpness_score"]
        + 0.25 * df["contrast_score"]
        + 0.20 * df["noise_score"]
        + 0.15 * df["exposure_score"]
        + 0.10 * df["entropy_score"]
    )

    df["pixel_quality_tier"] = df["pixel_quality_score"].apply(tier_from_score)

    df["normalized_quality_hints_list"] = df["quality_hints"].apply(normalize_hints)

    df["normalized_quality_hints"] = df["normalized_quality_hints_list"].apply(
        lambda hints: "|".join(hints)
    )

    df["report_quality_tier"] = df["normalized_quality_hints_list"].apply(
        report_tier_from_hints
    )

    df["acquisition_quality_tier"] = df.apply(acquisition_tier, axis=1)

    df["image_quality_label"] = df.apply(
        lambda row: final_quality_label(
            row["pixel_quality_tier"],
            row["report_quality_tier"],
            row["acquisition_quality_tier"],
        ),
        axis=1,
    )

    df["image_quality_score_0_5"] = df["image_quality_label"].map(LABEL_TO_SCORE)

    df["image_quality_confidence"] = df.apply(
        lambda row: confidence_from_signals(
            row["pixel_quality_tier"],
            row["report_quality_tier"],
            row["acquisition_quality_tier"],
        ),
        axis=1,
    )

    df["quality_gate"] = df["image_quality_label"].map(LABEL_TO_GATE)

    df["pixel_quality_score"] = df["pixel_quality_score"].round(4)
    df["image_quality_score_0_5"] = df["image_quality_score_0_5"].round(4)

    df = df.drop(columns=["normalized_quality_hints_list"])

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output_path, index=False)

    print("Image quality score export complete.")
    print("Rows exported:", len(df))
    print("Saved to:", args.output_path)
    print()

    print("Image quality label counts:")
    print(df["image_quality_label"].value_counts(dropna=False))
    print()

    print("Quality gate counts:")
    print(df["quality_gate"].value_counts(dropna=False))
    print()

    print("Score summary:")
    print(df["image_quality_score_0_5"].describe())
    print()

    print("Tier breakdown:")
    print(
        df[
            [
                "study_key",
                "pixel_quality_tier",
                "report_quality_tier",
                "acquisition_quality_tier",
                "image_quality_label",
                "image_quality_score_0_5",
                "image_quality_confidence",
                "quality_gate",
                "normalized_quality_hints",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()