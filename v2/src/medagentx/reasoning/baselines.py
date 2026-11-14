"""Non-LLM retrieval baselines for controlled fusion experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.statuses import LabelStatus
from medagentx.reasoning.fuse import is_gray_zone
from medagentx.retrieval.index import RetrievedStudy
from medagentx.vision.inference_output import VisionStudyOutput


@dataclass(frozen=True)
class StructuredVoteLabelResult:
    """One label decision from one-vote-per-neighbor structured evidence."""

    label: str
    vision_status: LabelStatus
    final_status: LabelStatus
    in_gray_zone: bool
    positive_votes: int
    negative_votes: int
    uncertain_votes: int
    unmentioned_votes: int
    positive_weight: float
    negative_weight: float
    changed: bool
    reason: str


@dataclass(frozen=True)
class StructuredVoteStudyResult:
    """Structured kNN decisions for one query study."""

    study_key: str
    method: str
    labels: tuple[StructuredVoteLabelResult, ...]


def structured_vote_study(
    output: VisionStudyOutput,
    neighbors: Sequence[RetrievedStudy],
    neighbor_statuses: Mapping[str, Mapping[str, LabelStatus]],
    *,
    margin: float,
    gray_zone_only: bool,
    similarity_weighted: bool,
) -> StructuredVoteStudyResult:
    """Apply independent report-level votes to one vision study output.

    Each retrieved study contributes at most one vote per label. Uncertain and
    unmentioned statuses abstain. Ties and no-evidence cells retain vision.
    """
    if margin < 0:
        raise ValueError("margin must be >= 0")
    if not neighbors:
        raise ValueError("neighbors must not be empty")
    if len({neighbor.study_key for neighbor in neighbors}) != len(neighbors):
        raise ValueError("neighbors must contain unique study keys")

    method = (
        "knn_similarity_weighted"
        if similarity_weighted
        else "knn_majority"
    ) + ("_gray" if gray_zone_only else "_all")
    results: list[StructuredVoteLabelResult] = []

    for label_output in output.labels:
        label = label_output.label
        if label not in DISEASE_LABELS:
            raise ValueError(f"Unsupported disease label: {label!r}")
        positive_votes = negative_votes = 0
        uncertain_votes = unmentioned_votes = 0
        positive_weight = negative_weight = 0.0
        for neighbor in neighbors:
            statuses = neighbor_statuses.get(neighbor.study_key)
            if statuses is None:
                raise ValueError(
                    f"Missing structured labels for neighbor {neighbor.study_key!r}"
                )
            status = statuses[label]
            weight = max(0.0, float(neighbor.similarity))
            if status is LabelStatus.PRESENT:
                positive_votes += 1
                positive_weight += weight
            elif status is LabelStatus.ABSENT:
                negative_votes += 1
                negative_weight += weight
            elif status is LabelStatus.UNCERTAIN:
                uncertain_votes += 1
            elif status is LabelStatus.UNMENTIONED:
                unmentioned_votes += 1
            else:
                raise ValueError(f"Unsupported neighbor status: {status!r}")

        gray = is_gray_zone(
            label_output.probability,
            label_output.threshold,
            margin=margin,
        )
        final = label_output.status
        reason = "vision retained outside gray zone"
        decision_allowed = gray or not gray_zone_only
        if decision_allowed:
            positive_score = (
                positive_weight if similarity_weighted else float(positive_votes)
            )
            negative_score = (
                negative_weight if similarity_weighted else float(negative_votes)
            )
            if positive_score > negative_score:
                final = LabelStatus.PRESENT
                reason = "positive structured neighbor vote"
            elif negative_score > positive_score:
                final = LabelStatus.ABSENT
                reason = "negative structured neighbor vote"
            else:
                reason = "vision retained on tied or absent structured evidence"

        results.append(
            StructuredVoteLabelResult(
                label=label,
                vision_status=label_output.status,
                final_status=final,
                in_gray_zone=gray,
                positive_votes=positive_votes,
                negative_votes=negative_votes,
                uncertain_votes=uncertain_votes,
                unmentioned_votes=unmentioned_votes,
                positive_weight=positive_weight,
                negative_weight=negative_weight,
                changed=final is not label_output.status,
                reason=reason,
            )
        )

    return StructuredVoteStudyResult(
        study_key=output.study_key,
        method=method,
        labels=tuple(results),
    )


def structured_vote_status_map(
    results: Sequence[StructuredVoteStudyResult],
) -> dict[tuple[str, str], LabelStatus]:
    """Flatten structured vote results for the offline Judge."""
    predictions: dict[tuple[str, str], LabelStatus] = {}
    for result in results:
        for label_result in result.labels:
            key = (result.study_key, label_result.label)
            if key in predictions:
                raise ValueError(f"Duplicate structured vote result: {key!r}")
            predictions[key] = label_result.final_status
    return predictions
