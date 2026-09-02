"""LangGraph state contracts for MEDAGENT-X live inference."""

from __future__ import annotations

from typing import Any, TypedDict

from medagentx.agents.evidence_verification import (
    LLMEvidenceVerificationAgentResult,
    StudyEvidenceVerificationResult,
)
from medagentx.agents.label_fusion import LabelFusionAgentResult
from medagentx.reasoning.fuse import FusionStudyResult
from medagentx.retrieval.index import RetrievedStudy
from medagentx.vision.inference_output import VisionStudyOutput


class MedAgentXInferenceState(TypedDict, total=False):
    """Shared state passed between live inference graph nodes."""

    study_key: str
    dicom_paths: tuple[str, ...]
    vision_output: VisionStudyOutput
    retrieved_cases: list[RetrievedStudy | dict[str, Any]]
    label_fusion_result: LabelFusionAgentResult
    fusion_result: FusionStudyResult
    evidence_verification: StudyEvidenceVerificationResult
    evidence_verification_agent_result: LLMEvidenceVerificationAgentResult
    report_writer_result: dict[str, Any]


def require_state_keys(
    state: MedAgentXInferenceState,
    required: tuple[str, ...],
    *,
    node_name: str,
) -> None:
    """Validate required graph-state keys before a node executes."""
    missing = [key for key in required if key not in state]
    if missing:
        raise ValueError(f"{node_name} missing required state keys: {missing}")
