"""LLM-assisted Label Fusion Agent for MEDAGENT-X."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from medagentx.contracts.label_fusion import (
    FUSION_LLM_REVIEW_SCHEMA,
    FusionChangedLabelContext,
    FusionLLMReviewResult,
    FusionReviewAction,
    FusionReviewValidationError,
    parse_fusion_llm_review_payload,
    validate_fusion_review_guardrails,
)
from medagentx.labels.statuses import LabelStatus
from medagentx.llm.ollama import OllamaClient, OllamaClientError
from medagentx.reasoning.constants import GRAY_ZONE_MARGIN
from medagentx.reasoning.fuse import (
    FusedLabelPrediction,
    FusionStudyResult,
    VisionLabelPrediction,
    fuse_study_labels,
)
from medagentx.reasoning.mentions import RetrievedReportCase


@dataclass(frozen=True)
class LabelFusionAgentResult:
    """Complete output from one Label Fusion Agent run."""

    study_key: str
    deterministic_result: FusionStudyResult
    final_result: FusionStudyResult
    llm_review: FusionLLMReviewResult | None
    llm_requested: bool
    llm_succeeded: bool
    fallback_used: bool
    fallback_reasons: tuple[str, ...]
    reviewed_labels: tuple[str, ...]
    kept_labels: tuple[str, ...]
    vetoed_labels: tuple[str, ...]
    uncertain_labels: tuple[str, ...]


class LabelFusionAgent:
    """Run deterministic fusion, then LLM-review deterministic changes."""

    def __init__(
        self,
        *,
        llm_client: OllamaClient | None = None,
        margin: float = GRAY_ZONE_MARGIN,
    ) -> None:
        if margin < 0:
            raise ValueError("margin must be >= 0")
        self.llm_client = llm_client or OllamaClient()
        self.margin = float(margin)

    def fuse(
        self,
        *,
        study_key: str,
        vision_predictions: Mapping[str, VisionLabelPrediction],
        retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
    ) -> LabelFusionAgentResult:
        """Fuse labels for one study with deterministic and LLM review stages."""

        deterministic_result = fuse_study_labels(
            vision_predictions,
            retrieved_cases,
            study_key=study_key,
            margin=self.margin,
        )

        changed_contexts = _changed_contexts(deterministic_result)
        if not changed_contexts:
            return LabelFusionAgentResult(
                study_key=study_key,
                deterministic_result=deterministic_result,
                final_result=deterministic_result,
                llm_review=None,
                llm_requested=False,
                llm_succeeded=False,
                fallback_used=False,
                fallback_reasons=(),
                reviewed_labels=(),
                kept_labels=(),
                vetoed_labels=(),
                uncertain_labels=(),
            )

        fallback_reasons: list[str] = []
        llm_review = self._review_with_llm(
            study_key=study_key,
            changed_contexts=changed_contexts,
            retrieved_cases=retrieved_cases,
            fallback_reasons=fallback_reasons,
        )

        if llm_review is None:
            return LabelFusionAgentResult(
                study_key=study_key,
                deterministic_result=deterministic_result,
                final_result=deterministic_result,
                llm_review=None,
                llm_requested=True,
                llm_succeeded=False,
                fallback_used=True,
                fallback_reasons=tuple(fallback_reasons),
                reviewed_labels=(),
                kept_labels=(),
                vetoed_labels=(),
                uncertain_labels=(),
            )

        final_result, action_summary, apply_fallback_reasons = _apply_llm_review(
            deterministic_result,
            llm_review,
            changed_contexts=changed_contexts,
        )
        fallback_reasons.extend(apply_fallback_reasons)

        return LabelFusionAgentResult(
            study_key=study_key,
            deterministic_result=deterministic_result,
            final_result=final_result,
            llm_review=llm_review,
            llm_requested=True,
            llm_succeeded=True,
            fallback_used=bool(fallback_reasons),
            fallback_reasons=tuple(fallback_reasons),
            reviewed_labels=tuple(sorted(action_summary["reviewed"])),
            kept_labels=tuple(sorted(action_summary["kept"])),
            vetoed_labels=tuple(sorted(action_summary["vetoed"])),
            uncertain_labels=tuple(sorted(action_summary["uncertain"])),
        )

    def _review_with_llm(
        self,
        *,
        study_key: str,
        changed_contexts: Sequence[FusionChangedLabelContext],
        retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
        fallback_reasons: list[str],
    ) -> FusionLLMReviewResult | None:
        system_prompt = _fusion_review_system_prompt()
        user_prompt = _fusion_review_user_prompt(
            study_key=study_key,
            changed_contexts=changed_contexts,
            retrieved_cases=retrieved_cases,
        )
        retrieved_case_ids = _retrieved_case_ids(retrieved_cases)

        try:
            payload = self.llm_client.chat_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=FUSION_LLM_REVIEW_SCHEMA,
            )
            review = parse_fusion_llm_review_payload(payload)
            validate_fusion_review_guardrails(
                review,
                changed_labels=changed_contexts,
                retrieved_case_ids=retrieved_case_ids,
            )
            return review
        except (OllamaClientError, FusionReviewValidationError) as exc:
            fallback_reasons.append(f"llm-review-failed: {exc}")

        repair_prompt = _fusion_repair_user_prompt(
            original_user_prompt=user_prompt,
            validation_error=fallback_reasons[-1],
        )

        try:
            payload = self.llm_client.chat_json(
                system_prompt=system_prompt,
                user_prompt=repair_prompt,
                schema=FUSION_LLM_REVIEW_SCHEMA,
            )
            review = parse_fusion_llm_review_payload(payload)
            repaired_review, partial_reasons = _partial_review_with_fallbacks(
                review,
                changed_contexts=changed_contexts,
                retrieved_case_ids=retrieved_case_ids,
            )
            fallback_reasons.extend(partial_reasons)
            return repaired_review
        except (OllamaClientError, FusionReviewValidationError) as exc:
            fallback_reasons.append(f"llm-repair-failed: {exc}")
            return None


def _changed_contexts(
    result: FusionStudyResult,
) -> tuple[FusionChangedLabelContext, ...]:
    contexts: list[FusionChangedLabelContext] = []
    for label_result in result.labels:
        if label_result.vision_status is label_result.fused_status:
            continue
        contexts.append(
            FusionChangedLabelContext(
                label=label_result.label,
                vision_status=label_result.vision_status,
                deterministic_status=label_result.fused_status,
                probability=label_result.probability,
                threshold=label_result.threshold,
                positive_count=label_result.positive_count,
                negative_count=label_result.negative_count,
                deterministic_reason=label_result.refinement_reason,
            )
        )
    return tuple(contexts)


def _partial_review_with_fallbacks(
    review: FusionLLMReviewResult,
    *,
    changed_contexts: Sequence[FusionChangedLabelContext],
    retrieved_case_ids: set[str],
) -> tuple[FusionLLMReviewResult, tuple[str, ...]]:
    """Keep valid label reviews and fall back only invalid/missing labels."""
    expected_labels = {item.label for item in changed_contexts}
    context_by_label = {item.label: item for item in changed_contexts}
    accepted = []
    seen: set[str] = set()
    fallback_reasons: list[str] = []

    for label_review in review.reviewed_labels:
        if label_review.label in seen:
            fallback_reasons.append(
                f"{label_review.label}: duplicate-review-fell-back-to-deterministic"
            )
            continue
        seen.add(label_review.label)

        context = context_by_label.get(label_review.label)
        if context is None:
            fallback_reasons.append(
                f"{label_review.label}: unexpected-review-ignored"
            )
            continue

        try:
            _validate_label_review(
                label_review,
                context=context,
                retrieved_case_ids=retrieved_case_ids,
            )
        except FusionReviewValidationError as exc:
            fallback_reasons.append(
                f"{label_review.label}: invalid-review-fell-back-to-deterministic: "
                f"{exc}"
            )
            continue
        accepted.append(label_review)

    missing = sorted(expected_labels - {item.label for item in accepted})
    fallback_reasons.extend(
        f"{label}: missing-review-fell-back-to-deterministic" for label in missing
    )

    return (
        FusionLLMReviewResult(
            reviewed_labels=tuple(accepted),
            overall_notes=review.overall_notes,
        ),
        tuple(fallback_reasons),
    )


def _validate_label_review(
    review,
    *,
    context: FusionChangedLabelContext,
    retrieved_case_ids: set[str],
) -> None:
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
            f"action={review.action.value!r} requires "
            f"final_status={expected.value!r}, got {review.final_status.value!r}"
        )

    referenced = set(review.supporting_case_ids) | set(review.contradicting_case_ids)
    unknown = sorted(referenced - retrieved_case_ids)
    if unknown:
        raise FusionReviewValidationError(
            f"references unknown retrieved case IDs: {unknown}"
        )


def _apply_llm_review(
    deterministic_result: FusionStudyResult,
    llm_review: FusionLLMReviewResult,
    *,
    changed_contexts: Sequence[FusionChangedLabelContext],
) -> tuple[FusionStudyResult, dict[str, set[str]], tuple[str, ...]]:
    review_by_label = llm_review.review_map()
    changed_labels = {item.label for item in changed_contexts}
    fallback_reasons: list[str] = []
    final_labels: list[FusedLabelPrediction] = []
    action_summary: dict[str, set[str]] = {
        "reviewed": set(),
        "kept": set(),
        "vetoed": set(),
        "uncertain": set(),
    }

    for label_result in deterministic_result.labels:
        review = review_by_label.get(label_result.label)
        if review is None:
            if label_result.label in changed_labels:
                fallback_reasons.append(
                    f"{label_result.label}: deterministic-status-used"
                )
            final_labels.append(label_result)
            continue

        action_summary["reviewed"].add(label_result.label)
        final_status = review.final_status
        if review.action is FusionReviewAction.KEEP:
            action_summary["kept"].add(label_result.label)
        elif review.action is FusionReviewAction.VETO:
            action_summary["vetoed"].add(label_result.label)
        elif review.action is FusionReviewAction.UNCERTAIN:
            action_summary["uncertain"].add(label_result.label)
        else:
            fallback_reasons.append(
                f"{label_result.label}: unsupported-action-{review.action}"
            )
            final_status = label_result.fused_status

        final_labels.append(
            FusedLabelPrediction(
                label=label_result.label,
                vision_status=label_result.vision_status,
                fused_status=final_status,
                probability=label_result.probability,
                threshold=label_result.threshold,
                in_gray_zone=label_result.in_gray_zone,
                positive_count=label_result.positive_count,
                negative_count=label_result.negative_count,
                refinement_reason=_reviewed_refinement_reason(
                    label_result.refinement_reason,
                    review,
                ),
            )
        )

    return (
        FusionStudyResult(
            study_key=deterministic_result.study_key,
            fusion_policy_version=deterministic_result.fusion_policy_version,
            labels=tuple(final_labels),
        ),
        action_summary,
        tuple(fallback_reasons),
    )


def _reviewed_refinement_reason(
    deterministic_reason: str,
    review: Any | None,
) -> str:
    if review is None:
        return deterministic_reason
    return (
        f"{deterministic_reason}; llm_review action={review.action.value} "
        f"confidence={review.confidence.value} "
        f"evidence={review.evidence_assessment.value}: {review.rationale}"
    )


def _fusion_review_system_prompt() -> str:
    return (
        "You are the MEDAGENT-X Label Fusion Agent. "
        "Your task is to review deterministic gray-zone label fusion changes. "
        "You MUST NOT diagnose new labels. "
        "You may only keep, veto, or mark uncertain the deterministic changes provided in the user message. "
        "Return valid JSON only. Do not include prose outside JSON."
    )


def _fusion_review_user_prompt(
    *,
    study_key: str,
    changed_contexts: Sequence[FusionChangedLabelContext],
    retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
) -> str:
    payload = {
        "task": "Review deterministic label fusion changes for this study.",
        "study_key": study_key,
        "allowed_actions": ["keep", "veto", "uncertain"],
        "allowed_final_statuses": ["present", "absent", "uncertain"],
        "instructions": [
            "Review exactly the changed labels provided.",
            "DO NOT add labels.",
            "DO NOT modify labels outside this list.",
            "Use the full retrieved reports as evidence.",
            "If evidence supports the deterministic change, use action keep.",
            "If evidence contradicts the deterministic change, use action veto.",
            "If evidence is mixed, ambiguous, historical, or insufficient, use action uncertain when clinically appropriate.",
            "Referenced case IDs must come from retrieved_cases.",
        ],
        "changed_labels": [
            {
                "label": item.label,
                "vision_status": item.vision_status.value,
                "deterministic_status": item.deterministic_status.value,
                "probability": item.probability,
                "threshold": item.threshold,
                "positive_count": item.positive_count,
                "negative_count": item.negative_count,
                "deterministic_reason": item.deterministic_reason,
            }
            for item in changed_contexts
        ],
        "retrieved_cases": [
            _retrieved_case_payload(case, index)
            for index, case in enumerate(retrieved_cases, start=1)
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _fusion_repair_user_prompt(
    *,
    original_user_prompt: str,
    validation_error: str,
) -> str:
    payload = {
        "task": "Repair the previous fusion review JSON.",
        "validation_error": validation_error,
        "instructions": [
            "Return valid JSON only.",
            "Follow the requested schema exactly.",
            "Review exactly the changed labels in the original request.",
            "Do not add labels or case IDs.",
            "Use only allowed enum values.",
        ],
        "original_request": json.loads(original_user_prompt),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _retrieved_case_payload(
    case: RetrievedReportCase | Mapping[str, Any],
    rank: int,
) -> dict[str, Any]:
    return {
        "rank": rank,
        "case_id": _case_id(case, rank),
        "study_key": _case_value(case, "study_key"),
        "deid_patient_id": _case_value(case, "deid_patient_id"),
        "similarity": _case_value(case, "similarity"),
        "distance": _case_value(case, "distance"),
        "document": _case_document(case),
    }


def _retrieved_case_ids(
    cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
) -> set[str]:
    return {_case_id(case, index) for index, case in enumerate(cases, start=1)}


def _case_value(case: RetrievedReportCase | Mapping[str, Any], key: str) -> Any:
    value = getattr(case, key, None)
    if value is not None:
        return value
    if isinstance(case, Mapping):
        return case.get(key)
    return None


def _case_document(case: RetrievedReportCase | Mapping[str, Any]) -> str:
    for key in ("document", "retrieved_document"):
        value = _case_value(case, key)
        if value is not None:
            return str(value or "")
    return ""


def _case_id(case: RetrievedReportCase | Mapping[str, Any], rank: int) -> str:
    for key in ("study_key", "case_id", "id"):
        value = _case_value(case, key)
        if value:
            return str(value)
    return f"retrieved-case-{rank}"
