"""Smoke-run the v2 LangGraph inference graph on real cohort data.

This script intentionally keeps runtime dependencies out of LangGraph state:
the vision backbone and retrieval collection are opened before graph assembly,
then bound into node callables.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from medagentx.agents.label_fusion import LabelFusionAgent
from medagentx.contracts.evidence_verification import (
    study_verification_to_json_dict,
    study_verifications_to_csv_rows,
)
from medagentx.data.balanced_constants import DEFAULT_BALANCED_COHORT_ROOT
from medagentx.evaluation.fusion_eval import fusion_results_to_frame
from medagentx.graphs import (
    build_inference_graph,
    evidence_verification_node,
    make_retrieval_node,
    make_vision_node,
)
from medagentx.llm.ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    OllamaClient,
    OllamaConfig,
)
from medagentx.reasoning.constants import (
    FUSION_RETRIEVAL_TOP_K,
    GRAY_ZONE_MARGIN,
)
from medagentx.reasoning.retrieve import open_retrieval_collection
from medagentx.reasoning.vision_adapter import fusion_vision_inputs
from medagentx.retrieval.constants import DEFAULT_COLLECTION_NAME
from medagentx.vision.backend import FineTunedRadDinoBackend
from medagentx.vision.constants import DEFAULT_BATCH_SIZE, DEFAULT_NUM_WORKERS
from medagentx.vision.data import build_study_inference_records
from medagentx.vision.inference_output import (
    VisionStudyOutput,
    study_outputs_to_prediction_frame,
)


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
DEFAULT_OUTPUT_ROOT = Path(DEFAULT_BALANCED_COHORT_ROOT) / "smoke_test_runs"


def _default_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


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
            "Required smoke-run artifacts are missing:\n" + "\n".join(missing)
        )


def _timestamp_run_name() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _smoke_result_row(
    *,
    index: int,
    total: int,
    final_state: dict[str, Any],
) -> dict[str, Any]:
    label_fusion = final_state["label_fusion_result"]
    verification = final_state["evidence_verification"]
    return {
        "index": index,
        "total": total,
        "study_key": final_state["study_key"],
        "retrieved_count": len(final_state["retrieved_cases"]),
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
        "final_predicted_labels": list(verification.predicted_labels),
        "overall_evidence_score": verification.overall_evidence_score,
        "report_writer_result": final_state["report_writer_result"],
    }


def _collection_embedding_dim(collection: Any) -> int:
    payload = collection.get(limit=1, include=["embeddings"])
    embeddings = payload.get("embeddings")
    if embeddings is None or len(embeddings) == 0:
        raise ValueError("Retrieval collection has no embeddings to inspect")
    return len(embeddings[0])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a small real-data smoke test through the v2 inference graph."
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path(DEFAULT_BALANCED_COHORT_ROOT),
    )
    parser.add_argument("--views-csv", type=Path, default=None)
    parser.add_argument("--dicom-root", type=Path, default=None)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=DEFAULT_LAST4_CHECKPOINT,
        help="Defaults to the last-4-blocks RAD-DINO checkpoint.",
    )
    parser.add_argument("--threshold-policy-json", type=Path, default=None)
    parser.add_argument(
        "--vector-db-dir",
        type=Path,
        default=DEFAULT_LAST4_VECTOR_DB_DIR,
        help="Defaults to the retrieval index rebuilt from the last-4-blocks checkpoint.",
    )
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--split", choices=("val", "test"), default="test")
    parser.add_argument("--max-studies", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--num-workers", type=int, default=DEFAULT_NUM_WORKERS)
    parser.add_argument("--device", default=_default_device())
    parser.add_argument("--no-mixed-precision", action="store_true")
    parser.add_argument("--retrieval-top-k", type=int, default=FUSION_RETRIEVAL_TOP_K)
    parser.add_argument("--gray-zone-margin", type=float, default=GRAY_ZONE_MARGIN)
    parser.add_argument("--ollama-model", default=DEFAULT_OLLAMA_MODEL)
    parser.add_argument("--ollama-base-url", default=DEFAULT_OLLAMA_BASE_URL)
    parser.add_argument("--ollama-temperature", type=float, default=0.0)
    parser.add_argument("--ollama-timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory where timestamped smoke run folders are written.",
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="Optional output folder name. Defaults to a UTC timestamp.",
    )
    parser.add_argument(
        "--allow-no-llm-review",
        action="store_true",
        help=(
            "Allow the smoke run to pass when none of the sampled studies trigger "
            "deterministic fusion changes for LLM review."
        ),
    )
    parser.add_argument(
        "--allow-llm-fallback",
        action="store_true",
        help="Allow the smoke run to pass when LLM review falls back to deterministic fusion.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.max_studies <= 0:
        raise ValueError("--max-studies must be > 0")

    cohort_root = args.cohort_root
    run_name = args.run_name or _timestamp_run_name()
    output_dir = args.output_root / run_name
    views_csv = args.views_csv or (cohort_root / "splits" / "view_splits.csv")
    dicom_root = args.dicom_root or (cohort_root / "dicom_train")
    vector_db_dir = args.vector_db_dir

    _require_existing_paths(
        {
            "views_csv": views_csv,
            "dicom_root": dicom_root,
            "checkpoint": args.checkpoint,
            "vector_db_dir": vector_db_dir,
        }
    )
    if args.threshold_policy_json is not None:
        _require_existing_paths({"threshold_policy_json": args.threshold_policy_json})

    print(
        "[GraphSmoke] "
        f"split={args.split} max_studies={args.max_studies} "
        f"checkpoint={args.checkpoint}"
    )
    views = pd.read_csv(views_csv, dtype=str)
    records = build_study_inference_records(views, split=args.split)[: args.max_studies]
    if not records:
        raise ValueError(f"No records found for split={args.split!r}")

    backend = FineTunedRadDinoBackend.from_checkpoint(
        args.checkpoint,
        device=args.device,
        mixed_precision=not args.no_mixed_precision,
    )
    study_outputs = backend.predict_study_outputs(
        records,
        dicom_root=dicom_root,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        threshold_overrides=_load_threshold_overrides(args.threshold_policy_json),
    )
    outputs_by_study_key = {output.study_key: output for output in study_outputs}

    def vision_backbone(
        study_key: str,
        dicom_paths: tuple[str, ...],
    ) -> VisionStudyOutput:
        output = outputs_by_study_key[study_key]
        if output.dicom_paths != dicom_paths:
            raise ValueError(
                f"DICOM path mismatch for {study_key}: "
                f"state={dicom_paths!r}, vision_output={output.dicom_paths!r}"
            )
        return output

    collection = open_retrieval_collection(
        vector_db_dir,
        collection_name=args.collection_name,
    )
    query_embedding_dim = len(study_outputs[0].study_embedding)
    index_embedding_dim = _collection_embedding_dim(collection)
    if index_embedding_dim != query_embedding_dim:
        raise RuntimeError(
            "Retrieval embedding dimension mismatch: "
            f"vision backbone produced dim={query_embedding_dim}, but Chroma "
            f"collection expects dim={index_embedding_dim}. Rebuild the retrieval "
            "index with the same checkpoint used by this smoke run: "
            f"{args.checkpoint}"
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

    def graph_fusion_node(state: dict[str, Any]) -> dict[str, Any]:
        fusion_result = label_fusion_agent.fuse(
            study_key=state["vision_output"].study_key,
            vision_predictions=fusion_vision_inputs(state["vision_output"]),
            retrieved_cases=state["retrieved_cases"],
        )
        return {
            "label_fusion_result": fusion_result,
            "fusion_result": fusion_result.final_result,
        }

    def graph_verification_node(state: dict[str, Any]) -> dict[str, Any]:
        return evidence_verification_node(state, margin=args.gray_zone_margin)

    graph = build_inference_graph(
        vision_node=make_vision_node(vision_backbone),
        retrieval_node=make_retrieval_node(collection, top_k=args.retrieval_top_k),
        fusion_node=graph_fusion_node,
        verification_node=graph_verification_node,
    )

    smoke_rows: list[dict[str, Any]] = []
    fusion_results = []
    verification_results = []
    llm_request_count = 0
    llm_success_count = 0
    fallback_count = 0
    for index, record in enumerate(records, start=1):
        final_state = graph.invoke(
            {
                "study_key": record.study_key,
                "dicom_paths": record.dicom_paths,
            }
        )
        verification = final_state["evidence_verification"]
        label_fusion = final_state["label_fusion_result"]
        fusion_results.append(final_state["fusion_result"])
        verification_results.append(verification)
        smoke_rows.append(
            _smoke_result_row(
                index=index,
                total=len(records),
                final_state=final_state,
            )
        )
        llm_request_count += int(label_fusion.llm_requested)
        llm_success_count += int(label_fusion.llm_succeeded)
        fallback_count += int(label_fusion.fallback_used)
        print(
            "[GraphSmoke] "
            f"{index}/{len(records)} study_key={record.study_key} "
            f"retrieved={len(final_state['retrieved_cases'])} "
            f"llm_requested={label_fusion.llm_requested} "
            f"llm_succeeded={label_fusion.llm_succeeded} "
            f"fallback_used={label_fusion.fallback_used} "
            f"predicted_labels={len(verification.predicted_labels)} "
            f"evidence_score={verification.overall_evidence_score} "
            f"report_status={final_state['report_writer_result']['status']}"
        )

    print(
        "[GraphSmoke] summary "
        f"studies={len(records)} llm_requested={llm_request_count} "
        f"llm_succeeded={llm_success_count} fallback_used={fallback_count}"
    )

    output_dir.mkdir(parents=True, exist_ok=False)
    run_config = {
        "cohort_root": str(cohort_root),
        "views_csv": str(views_csv),
        "dicom_root": str(dicom_root),
        "checkpoint": str(args.checkpoint),
        "vector_db_dir": str(vector_db_dir),
        "collection_name": args.collection_name,
        "split": args.split,
        "max_studies": args.max_studies,
        "batch_size": args.batch_size,
        "num_workers": args.num_workers,
        "device": args.device,
        "mixed_precision": not args.no_mixed_precision,
        "retrieval_top_k": args.retrieval_top_k,
        "gray_zone_margin": args.gray_zone_margin,
        "ollama_model": args.ollama_model,
        "ollama_base_url": args.ollama_base_url,
        "ollama_temperature": args.ollama_temperature,
        "ollama_timeout_seconds": args.ollama_timeout_seconds,
        "allow_no_llm_review": args.allow_no_llm_review,
        "allow_llm_fallback": args.allow_llm_fallback,
        "study_count": len(records),
        "llm_requested": llm_request_count,
        "llm_succeeded": llm_success_count,
        "fallback_used": fallback_count,
    }
    _write_json(output_dir / "run_config.json", run_config)

    with (output_dir / "graph_smoke_results.jsonl").open("w") as handle:
        for row in smoke_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    study_outputs_to_prediction_frame(study_outputs).to_csv(
        output_dir / "vision_study_predictions.csv",
        index=False,
    )
    fusion_results_to_frame(fusion_results).to_csv(
        output_dir / "fusion_label_predictions.csv",
        index=False,
    )
    _write_json(
        output_dir / "evidence_verification.json",
        [
            study_verification_to_json_dict(result)
            for result in verification_results
        ],
    )
    pd.DataFrame(study_verifications_to_csv_rows(verification_results)).to_csv(
        output_dir / "evidence_verification.csv",
        index=False,
    )
    print(f"[GraphSmoke] wrote outputs -> {output_dir}")

    if llm_request_count == 0 and not args.allow_no_llm_review:
        raise RuntimeError(
            "No sampled studies triggered deterministic fusion changes, so the LLM "
            "review path was not exercised. Increase --max-studies or pass "
            "--allow-no-llm-review for a deterministic-only smoke run."
        )
    if fallback_count and not args.allow_llm_fallback:
        raise RuntimeError(
            "At least one LLM review fell back to deterministic fusion. Ensure Ollama "
            "is running with the requested model, or pass --allow-llm-fallback."
        )


if __name__ == "__main__":
    main()
