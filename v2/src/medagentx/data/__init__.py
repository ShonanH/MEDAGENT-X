"""Offline Redivis metadata and DICOM retrieval package."""

from __future__ import annotations

import sys
from pathlib import Path

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.data.catalog import (
    METADATA_IDENTITY_COLUMNS,
    REPORT_COLUMNS,
    TABLES,
    RedivisTable,
    build_chexpert_labels_index_sql,
    build_dicom_train_index_probe_sql,
    build_dicom_train_index_sql,
    build_findings_fixed_lookup_sql,
    build_metadata_reports_sql,
    build_metadata_train_sql,
    get_table,
)
from medagentx.data.constants import (
    DEFAULT_SPLIT,
    FINDINGS_FIXED_JSON_NAME,
    REDIVIS_API_BASE_URL,
    REDIVIS_API_TOKEN_ENV,
    REDIVIS_CHEXPERT_LABELS_INDEX_TABLE_ID,
    REDIVIS_DATASET_ID,
    REDIVIS_DICOM_TRAIN_INDEX_TABLE_ID,
    REDIVIS_METADATA_TABLE_ID,
)
from medagentx.data.dicoms import (
    download_eligible_dicoms,
    local_dicom_path,
    summarize_download_status,
)
from medagentx.data.findings import (
    ensure_findings_fixed_json,
    resolve_findings_fixed_file_id,
)
from medagentx.data.paths import (
    clean_dicom_path,
    patient_id_from_study_key,
    study_key_from_path,
)
from medagentx.data.redivis_client import (
    RedivisClient,
    RedivisDownloadResult,
)
from medagentx.data.rows import (
    apply_eligibility_limits,
    attach_report_columns,
    build_dicom_file_id_lookup,
    build_eligible_dicom_rows,
    fetch_dicom_train_index,
    fetch_eligible_dicom_rows,
    fetch_metadata_train_rows,
    resolve_dicom_index_path_column,
)

__all__ = [
    "DEFAULT_SPLIT",
    "METADATA_IDENTITY_COLUMNS",
    "REPORT_COLUMNS",
    "FINDINGS_FIXED_JSON_NAME",
    "REDIVIS_API_BASE_URL",
    "REDIVIS_API_TOKEN_ENV",
    "REDIVIS_CHEXPERT_LABELS_INDEX_TABLE_ID",
    "REDIVIS_DATASET_ID",
    "REDIVIS_DICOM_TRAIN_INDEX_TABLE_ID",
    "REDIVIS_METADATA_TABLE_ID",
    "TABLES",
    "RedivisClient",
    "RedivisDownloadResult",
    "RedivisTable",
    "apply_eligibility_limits",
    "attach_report_columns",
    "build_chexpert_labels_index_sql",
    "build_dicom_file_id_lookup",
    "build_dicom_train_index_probe_sql",
    "build_dicom_train_index_sql",
    "build_eligible_dicom_rows",
    "build_findings_fixed_lookup_sql",
    "build_metadata_reports_sql",
    "build_metadata_train_sql",
    "clean_dicom_path",
    "download_eligible_dicoms",
    "ensure_findings_fixed_json",
    "fetch_dicom_train_index",
    "fetch_eligible_dicom_rows",
    "fetch_metadata_train_rows",
    "get_table",
    "local_dicom_path",
    "patient_id_from_study_key",
    "resolve_dicom_index_path_column",
    "resolve_findings_fixed_file_id",
    "study_key_from_path",
    "summarize_download_status",
]