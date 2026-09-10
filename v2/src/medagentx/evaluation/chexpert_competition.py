"""Adapters for the released expert-labeled CheXpert competition test set."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

import pandas as pd

from medagentx.evaluation.ground_truth import GroundTruthRecord
from medagentx.labels.constants import CHEXPERT_COMPETITION_LABELS
from medagentx.labels.statuses import LabelStatus


COMPETITION_SPLIT = "competition_test"
EXPECTED_STUDIES = 500
EXPECTED_VIEWS = 668


def competition_binary_status_map(
    statuses: Mapping[tuple[str, str], LabelStatus],
) -> tuple[dict[tuple[str, str], LabelStatus], pd.DataFrame]:
    """Map competition predictions to present-vs-not-present statuses."""
    labels = set(CHEXPERT_COMPETITION_LABELS)
    binary: dict[tuple[str, str], LabelStatus] = {}
    audit_rows: list[dict[str, str]] = []
    for (study_key, label), status in statuses.items():
        if label not in labels:
            continue
        mapped = (
            LabelStatus.PRESENT
            if status is LabelStatus.PRESENT
            else LabelStatus.ABSENT
        )
        binary[(study_key, label)] = mapped
        audit_rows.append(
            {
                "study_key": study_key,
                "label": label,
                "raw_status": status.value,
                "binary_status": mapped.value,
                "was_mapped": str(status is LabelStatus.UNCERTAIN).lower(),
            }
        )
    return binary, pd.DataFrame(audit_rows)


def _clean_path(value: object, *, field_name: str) -> PurePosixPath:
    text = str(value).strip().replace("\\", "/")
    if not text or text.lower() == "nan":
        raise ValueError(f"{field_name} must be a non-empty path")
    path = PurePosixPath(text)
    if ".." in path.parts:
        raise ValueError(f"Unsafe {field_name}: {value!r}")
    return path


def _path_after_test(value: object, *, field_name: str) -> PurePosixPath:
    path = _clean_path(value, field_name=field_name)
    parts = path.parts
    try:
        test_index = parts.index("test")
    except ValueError as exc:
        raise ValueError(f"{field_name} has no test path component: {value!r}") from exc
    relative = PurePosixPath(*parts[test_index + 1 :])
    if len(relative.parts) < 2:
        raise ValueError(f"Invalid CheXpert test path in {field_name}: {value!r}")
    return relative


def competition_study_key(value: object, *, field_name: str) -> str:
    """Normalize a released Study/Path value to patient/study."""
    relative = _path_after_test(value, field_name=field_name)
    return f"{relative.parts[0]}/{relative.parts[1]}"


def build_competition_view_manifest(
    test_labels: pd.DataFrame,
    *,
    image_root: str | Path,
    require_files: bool = True,
) -> pd.DataFrame:
    """Convert per-image CheXpert paths into the v2 inference-view contract."""
    if "Path" not in test_labels.columns:
        raise ValueError(
            "test_labels.csv missing required 'Path' column; "
            f"available={list(test_labels.columns)}"
        )
    if test_labels.empty:
        raise ValueError("test_labels.csv must not be empty")

    root = Path(image_root)
    rows: list[dict[str, object]] = []
    seen_paths: set[str] = set()
    for value in test_labels["Path"]:
        relative = _path_after_test(value, field_name="Path")
        relative_text = relative.as_posix()
        if relative_text in seen_paths:
            raise ValueError(f"Duplicate test image path: {relative_text}")
        seen_paths.add(relative_text)

        suffix = relative.suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png"}:
            raise ValueError(f"Unsupported test image extension: {relative_text}")
        local_path = root / relative_text
        if require_files and not local_path.is_file():
            raise FileNotFoundError(f"Competition test image missing: {local_path}")

        patient_id, study_id = relative.parts[:2]
        rows.append(
            {
                "study_key": f"{patient_id}/{study_id}",
                "deid_patient_id": patient_id,
                "split": COMPETITION_SPLIT,
                "dicom_path": relative_text,
                "source_path": str(value).strip(),
            }
        )
    return pd.DataFrame(rows)


def build_competition_ground_truth(
    groundtruth: pd.DataFrame,
    *,
    study_keys: Sequence[str],
) -> list[GroundTruthRecord]:
    """Build five-label binary records from expert majority-vote ground truth."""
    required = ("Study", *CHEXPERT_COMPETITION_LABELS)
    missing = [column for column in required if column not in groundtruth.columns]
    if missing:
        raise ValueError(
            f"groundtruth.csv missing required columns {missing}; "
            f"available={list(groundtruth.columns)}"
        )

    rows_by_key: dict[str, pd.Series] = {}
    for _, row in groundtruth.iterrows():
        key = competition_study_key(row["Study"], field_name="Study")
        if key in rows_by_key:
            raise ValueError(f"Duplicate expert ground-truth study: {key}")
        rows_by_key[key] = row

    requested_keys = tuple(dict.fromkeys(str(key).strip() for key in study_keys))
    missing_studies = [key for key in requested_keys if key not in rows_by_key]
    if missing_studies:
        raise ValueError(
            "Expert ground truth missing requested studies: "
            f"{missing_studies[:10]}"
        )

    records: list[GroundTruthRecord] = []
    for key in requested_keys:
        row = rows_by_key[key]
        for label in CHEXPERT_COMPETITION_LABELS:
            value = pd.to_numeric(pd.Series([row[label]]), errors="coerce").iloc[0]
            if pd.isna(value) or float(value) not in (0.0, 1.0):
                raise ValueError(
                    f"Expert label must be binary for study={key!r}, "
                    f"label={label!r}; got {row[label]!r}"
                )
            status = (
                LabelStatus.PRESENT if int(value) == 1 else LabelStatus.ABSENT
            )
            records.append(
                GroundTruthRecord(
                    study_key=key,
                    label=label,
                    ground_truth_status=status,
                    ground_truth_source="chexpert_expert_majority_vote",
                    ground_truth_policy_version="chexpert_competition_test_v1",
                )
            )
    return records
