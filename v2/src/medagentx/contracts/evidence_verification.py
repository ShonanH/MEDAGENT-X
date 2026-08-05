"""Stable output contract for Evidence Verification Agent results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from medagentx.agents.evidence_verification import (
    EvidenceSnippet,
    LabelVerificationResult,
    LabeledEvidenceSnippet,
    StudyEvidenceVerificationResult,
)


EVIDENCE_VERIFICATION_COLUMNS: tuple[str, ...] = (
    "study_key",
    "verification_policy_version",
    "predicted_labels",
    "overall_evidence_score",
    "vision_evidence_summary",
    "retrieval_evidence_summary",
    "fusion_evidence_summary",
    "evidence_narrative",
    "supporting_evidence",
    "contradicting_evidence",
    "label_evidence_details",
)


@dataclass(frozen=True)
class EvidenceVerificationRow:
    """One CSV/JSON-ready verification row for a study."""

    study_key: str
    verification_policy_version: str
    predicted_labels: tuple[str, ...]
    overall_evidence_score: int
    vision_evidence_summary: str
    retrieval_evidence_summary: str
    fusion_evidence_summary: str
    evidence_narrative: str
    supporting_evidence: tuple[dict[str, Any], ...]
    contradicting_evidence: tuple[dict[str, Any], ...]
    label_evidence_details: tuple[dict[str, Any], ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dictionary with nested evidence objects."""
        return {
            "study_key": self.study_key,
            "verification_policy_version": self.verification_policy_version,
            "predicted_labels": list(self.predicted_labels),
            "overall_evidence_score": self.overall_evidence_score,
            "vision_evidence_summary": self.vision_evidence_summary,
            "retrieval_evidence_summary": self.retrieval_evidence_summary,
            "fusion_evidence_summary": self.fusion_evidence_summary,
            "evidence_narrative": self.evidence_narrative,
            "supporting_evidence": list(self.supporting_evidence),
            "contradicting_evidence": list(self.contradicting_evidence),
            "label_evidence_details": list(self.label_evidence_details),
        }

    def to_csv_dict(self) -> dict[str, Any]:
        """Return a CSV-safe dictionary using compact JSON nested cells."""
        row = self.to_json_dict()
        for key in (
            "predicted_labels",
            "supporting_evidence",
            "contradicting_evidence",
            "label_evidence_details",
        ):
            row[key] = json.dumps(
                row[key],
                ensure_ascii=True,
                separators=(",", ":"),
            )
        return {column: row[column] for column in EVIDENCE_VERIFICATION_COLUMNS}


def evidence_snippet_to_dict(snippet: EvidenceSnippet) -> dict[str, Any]:
    """Convert one label-local evidence snippet to the public contract shape."""
    return {
        "case_id": snippet.case_id,
        "similarity": snippet.similarity,
        "snippet": snippet.snippet,
    }


def labeled_evidence_snippet_to_dict(
    snippet: LabeledEvidenceSnippet,
) -> dict[str, Any]:
    """Convert one study-level evidence snippet to the public contract shape."""
    return {
        "label": snippet.label,
        "case_id": snippet.case_id,
        "similarity": snippet.similarity,
        "snippet": snippet.snippet,
    }


def label_verification_to_detail(
    result: LabelVerificationResult,
) -> dict[str, Any]:
    """Convert one label verification result to nested study-level detail."""
    return {
        "label": result.label,
        "fused_status": result.fused_status.value,
        "vision_status": result.vision_status.value,
        "evidence_score": result.evidence_score,
        "vision_support": result.vision_support.value,
        "retrieval_support": result.retrieval_support.value,
        "contradiction_level": result.contradiction_level.value,
        "retrieval_positive_count": result.retrieval_positive_count,
        "retrieval_negative_count": result.retrieval_negative_count,
        "in_gray_zone": result.in_gray_zone,
        "fusion_changed": result.fusion_changed,
        "fusion_reason": result.fusion_reason,
        "evidence_summary": result.evidence_summary,
        "supporting_evidence": [
            evidence_snippet_to_dict(snippet)
            for snippet in result.supporting_evidence
        ],
        "contradicting_evidence": [
            evidence_snippet_to_dict(snippet)
            for snippet in result.contradicting_evidence
        ],
    }


def study_verification_to_row(
    result: StudyEvidenceVerificationResult,
) -> EvidenceVerificationRow:
    """Convert one study verification result to the stable row contract."""
    return EvidenceVerificationRow(
        study_key=result.study_key,
        verification_policy_version=result.verification_policy_version,
        predicted_labels=result.predicted_labels,
        overall_evidence_score=result.overall_evidence_score,
        vision_evidence_summary=result.vision_evidence_summary,
        retrieval_evidence_summary=result.retrieval_evidence_summary,
        fusion_evidence_summary=result.fusion_evidence_summary,
        evidence_narrative=result.evidence_narrative,
        supporting_evidence=tuple(
            labeled_evidence_snippet_to_dict(snippet)
            for snippet in result.supporting_evidence
        ),
        contradicting_evidence=tuple(
            labeled_evidence_snippet_to_dict(snippet)
            for snippet in result.contradicting_evidence
        ),
        label_evidence_details=tuple(
            label_verification_to_detail(label_result)
            for label_result in result.labels
            if label_result.fused_status.value != "absent"
        ),
    )


def study_verification_to_json_dict(
    result: StudyEvidenceVerificationResult,
) -> dict[str, Any]:
    """Return the nested JSON contract for one study verification result."""
    return study_verification_to_row(result).to_json_dict()


def study_verifications_to_csv_rows(
    results: list[StudyEvidenceVerificationResult],
) -> list[dict[str, Any]]:
    """Flatten study verification results into CSV-safe row dictionaries."""
    return [study_verification_to_row(result).to_csv_dict() for result in results]
