"""Verified Redivis table catalog and SQL builders for Stage A data access."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.data.constants import (
    DEFAULT_SPLIT,
    FINDINGS_FIXED_JSON_NAME,
    REDIVIS_CHEXPERT_LABELS_INDEX_TABLE_ID,
    REDIVIS_DATASET_ID,
    REDIVIS_DICOM_TRAIN_INDEX_TABLE_ID,
    REDIVIS_METADATA_TABLE_ID,
)

TableKind = Literal["rows", "file_index"]


@dataclass(frozen=True)
class RedivisTable:
    """One verified Redivis table in the locked catalog."""

    key: str
    slug: str
    reference_id: str
    description: str
    kind: TableKind

    @property
    def qualified_reference(self) -> str:
        return f"{REDIVIS_DATASET_ID}.{self.slug}:{self.reference_id}"


def _split_table_id(table_id: str) -> tuple[str, str]:
    if ":" not in table_id:
        raise ValueError(f"Invalid table id (expected slug:ref): {table_id!r}")
    slug, reference_id = table_id.split(":", maxsplit=1)
    if not slug or not reference_id:
        raise ValueError(f"Invalid table id: {table_id!r}")
    return slug, reference_id


_METADATA_SLUG, _METADATA_REF = _split_table_id(REDIVIS_METADATA_TABLE_ID)
_DICOM_SLUG, _DICOM_REF = _split_table_id(REDIVIS_DICOM_TRAIN_INDEX_TABLE_ID)
_LABELS_SLUG, _LABELS_REF = _split_table_id(REDIVIS_CHEXPERT_LABELS_INDEX_TABLE_ID)

TABLES: dict[str, RedivisTable] = {
    "metadata": RedivisTable(
        key="metadata",
        slug=_METADATA_SLUG,
        reference_id=_METADATA_REF,
        description="Image/report metadata rows.",
        kind="rows",
    ),
    "dicom_train_index": RedivisTable(
        key="dicom_train_index",
        slug=_DICOM_SLUG,
        reference_id=_DICOM_REF,
        description="Train DICOM file index (path -> file_id).",
        kind="file_index",
    ),
    "chexpert_labels_file_index": RedivisTable(
        key="chexpert_labels_file_index",
        slug=_LABELS_SLUG,
        reference_id=_LABELS_REF,
        description="Label asset file index (findings_fixed.json).",
        kind="file_index",
    ),
}


IDENTIFIER_COLUMNS: tuple[str, ...] = (
    "path_to_image",
    "path_to_dcm",
    "deid_patient_id",
    "patient_report_date_order",
    "section_accession_number",
)

DEMOGRAPHIC_COLUMNS: tuple[str, ...] = (
    "age",
    "sex",
    "race",
    "ethnicity",
)

REPORT_COLUMNS: tuple[str, ...] = (
    "report",
    "section_narrative",
    "section_clinical_history",
    "section_history",
    "section_comparison",
    "section_technique",
    "section_procedure_comments",
    "section_findings",
    "section_impression",
    "section_end_of_impression",
    "section_summary",
)

VIEW_COLUMNS: tuple[str, ...] = (
    "frontal_lateral",
    "ap_pa",
    "split",
)

METADATA_COLUMNS: tuple[str, ...] = (
    IDENTIFIER_COLUMNS + DEMOGRAPHIC_COLUMNS + REPORT_COLUMNS + VIEW_COLUMNS
)

# Eligibility only needs identifiers/views; report text is fetched later for the
# selected cohort so query responses stay under the Redivis 100MB rows limit.
METADATA_IDENTITY_COLUMNS: tuple[str, ...] = (
    IDENTIFIER_COLUMNS + DEMOGRAPHIC_COLUMNS + VIEW_COLUMNS
)

DICOM_INDEX_COLUMNS: tuple[str, ...] = (
    "name",
    "file_id",
    "path",
    "size",
    "md5",
)

LABELS_INDEX_COLUMNS: tuple[str, ...] = (
    "name",
    "file_id",
    "path",
    "size",
    "md5",
)


def get_table(key: str) -> RedivisTable:
    """Return one locked catalog table."""
    if key not in TABLES:
        raise KeyError(
            f"Unknown table key {key!r}. Locked keys: {sorted(TABLES)}"
        )
    return TABLES[key]


def sql_quote(value: str) -> str:
    """Escape a SQL string literal."""
    return "'" + value.replace("'", "''") + "'"


def sql_quote_identifier(name: str) -> str:
    """Escape a SQL identifier for BigQuery-style backtick quoting."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("identifier must be a non-empty string")
    cleaned = name.strip()
    if "`" in cleaned:
        raise ValueError(f"Invalid identifier: {name!r}")
    return f"`{cleaned}`"


