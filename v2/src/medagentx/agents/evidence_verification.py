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
class LabeledEvidenceSnippet:
    """One evidence snippet tied to the predicted label it supports or disputes."""

    label: str
    case_id: str
    similarity: float | None
    snippet: str


@dataclass(frozen=True)
class LabelVerificationResult:
    """Evidence verification output for one disease label."""

    label: str
    fused_status: LabelStatus
    vision_status: LabelStatus
    evidence_score: int
    vision_support: EvidenceLevel
    retrieval_support: EvidenceLevel
    contradiction_level: EvidenceLevel
    retrieval_positive_count: int
    retrieval_negative_count: int
    in_gray_zone: bool
    fusion_changed: bool
    fusion_reason: str
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
    predicted_labels: tuple[str, ...]
    overall_evidence_score: int
    vision_evidence_summary: str
    retrieval_evidence_summary: str
    fusion_evidence_summary: str
    evidence_narrative: str
    supporting_evidence: tuple[LabeledEvidenceSnippet, ...]
    contradicting_evidence: tuple[LabeledEvidenceSnippet, ...]
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


def _evidence_score(
    *,
    vision_support: EvidenceLevel,
    retrieval_support: EvidenceLevel,
    contradiction_level: EvidenceLevel,
) -> int:
    """Score how strongly evidence supports the fused label on a 1-5 scale."""
    if contradiction_level is EvidenceLevel.STRONG:
        return 1

    strong_sources = sum(
        level is EvidenceLevel.STRONG for level in (vision_support, retrieval_support)
    )
    supporting_sources = sum(
        level in (EvidenceLevel.WEAK, EvidenceLevel.MODERATE, EvidenceLevel.STRONG)
        for level in (vision_support, retrieval_support)
    )

    if retrieval_support is EvidenceLevel.MIXED:
        return 3
    if strong_sources == 2:
        return 5
    if strong_sources == 1:
        return 4 if supporting_sources == 2 else 3
    if supporting_sources == 2:
        return 3
    if supporting_sources == 1:
        return 2
    return 1


def _supporting_snippets_for_label(
    label: str,
    retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
    fused_status: LabelStatus,
) -> tuple[EvidenceSnippet, ...]:
    if fused_status is LabelStatus.ABSENT:
        return _evidence_snippets_for_label(label, retrieved_cases, negative=True)
    return _evidence_snippets_for_label(label, retrieved_cases, negative=False)


def _contradicting_snippets_for_label(
    label: str,
    retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
    fused_status: LabelStatus,
) -> tuple[EvidenceSnippet, ...]:
    if fused_status is LabelStatus.ABSENT:
        return _evidence_snippets_for_label(label, retrieved_cases, negative=False)
    return _evidence_snippets_for_label(label, retrieved_cases, negative=True)


def _predicted_label_results(
    results: Sequence[LabelVerificationResult],
) -> tuple[LabelVerificationResult, ...]:
    return tuple(
        result for result in results if result.fused_status is not LabelStatus.ABSENT
    )


def _format_prediction(result: LabelVerificationResult) -> str:
    if result.fused_status is LabelStatus.PRESENT:
        return result.label
    return f"{result.label} ({result.fused_status.value})"


def _join_text(items: Sequence[str]) -> str:
    cleaned = [item for item in items if item]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def _labeled_snippets(
    results: Sequence[LabelVerificationResult],
    *,
    supporting: bool,
    max_snippets: int = 8,
) -> tuple[LabeledEvidenceSnippet, ...]:
    snippets: list[LabeledEvidenceSnippet] = []
    seen: set[tuple[str, str, str]] = set()
    for result in results:
        source = result.supporting_evidence if supporting else result.contradicting_evidence
        for snippet in source:
            key = (result.label, snippet.case_id, snippet.snippet)
            if key in seen:
                continue
            seen.add(key)
            snippets.append(
                LabeledEvidenceSnippet(
                    label=result.label,
                    case_id=snippet.case_id,
                    similarity=snippet.similarity,
                    snippet=snippet.snippet,
                )
            )
            if len(snippets) >= max_snippets:
                return tuple(snippets)
    return tuple(snippets)


def _overall_evidence_score(
    predicted_results: Sequence[LabelVerificationResult],
) -> int:
    if not predicted_results:
        return 1
    average = sum(result.evidence_score for result in predicted_results) / len(
        predicted_results
    )
    return max(1, min(5, round(average)))


def _vision_evidence_summary(
    predicted_results: Sequence[LabelVerificationResult],
) -> str:
    if not predicted_results:
        return "The vision model did not flag any supervised disease label as a final positive prediction."
    supported = [
        result.label
        for result in predicted_results
        if result.vision_support
        in (EvidenceLevel.MODERATE, EvidenceLevel.STRONG)
    ]
    if supported:
        return (
            "The vision model independently flagged "
            f"{_join_text(supported)}."
        )
    return (
        "The final predicted labels were not strongly supported by the vision "
        "model alone."
    )


def _retrieval_evidence_summary(
    predicted_results: Sequence[LabelVerificationResult],
) -> str:
    if not predicted_results:
        return "No positive or uncertain predicted labels required retrieval support."
    supported = [
        (
            f"{result.label} ({result.retrieval_positive_count} positive, "
            f"{result.retrieval_negative_count} negated)"
        )
        for result in predicted_results
        if result.retrieval_support
        in (EvidenceLevel.WEAK, EvidenceLevel.MODERATE, EvidenceLevel.STRONG)
    ]
    contradicted = [
        (
            f"{result.label} ({result.retrieval_negative_count} negated vs "
            f"{result.retrieval_positive_count} positive)"
        )
        for result in predicted_results
        if result.retrieval_support is EvidenceLevel.CONTRADICTORY
    ]
    if supported and contradicted:
        return (
            "The top 5 visually similar retrieved studies supported "
            f"{_join_text(supported)}, but contained contradictory report "
            f"evidence for {_join_text(contradicted)}."
        )
    if supported:
        return (
            "The top 5 visually similar retrieved studies contained matching "
            f"report evidence for {_join_text(supported)}."
        )
    if contradicted:
        return (
            "The top 5 visually similar retrieved studies contained "
            f"contradictory report evidence for {_join_text(contradicted)}."
        )
    return (
        "The top 5 visually similar retrieved studies did not contain clear "
        "matching report evidence for the final predicted labels."
    )


