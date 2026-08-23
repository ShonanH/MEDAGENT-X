"""Smoke-run the v2 LangGraph inference graph on real cohort data.

This script intentionally keeps runtime dependencies out of LangGraph state:
the vision backbone and retrieval collection are opened before graph assembly,
then bound into node callables.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from medagentx.data.balanced_constants import DEFAULT_BALANCED_COHORT_ROOT
from medagentx.graphs import (
    build_inference_graph,
    evidence_verification_node,
    fusion_node,
    make_retrieval_node,
    make_vision_node,
)
from medagentx.reasoning.constants import (
    FUSION_RETRIEVAL_TOP_K,
    GRAY_ZONE_MARGIN,
)
from medagentx.reasoning.retrieve import (
    default_retrieval_chroma_dir,
    open_retrieval_collection,
)
from medagentx.retrieval.constants import DEFAULT_COLLECTION_NAME
from medagentx.vision.backend import FineTunedRadDinoBackend
from medagentx.vision.constants import DEFAULT_BATCH_SIZE, DEFAULT_NUM_WORKERS
from medagentx.vision.data import build_study_inference_records
from medagentx.vision.inference_output import VisionStudyOutput


DEFAULT_LAST4_CHECKPOINT = (
    Path(DEFAULT_BALANCED_COHORT_ROOT)
    / "vision"
    / "raddino_finetuned_v1_last4_blocks"
    / "best_checkpoint.pt"
)


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
    parser.add_argument("--vector-db-dir", type=Path, default=None)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--split", choices=("val", "test"), default="test")
    parser.add_argument("--max-studies", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--num-workers", type=int, default=DEFAULT_NUM_WORKERS)
    parser.add_argument("--device", default=_default_device())
    parser.add_argument("--no-mixed-precision", action="store_true")
    parser.add_argument("--retrieval-top-k", type=int, default=FUSION_RETRIEVAL_TOP_K)
    parser.add_argument("--gray-zone-margin", type=float, default=GRAY_ZONE_MARGIN)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.max_studies <= 0:
        raise ValueError("--max-studies must be > 0")

    cohort_root = args.cohort_root
    views_csv = args.views_csv or (cohort_root / "splits" / "view_splits.csv")
    dicom_root = args.dicom_root or (cohort_root / "dicom_train")
    vector_db_dir = args.vector_db_dir or default_retrieval_chroma_dir(cohort_root)

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

    def graph_fusion_node(state: dict[str, Any]) -> dict[str, Any]:
        return fusion_node(state, margin=args.gray_zone_margin)

    def graph_verification_node(state: dict[str, Any]) -> dict[str, Any]:
        return evidence_verification_node(state, margin=args.gray_zone_margin)

    graph = build_inference_graph(
        vision_node=make_vision_node(vision_backbone),
        retrieval_node=make_retrieval_node(collection, top_k=args.retrieval_top_k),
        fusion_node=graph_fusion_node,
        verification_node=graph_verification_node,
    )

    for index, record in enumerate(records, start=1):
        final_state = graph.invoke(
            {
                "study_key": record.study_key,
                "dicom_paths": record.dicom_paths,
            }
        )
        verification = final_state["evidence_verification"]
        print(
            "[GraphSmoke] "
            f"{index}/{len(records)} study_key={record.study_key} "
            f"retrieved={len(final_state['retrieved_cases'])} "
            f"predicted_labels={len(verification.predicted_labels)} "
            f"evidence_score={verification.overall_evidence_score} "
            f"report_status={final_state['report_writer_result']['status']}"
        )


if __name__ == "__main__":
    main()
