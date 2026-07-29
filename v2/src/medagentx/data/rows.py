"""Fetch and filter eligible CheXpert Plus metadata rows for Stage A."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.data.catalog import (
    build_dicom_train_index_sql,
    build_metadata_train_sql,
)
from medagentx.data.paths import clean_dicom_path, study_key_from_path
from medagentx.data.redivis_client import RedivisClient

_DICOM_INDEX_PATH_COLUMNS = (
    "path",
    "file_path",
    "file_name",
    "filename",
    "name",
    "dicom_path",
    "path_to_dcm",
)


def _require_columns(df: pd.DataFrame, columns: list[str], frame_name: str) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(
            f"{frame_name} missing required columns {missing}. "
            f"Available: {list(df.columns)}"
        )


def _positive_limit(name: str, value: int | None) -> int | None:
    if value is None:
        return None
    if value <= 0:
        raise ValueError(f"{name} must be > 0 when provided")
    return value


def fetch_metadata_train_rows(
    client: RedivisClient,
    *,
    limit: int | None = None,
    max_results: int = 100000,
) -> pd.DataFrame:
    """Fetch train metadata rows with non-null path_to_dcm."""
    if not isinstance(client, RedivisClient):
        raise ValueError("client must be a RedivisClient")

    sql = build_metadata_train_sql(limit=limit)
    df = client.run_sql_query(sql, max_results=max_results)
    _require_columns(
        df,
        ["path_to_dcm", "path_to_image", "deid_patient_id", "split"],
        "metadata",
    )
    return df


def fetch_dicom_train_index(
    client: RedivisClient,
    *,
    limit: int | None = None,
    max_results: int = 500000,
) -> pd.DataFrame:
    """Fetch the train DICOM file index."""
    if not isinstance(client, RedivisClient):
        raise ValueError("client must be a RedivisClient")

    sql = build_dicom_train_index_sql(limit=limit)
    df = client.run_sql_query(sql, max_results=max_results)
    _require_columns(df, ["file_id"], "dicom_train_index")

    if not any(column in df.columns for column in _DICOM_INDEX_PATH_COLUMNS):
        raise ValueError(
            "dicom_train_index has no recognized path column. "
            f"Available: {list(df.columns)}"
        )
    return df


def _index_clean_path(row: pd.Series) -> str:
    for column in _DICOM_INDEX_PATH_COLUMNS:
        if column not in row.index:
            continue
        raw = row.get(column)
        if raw is None or pd.isna(raw) or not str(raw).strip():
            continue
        return clean_dicom_path(raw)
    raise ValueError("DICOM index row has no usable path value")


def build_dicom_file_id_lookup(index_df: pd.DataFrame) -> dict[str, str]:
    """Map cleaned DICOM path -> file_id."""
    _require_columns(index_df, ["file_id"], "dicom_train_index")

    lookup: dict[str, str] = {}
    for _, row in index_df.iterrows():
        file_id = str(row["file_id"]).strip()
        if not file_id or file_id.lower() == "nan":
            continue
        try:
            cleaned = _index_clean_path(row)
        except ValueError:
            continue
        # First file_id wins for duplicate paths.
        lookup.setdefault(cleaned, file_id)
    if not lookup:
        raise ValueError("DICOM index produced an empty path -> file_id lookup")
    return lookup


def apply_eligibility_limits(
    df: pd.DataFrame,
    *,
    max_patients: int | None = None,
    max_studies: int | None = None,
    max_rows: int | None = None,
) -> pd.DataFrame:
    """Apply optional Stage A cohort size limits."""
    max_patients = _positive_limit("max_patients", max_patients)
    max_studies = _positive_limit("max_studies", max_studies)
    max_rows = _positive_limit("max_rows", max_rows)

    out = df.copy()

    if max_patients is not None:
        _require_columns(out, ["deid_patient_id"], "eligible_rows")
        keep = list(dict.fromkeys(out["deid_patient_id"].astype(str).tolist()))
        keep = keep[:max_patients]
        out = out[out["deid_patient_id"].astype(str).isin(keep)].copy()

    if max_studies is not None:
        _require_columns(out, ["study_key"], "eligible_rows")
        keep = list(dict.fromkeys(out["study_key"].astype(str).tolist()))
        keep = keep[:max_studies]
        out = out[out["study_key"].astype(str).isin(keep)].copy()

    if max_rows is not None:
        out = out.head(max_rows).copy()

    return out.reset_index(drop=True)


def build_eligible_dicom_rows(
    metadata_df: pd.DataFrame,
    index_df: pd.DataFrame,
    *,
    max_patients: int | None = None,
    max_studies: int | None = None,
    max_rows: int | None = None,
) -> pd.DataFrame:
    """Filter metadata to rows downloadable from the DICOM train index.

    Locked Stage A rules:
      1. metadata already train + path_to_dcm present (from SQL)
      2. cleaned path_to_dcm exists in dicom_train index
      3. attach study_key + file_id
      4. optional max_patients / max_studies / max_rows
    """
    _require_columns(
        metadata_df,
        ["path_to_dcm", "path_to_image", "deid_patient_id", "split"],
        "metadata",
    )

    lookup = build_dicom_file_id_lookup(index_df)

    rows: list[dict[str, Any]] = []
    for _, row in metadata_df.iterrows():
        try:
            cleaned = clean_dicom_path(row["path_to_dcm"])
            study_key = study_key_from_path(cleaned)
        except ValueError:
            continue

        file_id = lookup.get(cleaned)
        if file_id is None:
            continue

        out = row.to_dict()
        out["dicom_path"] = cleaned
        out["study_key"] = study_key
        out["file_id"] = file_id
        rows.append(out)

    eligible = pd.DataFrame(rows)
    if eligible.empty:
        raise ValueError(
            "No eligible rows after requiring DICOM-index membership"
        )

    return apply_eligibility_limits(
        eligible,
        max_patients=max_patients,
        max_studies=max_studies,
        max_rows=max_rows,
    )


def fetch_eligible_dicom_rows(
    client: RedivisClient,
    *,
    metadata_limit: int | None = None,
    index_limit: int | None = None,
    max_patients: int | None = None,
    max_studies: int | None = None,
    max_rows: int | None = None,
    metadata_max_results: int = 100000,
    index_max_results: int = 500000,
) -> pd.DataFrame:
    """End-to-end Stage A fetch: metadata ∩ DICOM index."""
    metadata_df = fetch_metadata_train_rows(
        client,
        limit=metadata_limit,
        max_results=metadata_max_results,
    )
    index_df = fetch_dicom_train_index(
        client,
        limit=index_limit,
        max_results=index_max_results,
    )
    return build_eligible_dicom_rows(
        metadata_df,
        index_df,
        max_patients=max_patients,
        max_studies=max_studies,
        max_rows=max_rows,
    )
