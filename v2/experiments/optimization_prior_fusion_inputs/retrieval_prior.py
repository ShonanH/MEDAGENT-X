"""Similarity-weighted retrieval label priors for prior-fusion experiments.

This module is the first Topic 2 building block. It does not make fusion
decisions. It only summarizes the structured labels of retrieved neighbor
studies as local empirical priors.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


DISEASE_LABELS: tuple[str, ...] = (
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
)

PRESENT = "present"
ABSENT = "absent"
UNCERTAIN = "uncertain"
UNMENTIONED = "unmentioned"
SCOREABLE_STATUSES = {PRESENT, ABSENT}
KNOWN_STATUSES = SCOREABLE_STATUSES | {UNCERTAIN, UNMENTIONED}
DEFAULT_TOP_CASES = 3


@dataclass(frozen=True)
class RetrievedCaseLabel:
    """One retrieved neighbor's structured label status for one disease."""

    study_key: str
    similarity: float
    weight: float
    status: str


@dataclass(frozen=True)
class RetrievalLabelPrior:
    """Similarity-weighted local label prior from retrieved training studies."""

    label: str
    present_prior: float
    absent_prior: float
    uncertain_rate: float
    unmentioned_rate: float
    scoreable_weight: float
    total_weight: float
    retrieval_confidence: float
    mean_similarity: float
    retrieved_count: int
    scoreable_count: int
    top_supporting_cases: tuple[str, ...]
    top_contradicting_cases: tuple[str, ...]


