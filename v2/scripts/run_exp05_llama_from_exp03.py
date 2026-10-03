"""Run Experiment 5 Llama fusion with Experiment 3's saved predictions.

This follows the retrieval and guarded LLM-review behavior of
``medagentx.cli.run_exp05_llm_fusion_with_retrieval_graph``, but it uses the
probabilities, thresholds, and statuses in Experiment 3's
``vision_study_predictions.csv`` as the fixed vision inputs.

Experiment 3's CSV does not persist RAD-DINO embeddings. A forward pass over
the DICOM views is therefore still required to regenerate *query embeddings*
for Chroma retrieval. The generated classification probabilities are
discarded; fusion always uses the saved Experiment 3 values. No vision
prediction CSV is regenerated or substituted.

The command also writes ``retrieved_cases.csv`` so subsequent experiments have
an auditable record of the retrieved report text and neighbor ranks.

Run from the repository root:

    ollama pull llama3.1:8b
    PYTHONPATH=v2/src python v2/scripts/run_exp05_llama_from_exp03.py \
      --allow-llm-fallback
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Sequence


_V2_ROOT = Path(__file__).resolve().parents[1]
_V2_SRC = _V2_ROOT / "src"
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.agents.label_fusion import LLM_REVIEW_POLICY_VERSION, LabelFusionAgent
from medagentx.data.balanced_constants import DEFAULT_BALANCED_COHORT_ROOT
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label
from medagentx.labels.statuses import LabelStatus
from medagentx.llm.ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    OllamaClient,
    OllamaConfig,
)
from medagentx.reasoning.constants import FUSION_RETRIEVAL_TOP_K, GRAY_ZONE_MARGIN
from medagentx.reasoning.fuse import VisionLabelPrediction


DEFAULT_SOURCE_VISION_CSV = Path(
    "v2/experiments/exp03_fusion_no_retrieval/vision_study_predictions.csv"
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
DEFAULT_COLLECTION_NAME = "medagentx_train_studies_v1"
DEFAULT_OUTPUT_DIR = Path(
    "v2/experiments/exp05_llm_fusion_with_retrieval_graph/"
    "llama3_1_8b_from_exp03"
)
OUTPUT_FILENAMES = (
    "run_config.json",
    "graph_fusion_results.jsonl",
    "vision_study_predictions.csv",
    "fusion_label_predictions.csv",
    "retrieved_cases.csv",
)


def _default_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _parse_status(value: object) -> LabelStatus:
    return LabelStatus(str(value).strip().lower())


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader), list(reader.fieldnames)


def _require_columns(
    available: Sequence[str], required: Iterable[str], *, description: str
) -> None:
    missing = [column for column in required if column not in available]
    if missing:
        raise ValueError(f"{description} is missing required columns: {missing}")


def _read_source_vision(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    rows, columns = _read_csv(path)
    required = [
        "study_key",
        "deid_patient_id",
        "split",
        "view_count",
        "dicom_paths",
    ]
    for label in DISEASE_LABELS:
        slug = snake_label(label)
        required.extend(
            (
                f"probability_{slug}",
                f"threshold_{slug}",
                f"status_{slug}",
            )
        )
    _require_columns(columns, required, description="Experiment 3 vision CSV")
    if not rows:
        raise ValueError("Experiment 3 vision CSV contains no study predictions")
    study_keys = [row["study_key"].strip() for row in rows]
    if any(not key for key in study_keys):
        raise ValueError("Experiment 3 vision CSV contains an empty study_key")
    if len(study_keys) != len(set(study_keys)):
        raise ValueError("Experiment 3 vision CSV contains duplicate study keys")
    return rows, columns


def _source_vision_predictions(row: dict[str, str]) -> dict[str, VisionLabelPrediction]:
    predictions: dict[str, VisionLabelPrediction] = {}
    for label in DISEASE_LABELS:
        slug = snake_label(label)
        predictions[label] = VisionLabelPrediction(
            label=label,
            probability=float(row[f"probability_{slug}"]),
            threshold=float(row[f"threshold_{slug}"]),
            status=_parse_status(row[f"status_{slug}"]),
        )
    return predictions


def _record_from_source_row(row: dict[str, str]) -> Any:
    """Build an inference record solely to regenerate a retrieval embedding."""
    from medagentx.vision.data import StudyInferenceRecord

    paths = tuple(path.strip() for path in row["dicom_paths"].split("|") if path.strip())
    if not paths:
        raise ValueError(f"Study {row['study_key']!r} has no DICOM paths in Exp03")
    return StudyInferenceRecord(
        study_key=row["study_key"].strip(),
        deid_patient_id=row["deid_patient_id"].strip(),
        split=row["split"].strip(),
        dicom_paths=paths,
    )


def _changed_labels(result: Any) -> list[str]:
    return [
        item.label
        for item in result.labels
        if item.vision_status is not item.fused_status
    ]


def _fusion_rows(fusion_results: Sequence[Any]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for result in fusion_results:
        for item in result.labels:
            deterministic_status = item.deterministic_status or item.fused_status
            rows.append(
                {
                    "study_key": result.study_key,
                    "fusion_policy_version": result.fusion_policy_version,
                    "label": item.label,
                    "probability": item.probability,
                    "threshold": item.threshold,
                    "vision_status": item.vision_status.value,
                    "deterministic_status": deterministic_status.value,
                    "fused_status": item.fused_status.value,
                    "in_gray_zone": item.in_gray_zone,
                    "positive_count": item.positive_count,
                    "negative_count": item.negative_count,
                    "llm_action": item.llm_action,
                    "llm_confidence": item.llm_confidence,
                    "llm_evidence_assessment": item.llm_evidence_assessment,
                    "llm_applied": item.llm_applied,
                    "llm_policy_reason": item.llm_policy_reason,
                    "refinement_reason": item.refinement_reason,
                }
            )
    return rows


def _write_csv(
    path: Path,
    rows: Sequence[dict[str, object]],
    fields: Sequence[str],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _retrieved_case_rows(
    *,
    source_row: dict[str, str],
    retrieved_cases: Sequence[Any],
) -> list[dict[str, object]]:
    paths = [path.strip() for path in source_row["dicom_paths"].split("|") if path.strip()]
    rows: list[dict[str, object]] = []
    for view_index, dicom_path in enumerate(paths, start=1):
        for rank, case in enumerate(retrieved_cases, start=1):
            rows.append(
                {
                    "query_study_key": source_row["study_key"],
                    "query_deid_patient_id": source_row["deid_patient_id"],
                    "query_split": source_row["split"],
                    "query_view_index": view_index,
                    "query_view_count": len(paths),
                    "query_dicom_path": dicom_path,
                    "retrieved_rank": rank,
                    "retrieved_study_key": case.study_key,
                    "retrieved_deid_patient_id": case.deid_patient_id,
                    "similarity": case.similarity,
                    "distance": case.distance,
                    "retrieved_document": case.document,
                }
            )
    return rows


def _prepare_output_dir(path: Path, *, overwrite: bool) -> None:
    path.mkdir(parents=True, exist_ok=True)
    existing = [path / name for name in OUTPUT_FILENAMES if (path / name).exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "Output files already exist; pass --overwrite to replace:\n"
            + "\n".join(str(item) for item in existing)
        )
    if overwrite:
        for item in existing:
            item.unlink()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-vision-csv", type=Path, default=DEFAULT_SOURCE_VISION_CSV)
    parser.add_argument("--cohort-root", type=Path, default=Path(DEFAULT_BALANCED_COHORT_ROOT))
    parser.add_argument("--dicom-root", type=Path, default=None)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_LAST4_CHECKPOINT)
    parser.add_argument("--vector-db-dir", type=Path, default=DEFAULT_LAST4_VECTOR_DB_DIR)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--device", default=_default_device())
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--no-mixed-precision", action="store_true")
    parser.add_argument("--retrieval-top-k", type=int, default=FUSION_RETRIEVAL_TOP_K)
    parser.add_argument("--gray-zone-margin", type=float, default=GRAY_ZONE_MARGIN)
    parser.add_argument("--ollama-model", default="llama3.1:8b")
    parser.add_argument("--ollama-base-url", default=DEFAULT_OLLAMA_BASE_URL)
    parser.add_argument("--ollama-temperature", type=float, default=0.0)
    parser.add_argument("--ollama-timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--allow-llm-fallback", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.num_workers < 0:
        raise ValueError("--num-workers must be >= 0")
    if args.retrieval_top_k <= 0:
        raise ValueError("--retrieval-top-k must be > 0")
    if args.gray_zone_margin < 0:
        raise ValueError("--gray-zone-margin must be >= 0")
    if args.ollama_timeout_seconds <= 0:
        raise ValueError("--ollama-timeout-seconds must be > 0")
    if args.progress_every <= 0:
        raise ValueError("--progress-every must be > 0")
    if not args.source_vision_csv.is_file():
        raise FileNotFoundError(f"Experiment 3 vision CSV not found: {args.source_vision_csv}")

    dicom_root = args.dicom_root or (args.cohort_root / "dicom_train")
    required_paths = {
        "DICOM root": dicom_root,
        "checkpoint": args.checkpoint,
        "Chroma vector database": args.vector_db_dir,
    }
    missing = [f"{name}: {path}" for name, path in required_paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "These artifacts are required only to regenerate query embeddings and "
            "retrieve reports:\n" + "\n".join(missing)
        )

    source_rows, _ = _read_source_vision(args.source_vision_csv)
    _prepare_output_dir(args.output_dir, overwrite=args.overwrite)

    from medagentx.reasoning.retrieve import (
        open_retrieval_collection,
        retrieve_similar_reports,
    )
    from medagentx.vision.backend import FineTunedRadDinoBackend

    backend = FineTunedRadDinoBackend.from_checkpoint(
        args.checkpoint,
        device=args.device,
        mixed_precision=not args.no_mixed_precision,
    )
    collection = open_retrieval_collection(
        args.vector_db_dir,
        collection_name=args.collection_name,
    )
    agent = LabelFusionAgent(
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

    fusion_results = []
    graph_rows = []
    retrieved_rows = []
    llm_requested = llm_succeeded = fallback_used = 0
    deterministic_changed = final_changed = 0
    started = time.perf_counter()

    for index, source_row in enumerate(source_rows, start=1):
        study_started = time.perf_counter()
        record = _record_from_source_row(source_row)
        generated_outputs = backend.predict_study_outputs(
            [record],
            dicom_root=dicom_root,
            batch_size=1,
            num_workers=args.num_workers,
        )
        if len(generated_outputs) != 1:
            raise RuntimeError(
                f"Embedding pass returned {len(generated_outputs)} outputs for {record.study_key!r}"
            )
        query_output = generated_outputs[0]
        if query_output.study_key != record.study_key:
            raise RuntimeError(
                "Embedding pass returned the wrong study key: "
                f"expected={record.study_key!r}, got={query_output.study_key!r}"
            )
        retrieved_cases = retrieve_similar_reports(
            collection,
            query_output,
            top_k=args.retrieval_top_k,
        )
        if len(retrieved_cases) != args.retrieval_top_k:
            raise RuntimeError(
                f"Retrieval returned {len(retrieved_cases)} cases for {record.study_key!r}; "
                f"expected {args.retrieval_top_k}"
            )
        label_fusion = agent.fuse(
            study_key=record.study_key,
            vision_predictions=_source_vision_predictions(source_row),
            retrieved_cases=retrieved_cases,
        )
        fusion_results.append(label_fusion.final_result)
        retrieved_rows.extend(
            _retrieved_case_rows(
                source_row=source_row,
                retrieved_cases=retrieved_cases,
            )
        )
        llm_requested += int(label_fusion.llm_requested)
        llm_succeeded += int(label_fusion.llm_succeeded)
        fallback_used += int(label_fusion.fallback_used)
        deterministic_changed_labels = _changed_labels(label_fusion.deterministic_result)
        final_changed_labels = _changed_labels(label_fusion.final_result)
        deterministic_changed += len(deterministic_changed_labels)
        final_changed += len(final_changed_labels)
        graph_rows.append(
            {
                "index": index,
                "total": len(source_rows),
                "elapsed_seconds": time.perf_counter() - study_started,
                "study_key": record.study_key,
                "retrieved_count": len(retrieved_cases),
                "deterministic_changed_labels": deterministic_changed_labels,
                "final_changed_labels": final_changed_labels,
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
        )
        if index == 1 or index % args.progress_every == 0 or index == len(source_rows):
            print(
                "[Exp05LlamaFromExp03] "
                f"{index}/{len(source_rows)} study_key={record.study_key} "
                f"retrieved={len(retrieved_cases)} "
                f"llm_requested={label_fusion.llm_requested} "
                f"llm_succeeded={label_fusion.llm_succeeded} "
                f"fallback_used={label_fusion.fallback_used}"
            )

    elapsed = time.perf_counter() - started
    shutil.copy2(args.source_vision_csv, args.output_dir / "vision_study_predictions.csv")
    _write_csv(
        args.output_dir / "fusion_label_predictions.csv",
        _fusion_rows(fusion_results),
        (
            "study_key", "fusion_policy_version", "label", "probability", "threshold",
            "vision_status", "deterministic_status", "fused_status", "in_gray_zone",
            "positive_count", "negative_count", "llm_action", "llm_confidence",
            "llm_evidence_assessment", "llm_applied", "llm_policy_reason",
            "refinement_reason",
        ),
    )
    _write_csv(
        args.output_dir / "retrieved_cases.csv",
        retrieved_rows,
        (
            "query_study_key", "query_deid_patient_id", "query_split", "query_view_index",
            "query_view_count", "query_dicom_path", "retrieved_rank", "retrieved_study_key",
            "retrieved_deid_patient_id", "similarity", "distance", "retrieved_document",
        ),
    )
    with (args.output_dir / "graph_fusion_results.jsonl").open(
        "w", encoding="utf-8"
    ) as handle:
        for row in graph_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    config = {
        "experiment": "exp05_llm_fusion_with_exp03_predictions",
        "source_vision_csv": str(args.source_vision_csv),
        "classification_predictions_reused_from_exp03": True,
        "embedding_generation_required_for_retrieval": True,
        "generated_classifier_probabilities_used": False,
        "dicom_root": str(dicom_root),
        "checkpoint": str(args.checkpoint),
        "vector_db_dir": str(args.vector_db_dir),
        "collection_name": args.collection_name,
        "output_dir": str(args.output_dir),
        "pipeline_stages_executed": [
            "query_embedding_generation",
            "retrieval",
            "deterministic_fusion",
            "llm_label_review",
        ],
        "fusion_llm_policy_version": LLM_REVIEW_POLICY_VERSION,
        "ollama_model": args.ollama_model,
        "ollama_base_url": args.ollama_base_url,
        "ollama_temperature": args.ollama_temperature,
        "ollama_timeout_seconds": args.ollama_timeout_seconds,
        "gray_zone_margin": args.gray_zone_margin,
        "retrieval_top_k": args.retrieval_top_k,
        "study_count": len(source_rows),
        "llm_requested": llm_requested,
        "llm_succeeded": llm_succeeded,
        "fallback_used": fallback_used,
        "deterministic_changed_labels": deterministic_changed,
        "final_changed_labels": final_changed,
        "retrieved_case_rows": len(retrieved_rows),
        "elapsed_seconds": elapsed,
    }
    (args.output_dir / "run_config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "[Exp05LlamaFromExp03] summary "
        f"studies={len(source_rows)} llm_requested={llm_requested} "
        f"llm_succeeded={llm_succeeded} fallback_used={fallback_used} "
        f"deterministic_changed_labels={deterministic_changed} "
        f"final_changed_labels={final_changed}"
    )
    print(f"[Exp05LlamaFromExp03] wrote outputs -> {args.output_dir}")
    if fallback_used and not args.allow_llm_fallback:
        raise RuntimeError(
            "One or more Llama reviews fell back to deterministic fusion. Outputs "
            "were saved; inspect graph_fusion_results.jsonl or pass --allow-llm-fallback."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
