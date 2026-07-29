"""Fetch and filter eligible CheXpert Plus metadata rows for Stage A."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.data.catalog import (
    METADATA_IDENTITY_COLUMNS,
    REPORT_COLUMNS,
    build_dicom_train_index_probe_sql,
    build_dicom_train_index_sql,
    build_metadata_reports_sql,
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

# Redivis rejects query results larger than 100MB on the rows endpoint, so every
# full-table read is paged with SQL LIMIT/OFFSET over a stable ORDER BY.
DEFAULT_METADATA_PAGE_SIZE = 50000
DEFAULT_INDEX_PAGE_SIZE = 100000
DEFAULT_REPORT_BATCH_SIZE = 500


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


def _fetch_paged(
    client: RedivisClient,
    build_sql: Callable[[int, int], str],
    *,
    limit: int | None,
    page_size: int,
    label: str,
) -> pd.DataFrame:
    """Read a table in LIMIT/OFFSET pages and concatenate the results."""
    if not isinstance(client, RedivisClient):
        raise ValueError("client must be a RedivisClient")
    if page_size <= 0:
        raise ValueError("page_size must be > 0")

    limit = _positive_limit("limit", limit)

    frames: list[pd.DataFrame] = []
    fetched = 0
    offset = 0

    while True:
        take = page_size if limit is None else min(page_size, limit - fetched)
        if take <= 0:
            break

        page = client.run_sql_query(build_sql(take, offset), max_results=take)
        if page.empty:
            break

        frames.append(page)
        fetched += len(page)
        offset += len(page)
        print(f"[{label}] fetched {fetched} rows")

        if len(page) < take:
            break

    if not frames:
        raise ValueError(f"{label} returned no rows")

    return pd.concat(frames, ignore_index=True)


def fetch_metadata_train_rows(
    client: RedivisClient,
    *,
    limit: int | None = None,
    page_size: int = DEFAULT_METADATA_PAGE_SIZE,
) -> pd.DataFrame:
    """Fetch train metadata identity rows with non-null path_to_dcm."""
    df = _fetch_paged(
        client,
        lambda take, offset: build_metadata_train_sql(
            limit=take,
            offset=offset,
            columns=METADATA_IDENTITY_COLUMNS,
        ),
        limit=limit,
        page_size=page_size,
        label="metadata",
    )
    _require_columns(
        df,
        ["path_to_dcm", "path_to_image", "deid_patient_id", "split"],
        "metadata",
    )
    return df


def resolve_dicom_index_path_column(client: RedivisClient) -> str:
    """Probe the DICOM file index and return its usable path column."""
    if not isinstance(client, RedivisClient):
        raise ValueError("client must be a RedivisClient")

    probe = client.run_sql_query(build_dicom_train_index_probe_sql(), max_results=5)
    _require_columns(probe, ["file_id"], "dicom_train_index")

    for column in _DICOM_INDEX_PATH_COLUMNS:
        if column not in probe.columns:
            continue
        values = probe[column].dropna().astype(str).str.strip()
        if not values.empty and (values != "").any():
            return column

    raise ValueError(
        "dicom_train_index has no recognized path column. "
        f"Available: {list(probe.columns)}"
    )


def fetch_dicom_train_index(
    client: RedivisClient,
    *,
    limit: int | None = None,
    page_size: int = DEFAULT_INDEX_PAGE_SIZE,
    path_column: str | None = None,
) -> pd.DataFrame:
    """Fetch the train DICOM file index as path + file_id pairs."""
    if path_column is None:
        path_column = resolve_dicom_index_path_column(client)

    df = _fetch_paged(
        client,
        lambda take, offset: build_dicom_train_index_sql(
            path_column=path_column,
            limit=take,
            offset=offset,
        ),
        limit=limit,
        page_size=page_size,
        label="dicom_index",
    )
    _require_columns(df, ["file_id", path_column], "dicom_train_index")
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


def attach_report_columns(
    client: RedivisClient,
    eligible_rows: pd.DataFrame,
    *,
    batch_size: int = DEFAULT_REPORT_BATCH_SIZE,
) -> pd.DataFrame:
    """Fetch report text for the eligible cohort only and join it back.

    Report columns are excluded from the eligibility scan because the full train
    split of report text exceeds the Redivis rows response limit.
    """
    if not isinstance(client, RedivisClient):
        raise ValueError("client must be a RedivisClient")
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    _require_columns(eligible_rows, ["path_to_dcm"], "eligible_rows")
    if eligible_rows.empty:
        raise ValueError("eligible_rows must be non-empty")

    paths = list(dict.fromkeys(eligible_rows["path_to_dcm"].astype(str).tolist()))

    frames: list[pd.DataFrame] = []
    for start in range(0, len(paths), batch_size):
        batch = paths[start : start + batch_size]
        page = client.run_sql_query(
            build_metadata_reports_sql(batch),
            max_results=len(batch),
        )
        if not page.empty:
            frames.append(page)
        print(f"[reports] fetched {min(start + batch_size, len(paths))}/{len(paths)}")

    if not frames:
        raise ValueError("No report rows returned for the eligible cohort")

    reports = pd.concat(frames, ignore_index=True)
    _require_columns(reports, ["path_to_dcm"], "metadata_reports")
    reports = reports.drop_duplicates(subset=["path_to_dcm"], keep="first")

    drop = [column for column in REPORT_COLUMNS if column in eligible_rows.columns]
    out = eligible_rows.drop(columns=drop) if drop else eligible_rows
    out = out.copy()
    out["path_to_dcm"] = out["path_to_dcm"].astype(str)
    reports["path_to_dcm"] = reports["path_to_dcm"].astype(str)

    return out.merge(reports, on="path_to_dcm", how="left")


def fetch_eligible_dicom_rows(
    client: RedivisClient,
    *,
    metadata_limit: int | None = None,
    index_limit: int | None = None,
    max_patients: int | None = None,
    max_studies: int | None = None,
    max_rows: int | None = None,
    metadata_page_size: int = DEFAULT_METADATA_PAGE_SIZE,
    index_page_size: int = DEFAULT_INDEX_PAGE_SIZE,
    include_reports: bool = True,
    report_batch_size: int = DEFAULT_REPORT_BATCH_SIZE,
) -> pd.DataFrame:
    """End-to-end Stage A fetch: metadata ∩ DICOM index (+ cohort reports)."""
    metadata_df = fetch_metadata_train_rows(
        client,
        limit=metadata_limit,
        page_size=metadata_page_size,
    )
    index_df = fetch_dicom_train_index(
        client,
        limit=index_limit,
        page_size=index_page_size,
    )
    eligible = build_eligible_dicom_rows(
        metadata_df,
        index_df,
        max_patients=max_patients,
        max_studies=max_studies,
        max_rows=max_rows,
    )
    if not include_reports:
        return eligible

    return attach_report_columns(
        client,
        eligible,
        batch_size=report_batch_size,
    )
