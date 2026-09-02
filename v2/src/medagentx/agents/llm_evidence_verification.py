"""Pure LLM Evidence Verification Agent for Experiment 7.

This agent does not call the deterministic Evidence Verification Agent and does
not call verify_study_evidence(). It builds an evidence-verification result
directly from fused labels, vision outputs, retrieved cases, and an LLM response.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from medagentx.agents.evidence_verification import (
    EvidenceLevel,
    EvidenceSnippet,
    LabelVerificationResult,
    LabeledEvidenceSnippet,
    StudyEvidenceVerificationResult,
)
from medagentx.contracts.evidence_verification_llm import (
    EVIDENCE_VERIFICATION_LLM_REVIEW_SCHEMA,
    EvidenceVerificationLLMReviewResult,
    EvidenceVerificationReviewValidationError,
    parse_evidence_verification_llm_review_payload,
)
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.statuses import LabelStatus
from medagentx.llm.ollama import OllamaClient, OllamaClientError
from medagentx.reasoning.fuse import FusionStudyResult
from medagentx.reasoning.mentions import (
    RetrievedReportCase,
)
from medagentx.vision.inference_output import VisionStudyOutput


LLM_ONLY_EVIDENCE_VERIFICATION_POLICY_VERSION = "llm_only_evidence_verification_v1"
LLM_ONLY_EVIDENCE_VERIFICATION_FAILED_POLICY_VERSION = (
    "llm_only_evidence_verification_failed_v1"
)


@dataclass(frozen=True)
class LLMOnlyEvidenceVerificationAgentResult:
    """Complete output from one pure LLM evidence-verification run."""

    study_key: str
    final_result: StudyEvidenceVerificationResult
    llm_review: EvidenceVerificationLLMReviewResult | None
    llm_requested: bool
    llm_succeeded: bool
    fallback_used: bool
    fallback_reasons: tuple[str, ...]
    reviewed_labels: tuple[str, ...]


class LLMOnlyEvidenceVerificationAgent:
    """Verify fused label evidence using only the LLM evidence-verification path."""

    def __init__(self, *, llm_client: OllamaClient | None = None) -> None:
        self.llm_client = llm_client or OllamaClient()

    def verify(
        self,
        *,
        vision_output: VisionStudyOutput,
        fusion_result: FusionStudyResult,
        retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
    ) -> LLMOnlyEvidenceVerificationAgentResult:
        if vision_output.study_key != fusion_result.study_key:
            raise ValueError(
                "vision_output and fusion_result study_key mismatch: "
                f"{vision_output.study_key!r} != {fusion_result.study_key!r}"
            )

        label_contexts = _label_contexts_for_prompt(
            vision_output=vision_output,
            fusion_result=fusion_result,
        )

        if not label_contexts:
            final_result = _no_predicted_labels_result(fusion_result.study_key)
            return LLMOnlyEvidenceVerificationAgentResult(
                study_key=fusion_result.study_key,
                final_result=final_result,
                llm_review=None,
                llm_requested=False,
                llm_succeeded=False,
                fallback_used=False,
                fallback_reasons=(),
                reviewed_labels=(),
            )

        fallback_reasons: list[str] = []
        llm_review = self._review_with_llm(
            study_key=fusion_result.study_key,
            label_contexts=label_contexts,
            retrieved_cases=retrieved_cases,
            fallback_reasons=fallback_reasons,
        )

        if llm_review is None:
            final_result = _llm_failed_result(
                vision_output=vision_output,
                fusion_result=fusion_result,
                fallback_reasons=fallback_reasons,
            )
            return LLMOnlyEvidenceVerificationAgentResult(
                study_key=fusion_result.study_key,
                final_result=final_result,
                llm_review=None,
                llm_requested=True,
                llm_succeeded=False,
                fallback_used=True,
                fallback_reasons=tuple(fallback_reasons),
                reviewed_labels=(),
            )

        final_result = _apply_llm_review(
            vision_output=vision_output,
            fusion_result=fusion_result,
            retrieved_cases=retrieved_cases,
            llm_review=llm_review,
        )
        return LLMOnlyEvidenceVerificationAgentResult(
            study_key=fusion_result.study_key,
            final_result=final_result,
            llm_review=llm_review,
            llm_requested=True,
            llm_succeeded=True,
            fallback_used=False,
            fallback_reasons=(),
            reviewed_labels=tuple(
                sorted(review.label for review in llm_review.reviewed_labels)
            ),
        )

    def _review_with_llm(
        self,
        *,
        study_key: str,
        label_contexts: Sequence[dict[str, Any]],
        retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
        fallback_reasons: list[str],
    ) -> EvidenceVerificationLLMReviewResult | None:
        system_prompt = _system_prompt()
        user_prompt = _user_prompt(
            study_key=study_key,
            label_contexts=label_contexts,
            retrieved_cases=retrieved_cases,
        )
        retrieved_case_ids = {
            _case_id(case) for case in retrieved_cases if _case_id(case)
        }

        try:
            payload = self.llm_client.chat_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=EVIDENCE_VERIFICATION_LLM_REVIEW_SCHEMA,
            )
            review = parse_evidence_verification_llm_review_payload(payload)
            _validate_llm_review(
                review,
                expected_labels={str(item["label"]) for item in label_contexts},
                retrieved_case_ids=retrieved_case_ids,
            )
            return review
        except (OllamaClientError, EvidenceVerificationReviewValidationError) as exc:
            fallback_reasons.append(f"llm-only-evidence-verification-failed: {exc}")
            return None


def _label_contexts_for_prompt(
    *,
    vision_output: VisionStudyOutput,
    fusion_result: FusionStudyResult,
) -> tuple[dict[str, Any], ...]:
    vision_by_label = vision_output.label_map()
    contexts: list[dict[str, Any]] = []

    for fused_label in fusion_result.labels:
        if fused_label.fused_status is LabelStatus.ABSENT:
            continue
        vision_label = vision_by_label[fused_label.label]
        contexts.append(
            {
                "label": fused_label.label,
                "fused_status": fused_label.fused_status.value,
                "vision_status": fused_label.vision_status.value,
                "probability": vision_label.probability,
                "threshold": vision_label.threshold,
                "in_gray_zone": fused_label.in_gray_zone,
                "fusion_changed": fused_label.vision_status
                is not fused_label.fused_status,
                "fusion_reason": fused_label.refinement_reason,
            }
        )
    return tuple(contexts)


def _validate_llm_review(
    review: EvidenceVerificationLLMReviewResult,
    *,
    expected_labels: set[str],
    retrieved_case_ids: set[str],
) -> None:
    actual_labels = {item.label for item in review.reviewed_labels}
    missing = sorted(expected_labels - actual_labels)
    unexpected = sorted(actual_labels - expected_labels)
    if missing or unexpected:
        raise EvidenceVerificationReviewValidationError(
            "LLM evidence labels must exactly match fused predicted labels; "
            f"missing={missing}, unexpected={unexpected}"
        )
    if len(actual_labels) != len(review.reviewed_labels):
        raise EvidenceVerificationReviewValidationError(
            "LLM evidence review contains duplicate labels"
        )

    allowed_contradiction_levels = {"none", "weak", "strong"}
    for label_review in review.reviewed_labels:
        referenced = set(label_review.supporting_case_ids) | set(
            label_review.contradicting_case_ids
        )
        unknown = sorted(referenced - retrieved_case_ids)
        if unknown:
            raise EvidenceVerificationReviewValidationError(
                f"{label_review.label} references unknown retrieved case IDs: {unknown}"
            )
        if label_review.contradiction_level.value not in allowed_contradiction_levels:
            raise EvidenceVerificationReviewValidationError(
                f"{label_review.label} contradiction_level must be one of "
                f"{sorted(allowed_contradiction_levels)}"
            )
        if label_review.evidence_assessment.value == "contradictory":
            if label_review.contradiction_level.value == "none":
                raise EvidenceVerificationReviewValidationError(
                    f"{label_review.label} contradictory assessment requires "
                    "weak or strong contradiction_level"
                )
            if not label_review.contradicting_case_ids:
                raise EvidenceVerificationReviewValidationError(
                    f"{label_review.label} contradictory assessment requires "
                    "at least one contradicting case ID"
                )


def _apply_llm_review(
    *,
    vision_output: VisionStudyOutput,
    fusion_result: FusionStudyResult,
    retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
    llm_review: EvidenceVerificationLLMReviewResult,
) -> StudyEvidenceVerificationResult:
    vision_by_label = vision_output.label_map()
    review_by_label = llm_review.review_map()
    labels: list[LabelVerificationResult] = []

    for fused_label in fusion_result.labels:
        vision_label = vision_by_label[fused_label.label]
        label_review = review_by_label.get(fused_label.label)

        if fused_label.fused_status is LabelStatus.ABSENT:
            labels.append(
                _absent_label_result(
                    fused_label=fused_label,
                    probability=vision_label.probability,
                    threshold=vision_label.threshold,
                )
            )
            continue

        if label_review is None:
            raise EvidenceVerificationReviewValidationError(
                f"Missing LLM evidence review for {fused_label.label}"
            )

        labels.append(
            LabelVerificationResult(
                label=fused_label.label,
                fused_status=fused_label.fused_status,
                vision_status=fused_label.vision_status,
                evidence_score=label_review.evidence_score,
                vision_support=EvidenceLevel(label_review.vision_support.value),
                retrieval_support=EvidenceLevel(label_review.retrieval_support.value),
                contradiction_level=EvidenceLevel(
                    label_review.contradiction_level.value
                ),
                retrieval_positive_count=len(label_review.supporting_case_ids),
                retrieval_negative_count=len(label_review.contradicting_case_ids),
                in_gray_zone=fused_label.in_gray_zone,
                fusion_changed=fused_label.vision_status
                is not fused_label.fused_status,
                fusion_reason=fused_label.refinement_reason,
                evidence_summary=label_review.rationale,
                supporting_evidence=_snippets_for_case_ids(
                    retrieved_cases=retrieved_cases,
                    case_ids=label_review.supporting_case_ids,
                ),
                contradicting_evidence=_snippets_for_case_ids(
                    retrieved_cases=retrieved_cases,
                    case_ids=label_review.contradicting_case_ids,
                ),
            )
        )

    predicted_results = _predicted_label_results(labels)
    return StudyEvidenceVerificationResult(
        study_key=fusion_result.study_key,
        predicted_labels=tuple(_format_prediction(item) for item in predicted_results),
        overall_evidence_score=llm_review.overall_evidence_score,
        vision_evidence_summary=llm_review.vision_evidence_summary,
        retrieval_evidence_summary=llm_review.retrieval_evidence_summary,
        fusion_evidence_summary=llm_review.fusion_evidence_summary,
        evidence_narrative=llm_review.evidence_narrative,
        supporting_evidence=_labeled_snippets(predicted_results, supporting=True),
        contradicting_evidence=_labeled_snippets(predicted_results, supporting=False),
        labels=tuple(labels),
        verification_policy_version=LLM_ONLY_EVIDENCE_VERIFICATION_POLICY_VERSION,
    )


def _absent_label_result(
    *,
    fused_label: Any,
    probability: float,
    threshold: float,
) -> LabelVerificationResult:
    return LabelVerificationResult(
        label=fused_label.label,
        fused_status=fused_label.fused_status,
        vision_status=fused_label.vision_status,
        evidence_score=1,
        vision_support=EvidenceLevel.NONE,
        retrieval_support=EvidenceLevel.NONE,
        contradiction_level=EvidenceLevel.NONE,
        retrieval_positive_count=0,
        retrieval_negative_count=0,
        in_gray_zone=fused_label.in_gray_zone,
        fusion_changed=fused_label.vision_status is not fused_label.fused_status,
        fusion_reason=fused_label.refinement_reason,
        evidence_summary=(
            "Not reviewed by the LLM evidence verifier because fused_status=absent; "
            f"p={float(probability):.4f}; threshold={float(threshold):.4f}."
        ),
        supporting_evidence=(),
        contradicting_evidence=(),
    )


def _no_predicted_labels_result(study_key: str) -> StudyEvidenceVerificationResult:
    return StudyEvidenceVerificationResult(
        study_key=study_key,
        predicted_labels=(),
        overall_evidence_score=1,
        vision_evidence_summary=(
            "No fused positive or uncertain disease labels were provided for LLM "
            "evidence verification."
        ),
        retrieval_evidence_summary=(
            "No retrieved evidence was reviewed because there were no fused "
            "positive or uncertain labels."
        ),
        fusion_evidence_summary="Fusion produced no label requiring LLM verification.",
        evidence_narrative=(
            "No LLM evidence verification was requested because there were no "
            "fused positive or uncertain labels."
        ),
        supporting_evidence=(),
        contradicting_evidence=(),
        labels=(),
        verification_policy_version=LLM_ONLY_EVIDENCE_VERIFICATION_POLICY_VERSION,
    )


def _llm_failed_result(
    *,
    vision_output: VisionStudyOutput,
    fusion_result: FusionStudyResult,
    fallback_reasons: Sequence[str],
) -> StudyEvidenceVerificationResult:
    vision_by_label = vision_output.label_map()
    labels: list[LabelVerificationResult] = []

    for fused_label in fusion_result.labels:
        vision_label = vision_by_label[fused_label.label]
        labels.append(
            LabelVerificationResult(
                label=fused_label.label,
                fused_status=fused_label.fused_status,
                vision_status=fused_label.vision_status,
                evidence_score=1,
                vision_support=EvidenceLevel.NONE,
                retrieval_support=EvidenceLevel.NONE,
                contradiction_level=EvidenceLevel.NONE,
                retrieval_positive_count=0,
                retrieval_negative_count=0,
                in_gray_zone=fused_label.in_gray_zone,
                fusion_changed=fused_label.vision_status
                is not fused_label.fused_status,
                fusion_reason=fused_label.refinement_reason,
                evidence_summary=(
                    "LLM-only evidence verification failed; no deterministic "
                    f"evidence verification was run. Reasons: {list(fallback_reasons)}. "
                    f"p={vision_label.probability:.4f}; "
                    f"threshold={vision_label.threshold:.4f}."
                ),
                supporting_evidence=(),
                contradicting_evidence=(),
            )
        )

    predicted_results = _predicted_label_results(labels)
    return StudyEvidenceVerificationResult(
        study_key=fusion_result.study_key,
        predicted_labels=tuple(_format_prediction(item) for item in predicted_results),
        overall_evidence_score=1,
        vision_evidence_summary="LLM-only evidence verification failed.",
        retrieval_evidence_summary="LLM-only evidence verification failed.",
        fusion_evidence_summary="LLM-only evidence verification failed.",
        evidence_narrative=(
            "LLM-only evidence verification failed. No deterministic evidence "
            "verification fallback was used."
        ),
        supporting_evidence=(),
        contradicting_evidence=(),
        labels=tuple(labels),
        verification_policy_version=(
            LLM_ONLY_EVIDENCE_VERIFICATION_FAILED_POLICY_VERSION
        ),
    )


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


def _snippets_for_case_ids(
    *,
    retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
    case_ids: Sequence[str],
    max_snippets: int = 3,
) -> tuple[EvidenceSnippet, ...]:
    requested = {str(case_id) for case_id in case_ids}
    if not requested:
        return ()

    snippets: list[EvidenceSnippet] = []
    for case in retrieved_cases:
        case_id = _case_id(case)
        if case_id not in requested:
            continue
        document = _case_document(case)
        snippets.append(
            EvidenceSnippet(
                case_id=case_id,
                similarity=_case_similarity(case),
                snippet=_document_excerpt(document, max_chars=260),
            )
        )
        if len(snippets) >= max_snippets:
            return tuple(snippets)
    return tuple(snippets)


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


def _document_excerpt(document: str, *, max_chars: int) -> str:
    normalized = " ".join(str(document or "").split())
    return normalized[:max_chars]


def _system_prompt() -> str:
    return (
        "You are the MEDAGENT-X LLM Evidence Verification Agent. "
        "You must verify only the fused disease labels provided by the user. "
        "Do not add labels. Do not remove labels. Do not change fused label statuses. "
        "Use the RAD-DINO probability/threshold and the actual retrieved report "
        "texts as evidence. Ignore any keyword-count summaries from earlier fusion "
        "steps; your retrieval assessment must come from reading the supplied "
        "reports. Retrieved reports are neighbor cases, not the target study "
        "report. Use only provided retrieved case IDs. Return strict JSON matching "
        "the schema and no prose outside JSON."
    )


def _user_prompt(
    *,
    study_key: str,
    label_contexts: Sequence[dict[str, Any]],
    retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
) -> str:
    payload = {
        "study_key": study_key,
        "task": (
            "Perform LLM-only evidence verification for the fused labels. "
            "Assign evidence scores, support levels, contradiction levels, "
            "summaries, and an evidence narrative directly from the provided "
            "vision and retrieval evidence."
        ),
        "hard_constraints": [
            "Review exactly the labels in label_contexts.",
            "Do not add labels.",
            "Do not remove labels.",
            "Do not change fused_status.",
            "Do not infer retrieval support from fusion keyword counts.",
            "Read the actual retrieved report texts to judge support, contradiction, and uncertainty.",
            "supporting_case_ids and contradicting_case_ids must come from retrieved_cases.",
            "Use contradictory only when there is explicit conflicting evidence.",
            "If evidence_assessment is contradictory, provide at least one contradicting_case_id.",
        ],
        "scoring_rules": {
            "1": "Evidence contradicts or does not support the fused label.",
            "2": "Weak single-source support.",
            "3": "Mixed or moderate support.",
            "4": "Strong support from one source plus compatible secondary evidence.",
            "5": "Strong support from both vision and retrieval evidence.",
        },
        "label_contexts": list(label_contexts),
        "retrieved_cases": [
            _retrieved_case_to_prompt_dict(case)
            for case in retrieved_cases
        ],
    }
    return json.dumps(payload, ensure_ascii=True, indent=2)


def _retrieved_case_to_prompt_dict(
    case: RetrievedReportCase | Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "case_id": _case_id(case),
        "similarity": _case_similarity(case),
        "document": _case_document(case)[:1400],
    }
