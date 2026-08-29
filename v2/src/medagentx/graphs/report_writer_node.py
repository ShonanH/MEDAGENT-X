"""LangGraph node wrapper for the Report Writing Agent."""

from __future__ import annotations

from medagentx.graphs.state import MedAgentXInferenceState, require_state_keys


def report_writer_node(state: MedAgentXInferenceState) -> MedAgentXInferenceState:
    """Attach a placeholder report writer result to graph state."""
    require_state_keys(
        state,
        ("study_key", "fusion_result", "evidence_verification"),
        node_name="report_writer_node",
    )

    return {
        "report_writer_result": {
            "study_key": state["study_key"],
            "status": "not_implemented",
            "report_text": "",
        }
    }