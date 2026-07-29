"""Label-gated cohort filtering and dropped-study auditing."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.data.findings_index import FindingsIndex
from medagentx.data.paths import path_to_image_key_from_row

DROP_REASON_MISSING_LABELS = "missing_labels"
DROP_REASON_CONFLICTING_FINDINGS = "conflicting_findings_records"
DROP_REASON_INVALID_LABEL_VALUE = "invalid_label_value"
DROP_REASON_ROW_LIMIT = "excluded_by_row_limit"

_REQUIRED_COLUMNS = (
    "study_key",
    "deid_patient_id",
    "dicom_path",
)


def _require_columns(df: pd.DataFrame, columns: tuple[str, ...], frame_name: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(
            f"{frame_name} missing required columns {missing}. "
            f"Available: {list(df.columns)}"
        )


def _study_order(df: pd.DataFrame) -> list[str]:
    return list(dict.fromkeys(df["study_key"].astype(str).tolist()))


def limit_to_whole_studies(
    eligible_rows: pd.DataFrame,
    *,
    max_rows: int | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep only whole studies and stop before exceeding max_rows."""
    if max_rows is None:
        return eligible_rows.copy(), pd.DataFrame()
    if max_rows <= 0:
        raise ValueError("max_rows must be > 0 when provided")

    _require_columns(eligible_rows, ("study_key",), "eligible_rows")
    kept_frames: list[pd.DataFrame] = []
    dropped_rows: list[dict[str, Any]] = []
    used_rows = 0

    for study_key in _study_order(eligible_rows):
        study_rows = eligible_rows[
            eligible_rows["study_key"].astype(str) == study_key
        ].copy()
        view_count = len(study_rows)
        if used_rows + view_count > max_rows:
            dropped_rows.append(
                _dropped_study_row(
                    study_rows=study_rows,
                    reason=DROP_REASON_ROW_LIMIT,
                    detail=(
                        f"Keeping whole studies only; adding {view_count} views "
                        f"would exceed max_rows={max_rows}."
                    ),
                )
            )
            continue

        kept_frames.append(study_rows)
        used_rows += view_count

    kept = (
        pd.concat(kept_frames, ignore_index=True)
        if kept_frames
        else pd.DataFrame(columns=eligible_rows.columns)
    )
    dropped = pd.DataFrame(dropped_rows)
    return kept.reset_index(drop=True), dropped