def _fusion_evidence_summary(
    predicted_results: Sequence[LabelVerificationResult],
) -> str:
    if not predicted_results:
        return "Fusion produced no positive or uncertain supervised disease prediction."
    changed = [result for result in predicted_results if result.fusion_changed]
    if not changed:
        return (
            "Fusion kept the vision model's final positive or uncertain "
            "predictions unchanged."
        )
    changed_labels = [
        f"{result.label}: {result.fusion_reason}" for result in changed
    ]
    return "Fusion updated these labels using retrieval evidence: " + _join_text(
        changed_labels
    )


def _evidence_narrative(
    *,
    predicted_results: Sequence[LabelVerificationResult],
    vision_summary: str,
    retrieval_summary: str,
    fusion_summary: str,
    overall_score: int,
    supporting_evidence: Sequence[LabeledEvidenceSnippet],
    contradicting_evidence: Sequence[LabeledEvidenceSnippet],
) -> str:
    if not predicted_results:
        return (
            "MEDAGENT-X did not produce any positive supervised disease label "
            "for this study. "
            f"{vision_summary} {retrieval_summary} Overall evidence score: "
            f"{overall_score}/5."
        )

    prediction_text = _join_text(
        [_format_prediction(result) for result in predicted_results]
    )
    parts = [
        f"MEDAGENT-X predicted {prediction_text} for this study.",
        vision_summary,
        retrieval_summary,
        fusion_summary,
    ]
    if supporting_evidence:
        examples = _join_text(
            [
                f"{snippet.label}: \"{snippet.snippet}\""
                for snippet in supporting_evidence[:3]
            ]
        )
        parts.append(f"Supporting retrieved examples include {examples}.")
    if contradicting_evidence:
        examples = _join_text(
            [
                f"{snippet.label}: \"{snippet.snippet}\""
                for snippet in contradicting_evidence[:3]
            ]
        )
        parts.append(f"Contradictory retrieved examples include {examples}.")
    parts.append(f"Overall evidence score: {overall_score}/5.")
    return " ".join(parts)


def _summary(
    *,
    fused_status: LabelStatus,
    probability: float,
    threshold: float,
    counts: MentionCounts,
    evidence_score: int,
) -> str:
    return (
        f"fused={fused_status.value}; p={probability:.4f}; "
        f"threshold={threshold:.4f}; retrieval_pos={counts.positive_count}; "
        f"retrieval_neg={counts.negative_count}; "
        f"evidence_score={evidence_score}"
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
        evidence_score = _evidence_score(
            vision_support=vision_support,
            retrieval_support=retrieval_support,
            contradiction_level=contradiction_level,
        )
        results.append(
            LabelVerificationResult(
                label=label,
                fused_status=fused_label.fused_status,
                vision_status=fused_label.vision_status,
                evidence_score=evidence_score,
                vision_support=vision_support,
                retrieval_support=retrieval_support,
                contradiction_level=contradiction_level,
                retrieval_positive_count=counts.positive_count,
                retrieval_negative_count=counts.negative_count,
                in_gray_zone=fused_label.in_gray_zone,
                fusion_changed=fused_label.vision_status != fused_label.fused_status,
                fusion_reason=fused_label.refinement_reason,
                evidence_summary=_summary(
                    fused_status=fused_label.fused_status,
                    probability=vision_label.probability,
                    threshold=vision_label.threshold,
                    counts=counts,
                    evidence_score=evidence_score,
                ),
                supporting_evidence=_supporting_snippets_for_label(
                    label,
                    retrieved_cases,
                    fused_label.fused_status,
                ),
                contradicting_evidence=_contradicting_snippets_for_label(
                    label,
                    retrieved_cases,
                    fused_label.fused_status,
                ),
            )
        )

    predicted_results = _predicted_label_results(results)
    supporting_evidence = _labeled_snippets(predicted_results, supporting=True)
    contradicting_evidence = _labeled_snippets(predicted_results, supporting=False)
    overall_score = _overall_evidence_score(predicted_results)
    vision_summary = _vision_evidence_summary(predicted_results)
    retrieval_summary = _retrieval_evidence_summary(predicted_results)
    fusion_summary = _fusion_evidence_summary(predicted_results)

    return StudyEvidenceVerificationResult(
        study_key=vision_output.study_key,
        predicted_labels=tuple(
            _format_prediction(result) for result in predicted_results
        ),
        overall_evidence_score=overall_score,
        vision_evidence_summary=vision_summary,
        retrieval_evidence_summary=retrieval_summary,
        fusion_evidence_summary=fusion_summary,
        evidence_narrative=_evidence_narrative(
            predicted_results=predicted_results,
            vision_summary=vision_summary,
            retrieval_summary=retrieval_summary,
            fusion_summary=fusion_summary,
            overall_score=overall_score,
            supporting_evidence=supporting_evidence,
            contradicting_evidence=contradicting_evidence,
        ),
        supporting_evidence=supporting_evidence,
        contradicting_evidence=contradicting_evidence,
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
