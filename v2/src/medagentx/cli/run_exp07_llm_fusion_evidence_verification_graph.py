"""Run Experiment 7: graph inference with LLM-only evidence verification."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from medagentx.agents.llm_evidence_verification import (
    LLM_ONLY_EVIDENCE_VERIFICATION_POLICY_VERSION,
    LLMOnlyEvidenceVerificationAgent,
)
from medagentx.contracts.evidence_verification import (
    study_verification_to_json_dict,
    study_verifications_to_csv_rows,
)
from medagentx.data.balanced_constants import DEFAULT_BALANCED_COHORT_ROOT
from medagentx.llm.ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    OllamaClient,
    OllamaConfig,
)
from medagentx.reasoning.constants import FUSION_RETRIEVAL_TOP_K, GRAY_ZONE_MARGIN


DEFAULT_COLLECTION_NAME = "medagentx_train_studies_v1"
DEFAULT_LAST4_CHECKPOINT = (
    Path(DEFAULT_BALANCED_COHORT_ROOT)
    / "vision"
    / "raddino_finetuned_v1_last4_blocks"
    / "best_checkpoint.pt"
)
DEFAULT_LAST4_VECTOR_DB_DIR = (
    Path(DEFAULT_BALANCED_COHORT_ROOT)
    / "retrieval"
    / "raddino_train_v1_last4_blocks"
    / "chroma"
)
DEFAULT_OUTPUT_DIR = Path("v2/experiments/exp07_llm_fusion_evidence_verification_graph")
OUTPUT_FILENAMES = (
    "run_config.json",
    "graph_reasoning_results.jsonl",
    "vision_study_predictions.csv",
    "fusion_label_predictions.csv",
    "retrieved_cases.csv",
    "evidence_verification.json",
    "evidence_verification.csv",
    "llm_evidence_policy_audit.csv",
    "llm_evidence_policy_summary.csv",
)


def _default_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _load_threshold_overrides(path: Path | None) -> dict[str, float] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text())
    selected = payload.get("selected_thresholds")
    if not isinstance(selected, dict):
        raise ValueError(f"{path} does not contain selected_thresholds")
    return {str(label): float(value) for label, value in selected.items()}


def _require_existing_paths(paths: dict[str, Path]) -> None:
    missing = [f"{name}: {path}" for name, path in paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Required Experiment 7 artifacts are missing:\n" + "\n".join(missing)
        )


def _prepare_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [
        output_dir / name for name in OUTPUT_FILENAMES if (output_dir / name).exists()
    ]
    if existing and not overwrite:
        raise FileExistsError(
            "Experiment 7 output files already exist. Pass --overwrite to replace:\n"
            + "\n".join(str(path) for path in existing)
        )
    if overwrite:
        for path in existing:
            path.unlink()


def _collection_embedding_dim(collection: Any) -> int:
    payload = collection.get(limit=1, include=["embeddings"])
    embeddings = payload.get("embeddings")
    if embeddings is None or len(embeddings) == 0:
        raise ValueError("Retrieval collection has no embeddings to inspect")
    return len(embeddings[0])


def _load_langgraph() -> tuple[Any, Any, Any]:
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError(
            "LangGraph is required for Experiment 7. Install project dependencies "
            "before graph construction."
        ) from exc
    return StateGraph, START, END


def _build_exp07_graph(
    *,
    vision_node,
    retrieval_node,
    fusion_node,
    evidence_verification_node,
):
    """Build START -> vision -> retrieval -> fusion -> LLM evidence -> END."""
    from medagentx.graphs.state import MedAgentXInferenceState

    StateGraph, START, END = _load_langgraph()
    graph = StateGraph(MedAgentXInferenceState)
    graph.add_node("vision", vision_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("fusion", fusion_node)
    graph.add_node("evidence_verification", evidence_verification_node)
    graph.add_edge(START, "vision")
    graph.add_edge("vision", "retrieval")
    graph.add_edge("retrieval", "fusion")
    graph.add_edge("fusion", "evidence_verification")
    graph.add_edge("evidence_verification", END)
    return graph.compile()


def _make_llm_only_evidence_node(agent: LLMOnlyEvidenceVerificationAgent):
    from medagentx.graphs.state import MedAgentXInferenceState, require_state_keys

    def evidence_verification_node(
        state: MedAgentXInferenceState,
    ) -> MedAgentXInferenceState:
        require_state_keys(
            state,
            ("vision_output", "retrieved_cases", "fusion_result"),
            node_name="llm_only_evidence_verification_node",
        )
        result = agent.verify(
            vision_output=state["vision_output"],
            fusion_result=state["fusion_result"],
            retrieved_cases=state["retrieved_cases"],
        )
        return {
            "evidence_verification_agent_result": result,
            "evidence_verification": result.final_result,
        }

    return evidence_verification_node


def _changed_labels(result: Any) -> list[str]:
    return [
        item.label
        for item in result.labels
        if item.vision_status is not item.fused_status
    ]


def _case_value(case: Any, key: str) -> Any:
    value = getattr(case, key, None)
    if value is not None:
        return value
    if isinstance(case, dict):
        return case.get(key)
    return None


def _case_document(case: Any) -> str:
    return str(_case_value(case, "document") or "")


def _case_similarity(case: Any) -> float | None:
    value = _case_value(case, "similarity")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _case_distance(case: Any) -> float | None:
    value = _case_value(case, "distance")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _retrieved_case_rows(
    *,
    final_state: dict[str, Any],
    query_split: str,
    query_dicom_paths: Iterable[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    query_paths = tuple(query_dicom_paths)
    for view_index, dicom_path in enumerate(query_paths, start=1):
        for rank, case in enumerate(final_state["retrieved_cases"], start=1):
            rows.append(
                {
                    "query_study_key": final_state["study_key"],
                    "query_deid_patient_id": _case_value(
                        final_state["vision_output"],
                        "deid_patient_id",
                    ),
                    "query_split": query_split,
                    "query_view_index": view_index,
                    "query_view_count": len(query_paths),
                    "query_dicom_path": dicom_path,
                    "retrieved_rank": rank,
                    "retrieved_study_key": _case_value(case, "study_key"),
                    "retrieved_deid_patient_id": _case_value(case, "deid_patient_id"),
                    "similarity": _case_similarity(case),
                    "distance": _case_distance(case),
                    "retrieved_document": _case_document(case),
                }
            )
    return rows


def _graph_result_row(
    *,
    index: int,
    total: int,
    elapsed_seconds: float,
    final_state: dict[str, Any],
) -> dict[str, Any]:
    label_fusion = final_state["label_fusion_result"]
    evidence_agent = final_state["evidence_verification_agent_result"]
    verification = final_state["evidence_verification"]
    return {
        "index": index,
        "total": total,
        "elapsed_seconds": elapsed_seconds,
        "study_key": final_state["study_key"],
        "retrieved_count": len(final_state["retrieved_cases"]),
        "final_predicted_labels": list(verification.predicted_labels),
        "overall_evidence_score": verification.overall_evidence_score,
        "fusion": {
            "llm_requested": label_fusion.llm_requested,
            "llm_succeeded": label_fusion.llm_succeeded,
            "fallback_used": label_fusion.fallback_used,
            "fallback_reasons": list(label_fusion.fallback_reasons),
            "deterministic_changed_labels": _changed_labels(
                label_fusion.deterministic_result
            ),
            "final_changed_labels": _changed_labels(label_fusion.final_result),
            "reviewed_labels": list(label_fusion.reviewed_labels),
            "kept_labels": list(label_fusion.kept_labels),
            "vetoed_labels": list(label_fusion.vetoed_labels),
            "uncertain_labels": list(label_fusion.uncertain_labels),
        },
        "evidence": {
            "mode": "llm_only",
            "llm_requested": evidence_agent.llm_requested,
            "llm_succeeded": evidence_agent.llm_succeeded,
            "fallback_used": evidence_agent.fallback_used,
            "fallback_reasons": list(evidence_agent.fallback_reasons),
            "reviewed_labels": list(evidence_agent.reviewed_labels),
        },
    }


def _evidence_audit_rows(agent_results: Iterable[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for agent_result in agent_results:
        verification = agent_result.final_result
        review_by_label = (
            agent_result.llm_review.review_map()
            if agent_result.llm_review is not None
            else {}
        )
        for label_result in verification.labels:
            if label_result.fused_status.value == "absent":
                continue

            review = review_by_label.get(label_result.label)
            rows.append(
                {
                    "study_key": agent_result.study_key,
                    "label": label_result.label,
                    "fused_status": label_result.fused_status.value,
                    "vision_status": label_result.vision_status.value,
                    "evidence_score": label_result.evidence_score,
                    "vision_support": label_result.vision_support.value,
                    "retrieval_support": label_result.retrieval_support.value,
                    "contradiction_level": label_result.contradiction_level.value,
                    "in_gray_zone": label_result.in_gray_zone,
                    "fusion_changed": label_result.fusion_changed,
                    "llm_requested": agent_result.llm_requested,
                    "llm_succeeded": agent_result.llm_succeeded,
                    "fallback_used": agent_result.fallback_used,
                    "fallback_reasons": _json_cell(
                        list(agent_result.fallback_reasons)
                    ),
                    "llm_reviewed": review is not None,
                    "llm_confidence": review.confidence.value if review else None,
                    "llm_evidence_assessment": (
                        review.evidence_assessment.value if review else None
                    ),
                    "llm_supporting_case_ids": _json_cell(
                        list(review.supporting_case_ids) if review else []
                    ),
                    "llm_contradicting_case_ids": _json_cell(
                        list(review.contradicting_case_ids) if review else []
                    ),
                    "evidence_summary": label_result.evidence_summary,
                }
            )
    return rows


def _evidence_policy_summary_frame(audit_frame: pd.DataFrame) -> pd.DataFrame:
    if audit_frame.empty:
        return pd.DataFrame()

    grouped = audit_frame.groupby(
        [
            "label",
            "llm_reviewed",
            "llm_confidence",
            "llm_evidence_assessment",
        ],
        dropna=False,
    )
    return grouped.agg(
        reviewed_cells=("study_key", "count"),
        fallback_used=("fallback_used", "sum"),
        mean_evidence_score=("evidence_score", "mean"),
    ).reset_index()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run Experiment 7: full graph inference with LLM label fusion and "
            "LLM-only evidence verification. No deterministic evidence "
            "verification is run."
        )
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path(DEFAULT_BALANCED_COHORT_ROOT),
    )
    parser.add_argument("--views-csv", type=Path, default=None)
    parser.add_argument("--dicom-root", type=Path, default=None)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_LAST4_CHECKPOINT)
    parser.add_argument("--threshold-policy-json", type=Path, default=None)
    parser.add_argument("--vector-db-dir", type=Path, default=DEFAULT_LAST4_VECTOR_DB_DIR)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--split",
        choices=("train", "val", "test", "all"),
        default="test",
    )
    parser.add_argument("--max-studies", type=int, default=None)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--device", default=_default_device())
    parser.add_argument("--no-mixed-precision", action="store_true")
    parser.add_argument("--retrieval-top-k", type=int, default=FUSION_RETRIEVAL_TOP_K)
    parser.add_argument("--gray-zone-margin", type=float, default=GRAY_ZONE_MARGIN)
    parser.add_argument("--ollama-model", default=DEFAULT_OLLAMA_MODEL)
    parser.add_argument("--ollama-base-url", default=DEFAULT_OLLAMA_BASE_URL)
    parser.add_argument("--ollama-temperature", type=float, default=0.0)
    parser.add_argument(
        "--ollama-timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument("--progress-every", type=int, default=1)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--allow-llm-fallback",
        action="store_true",
        help=(
            "Continue if label fusion or LLM-only evidence verification has an "
            "LLM failure. No deterministic evidence-verification fallback is used."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    from medagentx.agents.label_fusion import (
        LLM_REVIEW_POLICY_VERSION,
        LabelFusionAgent,
    )
    from medagentx.evaluation.fusion_eval import fusion_results_to_frame
    from medagentx.graphs.fusion_node import make_label_fusion_node
    from medagentx.graphs.retrieval_node import make_retrieval_node
    from medagentx.graphs.vision_node import make_vision_node
    from medagentx.reasoning.retrieve import open_retrieval_collection
    from medagentx.vision.backend import FineTunedRadDinoBackend
    from medagentx.vision.data import build_study_inference_records
    from medagentx.vision.inference_output import (
        VisionStudyOutput,
        study_outputs_to_prediction_frame,
    )

    if args.max_studies is not None and args.max_studies <= 0:
        raise ValueError("--max-studies must be > 0")
    if args.num_workers < 0:
        raise ValueError("--num-workers must be >= 0")
    if args.retrieval_top_k <= 0:
        raise ValueError("--retrieval-top-k must be > 0")
    if args.gray_zone_margin < 0:
        raise ValueError("--gray-zone-margin must be >= 0")
    if args.progress_every <= 0:
        raise ValueError("--progress-every must be > 0")

    cohort_root = args.cohort_root
    views_csv = args.views_csv or (cohort_root / "splits" / "view_splits.csv")
    dicom_root = args.dicom_root or (cohort_root / "dicom_train")
    _require_existing_paths(
        {
            "views_csv": views_csv,
            "dicom_root": dicom_root,
            "checkpoint": args.checkpoint,
            "vector_db_dir": args.vector_db_dir,
        }
    )
    if args.threshold_policy_json is not None:
        _require_existing_paths({"threshold_policy_json": args.threshold_policy_json})
    _prepare_output_dir(args.output_dir, overwrite=args.overwrite)

    print(
        "[Exp07LLMFusionLLMOnlyEvidenceGraph] "
        f"split={args.split} checkpoint={args.checkpoint} "
        f"output_dir={args.output_dir}"
    )
    views = pd.read_csv(views_csv, dtype=str)
    records = build_study_inference_records(
        views,
        split=None if args.split == "all" else args.split,
    )
    if args.max_studies is not None:
        records = records[: args.max_studies]
    if not records:
        raise ValueError(f"No records found for split={args.split!r}")

    backend = FineTunedRadDinoBackend.from_checkpoint(
        args.checkpoint,
        device=args.device,
        mixed_precision=not args.no_mixed_precision,
    )
    threshold_overrides = _load_threshold_overrides(args.threshold_policy_json)
    collection = open_retrieval_collection(
        args.vector_db_dir,
        collection_name=args.collection_name,
    )
    ollama_config = OllamaConfig(
        model=args.ollama_model,
        base_url=args.ollama_base_url,
        temperature=args.ollama_temperature,
        timeout_seconds=args.ollama_timeout_seconds,
    )
    label_fusion_agent = LabelFusionAgent(
        llm_client=OllamaClient(ollama_config),
        margin=args.gray_zone_margin,
    )
    evidence_agent = LLMOnlyEvidenceVerificationAgent(
        llm_client=OllamaClient(ollama_config),
    )

    current_vision_output: dict[str, VisionStudyOutput] = {}

    def vision_backbone(
        study_key: str,
        dicom_paths: tuple[str, ...],
    ) -> VisionStudyOutput:
        output = current_vision_output[study_key]
        if output.dicom_paths != dicom_paths:
            raise ValueError(
                f"DICOM path mismatch for {study_key}: "
                f"state={dicom_paths!r}, vision_output={output.dicom_paths!r}"
            )
        return output

    graph = _build_exp07_graph(
        vision_node=make_vision_node(vision_backbone),
        retrieval_node=make_retrieval_node(collection, top_k=args.retrieval_top_k),
        fusion_node=make_label_fusion_node(
            use_llm=True,
            llm_agent=label_fusion_agent,
            margin=args.gray_zone_margin,
        ),
        evidence_verification_node=_make_llm_only_evidence_node(evidence_agent),
    )

    graph_jsonl = args.output_dir / "graph_reasoning_results.jsonl"
    study_outputs: list[VisionStudyOutput] = []
    fusion_results = []
    verification_results = []
    evidence_agent_results = []
    retrieved_case_rows = []
    fusion_llm_request_count = 0
    fusion_llm_success_count = 0
    fusion_fallback_count = 0
    evidence_llm_request_count = 0
    evidence_llm_success_count = 0
    evidence_fallback_count = 0
    deterministic_changed_count = 0
    final_changed_count = 0
    start = time.perf_counter()

    with graph_jsonl.open("w") as handle:
        for index, record in enumerate(records, start=1):
            study_start = time.perf_counter()
            outputs = backend.predict_study_outputs(
                [record],
                dicom_root=dicom_root,
                batch_size=1,
                num_workers=args.num_workers,
                threshold_overrides=threshold_overrides,
            )
            if len(outputs) != 1:
                raise RuntimeError(
                    f"Vision backend returned {len(outputs)} outputs for one study"
                )
            vision_output = outputs[0]
            study_outputs.append(vision_output)
            current_vision_output.clear()
            current_vision_output[vision_output.study_key] = vision_output

            if index == 1:
                query_dim = len(vision_output.study_embedding)
                index_dim = _collection_embedding_dim(collection)
                if index_dim != query_dim:
                    raise RuntimeError(
                        "Retrieval embedding dimension mismatch: "
                        f"vision backbone produced dim={query_dim}, but Chroma "
                        f"collection expects dim={index_dim}. Rebuild the retrieval "
                        "index with the same checkpoint used by this run: "
                        f"{args.checkpoint}"
                    )

            final_state = graph.invoke(
                {
                    "study_key": record.study_key,
                    "dicom_paths": record.dicom_paths,
                }
            )
            label_fusion = final_state["label_fusion_result"]
            fusion_result = final_state["fusion_result"]
            verification_agent = final_state["evidence_verification_agent_result"]
            verification = final_state["evidence_verification"]

            fusion_results.append(fusion_result)
            verification_results.append(verification)
            evidence_agent_results.append(verification_agent)
            retrieved_case_rows.extend(
                _retrieved_case_rows(
                    final_state=final_state,
                    query_split=vision_output.split,
                    query_dicom_paths=vision_output.dicom_paths,
                )
            )
            fusion_llm_request_count += int(label_fusion.llm_requested)
            fusion_llm_success_count += int(label_fusion.llm_succeeded)
            fusion_fallback_count += int(label_fusion.fallback_used)
            evidence_llm_request_count += int(verification_agent.llm_requested)
            evidence_llm_success_count += int(verification_agent.llm_succeeded)
            evidence_fallback_count += int(verification_agent.fallback_used)
            deterministic_changed_count += len(
                _changed_labels(label_fusion.deterministic_result)
            )
            final_changed_count += len(_changed_labels(label_fusion.final_result))

            handle.write(
                json.dumps(
                    _graph_result_row(
                        index=index,
                        total=len(records),
                        elapsed_seconds=time.perf_counter() - study_start,
                        final_state=final_state,
                    ),
                    sort_keys=True,
                )
                + "\n"
            )
            handle.flush()

            if (
                index == 1
                or index % args.progress_every == 0
                or index == len(records)
            ):
                elapsed = time.perf_counter() - start
                print(
                    "[Exp07LLMFusionLLMOnlyEvidenceGraph] "
                    f"{index}/{len(records)} study_key={record.study_key} "
                    f"retrieved={len(final_state['retrieved_cases'])} "
                    f"fusion_llm_requested={label_fusion.llm_requested} "
                    f"fusion_llm_succeeded={label_fusion.llm_succeeded} "
                    f"fusion_fallback={label_fusion.fallback_used} "
                    f"evidence_llm_requested={verification_agent.llm_requested} "
                    f"evidence_llm_succeeded={verification_agent.llm_succeeded} "
                    f"evidence_fallback={verification_agent.fallback_used} "
                    f"predicted_labels={len(verification.predicted_labels)} "
                    f"evidence_score={verification.overall_evidence_score} "
                    f"elapsed={elapsed:.1f}s"
                )

    elapsed = time.perf_counter() - start
    run_config = {
        "experiment": "exp07_llm_fusion_llm_only_evidence_verification_graph",
        "cohort_root": str(cohort_root),
        "views_csv": str(views_csv),
        "dicom_root": str(dicom_root),
        "checkpoint": str(args.checkpoint),
        "threshold_policy_json": (
            str(args.threshold_policy_json)
            if args.threshold_policy_json is not None
            else None
        ),
        "vector_db_dir": str(args.vector_db_dir),
        "collection_name": args.collection_name,
        "output_dir": str(args.output_dir),
        "split": args.split,
        "max_studies": args.max_studies,
        "num_workers": args.num_workers,
        "device": args.device,
        "mixed_precision": not args.no_mixed_precision,
        "retrieval_top_k": args.retrieval_top_k,
        "gray_zone_margin": args.gray_zone_margin,
        "graph_nodes": [
            "vision",
            "retrieval",
            "fusion",
            "llm_only_evidence_verification",
        ],
        "report_writer_enabled": False,
        "fusion_mode": "llm_guarded_review",
        "fusion_llm_enabled": True,
        "fusion_llm_policy_version": LLM_REVIEW_POLICY_VERSION,
        "evidence_verification_enabled": True,
        "evidence_verification_mode": "llm_only",
        "evidence_verification_llm_enabled": True,
        "evidence_verification_policy_version": (
            LLM_ONLY_EVIDENCE_VERIFICATION_POLICY_VERSION
        ),
        "deterministic_evidence_verification_used": False,
        "deterministic_evidence_verification_fallback_used": False,
        "ollama_model": args.ollama_model,
        "ollama_base_url": args.ollama_base_url,
        "ollama_temperature": args.ollama_temperature,
        "ollama_timeout_seconds": args.ollama_timeout_seconds,
        "study_count": len(records),
        "fusion_llm_requested": fusion_llm_request_count,
        "fusion_llm_succeeded": fusion_llm_success_count,
        "fusion_fallback_used": fusion_fallback_count,
        "evidence_llm_requested": evidence_llm_request_count,
        "evidence_llm_succeeded": evidence_llm_success_count,
        "evidence_fallback_used": evidence_fallback_count,
        "deterministic_changed_labels": deterministic_changed_count,
        "final_changed_labels": final_changed_count,
        "retrieved_case_rows": len(retrieved_case_rows),
        "elapsed_seconds": elapsed,
    }
    _write_json(args.output_dir / "run_config.json", run_config)
    study_outputs_to_prediction_frame(study_outputs).to_csv(
        args.output_dir / "vision_study_predictions.csv",
        index=False,
    )
    fusion_results_to_frame(fusion_results).to_csv(
        args.output_dir / "fusion_label_predictions.csv",
        index=False,
    )
    pd.DataFrame(retrieved_case_rows).to_csv(
        args.output_dir / "retrieved_cases.csv",
        index=False,
    )
    _write_json(
        args.output_dir / "evidence_verification.json",
        [
            study_verification_to_json_dict(result)
            for result in verification_results
        ],
    )
    pd.DataFrame(study_verifications_to_csv_rows(verification_results)).to_csv(
        args.output_dir / "evidence_verification.csv",
        index=False,
    )

    audit_frame = pd.DataFrame(_evidence_audit_rows(evidence_agent_results))
    audit_frame.to_csv(args.output_dir / "llm_evidence_policy_audit.csv", index=False)
    _evidence_policy_summary_frame(audit_frame).to_csv(
        args.output_dir / "llm_evidence_policy_summary.csv",
        index=False,
    )

    print(
        "[Exp07LLMFusionLLMOnlyEvidenceGraph] summary "
        f"studies={len(records)} "
        f"fusion_llm_requested={fusion_llm_request_count} "
        f"fusion_llm_succeeded={fusion_llm_success_count} "
        f"fusion_fallback_used={fusion_fallback_count} "
        f"evidence_llm_requested={evidence_llm_request_count} "
        f"evidence_llm_succeeded={evidence_llm_success_count} "
        f"evidence_fallback_used={evidence_fallback_count} "
        f"retrieved_case_rows={len(retrieved_case_rows)}"
    )
    print(
        "[Exp07LLMFusionLLMOnlyEvidenceGraph] "
        f"wrote outputs -> {args.output_dir}"
    )

    if (
        fusion_fallback_count or evidence_fallback_count
    ) and not args.allow_llm_fallback:
        raise RuntimeError(
            "At least one LLM stage failed. Outputs were saved; inspect "
            "graph_reasoning_results.jsonl or pass --allow-llm-fallback. "
            "No deterministic evidence-verification fallback was used."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
