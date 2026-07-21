"""
CheXpert Plus Redivis SQL query definitions.

All table references and SELECT builders live here. Execution (HTTP POST/GET)
is handled by redivis_query_client.py.

To add a new export later:
  1. Add or extend a RedivisTable entry below (set reference id from Redivis UI).
  2. Add column list + build_*_query() function.
  3. Register a RedivisExportSpec in REDIVIS_EXPORTS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from medagentx.fusion.constants import DEFAULT_REDIVIS_CSV
from medagentx.paths import CHEXPERT_OUTPUT_DIR

# ---------------------------------------------------------------------------
# Dataset tables (CheXpert Plus v1.0 on Redivis)
# ---------------------------------------------------------------------------

CHEXPERT_PLUS_DATASET = "aimi.chexpert_plus:5yyj:v1_0"


@dataclass(frozen=True)
class RedivisTable:
    """One Redivis table in the CheXpert Plus dataset."""

    slug: str
    reference_id: str
    description: str
    kind: str = "rows"  # "rows" | "file_index"

    @property
    def qualified_reference(self) -> str:
        return f"{CHEXPERT_PLUS_DATASET}.{self.slug}:{self.reference_id}"


TABLES: dict[str, RedivisTable] = {
    "metadata": RedivisTable(
        slug="df_chexpert_plus_240401",
        reference_id="bavj",
        description="Image/report metadata (path_to_image, reports, demographics, split).",
        kind="rows",
    ),
    "chexpert_labels_file_index": RedivisTable(
        slug="chexpert_labels",
        reference_id="pmec",
        description="File index for label JSON assets (e.g. findings_fixed.json). Not per-image rows.",
        kind="file_index",
    ),
    "dicom_train_index": RedivisTable(
        slug="dicom_train",
        reference_id="1934",
        description="DICOM_train file index (file_id -> path_to_dcm).",
        kind="file_index",
    ),
    # Set reference_id from the Redivis table details page when you need these exports.
    "dicom_valid_index": RedivisTable(
        slug="dicom_valid",
        reference_id="TODO",
        description="DICOM_valid file index.",
        kind="file_index",
    ),
    "dicom_compressed_index": RedivisTable(
        slug="dicom_compressed",
        reference_id="TODO",
        description="DICOM_compressed file index.",
        kind="file_index",
    ),
    "png_train_index": RedivisTable(
        slug="png_train",
        reference_id="TODO",
        description="PNG_train file index.",
        kind="file_index",
    ),
    "png_valid_index": RedivisTable(
        slug="png_valid",
        reference_id="TODO",
        description="PNG_valid file index.",
        kind="file_index",
    ),
    "png_compressed_index": RedivisTable(
        slug="png_compressed",
        reference_id="TODO",
        description="PNG_compressed file index.",
        kind="file_index",
    ),
    "radgraph_xl_annotations": RedivisTable(
        slug="radgraph_xl_annotations",
        reference_id="TODO",
        description="RadGraph-XL annotation rows or file index.",
        kind="rows",
    ),
}


def table_reference(table_key: str) -> str:
    table = TABLES[table_key]
    if table.reference_id == "TODO":
        raise RuntimeError(
            f"Redivis table '{table_key}' has no reference id yet. "
            f"Open the table in Redivis and set TABLES['{table_key}'].reference_id."
        )
    return table.qualified_reference


# ---------------------------------------------------------------------------
# Column sets
# ---------------------------------------------------------------------------

IDENTIFIER_COLUMNS = [
    "path_to_image",
    "path_to_dcm",
    "deid_patient_id",
    "patient_report_date_order",
    "section_accession_number",
]

DEMOGRAPHIC_COLUMNS = [
    "age",
    "sex",
    "race",
    "ethnicity",
]

REPORT_COLUMNS = [
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
]

VIEW_COLUMNS = [
    "frontal_lateral",
    "ap_pa",
    "split",
]

CHEXPERT_LABEL_COLUMNS = [
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
    "Pneumonia",
    "Pneumothorax",
    "Fracture",
    "Lung Lesion",
    "Lung Opacity",
    "Enlarged Cardiomediastinum",
    "Pleural Other",
    "Support Devices",
    "No Finding",
]

METADATA_EXPORT_COLUMNS = IDENTIFIER_COLUMNS + DEMOGRAPHIC_COLUMNS + REPORT_COLUMNS

MANIFEST_COLUMNS = IDENTIFIER_COLUMNS[:2] + VIEW_COLUMNS[:2] + [
    "deid_patient_id",
    "patient_report_date_order",
    *DEMOGRAPHIC_COLUMNS,
    "split",
    "report",
    "section_findings",
    "section_impression",
]

IMAGE_LABEL_EXPORT_COLUMNS = ["path_to_image", "path_to_dcm", *CHEXPERT_LABEL_COLUMNS]

CHEXPERT_LABELS_FILE_INDEX_COLUMNS = [
    "file_id",
    "file_name",
    "size",
    "added_at",
    "md5_hash",
]

DICOM_FILE_INDEX_COLUMNS = [
    "file_id",
    "file_name",
    "path",
    "file_path",
    "name",
    "filename",
    "path_to_dcm",
    "dicom_path",
    "size",
    "added_at",
    "md5_hash",
]

REDIVIS_EXPORTS_DIR = CHEXPERT_OUTPUT_DIR / "redivis_exports"


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------


def sql_quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def normalize_text(value: Any) -> str:
    import re

    if value is None:
        return ""
    import pandas as pd

    if isinstance(value, float) and pd.isna(value):
        return ""

    normalized = str(value).strip().lower()
    normalized = normalized.replace("\\", "/")
    normalized = re.sub(r"/+", "/", normalized)
    return normalized


def columns_sql(columns: list[str]) -> str:
    return ",\n        ".join(f"`{column}`" for column in columns)


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------


def build_metadata_train_split_query(row_limit: int) -> str:
    return f"""
    SELECT
        {columns_sql(METADATA_EXPORT_COLUMNS)}
    FROM `{table_reference("metadata")}`
    WHERE path_to_dcm IS NOT NULL
      AND split = 'train'
    LIMIT {int(row_limit)}
    """


def build_metadata_filtered_by_dicom_paths_query(local_dicom_paths: list[str]) -> str:
    like_clauses = [
        f"LOWER(`path_to_dcm`) LIKE {sql_quote('%' + normalize_text(dicom_path))}"
        for dicom_path in local_dicom_paths
        if normalize_text(dicom_path)
    ]

    if not like_clauses:
        raise RuntimeError("No local DICOM paths were available for the Redivis query.")

    where_sql = "\n        OR ".join(like_clauses)

    return f"""
    SELECT
        {columns_sql(METADATA_EXPORT_COLUMNS)}
    FROM `{table_reference("metadata")}`
    WHERE
        {where_sql}
    """


def build_metadata_manifest_train_query(row_limit: int) -> str:
    return f"""
    SELECT
        {columns_sql(MANIFEST_COLUMNS)}
    FROM `{table_reference("metadata")}`
    WHERE path_to_dcm IS NOT NULL
      AND split = 'train'
    LIMIT {int(row_limit)}
    """


def build_metadata_probe_query(table_key: str = "metadata", row_limit: int = 1) -> str:
    """Discover column names for a table (SELECT * LIMIT n)."""
    return f"""
    SELECT *
    FROM `{table_reference(table_key)}`
    LIMIT {int(row_limit)}
    """


def build_chexpert_labels_file_index_query(row_limit: int = 100) -> str:
    """List label asset files (e.g. findings_fixed.json) in the CheXpert Labels table."""
    return f"""
    SELECT *
    FROM `{table_reference("chexpert_labels_file_index")}`
    LIMIT {int(row_limit)}
    """


def build_image_labels_for_paths_query(
    path_to_images: list[str],
    *,
    path_column: str = "path_to_image",
) -> str:
    """
    Fetch per-image CheXpert label columns from the main metadata table.

    Use when label columns live on df_chexpert_plus_240401 (not on the
    chexpert_labels file-index table).
    """
    selected = columns_sql(IMAGE_LABEL_EXPORT_COLUMNS)

    exact_clauses = [
        f"LOWER(`{path_column}`) = {sql_quote(normalize_text(path))}"
        for path in path_to_images
        if normalize_text(path)
    ]

    if not exact_clauses:
        raise RuntimeError("No path values were available for the image-labels query.")

    where_sql = "\n        OR ".join(exact_clauses)

    return f"""
    SELECT
        {selected}
    FROM `{table_reference("metadata")}`
    WHERE
        {where_sql}
    """


def build_image_labels_for_dicom_paths_query(path_to_dcms: list[str]) -> str:
    return build_image_labels_for_paths_query(path_to_dcms, path_column="path_to_dcm")


def build_dicom_train_file_index_query(row_limit: int = 250_000) -> str:
    return build_generic_file_index_query("dicom_train_index", row_limit)


def build_generic_file_index_query(table_key: str, row_limit: int) -> str:
    return f"""
    SELECT *
    FROM `{table_reference(table_key)}`
    LIMIT {int(row_limit)}
    """


def build_generic_table_probe_query(table_key: str, row_limit: int = 1) -> str:
    return build_metadata_probe_query(table_key=table_key, row_limit=row_limit)


# ---------------------------------------------------------------------------
# Export registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RedivisExportSpec:
    """Named export: SQL builder + default CSV output path."""

    name: str
    description: str
    default_output_csv: str
    build_query: Callable[..., str]
    default_max_results: int = 25_000


def _file_index_export_spec(
    table_key: str,
    *,
    export_name: str | None = None,
    row_limit: int = 250_000,
) -> RedivisExportSpec:
    table = TABLES[table_key]
    name = export_name or f"{table.slug}_file_index"
    return RedivisExportSpec(
        name=name,
        description=table.description,
        default_output_csv=str(REDIVIS_EXPORTS_DIR / f"{name}.csv"),
        build_query=lambda row_limit=row_limit, table_key=table_key, **_kwargs: build_generic_file_index_query(
            table_key, row_limit
        ),
        default_max_results=row_limit,
    )


def _table_probe_export_spec(table_key: str) -> RedivisExportSpec:
    table = TABLES[table_key]
    export_name = f"{table.slug}_probe"
    return RedivisExportSpec(
        name=export_name,
        description=f"Probe {table.slug} schema (SELECT * LIMIT 1).",
        default_output_csv=str(REDIVIS_EXPORTS_DIR / f"{export_name}.csv"),
        build_query=lambda row_limit=1, table_key=table_key, **_kwargs: build_generic_table_probe_query(
            table_key, row_limit
        ),
        default_max_results=1,
    )


REDIVIS_EXPORTS: dict[str, RedivisExportSpec] = {
    "metadata_train": RedivisExportSpec(
        name="metadata_train",
        description="Train-split metadata rows (reports + identifiers).",
        default_output_csv=str(DEFAULT_REDIVIS_CSV),
        build_query=lambda row_limit=25_000, **_kwargs: build_metadata_train_split_query(row_limit),
        default_max_results=25_000,
    ),
    "metadata_manifest_train": RedivisExportSpec(
        name="metadata_manifest_train",
        description="Train-split rows with view columns for study manifest building.",
        default_output_csv=str(REDIVIS_EXPORTS_DIR / "metadata_manifest_train.csv"),
        build_query=lambda row_limit=10_000, **_kwargs: build_metadata_manifest_train_query(row_limit),
        default_max_results=10_000,
    ),
    "chexpert_labels_file_index": RedivisExportSpec(
        name="chexpert_labels_file_index",
        description="File index for CheXpert Labels table (findings_fixed.json, etc.).",
        default_output_csv=str(REDIVIS_EXPORTS_DIR / "chexpert_labels_file_index.csv"),
        build_query=lambda row_limit=100, **_kwargs: build_chexpert_labels_file_index_query(row_limit),
        default_max_results=100,
    ),
    "dicom_train_file_index": _file_index_export_spec(
        "dicom_train_index",
        export_name="dicom_train_file_index",
    ),
    "dicom_valid_file_index": _file_index_export_spec("dicom_valid_index"),
    "dicom_compressed_file_index": _file_index_export_spec("dicom_compressed_index"),
    "png_train_file_index": _file_index_export_spec("png_train_index"),
    "png_valid_file_index": _file_index_export_spec("png_valid_index"),
    "png_compressed_file_index": _file_index_export_spec("png_compressed_index"),
    "radgraph_xl_annotations": RedivisExportSpec(
        name="radgraph_xl_annotations",
        description=TABLES["radgraph_xl_annotations"].description,
        default_output_csv=str(REDIVIS_EXPORTS_DIR / "radgraph_xl_annotations.csv"),
        build_query=lambda row_limit=25_000, **_kwargs: build_generic_file_index_query(
            "radgraph_xl_annotations", row_limit
        ),
        default_max_results=25_000,
    ),
    "metadata_probe": _table_probe_export_spec("metadata"),
    "chexpert_labels_probe": _table_probe_export_spec("chexpert_labels_file_index"),
    "dicom_train_probe": _table_probe_export_spec("dicom_train_index"),
}


def list_exports() -> list[str]:
    return sorted(REDIVIS_EXPORTS.keys())


def get_export(name: str) -> RedivisExportSpec:
    if name not in REDIVIS_EXPORTS:
        raise KeyError(f"Unknown Redivis export '{name}'. Available: {', '.join(list_exports())}")
    return REDIVIS_EXPORTS[name]


# Backward-compatible aliases used by older scripts
REDIVIS_TABLE_REFERENCE = TABLES["metadata"].qualified_reference
REDIVIS_CHEXPERT_LABELS_TABLE_REFERENCE = TABLES["chexpert_labels_file_index"].qualified_reference
SELECTED_REDIVIS_COLUMNS = METADATA_EXPORT_COLUMNS

build_train_split_query = build_metadata_train_split_query
build_filtered_redivis_sql = build_metadata_filtered_by_dicom_paths_query
build_filtered_chexpert_labels_sql = build_image_labels_for_paths_query
