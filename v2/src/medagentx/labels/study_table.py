"""Build study-level label tables from eligible cohort rows."""

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
from medagentx.labels.builder import build_study_label_bundle
from medagentx.labels.schema import study_bundle_to_row

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


def representative_dicom_path(study_rows: pd.DataFrame) -> str:
    """Return the locked representative study path: frontal first, else first view."""
    if "frontal_lateral" in study_rows.columns:
        frontal = study_rows[
            study_rows["frontal_lateral"].astype(str).str.lower() == "frontal"
        ]
        if not frontal.empty:
            return str(frontal.iloc[0]["dicom_path"]).strip()

    return str(study_rows.iloc[0]["dicom_path"]).strip()


def build_study_label_table(
    eligible_rows: pd.DataFrame,
    findings_index: FindingsIndex,
) -> pd.DataFrame:
    """Build one auditable study-level label row per study_key.

    The input cohort must already be label-gated. Each study contributes one
    or more per-view raw maps that are aggregated by build_study_label_bundle.
    """
    _require_columns(eligible_rows, _REQUIRED_COLUMNS, "eligible_rows")
    if eligible_rows.empty:
        raise ValueError("eligible_rows must be non-empty")

    study_keys = list(dict.fromkeys(eligible_rows["study_key"].astype(str).tolist()))
    rows: list[dict[str, Any]] = []

    for study_key in study_keys:
        study_rows = eligible_rows[
            eligible_rows["study_key"].astype(str) == study_key
        ].copy()
        view_raw_maps = []
        for _, row in study_rows.iterrows():
            join_key = path_to_image_key_from_row(row)
            raw_map = findings_index.build_view_raw_map(join_key)
            if raw_map is None:
                raise ValueError(
                    f"Study {study_key!r} is missing findings for {join_key!r}. "
                    "Run label-gated cohort filtering before building labels."
                )
            view_raw_maps.append(raw_map)

        bundle = build_study_label_bundle(
            study_key=study_key,
            deid_patient_id=str(study_rows.iloc[0]["deid_patient_id"]),
            dicom_path=representative_dicom_path(study_rows),
            view_raw_maps=view_raw_maps,
        )
        out = study_bundle_to_row(bundle)
        out["view_count"] = int(len(study_rows))
        rows.append(out)

    return pd.DataFrame(rows)
