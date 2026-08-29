"""Canonical DICOM path cleaning and study-key helpers."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

_STUDY_KEY_RE = re.compile(r"(patient\d+/study\d+)", re.IGNORECASE)
_PREFIXES = ("train/", "DICOM_train/", "dicom_train/")

# Preference order when resolving one findings join key from a metadata row.
_IMAGE_KEY_SOURCE_COLUMNS = ("path_to_image", "path_to_dcm", "dicom_path")
_BLANK_TEXT_VALUES = frozenset({"", "nan", "none"})


def clean_dicom_path(path: Any) -> str:
    """Normalize a Redivis or local DICOM path to a join key.

    Locked rules:
      - coerce to string and strip
      - replace \\ with /
      - strip leading ./
      - strip train/ / DICOM_train/ / dicom_train/ prefixes
      - also strip anything before /train/
    """
    if path is None:
        raise ValueError("path must not be None")

    cleaned = str(path).strip().replace("\\", "/").lstrip("./")
    if not cleaned:
        raise ValueError("path must not be blank")

    if "/train/" in cleaned:
        cleaned = cleaned.split("/train/", maxsplit=1)[1]

    for prefix in _PREFIXES:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break

    cleaned = cleaned.lstrip("/")
    if not cleaned:
        raise ValueError(f"path cleaned to empty string from {path!r}")
    return cleaned


def study_key_from_path(path: Any) -> str:
    """Derive study_key = patientXXXX/studyY from a DICOM path.

    Raises:
      ValueError: if a valid study key cannot be derived.
    """
    cleaned = clean_dicom_path(path)
    match = _STUDY_KEY_RE.search(cleaned)
    if match:
        return match.group(1).lower()

    parts = cleaned.split("/")
    if (
        len(parts) >= 2
        and parts[0].lower().startswith("patient")
        and parts[1].lower().startswith("study")
    ):
        return f"{parts[0].lower()}/{parts[1].lower()}"

    raise ValueError(f"Cannot derive study_key from path: {path!r}")


def normalize_path_to_image(path: Any) -> str:
    """Normalize a CheXpert image path for findings_fixed.json joins."""
    if path is None:
        return ""

    cleaned = str(path).strip().replace("\\", "/").lstrip("./")
    return cleaned


def path_to_image_join_key(path: Any) -> str:
    """Return the canonical findings join key for one metadata image path."""
    key = normalize_path_to_image(path)
    if not key:
        return ""
    if key.lower().endswith(".dcm"):
        key = f"{key[:-4]}.jpg"
    return key


def _is_blank_value(value: Any) -> bool:
    """Return True for None, NaN, or blank/placeholder path text."""
    if value is None:
        return True
    return str(value).strip().lower() in _BLANK_TEXT_VALUES


def path_to_image_key_from_row(row: Any) -> str:
    """Resolve the findings join key from one eligible metadata row."""
    if hasattr(row, "get"):
        for column in _IMAGE_KEY_SOURCE_COLUMNS:
            value = row.get(column)
            if _is_blank_value(value):
                continue
            key = path_to_image_join_key(value)
            if key:
                return key
    return ""


def path_to_image_join_keys(frame: pd.DataFrame) -> pd.Series:
    """Resolve findings join keys for a whole metadata table at once.

    Matches path_to_image_key_from_row per row, but stays vectorized so full
    cohort pools do not pay a Python-level cost for every view.
    """
    available = [
        column for column in _IMAGE_KEY_SOURCE_COLUMNS if column in frame.columns
    ]
    if not available:
        raise ValueError(
            "frame must contain at least one of "
            f"{list(_IMAGE_KEY_SOURCE_COLUMNS)}. Available: {list(frame.columns)}"
        )

    keys = pd.Series("", index=frame.index, dtype="object")
    for column in available:
        pending = keys == ""
        if not pending.any():
            break

        values = frame.loc[pending, column]
        text = (
            values.astype(str)
            .str.strip()
            .str.replace("\\", "/", regex=False)
            .str.replace(r"^[./]+", "", regex=True)
        )
        candidate = text.mask(
            text.str.lower().str.endswith(".dcm"),
            text.str.slice(stop=-4) + ".jpg",
        )
        blank = values.isna() | text.str.lower().isin(_BLANK_TEXT_VALUES)
        keys.loc[pending] = candidate.mask(blank, "")

    return keys


def patient_id_from_study_key(study_key: str) -> str:
    """Extract deid_patient_id from study_key."""
    if not isinstance(study_key, str) or not study_key.strip():
        raise ValueError("study_key must be a non-empty string")

    parts = study_key.strip().split("/")
    if len(parts) != 2 or not parts[0].startswith("patient"):
        raise ValueError(f"Invalid study_key: {study_key!r}")
    return parts[0]
