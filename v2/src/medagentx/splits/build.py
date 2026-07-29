"""Build auditable patient/study/view split tables from a quality cohort."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from medagentx.splits.assign import assign_patient_split
from medagentx.splits.constants import (
    ALL_SPLITS,
    SPLIT_POLICY_VERSION,
    SPLIT_SEED,
    TEST_RATIO,
    TRAIN_RATIO,
    VAL_RATIO,
)

_REQUIRED_COLUMNS = ("deid_patient_id", "study_key", "dicom_path")


def _require_columns(df: pd.DataFrame, columns: tuple[str, ...], name: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(
            f"{name} missing required columns {missing}. "
            f"Available: {list(df.columns)}"
        )


def build_patient_split_table(
    eligible_rows: pd.DataFrame,
    *,
    seed: int = SPLIT_SEED,
) -> pd.DataFrame:
    """Return one row per patient with a locked split assignment."""
    _require_columns(eligible_rows, ("deid_patient_id",), "eligible_rows")
    if eligible_rows.empty:
        raise ValueError("eligible_rows must be non-empty")

    patients = list(
        dict.fromkeys(eligible_rows["deid_patient_id"].astype(str).str.strip().tolist())
    )
    if any(not patient or patient.lower() == "nan" for patient in patients):
        raise ValueError("eligible_rows contains blank deid_patient_id values")

    rows: list[dict[str, Any]] = []
    for patient_id in patients:
        study_count = int(
            eligible_rows.loc[
                eligible_rows["deid_patient_id"].astype(str).str.strip() == patient_id,
                "study_key",
            ]
            .astype(str)
            .nunique()
        )
        view_count = int(
            (
                eligible_rows["deid_patient_id"].astype(str).str.strip() == patient_id
            ).sum()
        )
        rows.append(
            {
                "deid_patient_id": patient_id,
                "split": assign_patient_split(patient_id, seed=seed),
                "study_count": study_count,
                "view_count": view_count,
                "split_seed": seed,
                "split_policy_version": SPLIT_POLICY_VERSION,
            }
        )

    return pd.DataFrame(rows)


def build_study_split_table(
    eligible_rows: pd.DataFrame,
    patient_splits: pd.DataFrame,
) -> pd.DataFrame:
    """Propagate patient splits to unique study_key rows."""
    _require_columns(eligible_rows, ("deid_patient_id", "study_key"), "eligible_rows")
    _require_columns(
        patient_splits,
        ("deid_patient_id", "split"),
        "patient_splits",
    )

    studies = (
        eligible_rows[["study_key", "deid_patient_id"]]
        .astype(str)
        .drop_duplicates(subset=["study_key"], keep="first")
        .copy()
    )
    studies["deid_patient_id"] = studies["deid_patient_id"].str.strip()
    studies["study_key"] = studies["study_key"].str.strip()

    lookup = patient_splits[["deid_patient_id", "split"]].copy()
    lookup["deid_patient_id"] = lookup["deid_patient_id"].astype(str).str.strip()

    merged = studies.merge(lookup, on="deid_patient_id", how="left", validate="many_to_one")
    if merged["split"].isna().any():
        missing = merged.loc[merged["split"].isna(), "deid_patient_id"].tolist()
        raise ValueError(f"Missing patient splits for: {missing[:10]}")

    merged["split_policy_version"] = SPLIT_POLICY_VERSION
    return merged.reset_index(drop=True)


def build_view_split_table(
    eligible_rows: pd.DataFrame,
    patient_splits: pd.DataFrame,
) -> pd.DataFrame:
    """Attach patient split labels to every quality-eligible view."""
    _require_columns(eligible_rows, _REQUIRED_COLUMNS, "eligible_rows")
    _require_columns(
        patient_splits,
        ("deid_patient_id", "split"),
        "patient_splits",
    )

    views = eligible_rows.copy()
    views["deid_patient_id"] = views["deid_patient_id"].astype(str).str.strip()
    views["study_key"] = views["study_key"].astype(str).str.strip()
    views["dicom_path"] = views["dicom_path"].astype(str).str.strip()

    lookup = patient_splits[["deid_patient_id", "split"]].copy()
    lookup["deid_patient_id"] = lookup["deid_patient_id"].astype(str).str.strip()

    merged = views.merge(lookup, on="deid_patient_id", how="left", validate="many_to_one")
    if merged["split"].isna().any():
        missing = merged.loc[merged["split"].isna(), "deid_patient_id"].tolist()
        raise ValueError(f"Missing patient splits for: {missing[:10]}")

    merged["split_policy_version"] = SPLIT_POLICY_VERSION
    return merged.reset_index(drop=True)


def summarize_splits(
    patient_splits: pd.DataFrame,
    study_splits: pd.DataFrame,
    view_splits: pd.DataFrame,
) -> dict[str, int | float | str]:
    """Return a compact summary for CLI/audit output."""
    summary: dict[str, int | float | str] = {
        "patients": int(len(patient_splits)),
        "studies": int(len(study_splits)),
        "views": int(len(view_splits)),
        "split_seed": SPLIT_SEED,
        "train_ratio": TRAIN_RATIO,
        "val_ratio": VAL_RATIO,
        "test_ratio": TEST_RATIO,
        "split_policy_version": SPLIT_POLICY_VERSION,
    }
    for split_name in ALL_SPLITS:
        summary[f"patients_{split_name}"] = int(
            (patient_splits["split"].astype(str) == split_name).sum()
        )
        summary[f"studies_{split_name}"] = int(
            (study_splits["split"].astype(str) == split_name).sum()
        )
        summary[f"views_{split_name}"] = int(
            (view_splits["split"].astype(str) == split_name).sum()
        )
    return summary


def write_split_artifacts(
    output_root: str | Path,
    *,
    patient_splits: pd.DataFrame,
    study_splits: pd.DataFrame,
    view_splits: pd.DataFrame,
) -> dict[str, Path]:
    """Persist the canonical split tables under one stage directory."""
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)

    paths = {
        "patient_splits": root / "patient_splits.csv",
        "study_splits": root / "study_splits.csv",
        "view_splits": root / "view_splits.csv",
        "summary": root / "split_summary.csv",
    }

    patient_splits.to_csv(paths["patient_splits"], index=False)
    study_splits.to_csv(paths["study_splits"], index=False)
    view_splits.to_csv(paths["view_splits"], index=False)
    pd.DataFrame(
        [summarize_splits(patient_splits, study_splits, view_splits)]
    ).to_csv(paths["summary"], index=False)
    return paths


def build_and_write_splits(
    eligible_rows: pd.DataFrame,
    output_root: str | Path,
    *,
    seed: int = SPLIT_SEED,
) -> dict[str, Path]:
    """End-to-end split build for the quality-passed cohort."""
    patient_splits = build_patient_split_table(eligible_rows, seed=seed)
    study_splits = build_study_split_table(eligible_rows, patient_splits)
    view_splits = build_view_split_table(eligible_rows, patient_splits)
    return write_split_artifacts(
        output_root,
        patient_splits=patient_splits,
        study_splits=study_splits,
        view_splits=view_splits,
    )
