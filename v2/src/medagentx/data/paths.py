"""Canonical DICOM path cleaning and study-key helpers."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

_STUDY_KEY_RE = re.compile(r"(patient\d+/study\d+)", re.IGNORECASE)
_PREFIXES = ("train/", "DICOM_train/", "dicom_train/")


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


def patient_id_from_study_key(study_key: str) -> str:
    """Extract deid_patient_id from study_key."""
    if not isinstance(study_key, str) or not study_key.strip():
        raise ValueError("study_key must be a non-empty string")

    parts = study_key.strip().split("/")
    if len(parts) != 2 or not parts[0].startswith("patient"):
        raise ValueError(f"Invalid study_key: {study_key!r}")
    return parts[0]
