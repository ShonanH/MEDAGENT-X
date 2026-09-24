"""Redivis dataset identifiers and authentication constants for v2 data access."""

from __future__ import annotations

import sys
from pathlib import Path

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

# Auth: only this env var is accepted in v2.
REDIVIS_API_TOKEN_ENV = "REDIVIS_API_TOKEN"

# Locked CheXpert Plus dataset + verified tables (REST-only).
REDIVIS_DATASET_ID = "aimi.chexpert_plus:5yyj:v1_0"
REDIVIS_METADATA_TABLE_ID = "df_chexpert_plus_240401:bavj"
REDIVIS_PNG_TRAIN_INDEX_TABLE_ID = "png_train:s6cj"
REDIVIS_DICOM_TRAIN_INDEX_TABLE_ID = "dicom_train:1934"
REDIVIS_CHEXPERT_LABELS_INDEX_TABLE_ID = "chexpert_labels:pmec"

# REST endpoints
REDIVIS_API_BASE_URL = "https://redivis.com/api/v1"

# Locked Stage A eligibility defaults
DEFAULT_SPLIT = "train"
REQUIRE_PATH_TO_DCM = True
REQUIRE_IN_DICOM_INDEX = True

# Canonical weak-label asset name inside the labels file index
FINDINGS_FIXED_JSON_NAME = "findings_fixed.json"