def _paged(sql: str, *, limit: int | None, offset: int | None) -> str:
    """Append LIMIT/OFFSET, requiring LIMIT whenever OFFSET is used."""
    if limit is not None and limit <= 0:
        raise ValueError("limit must be > 0 when provided")
    if offset is not None:
        if offset < 0:
            raise ValueError("offset must be >= 0 when provided")
        if limit is None:
            raise ValueError("offset requires a limit")

    if limit is not None:
        sql = f"{sql}\nLIMIT {int(limit)}"
    if offset:
        sql = f"{sql}\nOFFSET {int(offset)}"
    return sql


def build_metadata_train_sql(
    *,
    limit: int | None = None,
    offset: int | None = None,
    columns: Sequence[str] = METADATA_IDENTITY_COLUMNS,
) -> str:
    """Build Stage A metadata SQL: train rows with non-null path_to_dcm.

    Defaults to identifier/view columns only. Report text is large enough that
    fetching it for the full train split exceeds the Redivis rows size limit.
    """
    if not columns:
        raise ValueError("columns must be non-empty")

    selected = ",\n  ".join(sql_quote_identifier(column) for column in columns)
    table = get_table("metadata").qualified_reference
    sql = f"""
SELECT
  {selected}
FROM `{table}`
WHERE split = {sql_quote(DEFAULT_SPLIT)}
  AND path_to_dcm IS NOT NULL
  AND TRIM(CAST(path_to_dcm AS STRING)) != ''
ORDER BY path_to_dcm
""".strip()

    return _paged(sql, limit=limit, offset=offset)


def build_metadata_reports_sql(paths: Sequence[str]) -> str:
    """Build report-column SQL for one batch of exact path_to_dcm values."""
    if not paths:
        raise ValueError("paths must be non-empty")

    columns = ("path_to_dcm",) + REPORT_COLUMNS
    selected = ",\n  ".join(sql_quote_identifier(column) for column in columns)
    table = get_table("metadata").qualified_reference
    values = ", ".join(sql_quote(str(path)) for path in paths)
    return f"""
SELECT
  {selected}
FROM `{table}`
WHERE path_to_dcm IN ({values})
""".strip()


def build_dicom_train_index_probe_sql(*, limit: int = 5) -> str:
    """Build a tiny probe query used to resolve the file-index schema."""
    if limit <= 0:
        raise ValueError("limit must be > 0")

    table = get_table("dicom_train_index").qualified_reference
    return f"""
SELECT *
FROM `{table}`
LIMIT {int(limit)}
""".strip()


def build_dicom_train_index_sql(
    *,
    path_column: str,
    limit: int | None = None,
    offset: int | None = None,
) -> str:
    """Build SQL for the train DICOM file index, narrowed to path + file_id.

    File-index schemas vary across Redivis exports, so the path column is
    resolved by probing before this query is built.
    """
    table = get_table("dicom_train_index").qualified_reference
    path_ref = sql_quote_identifier(path_column)
    sql = f"""
SELECT
  `file_id`,
  {path_ref}
FROM `{table}`
ORDER BY {path_ref}
""".strip()

    return _paged(sql, limit=limit, offset=offset)


def build_chexpert_labels_index_sql() -> str:
    """Build SQL for the CheXpert labels file index."""
    table = get_table("chexpert_labels_file_index").qualified_reference
    return f"""
SELECT *
FROM `{table}`
LIMIT 100
""".strip()


def build_findings_fixed_lookup_sql() -> str:
    """Fetch the small labels index so findings_fixed.json is resolved locally."""
    return build_chexpert_labels_index_sql()
