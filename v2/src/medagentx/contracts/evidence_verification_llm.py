"""Structured contracts for LLM-assisted evidence verification review."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.statuses import LabelStatus


class EvidenceVerificationReviewValidationError(ValueError):
    """Raised when an LLM evidence review violates schema or guardrails."""


class EvidenceReviewConfidence(str, Enum):
    """Allowed confidence levels for an LLM evidence review."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class EvidenceReviewSupportLevel(str, Enum):
    """Allowed support levels for LLM-reviewed evidence fields."""

    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    MIXED = "mixed"
    CONTRADICTORY = "contradictory"


class EvidenceReviewAssessment(str, Enum):
    """Overall LLM assessment of evidence for one predicted label."""

    SUPPORTING = "supporting"
    CONTRADICTORY = "contradictory"
    MIXED = "mixed"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class EvidenceVerificationLabelContext:
    """One predicted label eligible for LLM evidence review."""

    label: str
    fused_status: LabelStatus
    vision_status: LabelStatus
    deterministic_evidence_score: int
    deterministic_vision_support: str
    deterministic_retrieval_support: str
    deterministic_contradiction_level: str
    retrieval_positive_count: int
    retrieval_negative_count: int
    in_gray_zone: bool
    fusion_changed: bool
    fusion_reason: str
    deterministic_evidence_summary: str

    def __post_init__(self) -> None:
        if self.label not in DISEASE_LABELS:
            raise ValueError(f"Unsupported evidence label: {self.label!r}")
        if self.fused_status is LabelStatus.ABSENT:
            raise ValueError("LLM evidence review context must be for a predicted label")
        if not 1 <= int(self.deterministic_evidence_score) <= 5:
            raise ValueError("deterministic_evidence_score must be in the range 1-5")


@dataclass(frozen=True)
class EvidenceVerificationLabelReview:
    """Validated LLM evidence review for one predicted label."""

    label: str
    evidence_score: int
    confidence: EvidenceReviewConfidence
    vision_support: EvidenceReviewSupportLevel
    retrieval_support: EvidenceReviewSupportLevel
    contradiction_level: EvidenceReviewSupportLevel
    evidence_assessment: EvidenceReviewAssessment
    rationale: str
    supporting_case_ids: tuple[str, ...]
    contradicting_case_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.label not in DISEASE_LABELS:
            raise ValueError(f"Unsupported evidence label: {self.label!r}")
        if not 1 <= int(self.evidence_score) <= 5:
            raise ValueError("evidence_score must be in the range 1-5")
        if not self.rationale.strip():
            raise ValueError("Evidence label review rationale must be non-empty")


@dataclass(frozen=True)
class EvidenceVerificationLLMReviewResult:
    """Validated LLM response for evidence verification in one study."""

    reviewed_labels: tuple[EvidenceVerificationLabelReview, ...]
    overall_evidence_score: int
    vision_evidence_summary: str
    retrieval_evidence_summary: str
    fusion_evidence_summary: str
    evidence_narrative: str
    overall_notes: str

    def __post_init__(self) -> None:
        if not 1 <= int(self.overall_evidence_score) <= 5:
            raise ValueError("overall_evidence_score must be in the range 1-5")

    def review_map(self) -> dict[str, EvidenceVerificationLabelReview]:
        """Return reviews keyed by label."""
        return {review.label: review for review in self.reviewed_labels}


EVIDENCE_VERIFICATION_LLM_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "reviewed_labels",
        "overall_evidence_score",
        "vision_evidence_summary",
        "retrieval_evidence_summary",
        "fusion_evidence_summary",
        "evidence_narrative",
        "overall_notes",
    ],
    "properties": {
        "reviewed_labels": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "label",
                    "evidence_score",
                    "confidence",
                    "vision_support",
                    "retrieval_support",
                    "contradiction_level",
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
                    "evidence_score": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "confidence": {
                        "type": "string",
                        "enum": [item.value for item in EvidenceReviewConfidence],
                    },
                    "vision_support": {
                        "type": "string",
                        "enum": [item.value for item in EvidenceReviewSupportLevel],
                    },
                    "retrieval_support": {
                        "type": "string",
                        "enum": [item.value for item in EvidenceReviewSupportLevel],
                    },
                    "contradiction_level": {
                        "type": "string",
                        "enum": [item.value for item in EvidenceReviewSupportLevel],
                    },
                    "evidence_assessment": {
                        "type": "string",
                        "enum": [item.value for item in EvidenceReviewAssessment],
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
        "overall_evidence_score": {
            "type": "integer",
            "minimum": 1,
            "maximum": 5,
        },
        "vision_evidence_summary": {
            "type": "string",
        },
        "retrieval_evidence_summary": {
            "type": "string",
        },
        "fusion_evidence_summary": {
            "type": "string",
        },
        "evidence_narrative": {
            "type": "string",
        },
        "overall_notes": {
            "type": "string",
        },
    },
}


