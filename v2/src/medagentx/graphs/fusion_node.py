"""LangGraph node wrapper for label fusion."""

from __future__ import annotations

from medagentx.agents.label_fusion import LabelFusionAgent, LabelFusionAgentResult
from medagentx.graphs.state import MedAgentXInferenceState, require_state_keys
from medagentx.reasoning.constants import FUSION_USE_LLM, GRAY_ZONE_MARGIN
from medagentx.reasoning.fuse import FusionStudyResult, fuse_study_labels
from medagentx.reasoning.vision_adapter import fusion_vision_inputs


def _deterministic_label_fusion_result(
    *,
    study_key: str,
    fusion_result: FusionStudyResult,
) -> LabelFusionAgentResult:
    return LabelFusionAgentResult(
        study_key=study_key,
        deterministic_result=fusion_result,
        final_result=fusion_result,
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


def fusion_node(
    state: MedAgentXInferenceState,
    *,
    margin: float = GRAY_ZONE_MARGIN,
) -> MedAgentXInferenceState:
    """Run deterministic label fusion.

    Kept for backwards compatibility. Prefer make_label_fusion_node(...) when
    graph construction should choose deterministic vs LLM-reviewed fusion.
    """

    require_state_keys(
        state,
        ("vision_output", "retrieved_cases"),
        node_name="fusion_node",
    )

    vision_output = state["vision_output"]
    fusion_result = fuse_study_labels(
        fusion_vision_inputs(vision_output),
        state["retrieved_cases"],
        study_key=vision_output.study_key,
        margin=margin,
    )

    return {
        "label_fusion_result": _deterministic_label_fusion_result(
            study_key=vision_output.study_key,
            fusion_result=fusion_result,
        ),
        "fusion_result": fusion_result,
    }


def make_label_fusion_node(
    *,
    use_llm: bool = FUSION_USE_LLM,
    llm_agent: LabelFusionAgent | None = None,
    margin: float = GRAY_ZONE_MARGIN,
):
    """Create a graph fusion node with explicit deterministic/LLM wiring."""

    agent = llm_agent if use_llm else None
    if use_llm and agent is None:
        agent = LabelFusionAgent(margin=margin)

    def label_fusion_node(state: MedAgentXInferenceState) -> MedAgentXInferenceState:
        require_state_keys(
            state,
            ("vision_output", "retrieved_cases"),
            node_name="label_fusion_node",
        )

        vision_output = state["vision_output"]
        vision_predictions = fusion_vision_inputs(vision_output)

        if agent is not None:
            result = agent.fuse(
                study_key=vision_output.study_key,
                vision_predictions=vision_predictions,
                retrieved_cases=state["retrieved_cases"],
            )
            return {
                "label_fusion_result": result,
                "fusion_result": result.final_result,
            }

        fusion_result = fuse_study_labels(
            vision_predictions,
            state["retrieved_cases"],
            study_key=vision_output.study_key,
            margin=margin,
        )
        return {
            "label_fusion_result": _deterministic_label_fusion_result(
                study_key=vision_output.study_key,
                fusion_result=fusion_result,
            ),
            "fusion_result": fusion_result,
        }

    return label_fusion_node
