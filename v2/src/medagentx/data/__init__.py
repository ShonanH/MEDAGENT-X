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
from medagentx.data.balanced_constants import (
    BALANCED_COHORT_POLICY_VERSION,
    BALANCED_EVAL_MODE,
    NEGATIVE_TO_POSITIVE_RATIO,
    POST_QUALITY_POSITIVE_TARGETS,
    PRE_QUALITY_POSITIVE_TARGETS,
    SOFT_PATIENT_CAP,
)
from medagentx.data.balanced_select import (
    EnrichedCohortSelection,
    build_label_count_audit,
    build_patient_label_features,
    select_enriched_cohort,
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
from medagentx.data.cohort import (
    apply_label_gated_cohort,
    limit_to_whole_studies,
    load_findings_for_cohort,
    summarize_label_gated_cohort,
    write_label_gated_cohort_artifacts,
)
from medagentx.data.dicoms import (
    download_eligible_dicoms,
    local_dicom_path,
    reuse_existing_dicoms,
    summarize_download_status,
)
from medagentx.data.findings import (
    ensure_findings_fixed_json,
    resolve_findings_fixed_file_id,
)
from medagentx.data.findings_index import (
    FindingsIndex,
    FindingsRecord,
    summarize_findings_index,
)
from medagentx.data.paths import (
    clean_dicom_path,
    normalize_path_to_image,
    path_to_image_join_key,
    path_to_image_join_keys,
    path_to_image_key_from_row,
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
    "BALANCED_COHORT_POLICY_VERSION",
    "BALANCED_EVAL_MODE",
    "DEFAULT_SPLIT",
    "METADATA_IDENTITY_COLUMNS",
    "NEGATIVE_TO_POSITIVE_RATIO",
    "POST_QUALITY_POSITIVE_TARGETS",
    "PRE_QUALITY_POSITIVE_TARGETS",
    "REPORT_COLUMNS",
    "SOFT_PATIENT_CAP",
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
    "apply_label_gated_cohort",
    "attach_report_columns",
    "build_label_count_audit",
    "build_patient_label_features",
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
    "EnrichedCohortSelection",
    "ensure_findings_fixed_json",
    "fetch_dicom_train_index",
    "fetch_eligible_dicom_rows",
    "fetch_metadata_train_rows",
    "FindingsIndex",
    "FindingsRecord",
    "get_table",
    "limit_to_whole_studies",
    "load_findings_for_cohort",
    "local_dicom_path",
    "normalize_path_to_image",
    "path_to_image_join_key",
    "path_to_image_join_keys",
    "path_to_image_key_from_row",
    "patient_id_from_study_key",
    "resolve_dicom_index_path_column",
    "resolve_findings_fixed_file_id",
    "reuse_existing_dicoms",
    "select_enriched_cohort",
    "study_key_from_path",
    "summarize_download_status",
    "summarize_findings_index",
    "summarize_label_gated_cohort",
    "write_label_gated_cohort_artifacts",
]