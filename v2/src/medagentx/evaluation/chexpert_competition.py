"""Adapters for the released expert-labeled CheXpert competition test set."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

import pandas as pd

from medagentx.evaluation.ground_truth import GroundTruthRecord
from medagentx.labels.constants import CHEXPERT_COMPETITION_LABELS
from medagentx.labels.statuses import LabelStatus


COMPETITION_SPLIT = "competition_test"
EXPECTED_STUDIES = 500
EXPECTED_VIEWS = 668
COMPETITION_VALIDATION_SPLIT = "competition_val"
EXPECTED_VALIDATION_STUDIES = 200
EXPECTED_VALIDATION_VIEWS = 234


@dataclass(frozen=True)
class CompetitionThresholdMetrics:
    threshold: float
    tp: int
    tn: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    specificity: float
    positive_rate: float


@dataclass(frozen=True)
class CompetitionThresholdSelection:
    current: CompetitionThresholdMetrics
    selected: CompetitionThresholdMetrics


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


def _path_after_split(
    value: object,
    *,
    field_name: str,
    source_split: str,
) -> PurePosixPath:
    path = _clean_path(value, field_name=field_name)
    parts = path.parts
    split_components = (
        ("val", "valid") if source_split in {"val", "valid"} else (source_split,)
    )
    matching_indices = [
        parts.index(component)
        for component in split_components
        if component in parts
    ]
    if not matching_indices:
        raise ValueError(
            f"{field_name} has no {source_split} path component: {value!r}"
        )
    split_index = min(matching_indices)
    relative = PurePosixPath(*parts[split_index + 1 :])
    if len(relative.parts) < 2:
        raise ValueError(f"Invalid CheXpert test path in {field_name}: {value!r}")
    return relative


def _path_after_test(value: object, *, field_name: str) -> PurePosixPath:
    return _path_after_split(
        value,
        field_name=field_name,
        source_split="test",
    )


def competition_study_key(
    value: object,
    *,
    field_name: str,
    source_split: str = "test",
) -> str:
    """Normalize a released Study/Path value to patient/study."""
    relative = _path_after_split(
        value,
        field_name=field_name,
        source_split=source_split,
    )
    return f"{relative.parts[0]}/{relative.parts[1]}"


def build_competition_view_manifest(
    test_labels: pd.DataFrame,
    *,
    image_root: str | Path,
    require_files: bool = True,
    source_split: str = "test",
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
        relative = _path_after_split(
            value,
            field_name="Path",
            source_split=source_split,
        )
        relative_text = relative.as_posix()
        if relative_text in seen_paths:
            raise ValueError(f"Duplicate test image path: {relative_text}")
        seen_paths.add(relative_text)

        suffix = relative.suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png"}:
            raise ValueError(f"Unsupported test image extension: {relative_text}")
        local_path = root / relative_text
        if require_files and not local_path.is_file():
            raise FileNotFoundError(
                f"Competition {source_split} image missing: {local_path}"
            )

        patient_id, study_id = relative.parts[:2]
        rows.append(
            {
                "study_key": f"{patient_id}/{study_id}",
                "deid_patient_id": patient_id,
                "split": f"competition_{source_split}",
                "dicom_path": relative_text,
                "source_path": str(value).strip(),
            }
        )
    return pd.DataFrame(rows)


def build_competition_validation_ground_truth(
    validation_labels: pd.DataFrame,
    *,
    study_keys: Sequence[str],
) -> list[GroundTruthRecord]:
    """Build five-label study records from expert validation image rows."""
    required = ("Path", *CHEXPERT_COMPETITION_LABELS)
    missing = [column for column in required if column not in validation_labels.columns]
    if missing:
        raise ValueError(
            f"val_labels.csv missing required columns {missing}; "
            f"available={list(validation_labels.columns)}"
        )

    statuses_by_key: dict[str, dict[str, LabelStatus]] = {}
    for _, row in validation_labels.iterrows():
        key = competition_study_key(
            row["Path"],
            field_name="Path",
            source_split="val",
        )
        statuses: dict[str, LabelStatus] = {}
        for label in CHEXPERT_COMPETITION_LABELS:
            value = pd.to_numeric(pd.Series([row[label]]), errors="coerce").iloc[0]
            if pd.isna(value) or float(value) not in (0.0, 1.0):
                raise ValueError(
                    f"Validation expert label must be binary for study={key!r}, "
                    f"label={label!r}; got {row[label]!r}"
                )
            statuses[label] = (
                LabelStatus.PRESENT if int(value) == 1 else LabelStatus.ABSENT
            )
        existing = statuses_by_key.get(key)
        if existing is not None and existing != statuses:
            raise ValueError(f"Inconsistent validation labels across views: {key}")
        statuses_by_key[key] = statuses

    requested_keys = tuple(dict.fromkeys(str(key).strip() for key in study_keys))
    missing_studies = [key for key in requested_keys if key not in statuses_by_key]
    if missing_studies:
        raise ValueError(
            "Validation ground truth missing requested studies: "
            f"{missing_studies[:10]}"
        )

    records: list[GroundTruthRecord] = []
    for key in requested_keys:
        for label, status in statuses_by_key[key].items():
            records.append(
                GroundTruthRecord(
                    study_key=key,
                    label=label,
                    ground_truth_status=status,
                    ground_truth_source="chexpert_validation_expert_consensus",
                    ground_truth_policy_version="chexpert_competition_val_v1",
                )
            )
    return records


def _threshold_metrics(
    probabilities: Sequence[float],
    targets: Sequence[int],
    *,
    threshold: float,
) -> CompetitionThresholdMetrics:
    predicted = [probability >= threshold for probability in probabilities]
    pairs = tuple(zip(predicted, targets))
    tp = sum(prediction and target == 1 for prediction, target in pairs)
    tn = sum(not prediction and target == 0 for prediction, target in pairs)
    fp = sum(prediction and target == 0 for prediction, target in pairs)
    fn = sum(not prediction and target == 1 for prediction, target in pairs)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    return CompetitionThresholdMetrics(
        threshold=float(threshold),
        tp=int(tp),
        tn=int(tn),
        fp=int(fp),
        fn=int(fn),
        precision=float(precision),
        recall=float(recall),
        f1=float(f1),
        specificity=float(specificity),
        positive_rate=float((tp + fp) / len(targets)),
    )


def select_competition_f1_threshold(
    probabilities: Sequence[float],
    targets: Sequence[int],
    *,
    current_threshold: float,
    min_specificity: float = 0.0,
) -> CompetitionThresholdSelection:
    """Select maximum validation F1 subject to a specificity floor."""
    scores = [float(value) for value in probabilities]
    binary_targets = [int(value) for value in targets]
    if not scores or len(scores) != len(binary_targets):
        raise ValueError("probabilities and targets must be non-empty and equal length")
    if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in scores):
        raise ValueError("probabilities must be finite values in [0, 1]")
    if set(binary_targets) - {0, 1}:
        raise ValueError("targets must contain only 0 and 1")
    if set(binary_targets) != {0, 1}:
        raise ValueError("threshold calibration requires both target classes")
    if not 0.0 <= current_threshold <= 1.0:
        raise ValueError("current_threshold must be in [0, 1]")
    if not 0.0 <= min_specificity <= 1.0:
        raise ValueError("min_specificity must be in [0, 1]")

    current = _threshold_metrics(
        scores,
        binary_targets,
        threshold=float(current_threshold),
    )
    candidates = [
        _threshold_metrics(scores, binary_targets, threshold=threshold)
        for threshold in sorted(set(scores) | {1.0})
    ]
    eligible = [
        candidate
        for candidate in candidates
        if candidate.specificity >= min_specificity
    ]
    if not eligible:
        raise ValueError(
            "No observed-score threshold satisfies "
            f"min_specificity={min_specificity}"
        )
    selected = max(
        eligible,
        key=lambda item: (
            item.f1,
            item.precision,
            -abs(item.threshold - current_threshold),
            item.threshold,
        ),
    )
    return CompetitionThresholdSelection(current=current, selected=selected)


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
