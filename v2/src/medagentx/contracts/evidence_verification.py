"""Stable output contract for Evidence Verification Agent results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from medagentx.agents.evidence_verification import (
    EvidenceSnippet,
    LabelVerificationResult,
    StudyEvidenceVerificationResult,
)


EVIDENCE_VERIFICATION_COLUMNS: tuple[str, ...] = (
    "study_key",
    "verification_policy_version",
    "label",
    "fused_status",
    "verification_status",
    "evidence_score",
    "vision_support",
    "retrieval_support",
    "contradiction_level",
    "in_gray_zone",
    "fusion_changed",
    "evidence_summary",
    "supporting_evidence",
    "contradicting_evidence",
)


@dataclass(frozen=True)
class EvidenceVerificationRow:
    """One CSV/JSON-ready verification row for a study-label pair."""

    study_key: str
    verification_policy_version: str
    label: str
    fused_status: str
    verification_status: str
    evidence_score: int
    vision_support: str
    retrieval_support: str
    contradiction_level: str
    in_gray_zone: bool
    fusion_changed: bool
    evidence_summary: str
    supporting_evidence: tuple[dict[str, Any], ...]
    contradicting_evidence: tuple[dict[str, Any], ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dictionary with evidence snippets as lists."""
        return {
            "study_key": self.study_key,
            "verification_policy_version": self.verification_policy_version,
            "label": self.label,
            "fused_status": self.fused_status,
            "verification_status": self.verification_status,
            "evidence_score": self.evidence_score,
            "vision_support": self.vision_support,
            "retrieval_support": self.retrieval_support,
            "contradiction_level": self.contradiction_level,
            "in_gray_zone": self.in_gray_zone,
            "fusion_changed": self.fusion_changed,
            "evidence_summary": self.evidence_summary,
            "supporting_evidence": list(self.supporting_evidence),
            "contradicting_evidence": list(self.contradicting_evidence),
        }

    def to_csv_dict(self) -> dict[str, Any]:
        """Return a CSV-safe dictionary using compact JSON evidence cells."""
        row = self.to_json_dict()
        row["supporting_evidence"] = json.dumps(
            row["supporting_evidence"],
            ensure_ascii=True,
            separators=(",", ":"),
        )
        row["contradicting_evidence"] = json.dumps(
            row["contradicting_evidence"],
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return {column: row[column] for column in EVIDENCE_VERIFICATION_COLUMNS}


def evidence_snippet_to_dict(snippet: EvidenceSnippet) -> dict[str, Any]:
    """Convert one evidence snippet to the public contract shape."""
    return {
        "case_id": snippet.case_id,
        "similarity": snippet.similarity,
        "snippet": snippet.snippet,
    }


def label_verification_to_row(
    *,
    study_key: str,
    verification_policy_version: str,
    result: LabelVerificationResult,
) -> EvidenceVerificationRow:
    """Convert one label verification result to a contract row."""
    return EvidenceVerificationRow(
        study_key=study_key,
        verification_policy_version=verification_policy_version,
        label=result.label,
        fused_status=result.fused_status.value,
        verification_status=result.verification_status.value,
        evidence_score=result.evidence_score,
        vision_support=result.vision_support.value,
        retrieval_support=result.retrieval_support.value,
        contradiction_level=result.contradiction_level.value,
        in_gray_zone=result.in_gray_zone,
        fusion_changed=result.fusion_changed,
        evidence_summary=result.evidence_summary,
        supporting_evidence=tuple(
            evidence_snippet_to_dict(snippet)
            for snippet in result.supporting_evidence
        ),
        contradicting_evidence=tuple(
            evidence_snippet_to_dict(snippet)
            for snippet in result.contradicting_evidence
        ),
    )


def study_verification_to_rows(
    result: StudyEvidenceVerificationResult,
) -> list[EvidenceVerificationRow]:
    """Flatten one study verification result to one row per disease label."""
    return [
        label_verification_to_row(
            study_key=result.study_key,
            verification_policy_version=result.verification_policy_version,
            result=label_result,
        )
        for label_result in result.labels
    ]


def study_verification_to_json_dict(
    result: StudyEvidenceVerificationResult,
) -> dict[str, Any]:
    """Return the nested JSON contract for one study verification result."""
    return {
        "study_key": result.study_key,
        "verification_policy_version": result.verification_policy_version,
        "labels": [
            row.to_json_dict()
            for row in study_verification_to_rows(result)
        ],
    }


def study_verifications_to_csv_rows(
    results: list[StudyEvidenceVerificationResult],
) -> list[dict[str, Any]]:
    """Flatten study verification results into CSV-safe row dictionaries."""
    rows: list[dict[str, Any]] = []
    for result in results:
        rows.extend(row.to_csv_dict() for row in study_verification_to_rows(result))
    return rows
