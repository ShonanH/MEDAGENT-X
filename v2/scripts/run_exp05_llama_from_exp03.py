"""Run only the Experiment 5 Llama review stage from cached Experiment 3 data.

This command never loads the vision checkpoint or opens the Chroma index.  It
uses Experiment 3's permanent vision-prediction CSV and a cache of the ten
retrieved report cases per study, then applies the Experiment 5 deterministic
fusion and guarded Llama review.

The retrieval cache must contain the *report text*, not merely per-label
mention counts.  Llama needs the retrieved documents in order to make and
citate a review decision.  Accepted cache inputs are:

* JSONL: one object per study, with ``study_key`` and ``retrieved_cases``;
* CSV: the ``retrieved_cases.csv`` contract emitted by Experiment 7, including
  ``query_study_key``, ``retrieved_rank``, and ``retrieved_document``.

Example:

    ollama pull llama3.1:8b
    PYTHONPATH=v2/src python v2/scripts/run_exp05_llama_from_exp03.py \
      --retrieval-cases path/to/test_retrieved_cases.jsonl \
      --allow-llm-fallback

The output records both the cached source files and the fact that vision and
retrieval were deliberately skipped.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Sequence


_V2_ROOT = Path(__file__).resolve().parents[1]
_V2_SRC = _V2_ROOT / "src"
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.agents.label_fusion import LLM_REVIEW_POLICY_VERSION, LabelFusionAgent
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
DEFAULT_OUTPUT_DIR = Path(
    "v2/experiments/exp05_llm_fusion_with_retrieval_graph/"
    "llama3_1_8b_from_exp03"
)
OUTPUT_FILENAMES = (
    "run_config.json",
    "graph_fusion_results.jsonl",
    "vision_study_predictions.csv",
    "fusion_label_predictions.csv",
)


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


def _read_vision_predictions(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    rows, columns = _read_csv(path)
    required = ["study_key"]
    for label in DISEASE_LABELS:
        slug = snake_label(label)
        required.extend(
            (
                f"probability_{slug}",
                f"threshold_{slug}",
                f"status_{slug}",
            )
        )
    _require_columns(columns, required, description="source vision CSV")
    if not rows:
        raise ValueError("source vision CSV contains no study predictions")
    study_keys = [row["study_key"].strip() for row in rows]
    if any(not key for key in study_keys):
        raise ValueError("source vision CSV contains an empty study_key")
    if len(study_keys) != len(set(study_keys)):
        raise ValueError("source vision CSV contains duplicate study_key values")
    return rows, columns


def _as_float_or_none(value: object) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def _normalise_case(raw: dict[str, Any], *, description: str) -> dict[str, Any]:
    document = raw.get("document", raw.get("retrieved_document", ""))
    if not isinstance(document, str) or not document.strip():
        raise ValueError(f"{description} has an empty retrieved document")
    study_key = raw.get("study_key", raw.get("retrieved_study_key", ""))
    if not str(study_key).strip():
        raise ValueError(f"{description} has an empty retrieved study key")
    patient_id = raw.get("deid_patient_id", raw.get("retrieved_deid_patient_id", ""))
    return {
        "study_key": str(study_key).strip(),
        "deid_patient_id": str(patient_id or "").strip(),
        "document": document.strip(),
        "distance": _as_float_or_none(raw.get("distance")),
        "similarity": _as_float_or_none(raw.get("similarity")),
    }


def _load_jsonl_cases(path: Path) -> dict[str, list[dict[str, Any]]]:
    cases_by_study: dict[str, list[dict[str, Any]]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL line {line_number} must be an object")
            study_key = str(
                payload.get("study_key", payload.get("query_study_key", ""))
            ).strip()
            raw_cases = payload.get("retrieved_cases")
            if not study_key or not isinstance(raw_cases, list):
                raise ValueError(
                    f"JSONL line {line_number} must contain study_key and retrieved_cases"
                )
            if study_key in cases_by_study:
                raise ValueError(f"Duplicate retrieval-cache study_key: {study_key}")
            cases_by_study[study_key] = [
                _normalise_case(
                    raw_case,
                    description=(
                        f"retrieval case {case_index} for {study_key!r} "
                        f"on JSONL line {line_number}"
                    ),
                )
                for case_index, raw_case in enumerate(raw_cases, start=1)
                if isinstance(raw_case, dict)
            ]
            if len(cases_by_study[study_key]) != len(raw_cases):
                raise ValueError(
                    f"retrieved_cases for {study_key!r} must contain objects only"
                )
    return cases_by_study


def _load_csv_cases(path: Path) -> dict[str, list[dict[str, Any]]]:
    rows, columns = _read_csv(path)
    _require_columns(
        columns,
        ("query_study_key", "retrieved_rank", "retrieved_document"),
        description="retrieval cases CSV",
    )
    by_study_and_rank: dict[tuple[str, int], dict[str, Any]] = {}
    for row_number, row in enumerate(rows, start=2):
        study_key = row["query_study_key"].strip()
        if not study_key:
            raise ValueError(f"retrieval cases CSV row {row_number} has an empty query_study_key")
        try:
            rank = int(row["retrieved_rank"])
        except ValueError as exc:
            raise ValueError(
                f"retrieval cases CSV row {row_number} has an invalid retrieved_rank"
            ) from exc
        if rank <= 0:
            raise ValueError(f"retrieval cases CSV row {row_number} has a non-positive rank")
        key = (study_key, rank)
        case = _normalise_case(
            row, description=f"retrieval cases CSV row {row_number}"
        )
        existing = by_study_and_rank.get(key)
        if existing is not None and existing != case:
            raise ValueError(
                "retrieval cases CSV contains different duplicate rows for "
                f"study={study_key!r}, rank={rank}"
            )
        by_study_and_rank[key] = case
    cases_by_study: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for (study_key, rank), case in by_study_and_rank.items():
        cases_by_study.setdefault(study_key, []).append((rank, case))
    return {
        study_key: [case for _, case in sorted(cases, key=lambda item: item[0])]
        for study_key, cases in cases_by_study.items()
    }


def _load_retrieval_cases(path: Path) -> dict[str, list[dict[str, Any]]]:
    if path.suffix.lower() == ".csv":
        cases = _load_csv_cases(path)
    else:
        cases = _load_jsonl_cases(path)
    if not cases:
        raise ValueError("retrieval cache contains no study cases")
    return cases


def _vision_predictions(row: dict[str, str]) -> dict[str, VisionLabelPrediction]:
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


def _write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    fields = (
        "study_key", "fusion_policy_version", "label", "probability", "threshold",
        "vision_status", "deterministic_status", "fused_status", "in_gray_zone",
        "positive_count", "negative_count", "llm_action", "llm_confidence",
        "llm_evidence_assessment", "llm_applied", "llm_policy_reason",
        "refinement_reason",
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _write_source_vision_csv(
    path: Path,
    rows: Sequence[dict[str, str]],
    fields: Sequence[str],
) -> None:
    """Write the selected Experiment 3 rows without altering their values."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


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
    parser.add_argument(
        "--retrieval-cases",
        type=Path,
        required=True,
        help="JSONL or Exp07-compatible CSV containing retrieved report text for every source study.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--ollama-model", default="llama3.1:8b")
    parser.add_argument("--ollama-base-url", default=DEFAULT_OLLAMA_BASE_URL)
    parser.add_argument("--ollama-temperature", type=float, default=0.0)
    parser.add_argument("--ollama-timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--gray-zone-margin", type=float, default=GRAY_ZONE_MARGIN)
    parser.add_argument("--retrieval-top-k", type=int, default=FUSION_RETRIEVAL_TOP_K)
    parser.add_argument("--max-studies", type=int, default=None)
    parser.add_argument("--allow-llm-fallback", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.source_vision_csv.is_file():
        raise FileNotFoundError(f"Source vision CSV not found: {args.source_vision_csv}")
    if not args.retrieval_cases.is_file():
        raise FileNotFoundError(f"Retrieval cache not found: {args.retrieval_cases}")
    if args.gray_zone_margin < 0:
        raise ValueError("--gray-zone-margin must be >= 0")
    if args.retrieval_top_k <= 0:
        raise ValueError("--retrieval-top-k must be > 0")
    if args.ollama_timeout_seconds <= 0:
        raise ValueError("--ollama-timeout-seconds must be > 0")
    if args.max_studies is not None and args.max_studies <= 0:
        raise ValueError("--max-studies must be > 0")

    vision_rows, vision_fields = _read_vision_predictions(args.source_vision_csv)
    if args.max_studies is not None:
        vision_rows = vision_rows[: args.max_studies]
    retrieval_cases = _load_retrieval_cases(args.retrieval_cases)
    required_studies = [row["study_key"] for row in vision_rows]
    missing_studies = sorted(set(required_studies) - set(retrieval_cases))
    if missing_studies:
        raise ValueError(
            "Retrieval cache lacks Experiment 3 studies; first missing keys: "
            + ", ".join(missing_studies[:10])
        )
    wrong_count = [
        (study_key, len(retrieval_cases[study_key]))
        for study_key in required_studies
        if len(retrieval_cases[study_key]) != args.retrieval_top_k
    ]
    if wrong_count:
        examples = ", ".join(
            f"{study_key} ({count})" for study_key, count in wrong_count[:10]
        )
        raise ValueError(
            f"Each study must have exactly {args.retrieval_top_k} cached cases; "
            f"violations: {examples}"
        )

    _prepare_output_dir(args.output_dir, overwrite=args.overwrite)
    llm_client = OllamaClient(
        OllamaConfig(
            model=args.ollama_model,
            base_url=args.ollama_base_url,
            temperature=args.ollama_temperature,
            timeout_seconds=args.ollama_timeout_seconds,
        )
    )
    agent = LabelFusionAgent(llm_client=llm_client, margin=args.gray_zone_margin)

    fusion_results = []
    graph_rows = []
    llm_requested = llm_succeeded = fallback_used = 0
    deterministic_changed = final_changed = 0
    started = time.perf_counter()
    for index, row in enumerate(vision_rows, start=1):
        study_key = row["study_key"]
        study_started = time.perf_counter()
        result = agent.fuse(
            study_key=study_key,
            vision_predictions=_vision_predictions(row),
            retrieved_cases=retrieval_cases[study_key],
        )
        fusion_results.append(result.final_result)
        llm_requested += int(result.llm_requested)
        llm_succeeded += int(result.llm_succeeded)
        fallback_used += int(result.fallback_used)
        deterministic_changed_labels = _changed_labels(result.deterministic_result)
        final_changed_labels = _changed_labels(result.final_result)
        deterministic_changed += len(deterministic_changed_labels)
        final_changed += len(final_changed_labels)
        graph_rows.append(
            {
                "index": index,
                "total": len(vision_rows),
                "elapsed_seconds": time.perf_counter() - study_started,
                "study_key": study_key,
                "retrieved_count": len(retrieval_cases[study_key]),
                "deterministic_changed_labels": deterministic_changed_labels,
                "final_changed_labels": final_changed_labels,
                "llm": {
                    "requested": result.llm_requested,
                    "succeeded": result.llm_succeeded,
                    "fallback_used": result.fallback_used,
                    "fallback_reasons": list(result.fallback_reasons),
                    "reviewed_labels": list(result.reviewed_labels),
                    "kept_labels": list(result.kept_labels),
                    "vetoed_labels": list(result.vetoed_labels),
                    "uncertain_labels": list(result.uncertain_labels),
                },
            }
        )
        if index == 1 or index % 25 == 0 or index == len(vision_rows):
            print(
                "[Exp05LlamaFromExp03] "
                f"{index}/{len(vision_rows)} study_key={study_key} "
                f"llm_requested={result.llm_requested} "
                f"llm_succeeded={result.llm_succeeded} "
                f"fallback_used={result.fallback_used}"
            )

    elapsed = time.perf_counter() - started
    _write_source_vision_csv(
        args.output_dir / "vision_study_predictions.csv",
        vision_rows,
        vision_fields,
    )
    _write_csv(args.output_dir / "fusion_label_predictions.csv", _fusion_rows(fusion_results))
    with (args.output_dir / "graph_fusion_results.jsonl").open(
        "w", encoding="utf-8"
    ) as handle:
        for row in graph_rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    config = {
        "experiment": "exp05_llm_fusion_from_exp03_cached_retrieval",
        "source_vision_csv": str(args.source_vision_csv),
        "retrieval_cases": str(args.retrieval_cases),
        "output_dir": str(args.output_dir),
        "pipeline_stages_skipped": ["vision", "retrieval"],
        "pipeline_stages_executed": ["deterministic_fusion", "llm_label_review"],
        "fusion_llm_policy_version": LLM_REVIEW_POLICY_VERSION,
        "ollama_model": args.ollama_model,
        "ollama_base_url": args.ollama_base_url,
        "ollama_temperature": args.ollama_temperature,
        "ollama_timeout_seconds": args.ollama_timeout_seconds,
        "gray_zone_margin": args.gray_zone_margin,
        "retrieval_top_k": args.retrieval_top_k,
        "study_count": len(vision_rows),
        "llm_requested": llm_requested,
        "llm_succeeded": llm_succeeded,
        "fallback_used": fallback_used,
        "deterministic_changed_labels": deterministic_changed,
        "final_changed_labels": final_changed,
        "elapsed_seconds": elapsed,
    }
    (args.output_dir / "run_config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "[Exp05LlamaFromExp03] summary "
        f"studies={len(vision_rows)} llm_requested={llm_requested} "
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