def apply_label_gated_cohort(
    eligible_rows: pd.DataFrame,
    findings_index: FindingsIndex,
    *,
    max_rows: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep only studies whose every view has valid findings labels.

    Locked rules:
      1. Every view must have a findings_fixed.json record.
      2. Conflicting duplicate findings records drop the whole study.
      3. Invalid label values drop the whole study.
      4. max_rows keeps whole studies only.
    """
    _require_columns(eligible_rows, _REQUIRED_COLUMNS, "eligible_rows")
    if eligible_rows.empty:
        raise ValueError("eligible_rows must be non-empty")

    kept_frames: list[pd.DataFrame] = []
    dropped_rows: list[dict[str, Any]] = []

    for study_key in _study_order(eligible_rows):
        study_rows = eligible_rows[
            eligible_rows["study_key"].astype(str) == study_key
        ].copy()

        drop_reason, detail, missing_paths = _evaluate_study_labels(
            study_rows,
            findings_index,
        )
        if drop_reason is not None:
            dropped_rows.append(
                _dropped_study_row(
                    study_rows=study_rows,
                    reason=drop_reason,
                    detail=detail,
                    missing_paths=missing_paths,
                )
            )
            continue

        kept_frames.append(study_rows)

    kept = (
        pd.concat(kept_frames, ignore_index=True)
        if kept_frames
        else pd.DataFrame(columns=eligible_rows.columns)
    )
    kept = kept.reset_index(drop=True)

    kept, row_limit_dropped = limit_to_whole_studies(kept, max_rows=max_rows)
    if not row_limit_dropped.empty:
        dropped_rows.extend(row_limit_dropped.to_dict(orient="records"))

    dropped = pd.DataFrame(dropped_rows)
    if kept.empty and (dropped.empty or len(dropped) == 0):
        raise ValueError("Label-gated cohort produced no kept or dropped studies")
    return kept, dropped


def summarize_label_gated_cohort(
    eligible_rows: pd.DataFrame,
    kept_rows: pd.DataFrame,
    dropped_rows: pd.DataFrame,
) -> dict[str, int]:
    """Return a compact summary for CLI output."""
    input_studies = len(_study_order(eligible_rows)) if not eligible_rows.empty else 0
    kept_studies = len(_study_order(kept_rows)) if not kept_rows.empty else 0
    dropped_studies = (
        len(dropped_rows["study_key"].astype(str).unique())
        if not dropped_rows.empty and "study_key" in dropped_rows.columns
        else 0
    )
    return {
        "input_rows": int(len(eligible_rows)),
        "input_studies": input_studies,
        "kept_rows": int(len(kept_rows)),
        "kept_studies": kept_studies,
        "dropped_studies": dropped_studies,
        "dropped_rows": int(len(dropped_rows)),
    }


def load_findings_for_cohort(
    findings_path: str | Path,
    eligible_rows: pd.DataFrame,
) -> FindingsIndex:
    """Load only the findings records needed for one cohort."""
    keys = [
        path_to_image_key_from_row(row)
        for _, row in eligible_rows.iterrows()
    ]
    return FindingsIndex.subset_for_paths(findings_path, keys)


def write_label_gated_cohort_artifacts(
    output_root: str | Path,
    *,
    eligible_rows: pd.DataFrame,
    kept_rows: pd.DataFrame,
    dropped_rows: pd.DataFrame,
) -> dict[str, Path]:
    """Persist the canonical Stage A cohort tables."""
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)

    eligible_csv = root / "eligible_dicom_rows.csv"
    dropped_csv = root / "dropped_studies.csv"
    summary_csv = root / "cohort_summary.csv"

    kept_rows.to_csv(eligible_csv, index=False)
    dropped_rows.to_csv(dropped_csv, index=False)

    summary = summarize_label_gated_cohort(eligible_rows, kept_rows, dropped_rows)
    pd.DataFrame([summary]).to_csv(summary_csv, index=False)

    return {
        "eligible_csv": eligible_csv,
        "dropped_csv": dropped_csv,
        "summary_csv": summary_csv,
    }


def _evaluate_study_labels(
    study_rows: pd.DataFrame,
    findings_index: FindingsIndex,
) -> tuple[str | None, str, list[str]]:
    missing_paths: list[str] = []
    invalid_details: list[str] = []
    conflicting_paths: list[str] = []

    for _, row in study_rows.iterrows():
        join_key = path_to_image_key_from_row(row)
        if not join_key:
            missing_paths.append("<missing_path_to_image>")
            continue
        if findings_index.has_conflict(join_key):
            conflicting_paths.append(join_key)
            continue
        if findings_index.get(join_key) is None:
            missing_paths.append(join_key)
            continue

        raw_map = findings_index.build_view_raw_map(join_key)
        if raw_map is None:
            missing_paths.append(join_key)
            continue

        error = findings_index.validate_view_raw_map(raw_map)
        if error is not None:
            invalid_details.append(f"{join_key}: {error}")

    if conflicting_paths:
        return (
            DROP_REASON_CONFLICTING_FINDINGS,
            "Conflicting duplicate findings_fixed.json records.",
            sorted(set(conflicting_paths)),
        )
    if missing_paths:
        return (
            DROP_REASON_MISSING_LABELS,
            "One or more study views are missing findings labels.",
            sorted(set(missing_paths)),
        )
    if invalid_details:
        return (
            DROP_REASON_INVALID_LABEL_VALUE,
            "; ".join(invalid_details),
            [],
        )
    return None, "", []


def _dropped_study_row(
    *,
    study_rows: pd.DataFrame,
    reason: str,
    detail: str,
    missing_paths: list[str] | None = None,
) -> dict[str, Any]:
    study_key = str(study_rows.iloc[0]["study_key"])
    patient_id = str(study_rows.iloc[0]["deid_patient_id"])
    return {
        "study_key": study_key,
        "deid_patient_id": patient_id,
        "reason": reason,
        "view_count": int(len(study_rows)),
        "missing_path_to_images": ";".join(missing_paths or []),
        "detail": detail,
    }
