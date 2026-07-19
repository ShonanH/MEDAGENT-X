from __future__ import annotations

from medagentx.paths import CHEXPERT_OUTPUT_DIR, DATA_DIR, FUSION_OUTPUT_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR, SRC_ROOT, VECTOR_DB_DIR

from pathlib import Path
from typing import Any, TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph

from medagentx.agents.quality_gate_agent import quality_gate_node
from medagentx.agents.retrieval_agent import retrieval_agent_node
from medagentx.agents.disease_reasoning_agent import disease_reasoning_node
from medagentx.agents.judge_agent import judge_node


DEFAULT_QUALITY_EVIDENCE_CSV = str(CHEXPERT_OUTPUT_DIR / "quality_evidence_manifest.csv")
DEFAULT_QUALITY_GATE_CSV = str(CHEXPERT_OUTPUT_DIR / "quality_gate_decisions.csv")
DEFAULT_RETRIEVAL_RESULTS_CSV = str(CHEXPERT_OUTPUT_DIR / "retrieval_results.csv")
DEFAULT_DISEASE_REASONING_RESULTS_CSV = str(CHEXPERT_OUTPUT_DIR / "disease_reasoning_results.csv")
DEFAULT_GROUND_TRUTH_CSV = str(CHEXPERT_OUTPUT_DIR / "redivis_chexpert_plus_filtered_rows.csv")
DEFAULT_JUDGE_RESULTS_CSV = str(CHEXPERT_OUTPUT_DIR / "judge_results.csv")
DEFAULT_JUDGE_REPORT_PATH = str(CHEXPERT_OUTPUT_DIR / "judge_report.md")
DEFAULT_CLASSIFIER_PREDICTIONS_CSV = (
    str(FUSION_OUTPUT_DIR / "ensemble_classifier_predictions.csv")
)


class MedAgentXState(TypedDict, total=False):
    study_key: str
    dicom_path: str
    top_k: int
    quality_evidence_csv: str
    quality_gate_csv: str
    retrieval_results_csv: str
    disease_reasoning_results_csv: str
    classifier_predictions_csv: str
    reasoning_model: str
    quality_gate_decision: str
    quality_route_next: str
    retrieved_cases: list[dict[str, Any]]
    reasoning_result: dict[str, Any]
    route_next: str
    completed_steps: list[str]
    ground_truth_csv: str
    judge_results_csv: str
    judge_report_path: str
    judge_case_count: int


def _progress(message: str) -> None:
    print(f"[MEDAGENT-X] {message}", flush=True)


def _normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().lower().replace("\\", "/")


def _append_step(state: MedAgentXState, step: str) -> list[str]:
    return [*state.get("completed_steps", []), step]


def quality_gate_graph_node(state: MedAgentXState) -> dict[str, Any]:
    _progress("Starting Quality Gate Agent.")

    quality_gate_node(
        {
            "input_csv": state["quality_evidence_csv"],
            "output_csv": state["quality_gate_csv"],
            "decisions": [],
        }
    )

    gate_df = pd.read_csv(state["quality_gate_csv"], dtype=str)

    matched = gate_df[
        gate_df["study_key"].map(_normalize_text).eq(_normalize_text(state["study_key"]))
        & gate_df["dicom_path"].map(_normalize_text).eq(_normalize_text(state["dicom_path"]))
    ]

    if matched.empty:
        raise RuntimeError(
            "Quality Gate completed, but the requested case was not found in "
            f"{state['quality_gate_csv']}: "
            f"{state['study_key']} / {state['dicom_path']}"
        )

    row = matched.iloc[0]
    decision = row.get("quality_gate_decision", "")
    route_next = row.get("route_next", "")

    if decision == "fail":
        route_next = "stop_unreliable"

    _progress(f"Quality Gate complete. Decision: {decision}. Route: {route_next}.")

    return {
        "quality_gate_decision": decision,
        "quality_route_next": route_next,
        "route_next": route_next,
        "completed_steps": _append_step(state, "quality_gate_agent"),
    }


def route_after_quality_gate(state: MedAgentXState) -> str:
    if state.get("route_next") == "stop_unreliable":
        _progress("Stopping graph because Quality Gate marked this case unreliable.")
        return END

    return "retrieval_agent"


def retrieval_graph_node(state: MedAgentXState) -> dict[str, Any]:
    _progress(f"Starting Retrieval Agent. top_k={state['top_k']}.")

    retrieval_result = retrieval_agent_node(
        {
            "study_key": state["study_key"],
            "dicom_path": state["dicom_path"],
            "top_k": state["top_k"],
            "output_csv": state["retrieval_results_csv"],
            "retrieved_cases": [],
            "route_next": "",
        }
    )

    retrieved_cases = retrieval_result.get("retrieved_cases", [])
    route_next = retrieval_result.get("route_next", "")

    _progress(f"Retrieval Agent complete. Retrieved cases: {len(retrieved_cases)}. Route: {route_next}.")

    return {
        "retrieved_cases": retrieved_cases,
        "route_next": route_next,
        "completed_steps": _append_step(state, "retrieval_agent"),
    }


def route_after_retrieval(state: MedAgentXState) -> str:
    if state.get("route_next") == "stop_unreliable":
        _progress("Stopping graph after Retrieval Agent route decision.")
        return END

    return "disease_reasoning_agent"


