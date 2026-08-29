"""Structured contracts for LLM-assisted label fusion review."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.statuses import LabelStatus


class FusionReviewValidationError(ValueError):
    """Raised when an LLM fusion review violates schema or guardrails."""


class FusionReviewAction(str, Enum):
    """Allowed LLM actions for a deterministic fusion change."""

    KEEP = "keep"
    VETO = "veto"
    UNCERTAIN = "uncertain"


class FusionReviewConfidence(str, Enum):
    """Allowed confidence levels for an LLM fusion review."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class FusionEvidenceAssessment(str, Enum):
    """Allowed evidence assessment values for an LLM fusion review."""

    SUPPORTING = "supporting"
    CONTRADICTORY = "contradictory"
    MIXED = "mixed"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class FusionChangedLabelContext:
    """One deterministic fusion change eligible for LLM review."""

    label: str
    vision_status: LabelStatus
    deterministic_status: LabelStatus
    probability: float
    threshold: float
    positive_count: int
    negative_count: int
    deterministic_reason: str

    def __post_init__(self) -> None:
        if self.label not in DISEASE_LABELS:
            raise ValueError(f"Unsupported fusion label: {self.label!r}")
        if self.vision_status is self.deterministic_status:
            raise ValueError("LLM review context must describe a changed label")


@dataclass(frozen=True)
class FusionLabelReview:
    """Validated LLM review for one deterministic fusion change."""

    label: str
    action: FusionReviewAction
    final_status: LabelStatus
    confidence: FusionReviewConfidence
    evidence_assessment: FusionEvidenceAssessment
    rationale: str
    supporting_case_ids: tuple[str, ...]
    contradicting_case_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.label not in DISEASE_LABELS:
            raise ValueError(f"Unsupported fusion label: {self.label!r}")
        if not self.rationale.strip():
            raise ValueError("Fusion label review rationale must be non-empty")


@dataclass(frozen=True)
class FusionLLMReviewResult:
    """Validated LLM response for all deterministic fusion changes in one study."""

    reviewed_labels: tuple[FusionLabelReview, ...]
    overall_notes: str

    def review_map(self) -> dict[str, FusionLabelReview]:
        """Return reviews keyed by label."""
        return {review.label: review for review in self.reviewed_labels}


FUSION_LLM_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reviewed_labels", "overall_notes"],
    "properties": {
        "reviewed_labels": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "label",
                    "action",
                    "final_status",
                    "confidence",
                    "evidence_assessment",
                    "rationale",
                    "supporting_case_ids",
                    "contradicting_case_ids",
                ],
                "properties": {
                    "label": {
                        "type": "string",
                        "enum": list(DISEASE_LABELS),
                    },
                    "action": {
                        "type": "string",
                        "enum": [item.value for item in FusionReviewAction],
                    },
                    "final_status": {
                        "type": "string",
                        "enum": [
                            LabelStatus.PRESENT.value,
                            LabelStatus.ABSENT.value,
                            LabelStatus.UNCERTAIN.value,
                        ],
                    },
                    "confidence": {
                        "type": "string",
                        "enum": [item.value for item in FusionReviewConfidence],
                    },
                    "evidence_assessment": {
                        "type": "string",
                        "enum": [item.value for item in FusionEvidenceAssessment],
                    },
                    "rationale": {
                        "type": "string",
                    },
                    "supporting_case_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "contradicting_case_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "overall_notes": {
            "type": "string",
        },
    },
}


