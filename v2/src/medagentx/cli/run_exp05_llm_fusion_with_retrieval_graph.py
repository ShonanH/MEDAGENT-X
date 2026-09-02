"""Run Experiment 5: LangGraph vision -> retrieval -> LLM label fusion."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd

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
DEFAULT_OUTPUT_DIR = Path("v2/experiments/exp05_llm_fusion_with_retrieval_graph")
OUTPUT_FILENAMES = (
    "run_config.json",
    "graph_fusion_results.jsonl",
    "vision_study_predictions.csv",
    "fusion_label_predictions.csv",
)


def _default_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


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
            "Required Experiment 5 artifacts are missing:\n" + "\n".join(missing)
        )


def _prepare_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [
        output_dir / name for name in OUTPUT_FILENAMES if (output_dir / name).exists()
    ]
    if existing and not overwrite:
        raise FileExistsError(
            "Experiment 5 output files already exist. Pass --overwrite to replace:\n"
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
            "LangGraph is required for Experiment 5. Install project dependencies "
            "before graph construction."
        ) from exc
    return StateGraph, START, END


def _build_fusion_only_graph(
    *,
    vision_node,
    retrieval_node,
    fusion_node,
):
    """Build START -> vision -> retrieval -> fusion -> END."""
    from medagentx.graphs.state import MedAgentXInferenceState

    StateGraph, START, END = _load_langgraph()
    graph = StateGraph(MedAgentXInferenceState)
    graph.add_node("vision", vision_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("fusion", fusion_node)
    graph.add_edge(START, "vision")
    graph.add_edge("vision", "retrieval")
    graph.add_edge("retrieval", "fusion")
    graph.add_edge("fusion", END)
    return graph.compile()


def _changed_labels(result) -> list[str]:
    return [
        item.label
        for item in result.labels
        if item.vision_status is not item.fused_status
    ]


def _graph_result_row(
    *,
    index: int,
    total: int,
    elapsed_seconds: float,
    final_state: dict[str, Any],
) -> dict[str, Any]:
    label_fusion = final_state["label_fusion_result"]
    deterministic_changed = _changed_labels(label_fusion.deterministic_result)
    final_changed = _changed_labels(label_fusion.final_result)
    return {
        "index": index,
        "total": total,
        "elapsed_seconds": elapsed_seconds,
        "study_key": final_state["study_key"],
        "retrieved_count": len(final_state["retrieved_cases"]),
        "deterministic_changed_labels": deterministic_changed,
        "final_changed_labels": final_changed,
        "llm": {
            "requested": label_fusion.llm_requested,
            "succeeded": label_fusion.llm_succeeded,
            "fallback_used": label_fusion.fallback_used,
            "fallback_reasons": list(label_fusion.fallback_reasons),
            "reviewed_labels": list(label_fusion.reviewed_labels),
            "kept_labels": list(label_fusion.kept_labels),
            "vetoed_labels": list(label_fusion.vetoed_labels),
            "uncertain_labels": list(label_fusion.uncertain_labels),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run Experiment 5: LangGraph vision -> retrieval -> LLM label fusion. "
            "Evidence verification is intentionally excluded."
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
        help="Continue when LLM review falls back to deterministic fusion.",
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
        "[Exp05LLMFusionGraph] "
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
    label_fusion_agent = LabelFusionAgent(
        llm_client=OllamaClient(
            OllamaConfig(
                model=args.ollama_model,
                base_url=args.ollama_base_url,
                temperature=args.ollama_temperature,
                timeout_seconds=args.ollama_timeout_seconds,
            )
        ),
        margin=args.gray_zone_margin,
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

    graph = _build_fusion_only_graph(
        vision_node=make_vision_node(vision_backbone),
        retrieval_node=make_retrieval_node(collection, top_k=args.retrieval_top_k),
        fusion_node=make_label_fusion_node(
            use_llm=True,
            llm_agent=label_fusion_agent,
            margin=args.gray_zone_margin,
        ),
    )

    graph_jsonl = args.output_dir / "graph_fusion_results.jsonl"
    study_outputs: list[VisionStudyOutput] = []
    fusion_results = []
    llm_request_count = 0
    llm_success_count = 0
    fallback_count = 0
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
            fusion_results.append(fusion_result)
            llm_request_count += int(label_fusion.llm_requested)
            llm_success_count += int(label_fusion.llm_succeeded)
            fallback_count += int(label_fusion.fallback_used)
            deterministic_changed_count += len(
                _changed_labels(label_fusion.deterministic_result)
            )
            final_changed_count += len(_changed_labels(label_fusion.final_result))

            row = _graph_result_row(
                index=index,
                total=len(records),
                elapsed_seconds=time.perf_counter() - study_start,
                final_state=final_state,
            )
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            handle.flush()

            if (
                index == 1
                or index % args.progress_every == 0
                or index == len(records)
            ):
                elapsed = time.perf_counter() - start
                print(
                    "[Exp05LLMFusionGraph] "
                    f"{index}/{len(records)} study_key={record.study_key} "
                    f"retrieved={len(final_state['retrieved_cases'])} "
                    f"llm_requested={label_fusion.llm_requested} "
                    f"llm_succeeded={label_fusion.llm_succeeded} "
                    f"fallback_used={label_fusion.fallback_used} "
                    f"elapsed={elapsed:.1f}s"
                )

    elapsed = time.perf_counter() - start
    run_config = {
        "experiment": "exp05_llm_fusion_with_retrieval_graph",
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
        "graph_nodes": ["vision", "retrieval", "fusion"],
        "evidence_verification_enabled": False,
        "fusion_mode": "llm_guarded_review",
        "fusion_llm_enabled": True,
        "fusion_llm_policy_version": LLM_REVIEW_POLICY_VERSION,
        "ollama_model": args.ollama_model,
        "ollama_base_url": args.ollama_base_url,
        "ollama_temperature": args.ollama_temperature,
        "ollama_timeout_seconds": args.ollama_timeout_seconds,
        "study_count": len(records),
        "llm_requested": llm_request_count,
        "llm_succeeded": llm_success_count,
        "fallback_used": fallback_count,
        "deterministic_changed_labels": deterministic_changed_count,
        "final_changed_labels": final_changed_count,
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

    print(
        "[Exp05LLMFusionGraph] summary "
        f"studies={len(records)} llm_requested={llm_request_count} "
        f"llm_succeeded={llm_success_count} fallback_used={fallback_count} "
        f"deterministic_changed_labels={deterministic_changed_count} "
        f"final_changed_labels={final_changed_count}"
    )
    print(f"[Exp05LLMFusionGraph] wrote outputs -> {args.output_dir}")

    if fallback_count and not args.allow_llm_fallback:
        raise RuntimeError(
            "At least one LLM review fell back to deterministic fusion. Outputs were "
            "saved; inspect graph_fusion_results.jsonl or pass --allow-llm-fallback."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