def _string_tuple(values: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(values, list):
        raise EvidenceVerificationReviewValidationError(f"{field_name} must be a list")
    normalized = tuple(str(value).strip() for value in values)
    if any(not value for value in normalized):
        raise EvidenceVerificationReviewValidationError(
            f"{field_name} cannot contain blank IDs"
        )
    return normalized


def _required_string(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str):
        raise EvidenceVerificationReviewValidationError(
            f"{field_name} must be a string"
        )
    return value.strip()


def _required_score(payload: Mapping[str, Any], field_name: str) -> int:
    try:
        score = int(payload[field_name])
    except KeyError as exc:
        raise EvidenceVerificationReviewValidationError(
            f"missing required field {field_name!r}"
        ) from exc
    except (TypeError, ValueError) as exc:
        raise EvidenceVerificationReviewValidationError(
            f"{field_name} must be an integer"
        ) from exc

    if not 1 <= score <= 5:
        raise EvidenceVerificationReviewValidationError(
            f"{field_name} must be in the range 1-5"
        )
    return score


def parse_evidence_verification_llm_review_payload(
    payload: Mapping[str, Any],
) -> EvidenceVerificationLLMReviewResult:
    """Parse raw LLM JSON into typed evidence review objects."""
    reviewed_raw = payload.get("reviewed_labels")
    if not isinstance(reviewed_raw, list):
        raise EvidenceVerificationReviewValidationError(
            "reviewed_labels must be a list"
        )

    reviews: list[EvidenceVerificationLabelReview] = []
    for index, item in enumerate(reviewed_raw):
        if not isinstance(item, Mapping):
            raise EvidenceVerificationReviewValidationError(
                f"reviewed_labels[{index}] must be an object"
            )

        try:
            review = EvidenceVerificationLabelReview(
                label=str(item["label"]).strip(),
                evidence_score=_required_score(item, "evidence_score"),
                confidence=EvidenceReviewConfidence(
                    str(item["confidence"]).strip().lower()
                ),
                vision_support=EvidenceReviewSupportLevel(
                    str(item["vision_support"]).strip().lower()
                ),
                retrieval_support=EvidenceReviewSupportLevel(
                    str(item["retrieval_support"]).strip().lower()
                ),
                contradiction_level=EvidenceReviewSupportLevel(
                    str(item["contradiction_level"]).strip().lower()
                ),
                evidence_assessment=EvidenceReviewAssessment(
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
            raise EvidenceVerificationReviewValidationError(
                f"reviewed_labels[{index}] missing required field {exc.args[0]!r}"
            ) from exc
        except ValueError as exc:
            raise EvidenceVerificationReviewValidationError(
                f"reviewed_labels[{index}] has invalid value: {exc}"
            ) from exc
        reviews.append(review)

    return EvidenceVerificationLLMReviewResult(
        reviewed_labels=tuple(reviews),
        overall_evidence_score=_required_score(payload, "overall_evidence_score"),
        vision_evidence_summary=_required_string(payload, "vision_evidence_summary"),
        retrieval_evidence_summary=_required_string(
            payload,
            "retrieval_evidence_summary",
        ),
        fusion_evidence_summary=_required_string(payload, "fusion_evidence_summary"),
        evidence_narrative=_required_string(payload, "evidence_narrative"),
        overall_notes=_required_string(payload, "overall_notes"),
    )


def validate_evidence_verification_review_guardrails(
    review_result: EvidenceVerificationLLMReviewResult,
    *,
    label_contexts: Sequence[EvidenceVerificationLabelContext],
    retrieved_case_ids: set[str],
) -> None:
    """Validate LLM evidence review output against deterministic verification context."""

    expected_labels = {item.label for item in label_contexts}
    actual_labels = {item.label for item in review_result.reviewed_labels}

    missing = sorted(expected_labels - actual_labels)
    unexpected = sorted(actual_labels - expected_labels)
    if missing or unexpected:
        raise EvidenceVerificationReviewValidationError(
            "LLM evidence review labels must exactly match predicted labels; "
            f"missing={missing}, unexpected={unexpected}"
        )

    if len(actual_labels) != len(review_result.reviewed_labels):
        raise EvidenceVerificationReviewValidationError(
            "LLM evidence review contains duplicate labels"
        )

    for review in review_result.reviewed_labels:
        _validate_case_ids(review, retrieved_case_ids)


def _validate_case_ids(
    review: EvidenceVerificationLabelReview,
    retrieved_case_ids: set[str],
) -> None:
    referenced = set(review.supporting_case_ids) | set(review.contradicting_case_ids)
    unknown = sorted(referenced - retrieved_case_ids)
    if unknown:
        raise EvidenceVerificationReviewValidationError(
            f"{review.label} references unknown retrieved case IDs: {unknown}"
        )