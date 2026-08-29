"""LangGraph node wrapper for the Evidence Verification Agent."""

from __future__ import annotations

from medagentx.agents.evidence_verification import EvidenceVerificationAgent
from medagentx.graphs.state import MedAgentXInferenceState, require_state_keys
from medagentx.reasoning.constants import GRAY_ZONE_MARGIN


def evidence_verification_node(
    state: MedAgentXInferenceState,
    *,
    margin: float = GRAY_ZONE_MARGIN,
) -> MedAgentXInferenceState:
    """Verify fused label evidence and attach the result to graph state."""
    require_state_keys(
        state,
        ("vision_output", "retrieved_cases", "fusion_result"),
        node_name="evidence_verification_node",
    )
    agent = EvidenceVerificationAgent(margin=margin)
    verification = agent.verify(
        vision_output=state["vision_output"],
        fusion_result=state["fusion_result"],
        retrieved_cases=state["retrieved_cases"],
    )
    return {"evidence_verification": verification}
