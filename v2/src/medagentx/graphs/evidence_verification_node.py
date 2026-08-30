"""LangGraph node wrappers for Evidence Verification Agents."""

from __future__ import annotations

from medagentx.agents.evidence_verification import (
    EvidenceVerificationAgent,
    LLMEvidenceVerificationAgent,
)
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


def make_evidence_verification_node(
    *,
    use_llm: bool = False,
    llm_agent: LLMEvidenceVerificationAgent | None = None,
    margin: float = GRAY_ZONE_MARGIN,
):
    """Create a graph evidence-verification node with deterministic/LLM wiring."""

    agent = llm_agent if use_llm else None
    if use_llm and agent is None:
        agent = LLMEvidenceVerificationAgent(margin=margin)

    def graph_evidence_verification_node(
        state: MedAgentXInferenceState,
    ) -> MedAgentXInferenceState:
        require_state_keys(
            state,
            ("vision_output", "retrieved_cases", "fusion_result"),
            node_name="evidence_verification_node",
        )

        if agent is not None:
            result = agent.verify(
                vision_output=state["vision_output"],
                fusion_result=state["fusion_result"],
                retrieved_cases=state["retrieved_cases"],
            )
            return {
                "evidence_verification_agent_result": result,
                "evidence_verification": result.final_result,
            }

        deterministic_agent = EvidenceVerificationAgent(margin=margin)
        verification = deterministic_agent.verify(
            vision_output=state["vision_output"],
            fusion_result=state["fusion_result"],
            retrieved_cases=state["retrieved_cases"],
        )
        return {"evidence_verification": verification}

    return graph_evidence_verification_node
