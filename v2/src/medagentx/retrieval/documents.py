"""Build study-level report payloads for the retrieval index."""

from __future__ import annotations

from typing import Any

import pandas as pd

from medagentx.retrieval.constants import (
    INDEX_METADATA_COLUMNS,
    REPORT_PAYLOAD_COLUMNS,
)

_REQUIRED_VIEW_COLUMNS = ("study_key", "deid_patient_id", *REPORT_PAYLOAD_COLUMNS)


def _require_columns(df: pd.DataFrame, columns: tuple[str, ...], name: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(
            f"{name} missing required columns {missing}. "
            f"Available: {list(df.columns)}"
        )


def _clean_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none"}:
        return ""
    return text


def _first_non_empty(rows: pd.DataFrame, column: str) -> str:
    for value in rows[column].tolist():
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return ""


def build_retrieval_document(
    *,
    section_findings: str = "",
    section_impression: str = "",
) -> str:
    """Concatenate the locked report sections into one retrieval document."""
    parts: list[str] = []
    findings = _clean_text(section_findings)
    impression = _clean_text(section_impression)
    if findings:
        parts.append(f"Findings: {findings}")
    if impression:
        parts.append(f"Impression: {impression}")
    return "\n\n".join(parts).strip()


def build_study_report_table(eligible_rows: pd.DataFrame) -> pd.DataFrame:
    """Collapse per-view cohort rows into one report payload per study."""
    _require_columns(eligible_rows, _REQUIRED_VIEW_COLUMNS, "eligible_rows")
    if eligible_rows.empty:
        raise ValueError("eligible_rows must be non-empty")

    views = eligible_rows.copy()
    views["study_key"] = views["study_key"].astype(str).str.strip()
    views["deid_patient_id"] = views["deid_patient_id"].astype(str).str.strip()
    if views["study_key"].str.lower().isin({"", "nan"}).any():
        raise ValueError("eligible_rows contains blank study_key values")
    if views["deid_patient_id"].str.lower().isin({"", "nan"}).any():
        raise ValueError("eligible_rows contains blank deid_patient_id values")

    rows: list[dict[str, str]] = []
    for study_key, group in views.groupby("study_key", sort=False):
        patient_ids = group["deid_patient_id"].unique()
        if len(patient_ids) != 1:
            raise ValueError(
                f"Study {study_key!r} maps to multiple patient IDs: {patient_ids}"
            )
        findings = _first_non_empty(group, "section_findings")
        impression = _first_non_empty(group, "section_impression")
        document = build_retrieval_document(
            section_findings=findings,
            section_impression=impression,
        )
        rows.append(
            {
                "study_key": str(study_key),
                "deid_patient_id": str(patient_ids[0]),
                "section_findings": findings,
                "section_impression": impression,
                "retrieval_document": document,
            }
        )

    table = pd.DataFrame(rows)
    for column in INDEX_METADATA_COLUMNS:
        if table[column].str.strip().eq("").any():
            raise ValueError(f"study report table contains blank {column!r} values")
    return table.reset_index(drop=True)


def truncate_document(document: str, *, max_chars: int) -> str:
    """Truncate a retrieval document while keeping the prefix auditable."""
    cleaned = document.strip()
    if max_chars <= 0:
        raise ValueError("max_chars must be > 0")
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars]
