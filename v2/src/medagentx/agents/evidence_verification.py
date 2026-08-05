"""Deterministic Evidence Verification Agent for fused label outputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.statuses import LabelStatus
from medagentx.reasoning.constants import GRAY_ZONE_MARGIN
from medagentx.reasoning.fuse import FusionStudyResult
from medagentx.reasoning.mentions import (
    LABEL_TERMS,
    MentionCounts,
    RetrievedReportCase,
    count_retrieval_mentions,
    sentence_has_negation,
    split_sentences,
)
from medagentx.vision.inference_output import VisionStudyOutput


class VerificationStatus(str, Enum):
    """Structured verification result for one label."""

    SUPPORTED = "supported"
    WEAK_SUPPORT = "weak_support"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"


class EvidenceLevel(str, Enum):
    """Human-readable evidence level for component evidence fields."""

    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    MIXED = "mixed"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True)
class EvidenceSnippet:
    """One retrieved report sentence used as evidence."""

    case_id: str
    similarity: float | None
    snippet: str


@dataclass(frozen=True)
class LabelVerificationResult:
    """Evidence verification output for one disease label."""

    label: str
    fused_status: LabelStatus
    verification_status: VerificationStatus
    evidence_score: int
    vision_support: EvidenceLevel
    retrieval_support: EvidenceLevel
    contradiction_level: EvidenceLevel
    in_gray_zone: bool
    fusion_changed: bool
    evidence_summary: str
    supporting_evidence: tuple[EvidenceSnippet, ...]
    contradicting_evidence: tuple[EvidenceSnippet, ...]

    def __post_init__(self) -> None:
        if self.label not in DISEASE_LABELS:
            raise ValueError(f"Unsupported verification label: {self.label!r}")
        if not 1 <= self.evidence_score <= 5:
            raise ValueError("evidence_score must be in the range 1-5")


@dataclass(frozen=True)
class StudyEvidenceVerificationResult:
    """Evidence verification output for one study."""

    study_key: str
    labels: tuple[LabelVerificationResult, ...]
    verification_policy_version: str = "evidence_verification_policy_v1"

    def label_map(self) -> dict[str, LabelVerificationResult]:
        return {item.label: item for item in self.labels}


def _case_value(case: RetrievedReportCase | Mapping[str, Any], key: str) -> Any:
    value = getattr(case, key, None)
    if value is not None:
        return value
    if isinstance(case, Mapping):
        return case.get(key)
    return None


def _case_document(case: RetrievedReportCase | Mapping[str, Any]) -> str:
    document = _case_value(case, "document")
    if document is not None:
        return str(document or "")
    if isinstance(case, Mapping):
        return str(case.get("retrieved_document") or "")
    return ""


def _case_id(case: RetrievedReportCase | Mapping[str, Any]) -> str:
    for key in ("study_key", "case_id", "id"):
        value = _case_value(case, key)
        if value:
            return str(value)
    return ""


def _case_similarity(case: RetrievedReportCase | Mapping[str, Any]) -> float | None:
    value = _case_value(case, "similarity")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _evidence_snippets_for_label(
    label: str,
    retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
    *,
    negative: bool,
    max_snippets: int = 3,
) -> tuple[EvidenceSnippet, ...]:
    snippets: list[EvidenceSnippet] = []
    terms = LABEL_TERMS[label]
    for case in retrieved_cases:
        document = _case_document(case)
        for sentence in split_sentences(document):
            matched_terms = [term for term in terms if term in sentence]
            if not matched_terms:
                continue
            is_negative = any(
                sentence_has_negation(sentence, term) for term in matched_terms
            )
            if is_negative != negative:
                continue
            snippets.append(
                EvidenceSnippet(
                    case_id=_case_id(case),
                    similarity=_case_similarity(case),
                    snippet=sentence[:260],
                )
            )
            if len(snippets) >= max_snippets:
                return tuple(snippets)
    return tuple(snippets)


def _vision_support(
    *,
    fused_status: LabelStatus,
    probability: float,
    threshold: float,
    margin: float,
) -> EvidenceLevel:
    delta = float(probability) - float(threshold)
    if fused_status is LabelStatus.PRESENT:
        if delta >= margin:
            return EvidenceLevel.STRONG
        if delta >= 0:
            return EvidenceLevel.MODERATE
        if abs(delta) <= margin:
            return EvidenceLevel.WEAK
        return EvidenceLevel.NONE
    if fused_status is LabelStatus.ABSENT:
        if delta <= -margin:
            return EvidenceLevel.STRONG
        if delta < 0:
            return EvidenceLevel.MODERATE
        if abs(delta) <= margin:
            return EvidenceLevel.WEAK
        return EvidenceLevel.CONTRADICTORY
    if abs(delta) <= margin:
        return EvidenceLevel.WEAK
    return EvidenceLevel.NONE


def _retrieval_support(
    *,
    fused_status: LabelStatus,
    counts: MentionCounts,
) -> EvidenceLevel:
    positives = counts.positive_count
    negatives = counts.negative_count
    if fused_status is LabelStatus.PRESENT:
        if negatives >= 3 and negatives > positives:
            return EvidenceLevel.CONTRADICTORY
        if positives >= 4 and negatives == 0:
            return EvidenceLevel.STRONG
        if positives >= 2 and positives >= negatives:
            return EvidenceLevel.MODERATE
        if positives > 0:
            return EvidenceLevel.WEAK
        return EvidenceLevel.NONE
    if fused_status is LabelStatus.ABSENT:
        if positives >= 3 and positives > negatives:
            return EvidenceLevel.CONTRADICTORY
        if negatives >= 3 and positives == 0:
            return EvidenceLevel.STRONG
        if negatives > positives:
            return EvidenceLevel.MODERATE
        if negatives > 0:
            return EvidenceLevel.WEAK
        return EvidenceLevel.NONE
    if positives > 0 and negatives > 0:
        return EvidenceLevel.MIXED
    if positives > 0 or negatives > 0:
        return EvidenceLevel.WEAK
    return EvidenceLevel.NONE


def _contradiction_level(
    *,
    vision_support: EvidenceLevel,
    retrieval_support: EvidenceLevel,
) -> EvidenceLevel:
    if EvidenceLevel.CONTRADICTORY in (vision_support, retrieval_support):
        return EvidenceLevel.STRONG
    if retrieval_support is EvidenceLevel.MIXED:
        return EvidenceLevel.WEAK
    return EvidenceLevel.NONE


def _verification_status_and_score(
    *,
    fused_status: LabelStatus,
    vision_support: EvidenceLevel,
    retrieval_support: EvidenceLevel,
    contradiction_level: EvidenceLevel,
) -> tuple[VerificationStatus, int]:
    if contradiction_level is EvidenceLevel.STRONG:
        return VerificationStatus.CONTRADICTED, 2

    strong_sources = sum(
        level is EvidenceLevel.STRONG for level in (vision_support, retrieval_support)
    )
    supporting_sources = sum(
        level in (EvidenceLevel.WEAK, EvidenceLevel.MODERATE, EvidenceLevel.STRONG)
        for level in (vision_support, retrieval_support)
    )

    if fused_status is LabelStatus.ABSENT:
        if supporting_sources > 0:
            return VerificationStatus.NOT_APPLICABLE, 1
        return VerificationStatus.NOT_APPLICABLE, 1

    if fused_status is LabelStatus.PRESENT:
        if strong_sources == 2:
            return VerificationStatus.SUPPORTED, 5
        if strong_sources == 1 and supporting_sources == 2:
            return VerificationStatus.SUPPORTED, 4
        if supporting_sources == 2:
            return VerificationStatus.WEAK_SUPPORT, 3
        if supporting_sources == 1:
            return VerificationStatus.WEAK_SUPPORT, 2
        return VerificationStatus.INSUFFICIENT_EVIDENCE, 1

    if retrieval_support is EvidenceLevel.MIXED:
        return VerificationStatus.WEAK_SUPPORT, 3
    if supporting_sources > 0:
        return VerificationStatus.WEAK_SUPPORT, 2
    return VerificationStatus.INSUFFICIENT_EVIDENCE, 1


def _summary(
    *,
    fused_status: LabelStatus,
    probability: float,
    threshold: float,
    counts: MentionCounts,
    verification_status: VerificationStatus,
    evidence_score: int,
) -> str:
    return (
        f"fused={fused_status.value}; p={probability:.4f}; "
        f"threshold={threshold:.4f}; retrieval_pos={counts.positive_count}; "
        f"retrieval_neg={counts.negative_count}; "
        f"verification={verification_status.value}; score={evidence_score}"
    )


def verify_study_evidence(
    *,
    vision_output: VisionStudyOutput,
    fusion_result: FusionStudyResult,
    retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
    margin: float = GRAY_ZONE_MARGIN,
) -> StudyEvidenceVerificationResult:
    """Verify fused label evidence for one study without changing labels."""
    if vision_output.study_key != fusion_result.study_key:
        raise ValueError(
            "vision_output and fusion_result study_key mismatch: "
            f"{vision_output.study_key!r} != {fusion_result.study_key!r}"
        )

    vision_by_label = vision_output.label_map()
    fusion_by_label = {item.label: item for item in fusion_result.labels}
    missing_vision = sorted(set(DISEASE_LABELS) - set(vision_by_label))
    missing_fusion = sorted(set(DISEASE_LABELS) - set(fusion_by_label))
    if missing_vision or missing_fusion:
        raise ValueError(
            "Missing verification labels: "
            f"vision={missing_vision}, fusion={missing_fusion}"
        )

    mention_counts = count_retrieval_mentions(retrieved_cases)
    results: list[LabelVerificationResult] = []
    for label in DISEASE_LABELS:
        vision_label = vision_by_label[label]
        fused_label = fusion_by_label[label]
        counts = mention_counts[label]
        vision_support = _vision_support(
            fused_status=fused_label.fused_status,
            probability=fused_label.probability,
            threshold=fused_label.threshold,
            margin=margin,
        )
        retrieval_support = _retrieval_support(
            fused_status=fused_label.fused_status,
            counts=counts,
        )
        contradiction_level = _contradiction_level(
            vision_support=vision_support,
            retrieval_support=retrieval_support,
        )
        verification_status, evidence_score = _verification_status_and_score(
            fused_status=fused_label.fused_status,
            vision_support=vision_support,
            retrieval_support=retrieval_support,
            contradiction_level=contradiction_level,
        )
        results.append(
            LabelVerificationResult(
                label=label,
                fused_status=fused_label.fused_status,
                verification_status=verification_status,
                evidence_score=evidence_score,
                vision_support=vision_support,
                retrieval_support=retrieval_support,
                contradiction_level=contradiction_level,
                in_gray_zone=fused_label.in_gray_zone,
                fusion_changed=fused_label.vision_status != fused_label.fused_status,
                evidence_summary=_summary(
                    fused_status=fused_label.fused_status,
                    probability=vision_label.probability,
                    threshold=vision_label.threshold,
                    counts=counts,
                    verification_status=verification_status,
                    evidence_score=evidence_score,
                ),
                supporting_evidence=_evidence_snippets_for_label(
                    label,
                    retrieved_cases,
                    negative=False,
                ),
                contradicting_evidence=_evidence_snippets_for_label(
                    label,
                    retrieved_cases,
                    negative=True,
                ),
            )
        )

    return StudyEvidenceVerificationResult(
        study_key=vision_output.study_key,
        labels=tuple(results),
    )


class EvidenceVerificationAgent:
    """Rules-first verification agent with an explicit callable interface."""

    def __init__(self, *, margin: float = GRAY_ZONE_MARGIN) -> None:
        self.margin = float(margin)

    def verify(
        self,
        *,
        vision_output: VisionStudyOutput,
        fusion_result: FusionStudyResult,
        retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
    ) -> StudyEvidenceVerificationResult:
        return verify_study_evidence(
            vision_output=vision_output,
            fusion_result=fusion_result,
            retrieved_cases=retrieved_cases,
            margin=self.margin,
        )
