"""Tests for one-vote-per-neighbor retrieval baselines."""

from __future__ import annotations

from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.statuses import LabelStatus
from medagentx.reasoning.baselines import structured_vote_study
from medagentx.retrieval.index import RetrievedStudy
from medagentx.vision.inference_output import (
    VisionLabelOutput,
    VisionStudyOutput,
)


def _output(probability: float = 0.45) -> VisionStudyOutput:
    return VisionStudyOutput(
        study_key="query",
        deid_patient_id="query-patient",
        split="val",
        view_count=1,
        dicom_paths=("query.dcm",),
        vision_backend_id="test",
        study_embedding=(0.1, 0.2),
        labels=tuple(
            VisionLabelOutput.from_probability(label, probability, 0.5)
            for label in DISEASE_LABELS
        ),
    )


def _neighbor(key: str, similarity: float) -> RetrievedStudy:
    return RetrievedStudy(
        study_key=key,
        deid_patient_id=f"patient-{key}",
        document="report",
        distance=1.0 - similarity,
        similarity=similarity,
    )


def _statuses(**overrides: LabelStatus) -> dict[str, LabelStatus]:
    values = {label: LabelStatus.UNMENTIONED for label in DISEASE_LABELS}
    values.update(overrides)
    return values


def test_majority_vote_counts_each_neighbor_once() -> None:
    neighbors = [_neighbor("a", 0.8), _neighbor("b", 0.7), _neighbor("c", 0.6)]
    statuses = {
        "a": _statuses(Atelectasis=LabelStatus.PRESENT),
        "b": _statuses(Atelectasis=LabelStatus.PRESENT),
        "c": _statuses(Atelectasis=LabelStatus.ABSENT),
    }

    result = structured_vote_study(
        _output(),
        neighbors,
        statuses,
        margin=0.15,
        gray_zone_only=True,
        similarity_weighted=False,
    )

    atelectasis = result.labels[0]
    assert atelectasis.positive_votes == 2
    assert atelectasis.negative_votes == 1
    assert atelectasis.final_status is LabelStatus.PRESENT


def test_similarity_weighting_can_override_unweighted_majority() -> None:
    neighbors = [_neighbor("a", 0.1), _neighbor("b", 0.1), _neighbor("c", 0.9)]
    statuses = {
        "a": _statuses(Atelectasis=LabelStatus.PRESENT),
        "b": _statuses(Atelectasis=LabelStatus.PRESENT),
        "c": _statuses(Atelectasis=LabelStatus.ABSENT),
    }

    result = structured_vote_study(
        _output(),
        neighbors,
        statuses,
        margin=0.15,
        gray_zone_only=True,
        similarity_weighted=True,
    )

    assert result.labels[0].final_status is LabelStatus.ABSENT


def test_gray_zone_gate_preserves_strong_vision_prediction() -> None:
    neighbors = [_neighbor("a", 0.9)]
    statuses = {"a": _statuses(Atelectasis=LabelStatus.ABSENT)}

    result = structured_vote_study(
        _output(probability=0.9),
        neighbors,
        statuses,
        margin=0.15,
        gray_zone_only=True,
        similarity_weighted=False,
    )

    assert result.labels[0].vision_status is LabelStatus.PRESENT
    assert result.labels[0].final_status is LabelStatus.PRESENT
    assert not result.labels[0].changed
