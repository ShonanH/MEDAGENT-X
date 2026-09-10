"""Run the Experiment 5 fusion pipeline on the CheXpert competition test set."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from medagentx.cli.run_exp05_llm_fusion_with_retrieval_graph import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_LAST4_CHECKPOINT,
    DEFAULT_LAST4_VECTOR_DB_DIR,
    _build_fusion_only_graph,
    _collection_embedding_dim,
    _default_device,
    _graph_result_row,
    _load_threshold_overrides,
)
from medagentx.evaluation.chexpert_competition import (
    EXPECTED_STUDIES,
    EXPECTED_VIEWS,
    build_competition_ground_truth,
    build_competition_view_manifest,
    competition_binary_status_map,
)
from medagentx.evaluation.fusion_eval import (
    fusion_results_to_frame,
    fusion_status_map,
    named_judge_summary_payload,
    per_label_metrics_frame,
    run_named_judge_result,
    status_confusion_by_label_frame,
    vision_status_map,
)
from medagentx.evaluation.ground_truth import ground_truth_record_to_row
from medagentx.labels.constants import CHEXPERT_COMPETITION_LABELS


DEFAULT_DATASET_ROOT = Path(
    "v2/data/chexpert_competition_test/chexlocalize/CheXpert"
)
DEFAULT_EXPERT_LABELS = Path("v2/data/groundtruth.csv")
DEFAULT_THRESHOLD_POLICY = Path(
    "v2/artifacts/cohort_balanced_v1/reasoning/fusion_eval_v1/"
    "val_last4_blocks/val/threshold_tuning/threshold_policy_v2.json"
)
DEFAULT_OUTPUT_DIR = Path(
    "v2/experiments/exp15_competition_exp05_fusion/competition"
)
OUTPUT_FILENAMES = (
    "run_config.json",
    "graph_fusion_results.jsonl",
    "competition_view_manifest.csv",
    "competition_ground_truth.csv",
    "vision_study_predictions.csv",
    "fusion_label_predictions.csv",
    "binary_status_mapping.csv",
    "per_label_metrics.csv",
    "status_confusion_by_label.csv",
    "judge_summary.json",
)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _format_metric(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.4f}"


def _require_paths(paths: Mapping[str, Path]) -> None:
    missing = [f"{name}: {path}" for name, path in paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError("Required artifacts are missing:\n" + "\n".join(missing))


def _prepare_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [output_dir / name for name in OUTPUT_FILENAMES if (output_dir / name).exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "Competition fusion outputs already exist; pass --overwrite:\n"
            + "\n".join(str(path) for path in existing)
        )
    if overwrite:
        for path in existing:
            path.unlink()


def build_parser() -> argparse.ArgumentParser:
    from medagentx.llm.ollama import (
        DEFAULT_OLLAMA_BASE_URL,
        DEFAULT_OLLAMA_MODEL,
        DEFAULT_TIMEOUT_SECONDS,
    )
    from medagentx.reasoning.constants import FUSION_RETRIEVAL_TOP_K, GRAY_ZONE_MARGIN

    parser = argparse.ArgumentParser(
        description=(
            "Run the locked Exp05 vision-retrieval-LLM fusion pipeline on the "
            "500-study expert-labeled CheXpert competition test set."
        )
    )
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--test-labels-csv", type=Path, default=None)
    parser.add_argument(
        "--expert-labels-csv", type=Path, default=DEFAULT_EXPERT_LABELS
    )
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_LAST4_CHECKPOINT)
    parser.add_argument(
        "--threshold-policy-json", type=Path, default=DEFAULT_THRESHOLD_POLICY
    )
    parser.add_argument(
        "--vector-db-dir", type=Path, default=DEFAULT_LAST4_VECTOR_DB_DIR
    )
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
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
        "--ollama-timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS
    )
    parser.add_argument("--progress-every", type=int, default=1)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--allow-llm-fallback", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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

    image_root = args.dataset_root / "test"
    test_labels_csv = args.test_labels_csv or (
        args.dataset_root / "test_labels.csv"
    )
    _require_paths(
        {
            "competition image root": image_root,
            "test labels CSV": test_labels_csv,
            "expert labels CSV": args.expert_labels_csv,
            "checkpoint": args.checkpoint,
            "threshold policy": args.threshold_policy_json,
            "retrieval database": args.vector_db_dir,
        }
    )
    _prepare_output_dir(args.output_dir, overwrite=args.overwrite)

    test_rows = pd.read_csv(test_labels_csv, dtype=str)
    manifest = build_competition_view_manifest(test_rows, image_root=image_root)
    full_study_count = int(manifest["study_key"].nunique())
    if args.max_studies is None and (
        len(manifest) != EXPECTED_VIEWS or full_study_count != EXPECTED_STUDIES
    ):
        raise ValueError(
            "Released competition size mismatch: expected "
            f"{EXPECTED_STUDIES} studies/{EXPECTED_VIEWS} views, got "
            f"{full_study_count} studies/{len(manifest)} views"
        )

    from medagentx.agents.label_fusion import (
        LLM_REVIEW_POLICY_VERSION,
        LabelFusionAgent,
    )
    from medagentx.graphs.fusion_node import make_label_fusion_node
    from medagentx.graphs.retrieval_node import make_retrieval_node
    from medagentx.graphs.vision_node import make_vision_node
    from medagentx.llm.ollama import OllamaClient, OllamaConfig
    from medagentx.reasoning.retrieve import open_retrieval_collection
    from medagentx.vision.backend import FineTunedRadDinoBackend
    from medagentx.vision.data import (
        build_study_inference_records,
        raster_to_pil_rgb,
    )
    from medagentx.vision.inference_output import (
        VisionStudyOutput,
        study_outputs_to_prediction_frame,
    )

    records = build_study_inference_records(manifest)
    if args.max_studies is not None:
        records = records[: args.max_studies]
    selected_keys = {record.study_key for record in records}
    selected_manifest = manifest[manifest["study_key"].isin(selected_keys)].copy()

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
            raise ValueError(f"Image path mismatch for study {study_key}")
        return output

    graph = _build_fusion_only_graph(
        vision_node=make_vision_node(vision_backbone),
        retrieval_node=make_retrieval_node(
            collection, top_k=args.retrieval_top_k
        ),
        fusion_node=make_label_fusion_node(
            use_llm=True,
            llm_agent=label_fusion_agent,
            margin=args.gray_zone_margin,
        ),
    )

    study_outputs: list[VisionStudyOutput] = []
    fusion_results = []
    llm_request_count = 0
    llm_success_count = 0
    fallback_count = 0
    started = time.perf_counter()
    graph_jsonl = args.output_dir / "graph_fusion_results.jsonl"
    with graph_jsonl.open("w", encoding="utf-8") as handle:
        for index, record in enumerate(records, start=1):
            study_started = time.perf_counter()
            outputs = backend.predict_study_outputs(
                [record],
                dicom_root=image_root,
                batch_size=1,
                num_workers=args.num_workers,
                threshold_overrides=threshold_overrides,
                image_loader=raster_to_pil_rgb,
            )
            if len(outputs) != 1:
                raise RuntimeError("Vision backend must return exactly one study")
            vision_output = outputs[0]
            study_outputs.append(vision_output)
            current_vision_output.clear()
            current_vision_output[record.study_key] = vision_output

            if index == 1:
                query_dim = len(vision_output.study_embedding)
                index_dim = _collection_embedding_dim(collection)
                if query_dim != index_dim:
                    raise RuntimeError(
                        f"Retrieval dimension mismatch: query={query_dim}, "
                        f"index={index_dim}"
                    )

            final_state = graph.invoke(
                {
                    "study_key": record.study_key,
                    "dicom_paths": record.dicom_paths,
                }
            )
            label_fusion = final_state["label_fusion_result"]
            fusion_results.append(final_state["fusion_result"])
            llm_request_count += int(label_fusion.llm_requested)
            llm_success_count += int(label_fusion.llm_succeeded)
            fallback_count += int(label_fusion.fallback_used)
            row = _graph_result_row(
                index=index,
                total=len(records),
                elapsed_seconds=time.perf_counter() - study_started,
                final_state=final_state,
            )
            handle.write(json.dumps(row, sort_keys=True) + "\n")
            handle.flush()

            if index == 1 or index % args.progress_every == 0 or index == len(records):
                print(
                    "[CompetitionFusion] "
                    f"{index}/{len(records)} study={record.study_key} "
                    f"llm_requested={label_fusion.llm_requested} "
                    f"llm_succeeded={label_fusion.llm_succeeded} "
                    f"fallback={label_fusion.fallback_used} "
                    f"elapsed={time.perf_counter() - started:.1f}s",
                    flush=True,
                )

    # Ground truth is deliberately loaded only after all predictions finish.
    expert_rows = pd.read_csv(args.expert_labels_csv, dtype=str)
    ground_truth = build_competition_ground_truth(
        expert_rows,
        study_keys=[record.study_key for record in records],
    )
    vision_binary, vision_mapping = competition_binary_status_map(
        vision_status_map(study_outputs)
    )
    fusion_binary, fusion_mapping = competition_binary_status_map(
        fusion_status_map(fusion_results)
    )
    vision_mapping.insert(0, "run_name", "vision_full")
    fusion_mapping.insert(0, "run_name", "fusion_full")
    mappings = pd.concat([vision_mapping, fusion_mapping], ignore_index=True)

    judge_runs = [
        run_named_judge_result(
            name="vision_full",
            eval_scope="competition_test",
            ground_truth_records=ground_truth,
            predicted_statuses=vision_binary,
        ),
        run_named_judge_result(
            name="fusion_full",
            eval_scope="competition_test",
            ground_truth_records=ground_truth,
            predicted_statuses=fusion_binary,
        ),
    ]

    selected_manifest.to_csv(
        args.output_dir / "competition_view_manifest.csv", index=False
    )
    pd.DataFrame(
        [ground_truth_record_to_row(record) for record in ground_truth]
    ).to_csv(args.output_dir / "competition_ground_truth.csv", index=False)
    study_outputs_to_prediction_frame(study_outputs).to_csv(
        args.output_dir / "vision_study_predictions.csv", index=False
    )
    fusion_results_to_frame(fusion_results).to_csv(
        args.output_dir / "fusion_label_predictions.csv", index=False
    )
    mappings.to_csv(args.output_dir / "binary_status_mapping.csv", index=False)
    per_label_metrics_frame(judge_runs).to_csv(
        args.output_dir / "per_label_metrics.csv", index=False
    )
    status_confusion_by_label_frame(judge_runs).to_csv(
        args.output_dir / "status_confusion_by_label.csv", index=False
    )

    summaries = [named_judge_summary_payload(run) for run in judge_runs]
    _write_json(
        args.output_dir / "judge_summary.json",
        {
            "experiment": "exp15_competition_exp05_fusion",
            "labels": list(CHEXPERT_COMPETITION_LABELS),
            "binary_policy": "present=positive; absent_or_uncertain=negative",
            "runs": summaries,
        },
    )
    elapsed = time.perf_counter() - started
    _write_json(
        args.output_dir / "run_config.json",
        {
            "experiment": "exp15_competition_exp05_fusion",
            "dataset_root": str(args.dataset_root),
            "test_labels_csv": str(test_labels_csv),
            "expert_labels_csv": str(args.expert_labels_csv),
            "checkpoint": str(args.checkpoint),
            "threshold_policy_json": str(args.threshold_policy_json),
            "vector_db_dir": str(args.vector_db_dir),
            "collection_name": args.collection_name,
            "output_dir": str(args.output_dir),
            "device": args.device,
            "mixed_precision": not args.no_mixed_precision,
            "retrieval_top_k": args.retrieval_top_k,
            "gray_zone_margin": args.gray_zone_margin,
            "ollama_model": args.ollama_model,
            "ollama_base_url": args.ollama_base_url,
            "ollama_temperature": args.ollama_temperature,
            "ollama_timeout_seconds": args.ollama_timeout_seconds,
            "fusion_llm_policy_version": LLM_REVIEW_POLICY_VERSION,
            "study_count": len(records),
            "view_count": len(selected_manifest),
            "max_studies": args.max_studies,
            "llm_requested": llm_request_count,
            "llm_succeeded": llm_success_count,
            "fallback_used": fallback_count,
            "elapsed_seconds": elapsed,
        },
    )

    for summary in summaries:
        print(
            f"[CompetitionFusion] {summary['name']}: "
            f"macro_f1={_format_metric(summary['macro_f1'])} "
            f"macro_precision={_format_metric(summary['macro_precision'])} "
            f"macro_recall={_format_metric(summary['macro_recall'])} "
            f"coverage={_format_metric(summary['coverage'])}",
            flush=True,
        )
    print(f"[CompetitionFusion] wrote results -> {args.output_dir}", flush=True)
    if fallback_count and not args.allow_llm_fallback:
        raise RuntimeError(
            "At least one LLM review used fallback. Outputs were saved; inspect "
            "graph_fusion_results.jsonl or pass --allow-llm-fallback."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
