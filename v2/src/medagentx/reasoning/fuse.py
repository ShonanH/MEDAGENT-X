"""Deterministic gray-zone label fusion over vision and retrieval evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from medagentx.labels.statuses import LabelStatus
from medagentx.reasoning.constants import (
    DEMOTION_MIN_NEGATIVE_COUNT,
    DEMOTION_REQUIRES_NEGATIVE_MAJORITY,
    FUSION_LABELS,
    FUSION_POLICY_VERSION,
    GRAY_ZONE_MARGIN,
    LABEL_FUSION_RULE_OVERRIDES,
    PROMOTION_MAX_NEGATIVE_COUNT,
    PROMOTION_MIN_POSITIVE_COUNT,
)
from medagentx.reasoning.mentions import (
    MentionCounts,
    RetrievedReportCase,
    count_retrieval_mentions,
)


@dataclass(frozen=True)
class VisionLabelPrediction:
    """One disease prediction from the vision backend."""

    label: str
    probability: float
    threshold: float
    status: LabelStatus | None = None

    def __post_init__(self) -> None:
        if self.label not in FUSION_LABELS:
            raise ValueError(f"Unsupported fusion label: {self.label!r}")
        if self.status is not None and self.status not in {
            LabelStatus.PRESENT,
            LabelStatus.ABSENT,
        }:
            raise ValueError(
                f"Vision status must be present or absent, got {self.status!r}"
            )

    @property
    def vision_status(self) -> LabelStatus:
        if self.status is not None:
            return self.status
        return vision_status_from_probability(self.probability, self.threshold)


@dataclass(frozen=True)
class FusedLabelPrediction:
    """One fused disease status with audit metadata."""

    label: str
    vision_status: LabelStatus
    fused_status: LabelStatus
    probability: float
    threshold: float
    in_gray_zone: bool
    positive_count: int
    negative_count: int
    refinement_reason: str


@dataclass(frozen=True)
class FusionStudyResult:
    """Fusion output for one study."""

    study_key: str
    fusion_policy_version: str
    labels: tuple[FusedLabelPrediction, ...]


@dataclass(frozen=True)
class FusionLabelRule:
    """Per-label deterministic fusion knobs."""

    promotion_min_positive_count: int = PROMOTION_MIN_POSITIVE_COUNT
    promotion_max_negative_count: int = PROMOTION_MAX_NEGATIVE_COUNT
    demotion_min_negative_count: int = DEMOTION_MIN_NEGATIVE_COUNT
    demotion_requires_negative_majority: bool = DEMOTION_REQUIRES_NEGATIVE_MAJORITY


def fusion_rule_for_label(label: str) -> FusionLabelRule:
    """Return the default rule plus any label-specific overrides."""
    if label not in FUSION_LABELS:
        raise ValueError(f"Unsupported fusion label: {label!r}")
    overrides = LABEL_FUSION_RULE_OVERRIDES.get(label, {})
    allowed = set(FusionLabelRule.__dataclass_fields__)
    unexpected = sorted(set(overrides) - allowed)
    if unexpected:
        raise ValueError(f"Unexpected fusion rule keys for {label}: {unexpected}")
    return FusionLabelRule(**overrides)


def vision_status_from_probability(
    probability: float,
    threshold: float,
) -> LabelStatus:
    """Map a calibrated vision probability to a binary present/absent status."""
    return (
        LabelStatus.PRESENT
        if float(probability) >= float(threshold)
        else LabelStatus.ABSENT
    )


def is_gray_zone(
    probability: float,
    threshold: float,
    *,
    margin: float = GRAY_ZONE_MARGIN,
) -> bool:
    """Return True when fusion is allowed to override vision for this label."""
    return abs(float(probability) - float(threshold)) <= float(margin)


def retrieval_supports_promotion(
    counts: MentionCounts,
    rule: FusionLabelRule,
) -> bool:
    """Strong net-positive retrieval evidence required before promotion."""
    return (
        counts.positive_count >= rule.promotion_min_positive_count
        and counts.negative_count <= rule.promotion_max_negative_count
    )


def retrieval_supports_demotion(
    counts: MentionCounts,
    rule: FusionLabelRule,
) -> bool:
    """Return True when retrieval negatives outweigh positives."""
    if counts.negative_count < rule.demotion_min_negative_count:
        return False
    if not rule.demotion_requires_negative_majority:
        return True
    if not DEMOTION_REQUIRES_NEGATIVE_MAJORITY:
        return False
    return counts.negative_count > counts.positive_count


def retrieval_strongly_negative(
    counts: MentionCounts,
    rule: FusionLabelRule,
) -> bool:
    """Mirror the promotion bar for strong negative-only retrieval context."""
    return (
        counts.positive_count == 0
        and counts.negative_count >= rule.promotion_min_positive_count
    )


def fuse_label(
    prediction: VisionLabelPrediction,
    mention_counts: MentionCounts,
    *,
    margin: float = GRAY_ZONE_MARGIN,
) -> FusedLabelPrediction:
    """Apply the locked fusion policy to one disease label."""
    vision_status = prediction.vision_status
    rule = fusion_rule_for_label(prediction.label)
    gray_zone = is_gray_zone(
        prediction.probability,
        prediction.threshold,
        margin=margin,
    )
    fused_status = vision_status
    reason = "vision kept (strong zone)"

    if gray_zone:
        reason = "vision kept (gray zone, insufficient retrieval signal)"
        if (
            vision_status == LabelStatus.ABSENT
            and retrieval_supports_promotion(mention_counts, rule)
        ):
            fused_status = LabelStatus.PRESENT
            reason = (
                "promoted absent to present: "
                f"{mention_counts.positive_count} positive mentions, "
                f"{mention_counts.negative_count} negative mentions"
            )
        elif (
            vision_status == LabelStatus.PRESENT
            and retrieval_supports_demotion(mention_counts, rule)
        ):
            if retrieval_strongly_negative(mention_counts, rule):
                fused_status = LabelStatus.ABSENT
                reason = (
                    "demoted present to absent: "
                    f"{mention_counts.negative_count} negative mentions, "
                    f"{mention_counts.positive_count} positive mentions"
                )
            else:
                fused_status = LabelStatus.UNCERTAIN
                reason = (
                    "demoted present to uncertain: "
                    f"{mention_counts.negative_count} negative mentions outweigh "
                    f"{mention_counts.positive_count} positive mentions"
                )

    return FusedLabelPrediction(
        label=prediction.label,
        vision_status=vision_status,
        fused_status=fused_status,
        probability=float(prediction.probability),
        threshold=float(prediction.threshold),
        in_gray_zone=gray_zone,
        positive_count=mention_counts.positive_count,
        negative_count=mention_counts.negative_count,
        refinement_reason=reason,
    )


def fuse_study_labels(
    vision_predictions: Mapping[str, VisionLabelPrediction],
    retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
    *,
    study_key: str = "",
    margin: float = GRAY_ZONE_MARGIN,
) -> FusionStudyResult:
    """Fuse vision predictions with retrieved report evidence for one study."""
    missing_labels = [label for label in FUSION_LABELS if label not in vision_predictions]
    if missing_labels:
        raise ValueError(
            "Missing vision predictions for labels: "
            + ", ".join(missing_labels)
        )

    mention_counts = count_retrieval_mentions(retrieved_cases)
    fused_labels: list[FusedLabelPrediction] = []
    for label in FUSION_LABELS:
        fused_labels.append(
            fuse_label(
                vision_predictions[label],
                mention_counts[label],
                margin=margin,
            )
        )

    return FusionStudyResult(
        study_key=study_key,
        fusion_policy_version=FUSION_POLICY_VERSION,
        labels=tuple(fused_labels),
    )