def _string_tuple(values: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(values, list):
        raise FusionReviewValidationError(f"{field_name} must be a list")
    normalized = tuple(str(value).strip() for value in values)
    if any(not value for value in normalized):
        raise FusionReviewValidationError(f"{field_name} cannot contain blank IDs")
    return normalized


def parse_fusion_llm_review_payload(
    payload: Mapping[str, Any],
) -> FusionLLMReviewResult:
    """Parse raw LLM JSON into typed review objects."""
    reviewed_raw = payload.get("reviewed_labels")
    if not isinstance(reviewed_raw, list):
        raise FusionReviewValidationError("reviewed_labels must be a list")

    reviews: list[FusionLabelReview] = []
    for index, item in enumerate(reviewed_raw):
        if not isinstance(item, Mapping):
            raise FusionReviewValidationError(
                f"reviewed_labels[{index}] must be an object"
            )

        try:
            review = FusionLabelReview(
                label=str(item["label"]).strip(),
                action=FusionReviewAction(str(item["action"]).strip().lower()),
                final_status=LabelStatus(str(item["final_status"]).strip().lower()),
                confidence=FusionReviewConfidence(
                    str(item["confidence"]).strip().lower()
                ),
                evidence_assessment=FusionEvidenceAssessment(
                    str(item["evidence_assessment"]).strip().lower()
                ),
                rationale=str(item["rationale"]).strip(),
                supporting_case_ids=_string_tuple(
                    item["supporting_case_ids"],
                    "supporting_case_ids",
                ),
                contradicting_case_ids=_string_tuple(
                    item["contradicting_case_ids"],
                    "contradicting_case_ids",
                ),
            )
        except KeyError as exc:
            raise FusionReviewValidationError(
                f"reviewed_labels[{index}] missing required field {exc.args[0]!r}"
            ) from exc
        except ValueError as exc:
            raise FusionReviewValidationError(
                f"reviewed_labels[{index}] has invalid value: {exc}"
            ) from exc
        reviews.append(review)

    if not isinstance(payload.get("overall_notes"), str):
        raise FusionReviewValidationError("overall_notes must be a string")
    overall_notes = str(payload["overall_notes"]).strip()

    return FusionLLMReviewResult(
        reviewed_labels=tuple(reviews),
        overall_notes=overall_notes,
    )


def validate_fusion_review_guardrails(
    review_result: FusionLLMReviewResult,
    *,
    changed_labels: Sequence[FusionChangedLabelContext],
    retrieved_case_ids: set[str],
) -> None:
    """Validate LLM review output against deterministic fusion guardrails."""

    expected_labels = {item.label for item in changed_labels}
    actual_labels = {item.label for item in review_result.reviewed_labels}

    missing = sorted(expected_labels - actual_labels)
    unexpected = sorted(actual_labels - expected_labels)
    if missing or unexpected:
        raise FusionReviewValidationError(
            "LLM review labels must exactly match deterministic changed labels; "
            f"missing={missing}, unexpected={unexpected}"
        )

    if len(actual_labels) != len(review_result.reviewed_labels):
        raise FusionReviewValidationError("LLM review contains duplicate labels")

    context_by_label = {item.label: item for item in changed_labels}
    for review in review_result.reviewed_labels:
        context = context_by_label[review.label]
        _validate_review_status_transition(review, context)
        _validate_case_ids(review, retrieved_case_ids)


def _validate_review_status_transition(
    review: FusionLabelReview,
    context: FusionChangedLabelContext,
) -> None:
    """Validate action/final_status consistency for one changed label."""

    if review.action is FusionReviewAction.KEEP:
        expected = context.deterministic_status
    elif review.action is FusionReviewAction.VETO:
        expected = context.vision_status
    elif review.action is FusionReviewAction.UNCERTAIN:
        expected = LabelStatus.UNCERTAIN
    else:
        raise FusionReviewValidationError(f"Unsupported action: {review.action}")

    if review.final_status is not expected:
        raise FusionReviewValidationError(
            f"{review.label} action={review.action.value!r} requires "
            f"final_status={expected.value!r}, got {review.final_status.value!r}"
        )


def _validate_case_ids(review: FusionLabelReview, retrieved_case_ids: set[str]) -> None:
    referenced = set(review.supporting_case_ids) | set(review.contradicting_case_ids)
    unknown = sorted(referenced - retrieved_case_ids)
    if unknown:
        raise FusionReviewValidationError(
            f"{review.label} references unknown retrieved case IDs: {unknown}"
        )
