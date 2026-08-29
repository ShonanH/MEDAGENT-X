"""LangGraph assembly for MEDAGENT-X live inference."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from medagentx.graphs.evidence_verification_node import evidence_verification_node
from medagentx.graphs.report_writer_node import report_writer_node
from medagentx.graphs.state import MedAgentXInferenceState


GraphNode = Callable[[MedAgentXInferenceState], MedAgentXInferenceState]


def _load_langgraph() -> tuple[Any, Any, Any]:
    """Import LangGraph lazily so schema modules stay lightweight."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError(
            "LangGraph is required to build the MEDAGENT-X inference graph. "
            "Install project dependencies before graph construction."
        ) from exc
    return StateGraph, START, END

def build_inference_graph(
    *,
    vision_node: GraphNode,
    retrieval_node: GraphNode,
    fusion_node: GraphNode,
    verification_node: GraphNode = evidence_verification_node,
    report_node: GraphNode = report_writer_node,
) -> Any:
    """Build the live Vision -> Retrieval -> Fusion -> Verification -> Report graph."""
    StateGraph, START, END = _load_langgraph()
    graph = StateGraph(MedAgentXInferenceState)
    graph.add_node("vision", vision_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("fusion", fusion_node)
    graph.add_node("evidence_verification", verification_node)
    graph.add_node("report_writer", report_node)

    graph.add_edge(START, "vision")
    graph.add_edge("vision", "retrieval")
    graph.add_edge("retrieval", "fusion")
    graph.add_edge("fusion", "evidence_verification")
    graph.add_edge("evidence_verification", "report_writer")
    graph.add_edge("report_writer", END)
    return graph.compile()