def snake_label(label: str) -> str:
    """Return the study_label_table slug for one CheXpert label."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def normalize_study_key(value: Any) -> str:
    """Normalize study keys for stable lookup."""
    return str(value or "").strip().lower()


def status_column(label: str) -> str:
    """Return the status column name for one disease label."""
    if label not in DISEASE_LABELS:
        raise ValueError(f"Unsupported disease label: {label!r}")
    return f"status_{snake_label(label)}"


def load_study_label_status_lookup(
    study_label_table_csv: str | Path,
    *,
    labels: Sequence[str] = DISEASE_LABELS,
) -> dict[str, dict[str, str]]:
    """Load study_key -> label -> status from a study_label_table.csv file."""
    path = Path(study_label_table_csv)
    if not path.exists():
        raise FileNotFoundError(f"Study label table is missing: {path}")

    label_tuple = tuple(labels)
    required_columns = [
        "study_key",
        *[status_column(label) for label in label_tuple],
    ]
    lookup: dict[str, dict[str, str]] = {}

    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Study label table has no header: {path}")

        missing = [
            column
            for column in required_columns
            if column not in reader.fieldnames
        ]
        if missing:
            raise ValueError(
                f"Study label table missing required columns {missing}. "
                f"Available columns: {reader.fieldnames}"
            )

        for row_number, row in enumerate(reader, start=2):
            study_key = normalize_study_key(row.get("study_key"))
            if not study_key:
                raise ValueError(f"Blank study_key at {path}:{row_number}")
            if study_key in lookup:
                raise ValueError(f"Duplicate study_key {study_key!r} in {path}")

            label_statuses: dict[str, str] = {}
            for label in label_tuple:
                value = str(row[status_column(label)] or "").strip().lower()
                if value not in KNOWN_STATUSES:
                    raise ValueError(
                        f"Invalid status {value!r} for {label!r} "
                        f"at {path}:{row_number}"
                    )
                label_statuses[label] = value

            lookup[study_key] = label_statuses

    if not lookup:
        raise ValueError(f"Study label table contains no rows: {path}")
    return lookup


def _case_value(case: Any, key: str) -> Any:
    if isinstance(case, Mapping):
        return case.get(key)
    return getattr(case, key, None)


def _case_study_key(case: Any) -> str:
    value = _case_value(case, "study_key")
    if value is None:
        value = _case_value(case, "case_id")
    study_key = normalize_study_key(value)
    if not study_key:
        raise ValueError(f"Retrieved case is missing study_key/case_id: {case!r}")
    return study_key


def _case_similarity(case: Any) -> float:
    value = _case_value(case, "similarity")
    if value is None:
        raise ValueError(f"Retrieved case is missing similarity: {case!r}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid retrieved similarity {value!r}") from exc


def similarity_weight(similarity: float) -> float:
    """Convert a retrieval similarity into a nonnegative prior weight."""
    return max(0.0, float(similarity))


def retrieval_case_labels_for_label(
    *,
    label: str,
    retrieved_cases: Sequence[Any],
    study_label_statuses: Mapping[str, Mapping[str, str]],
) -> tuple[RetrievedCaseLabel, ...]:
    """Attach structured label statuses to retrieved cases for one label."""
    if label not in DISEASE_LABELS:
        raise ValueError(f"Unsupported disease label: {label!r}")

    labeled_cases: list[RetrievedCaseLabel] = []
    for case in retrieved_cases:
        study_key = _case_study_key(case)
        statuses = study_label_statuses.get(study_key)
        if statuses is None:
            raise KeyError(
                f"Retrieved study {study_key!r} is missing from label table"
            )

        status = str(statuses.get(label, "")).strip().lower()
        if status not in KNOWN_STATUSES:
            raise ValueError(
                f"Invalid or missing status {status!r} for label {label!r} "
                f"and retrieved study {study_key!r}"
            )

        similarity = _case_similarity(case)
        labeled_cases.append(
            RetrievedCaseLabel(
                study_key=study_key,
                similarity=similarity,
                weight=similarity_weight(similarity),
                status=status,
            )
        )

    return tuple(labeled_cases)


def compute_retrieval_label_prior(
    *,
    label: str,
    retrieved_cases: Sequence[Any],
    study_label_statuses: Mapping[str, Mapping[str, str]],
    top_cases: int = DEFAULT_TOP_CASES,
) -> RetrievalLabelPrior:
    """Compute one label's similarity-weighted retrieval prior."""
    if top_cases < 0:
        raise ValueError("top_cases must be >= 0")

    labeled_cases = retrieval_case_labels_for_label(
        label=label,
        retrieved_cases=retrieved_cases,
        study_label_statuses=study_label_statuses,
    )

    total_weight = sum(case.weight for case in labeled_cases)
    present_weight = sum(
        case.weight for case in labeled_cases if case.status == PRESENT
    )
    absent_weight = sum(case.weight for case in labeled_cases if case.status == ABSENT)
    uncertain_weight = sum(
        case.weight for case in labeled_cases if case.status == UNCERTAIN
    )
    unmentioned_weight = sum(
        case.weight for case in labeled_cases if case.status == UNMENTIONED
    )
    scoreable_weight = present_weight + absent_weight

    present_prior = present_weight / scoreable_weight if scoreable_weight else 0.0
    absent_prior = absent_weight / scoreable_weight if scoreable_weight else 0.0
    uncertain_rate = uncertain_weight / total_weight if total_weight else 0.0
    unmentioned_rate = unmentioned_weight / total_weight if total_weight else 0.0
    retrieval_confidence = scoreable_weight / total_weight if total_weight else 0.0
    mean_similarity = (
        sum(case.similarity for case in labeled_cases) / len(labeled_cases)
        if labeled_cases
        else 0.0
    )

    supporting_cases = _top_case_ids(
        labeled_cases,
        status=PRESENT,
        top_cases=top_cases,
    )
    contradicting_cases = _top_case_ids(
        labeled_cases,
        status=ABSENT,
        top_cases=top_cases,
    )

    return RetrievalLabelPrior(
        label=label,
        present_prior=present_prior,
        absent_prior=absent_prior,
        uncertain_rate=uncertain_rate,
        unmentioned_rate=unmentioned_rate,
        scoreable_weight=scoreable_weight,
        total_weight=total_weight,
        retrieval_confidence=retrieval_confidence,
        mean_similarity=mean_similarity,
        retrieved_count=len(labeled_cases),
        scoreable_count=sum(
            case.status in SCOREABLE_STATUSES for case in labeled_cases
        ),
        top_supporting_cases=supporting_cases,
        top_contradicting_cases=contradicting_cases,
    )


def compute_retrieval_priors(
    *,
    retrieved_cases: Sequence[Any],
    study_label_statuses: Mapping[str, Mapping[str, str]],
    labels: Sequence[str] = DISEASE_LABELS,
    top_cases: int = DEFAULT_TOP_CASES,
) -> dict[str, RetrievalLabelPrior]:
    """Compute retrieval priors for all requested disease labels."""
    return {
        label: compute_retrieval_label_prior(
            label=label,
            retrieved_cases=retrieved_cases,
            study_label_statuses=study_label_statuses,
            top_cases=top_cases,
        )
        for label in labels
    }


def _top_case_ids(
    cases: Sequence[RetrievedCaseLabel],
    *,
    status: str,
    top_cases: int,
) -> tuple[str, ...]:
    selected = [case for case in cases if case.status == status]
    selected.sort(key=lambda case: case.weight, reverse=True)
    return tuple(case.study_key for case in selected[:top_cases])
