import argparse
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUALITY_GATE_THRESHOLD = 3.5


HINT_PENALTIES = {
    "portable": 0.05,
    "low_lung_volume": 0.10,
    "rotation": 0.12,
    "motion": 0.20,
    "limited": 0.20,
    "suboptimal": 0.20,
    "underpenetrated": 0.20,
    "overpenetrated": 0.20,
    "poor_inspiration": 0.15,
    "expiratory": 0.15,
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create candidate pseudo 0-5 image-quality scores."
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
        / "chexpert_plus_50_pseudo_quality_scores.csv",
    )

    return parser.parse_args()

def clip01(values):
    return np.clip(values, 0.0, 1.0)

def percentile_score(series, higher_is_better=True):
    lower = float(series.quantile(0.05))
    upper = float(series.quantile(0.95))

    if upper <= lower:
        return pd.Series(np.ones(len(series)), index=series.index)

    score = (series - lower) / (upper-lower)
    score = clip01(score)

    if not higher_is_better:
        score = 1.0 - score

    return score

def centered_score(series):
    lower = float(series.quantile(0.05))
    center = float(series.median())
    upper = float(series.quantile(0.95))

    radius = max(abs(center - lower), abs(upper - center))

    if radius <= 0:
        return pd.Series(np.ones(len(series)), index=series.index)

    score = 1.0 - (abs(series - center) / radius)

    return clip01(score)

def normalize_quality_hints(value):
    if pd.isna(value) or str(value).strip() == "":
        return []

    normalized = []

    for hint in str(value).split("|"):
        hint = hint.strip().lower()

        if hint in ("low lung volume", "low lung volumes"):
            hint = "low_lung_volume"

        if hint in ("rotated", "rotation"):
            hint = "rotation"

        if hint in ("poor inspiration", "shallow inspiration"):
            hint = "poor_inspiration"

        if hint:
            normalized.append(hint)

    return sorted(set(normalized))



def compute_report_hint_score(hints):
    penalty = 0.0

    for hint in hints:
        penalty += HINT_PENALTIES.get(hint, 0.10)

    penalty = min(penalty, 0.50)

    return 1.0 - penalty


def add_gate(df, score_column, gate_column):
    df[gate_column] = np.where(df[score_column] >= QUALITY_GATE_THRESHOLD, "proceed", "review")

def main():
    args = parse_args()

    df = pd.read_csv(args.artifact_path)

    required_columns = [
        "study_key",
        "dicom_path",
        "contrast_proxy",
        "noise_proxy",
        "sharpness_proxy",
        "intensity_mean",
        "rows",
        "columns",
        "entropy",
        "quality_hints",
    ]

    missing_columns = [column for column in required_columns if column not in df.columns]

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    #Sub scores: all are 0-1 where 1 means best quality
    df["sharpness_score"] = percentile_score(
        df["sharpness_proxy"],
        higher_is_better = True
    )

    df["contrast_score"] = percentile_score(
        df["contrast_proxy"],
        higher_is_better = True
    )

    df["noise_score"] = percentile_score(
        df["noise_proxy"],
        higher_is_better=False
    )

    df["exposure_score"] = centered_score(
        df["intensity_mean"]
    )

    df["entropy_score"] = percentile_score(
        df["entropy"],
        higher_is_better = True
    )

    min_dimension = df[["rows", "columns"]].min(axis=1)

    df["resolution_score"] = percentile_score(
        min_dimension,
        higher_is_better=True
    )

    df["normalized_quality_hints"] = df["quality_hints"].apply(
        lambda value: "|".join(normalize_quality_hints(value))
    )

    df["report_hint_score"] = df["normalized_quality_hints"].apply(
        lambda value: compute_report_hint_score(value.split("|") if value else [])
    )

    # Balanced score
    df["pseudo_score_balanced_0_5"] = 5.0 * (
        0.20 * df["sharpness_score"]
        + 0.20 * df["contrast_score"]
        + 0.20 * df["noise_score"]
        + 0.15 * df["exposure_score"]
        + 0.15 * df["entropy_score"]
        + 0.10 * df["report_hint_score"]
    )

    # Artifact Sensitive score
    df["pseudo_score_artifact_sensitive_0_5"] = 5.0 * (
        0.30 * df["sharpness_score"]
        + 0.25 * df["noise_score"]
        + 0.20 * df["contrast_score"]
        + 0.10 * df["exposure_score"]
        + 0.05 * df["entropy_score"]
        + 0.10 * df["report_hint_score"]
    )

    # Conservative Clinical Gate score.
    df["pseudo_score_conservative_0_5"] = 5.0 * (
        0.25 * df["sharpness_score"]
        + 0.20 * df["contrast_score"]
        + 0.20 * df["noise_score"]
        + 0.15 * df["exposure_score"]
        + 0.10 * df["resolution_score"]
        + 0.10 * df["report_hint_score"]
    )

    score_columns = [
        "pseudo_score_balanced_0_5",
        "pseudo_score_artifact_sensitive_0_5",
        "pseudo_score_conservative_0_5",
    ]


    for column in score_columns:
        df[column] = df[column].round(4)

    add_gate(df, "pseudo_score_balanced_0_5", "quality_gate_balanced")
    add_gate(df, "pseudo_score_artifact_sensitive_0_5", "quality_gate_artifact_sensitive")
    add_gate(df, "pseudo_score_conservative_0_5", "quality_gate_conservative")

    # Using conservative score for now

    df["recommended_pseudo_quality_score_0_5"] =df["pseudo_score_conservative_0_5"]
    df["recommended_quality_gate"] = df["quality_gate_conservative"]

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output_path, index=False)

    print("Pseudo quality score export complete.")
    print("Rows exported:", len(df))
    print("Saved to:", args.output_path)
    print()

    print("Score summaries:")
    print(df[score_columns].describe())
    print()

    print("Gate counts:")
    print("Balanced:")
    print(df["quality_gate_balanced"].value_counts(dropna=False))
    print()
    print("Artifact-sensitive:")
    print(df["quality_gate_artifact_sensitive"].value_counts(dropna=False))
    print()
    print("Conservative:")
    print(df["quality_gate_conservative"].value_counts(dropna=False))
    print()

    print("Lowest conservative scores:")
    print(
        df[
            [
                "study_key",
                "pseudo_score_conservative_0_5",
                "quality_gate_conservative",
                "normalized_quality_hints",
            ]
        ]
        .sort_values("pseudo_score_conservative_0_5")
        .head(10)
        .to_string(index=False)
    )
    print()

    print("Highest conservative scores:")
    print(
        df[
            [
                "study_key",
                "pseudo_score_conservative_0_5",
                "quality_gate_conservative",
                "normalized_quality_hints",
            ]
        ]
        .sort_values("pseudo_score_conservative_0_5", ascending=False)
        .head(10)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()

































































    