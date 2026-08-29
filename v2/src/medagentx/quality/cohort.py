"""Apply per-view quality decisions to the study cohort."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

KEEP_DECISIONS = frozenset({"pass", "review_with_technical_warning"})

_IDENTITY_COLUMNS = ("study_key", "deid_patient_id", "dicom_path")


def _require_columns(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    frame_name: str,
) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(
            f"{frame_name} missing required columns {missing}. "
            f"Available: {list(frame.columns)}"
        )


def apply_view_quality_filter(
    eligible_rows: pd.DataFrame,
    decisions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Drop failed views and retain studies with at least one usable view.

    Returns:
      quality_eligible_rows: pass/warning views only
      failed_views: failed view decisions
      study_summary: one row per input study, including all-view-fail decisions
    """
    _require_columns(eligible_rows, _IDENTITY_COLUMNS, "eligible_rows")
    _require_columns(
        decisions,
        _IDENTITY_COLUMNS + ("quality_decision", "quality_reason"),
        "quality_decisions",
    )

    if eligible_rows.empty:
        raise ValueError("eligible_rows must be non-empty")
    if eligible_rows["dicom_path"].astype(str).duplicated().any():
        raise ValueError("eligible_rows contains duplicate dicom_path values")
    if decisions["dicom_path"].astype(str).duplicated().any():
        raise ValueError("quality_decisions contains duplicate dicom_path values")

    decision_columns = [
        "dicom_path",
        "quality_decision",
        "quality_reason",
        "quality_policy_version",
    ]
    merged = eligible_rows.merge(
        decisions[decision_columns],
        on="dicom_path",
        how="left",
        validate="one_to_one",
    )
    if merged["quality_decision"].isna().any():
        missing_paths = merged.loc[
            merged["quality_decision"].isna(), "dicom_path"
        ].astype(str)
        raise ValueError(
            "Missing quality decisions for DICOM paths: "
            f"{missing_paths.head(10).tolist()}"
        )

    keep_mask = merged["quality_decision"].isin(KEEP_DECISIONS)
    quality_eligible = merged.loc[keep_mask].copy().reset_index(drop=True)
    failed_views = decisions.loc[
        decisions["quality_decision"].astype(str) == "fail"
    ].copy().reset_index(drop=True)

    summary_rows: list[dict[str, object]] = []
    for study_key, study_rows in merged.groupby("study_key", sort=False):
        usable = study_rows["quality_decision"].isin(KEEP_DECISIONS)
        failed = study_rows["quality_decision"].astype(str) == "fail"
        failed_paths = study_rows.loc[failed, "dicom_path"].astype(str).tolist()
        kept_paths = study_rows.loc[usable, "dicom_path"].astype(str).tolist()
        all_views_failed = bool(failed.all())

        summary_rows.append(
            {
                "study_key": str(study_key),
                "deid_patient_id": str(study_rows.iloc[0]["deid_patient_id"]),
                "input_view_count": int(len(study_rows)),
                "kept_view_count": int(usable.sum()),
                "failed_view_count": int(failed.sum()),
                "all_views_failed": all_views_failed,
                "study_quality_status": (
                    "fail_all_views"
                    if all_views_failed
                    else (
                        "kept_with_failed_views"
                        if bool(failed.any())
                        else "kept_all_views"
                    )
                ),
                "kept_dicom_paths": ";".join(kept_paths),
                "failed_dicom_paths": ";".join(failed_paths),
            }
        )

    study_summary = pd.DataFrame(summary_rows)
    return quality_eligible, failed_views, study_summary


def write_quality_artifacts(
    output_root: str | Path,
    *,
    decisions: pd.DataFrame,
    quality_eligible_rows: pd.DataFrame,
    failed_views: pd.DataFrame,
    study_summary: pd.DataFrame,
) -> dict[str, Path]:
    """Write all quality outputs under one stage-specific directory."""
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)

    paths = {
        "view_decisions": root / "view_quality_decisions.csv",
        "eligible_rows": root / "eligible_dicom_rows.csv",
        "failed_views": root / "failed_views.csv",
        "study_summary": root / "study_quality_summary.csv",
        "dropped_studies": root / "dropped_studies.csv",
        "summary": root / "quality_summary.csv",
    }

    dropped_studies = study_summary.loc[
        study_summary["all_views_failed"].astype(bool)
    ].copy()
    summary = {
        "input_views": int(len(decisions)),
        "pass_views": int(
            (decisions["quality_decision"].astype(str) == "pass").sum()
        ),
        "warning_views": int(
            (
                decisions["quality_decision"].astype(str)
                == "review_with_technical_warning"
            ).sum()
        ),
        "failed_views": int(len(failed_views)),
        "input_studies": int(len(study_summary)),
        "kept_studies": int((~study_summary["all_views_failed"]).sum()),
        "dropped_studies": int(study_summary["all_views_failed"].sum()),
    }

    decisions.to_csv(paths["view_decisions"], index=False)
    quality_eligible_rows.to_csv(paths["eligible_rows"], index=False)
    failed_views.to_csv(paths["failed_views"], index=False)
    study_summary.to_csv(paths["study_summary"], index=False)
    dropped_studies.to_csv(paths["dropped_studies"], index=False)
    pd.DataFrame([summary]).to_csv(paths["summary"], index=False)
    return paths