def disease_reasoning_graph_node(state: MedAgentXState) -> dict[str, Any]:
    _progress("Starting Disease Reasoning Agent.")

    classifier_predictions_csv = state.get(
        "classifier_predictions_csv",
        DEFAULT_CLASSIFIER_PREDICTIONS_CSV,
    )

    node_state: dict[str, Any] = {
        "retrieval_results_path": state["retrieval_results_csv"],
        "image_classifier_predictions_path": classifier_predictions_csv,
        "disease_reasoning_results_path": state["disease_reasoning_results_csv"],
        "retrieval_top_k": state["top_k"],
        "reasoning_result": {},
        "route_next": "",
        "verbose": True,
    }

    if state.get("reasoning_model"):
        node_state["ollama_reasoning_model"] = state["reasoning_model"]

    disease_result = disease_reasoning_node(node_state)

    route_next = disease_result.get("route_next", "judge_agent")
    disease_results_path = disease_result.get(
        "disease_reasoning_results_path",
        state["disease_reasoning_results_csv"],
    )

    _progress(f"Disease Reasoning Agent complete. Route: {route_next}.")

    return {
        "disease_reasoning_results_csv": disease_results_path,
        "reasoning_result": disease_result.get("reasoning_result", {}),
        "route_next": route_next,
        "completed_steps": _append_step(state, "disease_reasoning_agent"),
    }


def judge_graph_node(state: MedAgentXState) -> dict[str, Any]:
    _progress("Starting Judge Agent.")

    judge_result = judge_node(
        {
            "disease_reasoning_results_path": state["disease_reasoning_results_csv"],
            "ground_truth_path": state["ground_truth_csv"],
            "judge_results_path": state["judge_results_csv"],
            "judge_report_path": state["judge_report_path"],
            "verbose": True,
        }
    )

    case_count = int(judge_result.get("judge_case_count", 0))

    _progress(f"Judge Agent complete. Judged cases: {case_count}.")

    return {
        "judge_results_csv": judge_result.get("judge_results_path", state["judge_results_csv"]),
        "judge_report_path": judge_result.get("judge_report_path", state["judge_report_path"]),
        "judge_case_count": case_count,
        "route_next": "complete",
        "completed_steps": _append_step(state, "judge_agent"),
    }


def build_medagentx_graph():
    graph = StateGraph(MedAgentXState)

    graph.add_node("quality_gate_agent", quality_gate_graph_node)
    graph.add_node("retrieval_agent", retrieval_graph_node)
    graph.add_node("disease_reasoning_agent", disease_reasoning_graph_node)
    graph.add_node("judge_agent", judge_graph_node)

    graph.add_edge(START, "quality_gate_agent")

    graph.add_conditional_edges(
        "quality_gate_agent",
        route_after_quality_gate,
        ["retrieval_agent", END],
    )

    graph.add_conditional_edges(
        "retrieval_agent",
        route_after_retrieval,
        ["disease_reasoning_agent", END],
    )

    graph.add_edge("disease_reasoning_agent", "judge_agent")
    graph.add_edge("judge_agent", END)

    return graph.compile()


def run_medagentx_graph(
    study_key: str,
    dicom_path: str,
    top_k: int = 5,
    quality_evidence_csv: str = DEFAULT_QUALITY_EVIDENCE_CSV,
    quality_gate_csv: str = DEFAULT_QUALITY_GATE_CSV,
    retrieval_results_csv: str = DEFAULT_RETRIEVAL_RESULTS_CSV,
    disease_reasoning_results_csv: str = DEFAULT_DISEASE_REASONING_RESULTS_CSV,
    classifier_predictions_csv: str = DEFAULT_CLASSIFIER_PREDICTIONS_CSV,
    ground_truth_csv: str = DEFAULT_GROUND_TRUTH_CSV,
    judge_results_csv: str = DEFAULT_JUDGE_RESULTS_CSV,
    judge_report_path: str = DEFAULT_JUDGE_REPORT_PATH,
    reasoning_model: str = "",
) -> MedAgentXState:
    classifier_path = Path(classifier_predictions_csv)
    if not classifier_path.exists():
        raise FileNotFoundError(
            f"Missing classifier predictions: {classifier_path}. "
            "Run scripts 11_run_densenet_predictions.py, 12_run_fusion_inference.py, "
            "and 13_build_ensemble_classifier_predictions.py first."
        )

    _progress("Starting continuous MEDAGENT-X graph.")

    graph = build_medagentx_graph()

    result = graph.invoke(
        {
            "study_key": study_key,
            "dicom_path": dicom_path,
            "top_k": top_k,
            "quality_evidence_csv": quality_evidence_csv,
            "quality_gate_csv": quality_gate_csv,
            "retrieval_results_csv": retrieval_results_csv,
            "disease_reasoning_results_csv": disease_reasoning_results_csv,
            "classifier_predictions_csv": classifier_predictions_csv,
            "reasoning_model": reasoning_model,
            "quality_gate_decision": "",
            "quality_route_next": "",
            "retrieved_cases": [],
            "reasoning_result": {},
            "route_next": "",
            "completed_steps": [],
            "ground_truth_csv": ground_truth_csv,
            "judge_results_csv": judge_results_csv,
            "judge_report_path": judge_report_path,
            "judge_case_count": 0,
        }
    )

    _progress(f"Graph complete. Completed steps: {result['completed_steps']}.")

    return result
