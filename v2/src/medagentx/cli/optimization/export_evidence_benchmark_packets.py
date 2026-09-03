"""Export Exp 7 evidence-verification packets for human annotation."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_SOURCE_RUN_DIR = Path(
    "v2/experiments/exp07_llm_fusion_evidence_verification_graph/qwen3_14b"
)
DEFAULT_OUTPUT_DIR = Path("v2/experiments/optimization_evidence_benchmark")
DEFAULT_OUTPUT_PREFIX = "annotation_packets_exp07"
PACKET_SCHEMA_VERSION = "optimization_evidence_benchmark_packet_v1"

HARD_LABELS = {
    "Pneumothorax",
    "Fracture",
    "Lung Lesion",
    "Pleural Other",
}

PACKET_COLUMNS = (
    "packet_schema_version",
    "source_experiment",
    "source_run_dir",
    "split",
    "retrieval_top_k",
    "fusion_policy_version",
    "verification_policy_version",
    "sample_rank",
    "sampling_reason",
    "is_pilot_packet",
    "is_fallback_like",
    "fallback_reasons",
    "study_key",
    "label",
    "vision_status",
    "deterministic_status",
    "fused_status",
    "probability",
    "threshold",
    "in_gray_zone",
    "fusion_changed",
    "fusion_reason",
    "retrieval_positive_count",
    "retrieval_negative_count",
    "deterministic_evidence_score",
    "final_evidence_score",
    "deterministic_retrieval_support",
    "final_retrieval_support",
    "deterministic_contradiction_level",
    "final_contradiction_level",
    "llm_reviewed",
    "llm_action",
    "llm_confidence",
    "llm_evidence_assessment",
    "llm_applied",
    "llm_policy_reason",
    "llm_supporting_case_ids",
    "llm_contradicting_case_ids",
    "supporting_evidence",
    "contradicting_evidence",
    "final_evidence_summary",
    "human_support_label",
    "human_error_tags",
    "human_notes",
)

CSV_JSON_COLUMNS = {
    "fallback_reasons",
    "llm_supporting_case_ids",
    "llm_contradicting_case_ids",
    "supporting_evidence",
    "contradicting_evidence",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build human-annotation packets from saved Exp 7 fusion and "
            "evidence-verification artifacts."
        )
    )
    parser.add_argument(
        "--source-run-dir",
        type=Path,
        default=DEFAULT_SOURCE_RUN_DIR,
        help="Folder containing Exp 7 output artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Folder where annotation packet files will be written.",
    )
    parser.add_argument(
        "--output-prefix",
        default=DEFAULT_OUTPUT_PREFIX,
        help="Prefix for JSONL and CSV packet outputs.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=200,
        help=(
            "Target number of packets. Mandatory hard cases are always kept, "
            "so output can exceed this target."
        ),
    )
    parser.add_argument(
        "--pilot-size",
        type=int,
        default=40,
        help="Number of selected packets marked as the pilot annotation subset.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Deterministic seed used when sampling fill packets.",
    )
    return parser


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required CSV is missing: {path}")
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Required JSON is missing: {path}")
    return json.loads(path.read_text())


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none", "null"}


def _first_nonblank(*values: Any, default: str = "") -> str:
    for value in values:
        if not _is_blank(value):
            return str(value).strip()
    return default


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _parse_float(value: Any) -> float | str:
    if _is_blank(value):
        return ""
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected numeric float value, got {value!r}") from exc


def _parse_int(value: Any) -> int | str:
    if _is_blank(value):
        return ""
    try:
        return int(float(str(value)))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected numeric integer value, got {value!r}") from exc


def _parse_json_cell(value: Any, fallback: Any) -> Any:
    if _is_blank(value):
        return fallback
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return fallback


def _require_columns(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    frame_name: str,
) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(
            f"{frame_name} missing required columns {missing}. "
            f"Available columns: {list(frame.columns)}"
        )


def _load_evidence_details(
    evidence_json: Path,
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, dict[str, Any]]]:
    payload = _read_json(evidence_json)
    if not isinstance(payload, list):
        raise ValueError(f"{evidence_json} must contain a list of study results")

    details_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    study_meta_by_key: dict[str, dict[str, Any]] = {}

    for study_result in payload:
        if not isinstance(study_result, dict):
            continue
        study_key = str(study_result.get("study_key", "")).strip()
        if not study_key:
            continue

        study_meta_by_key[study_key] = {
            "verification_policy_version": study_result.get(
                "verification_policy_version",
                "",
            ),
            "overall_evidence_score": study_result.get("overall_evidence_score", ""),
        }

        label_details = study_result.get("label_evidence_details") or []

        if not isinstance(label_details, list):
            continue
        for detail in label_details:
            if not isinstance(detail, dict):
                continue

            label = str(detail.get("label", "")).strip()
            if label:
                details_by_key[(study_key, label)] = detail

    return details_by_key, study_meta_by_key


def _list_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if _is_blank(value):
        return []

    return [str(value)]


def _load_graph_trace(graph_jsonl: Path) -> dict[str, dict[str, Any]]:
    if not graph_jsonl.exists():
        raise FileNotFoundError(f"Required JSONL file is missing: {graph_jsonl}")

    trace_by_study: dict[str, dict[str, Any]] = {}
    with graph_jsonl.open() as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{graph_jsonl} line {line_number} is not valid JSON"
                ) from exc

            study_key = str(row.get("study_key", "")).strip()
            if not study_key:
                continue

            fallback_used = False
            fallback_reasons: list[str] = []

            for key in ("fusion_llm", "evidence_llm", "llm"):
                block = row.get(key)
                if not isinstance(block, dict):
                    continue
                fallback_used = fallback_used or _parse_bool(
                    block.get("fallback_used", False)
                )

                fallback_reasons.extend(_list_values(block.get("fallback_reasons")))

            trace_by_study[study_key] = {
                "fallback_used": fallback_used,
                "fallback_reasons": sorted(set(fallback_reasons)),
            }

    return trace_by_study


def _audit_rows_by_key(
    audit_frame: pd.DataFrame,
) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row["study_key"]).strip(), str(row["label"]).strip()): row.to_dict()
        for _, row in audit_frame.iterrows()
    }

def _is_final_fusion_change(row: dict[str, Any]) -> bool:
    vision_status = str(row.get("vision_status", "")).strip().lower()
    fused_status = str(row.get("fused_status", "")).strip().lower()
    return vision_status != fused_status


def _is_demotion(packet: dict[str, Any]) -> bool:
    return (
        packet["vision_status"] == "present"
        and packet["fused_status"] in {"absent", "uncertain"}
    )

def _fallback_reasons(
    *,
    assessment: str,
    llm_reviewed: bool,
    audit: dict[str, Any],
    graph_trace: dict[str, Any],
) -> list[str]:
    reasons = []
    reasons.extend(
        _list_values(_parse_json_cell(audit.get("fallback_reasons"), []))
    )
    reasons.extend(_list_values(graph_trace.get("fallback_reasons", [])))

    if _is_blank(assessment):
        reasons.append("llm-evidence-assessment-blank")
    if not llm_reviewed:
        reasons.append("llm-not-reviewed")
    if _parse_bool(graph_trace.get("fallback_used", False)):
        reasons.append("graph-trace-fallback-used")

    return sorted(set(reason for reason in reasons if not _is_blank(reason)))


def _make_packets(
    *,
    source_run_dir: Path,
    fusion_frame: pd.DataFrame,
    audit_frame: pd.DataFrame,
    evidence_details: dict[tuple[str, str], dict[str, Any]],
    study_meta: dict[str, dict[str, Any]],
    graph_trace: dict[str, dict[str, Any]],
    run_config: dict[str, Any],
) -> list[dict[str, Any]]:
    audit_by_key = _audit_rows_by_key(audit_frame)
    packets: list[dict[str, Any]] = []

    for _, fusion_row_raw in fusion_frame.iterrows():
        fusion_row = fusion_row_raw.to_dict()
        if not _is_final_fusion_change(fusion_row):
            continue

        study_key = str(fusion_row["study_key"]).strip()
        label = str(fusion_row["label"]).strip()
        key = (study_key, label)

        audit = audit_by_key.get(key, {})
        detail = evidence_details.get(key, {})
        meta = study_meta.get(study_key, {})
        trace = graph_trace.get(study_key, {})

        assessment = _first_nonblank(
            audit.get("llm_evidence_assessment"),
            fusion_row.get("llm_evidence_assessment"),
        )
        llm_reviewed = _parse_bool(
            _first_nonblank(
                audit.get("llm_reviewed"),
                bool(_first_nonblank(assessment, fusion_row.get("llm_action"))),
            )
        )

        reasons = _fallback_reasons(
            assessment=assessment,
            llm_reviewed=llm_reviewed,
            audit=audit,
            graph_trace=trace,
        )
        if not audit:
            reasons.append("missing-audit-row")
        if not detail:
            reasons.append("missing-label-evidence-detail")
        reasons = sorted(set(reason for reason in reasons if not _is_blank(reason)))

        packet = {
            "packet_schema_version": PACKET_SCHEMA_VERSION,
            "source_experiment": _first_nonblank(
                run_config.get("experiment"),
                source_run_dir.parent.name,
            ),
            "source_run_dir": str(source_run_dir),
            "split": _first_nonblank(run_config.get("split")),
            "retrieval_top_k": _parse_int(run_config.get("retrieval_top_k")),
            "fusion_policy_version": _first_nonblank(
                fusion_row.get("fusion_policy_version"),
                run_config.get("fusion_policy_version"),
            ),
            "verification_policy_version": _first_nonblank(
                meta.get("verification_policy_version"),
                run_config.get("evidence_verification_llm_policy_version"),
            ),
            "sample_rank": "",
            "sampling_reason": "",
            "is_pilot_packet": False,
            "is_fallback_like": bool(reasons),
            "fallback_reasons": reasons,
            "study_key": study_key,
            "label": label,
            "vision_status": str(
                fusion_row.get("vision_status", "")
            ).strip().lower(),
            "deterministic_status": _first_nonblank(
                fusion_row.get("deterministic_status"),
                fusion_row.get("fused_status"),
            ).lower(),
            "fused_status": str(
                fusion_row.get("fused_status", "")
            ).strip().lower(),
            "probability": _parse_float(fusion_row.get("probability")),
            "threshold": _parse_float(fusion_row.get("threshold")),
            "in_gray_zone": _parse_bool(fusion_row.get("in_gray_zone")),
            "fusion_changed": True,
            "fusion_reason": _first_nonblank(
                detail.get("fusion_reason"),
                fusion_row.get("refinement_reason"),
            ),
            "retrieval_positive_count": _parse_int(
                _first_nonblank(
                    fusion_row.get("positive_count"),
                    audit.get("retrieval_positive_count"),
                    detail.get("retrieval_positive_count"),
                )
            ),
            "retrieval_negative_count": _parse_int(
                _first_nonblank(
                    fusion_row.get("negative_count"),
                    audit.get("retrieval_negative_count"),
                    detail.get("retrieval_negative_count"),
                )
            ),
            "deterministic_evidence_score": _parse_int(
                audit.get("deterministic_evidence_score")
            ),
            "final_evidence_score": _parse_int(
                _first_nonblank(
                    audit.get("final_evidence_score"),
                    detail.get("evidence_score"),
                )
            ),
            "deterministic_retrieval_support": _first_nonblank(
                audit.get("deterministic_retrieval_support")
            ),
            "final_retrieval_support": _first_nonblank(
                audit.get("final_retrieval_support"),
                detail.get("retrieval_support"),
            ),
            "deterministic_contradiction_level": _first_nonblank(
                audit.get("deterministic_contradiction_level")
            ),
            "final_contradiction_level": _first_nonblank(
                audit.get("final_contradiction_level"),
                detail.get("contradiction_level"),
            ),
            "llm_reviewed": llm_reviewed,
            "llm_action": _first_nonblank(fusion_row.get("llm_action")),
            "llm_confidence": _first_nonblank(
                audit.get("llm_confidence"),
                fusion_row.get("llm_confidence"),
            ),
            "llm_evidence_assessment": assessment,
            "llm_applied": _first_nonblank(fusion_row.get("llm_applied")),
            "llm_policy_reason": _first_nonblank(
                fusion_row.get("llm_policy_reason")
            ),
            "llm_supporting_case_ids": _parse_json_cell(
                audit.get("llm_supporting_case_ids"),
                [],
            ),
            "llm_contradicting_case_ids": _parse_json_cell(
                audit.get("llm_contradicting_case_ids"),
                [],
            ),
            "supporting_evidence": detail.get("supporting_evidence") or [],
            "contradicting_evidence": detail.get("contradicting_evidence") or [],
            "final_evidence_summary": _first_nonblank(
                audit.get("final_evidence_summary"),
                detail.get("evidence_summary"),
            ),
            "human_support_label": "",
            "human_error_tags": "",
            "human_notes": "",
        }
        packets.append(packet)

    return packets


def _mandatory_reasons(packet: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    assessment = str(packet["llm_evidence_assessment"]).strip().lower()

    if assessment == "contradictory":
        reasons.append("include_all_contradictory")
    if assessment == "insufficient":
        reasons.append("include_all_insufficient")
    if packet["is_fallback_like"]:
        reasons.append("include_all_fallback_like")
    if _is_demotion(packet):
        reasons.append("include_all_demotions")

    return reasons


def _packet_sort_key(packet: dict[str, Any]) -> tuple[int, str, str]:
    assessment = str(packet["llm_evidence_assessment"]).strip().lower()

    if assessment == "contradictory":
        priority = 0
    elif assessment == "insufficient":
        priority = 1
    elif packet["is_fallback_like"]:
        priority = 2
    elif _is_demotion(packet):
        priority = 3
    elif packet["label"] in HARD_LABELS:
        priority = 4
    elif assessment == "mixed":
        priority = 5
    elif assessment == "supporting":
        priority = 6
    else:
        priority = 7

    return priority, packet["label"], packet["study_key"]


def _bucket_name(packet: dict[str, Any]) -> str:
    assessment = str(packet["llm_evidence_assessment"]).strip().lower()

    if packet["label"] in HARD_LABELS and assessment in {"supporting", "mixed"}:
        return "hard_label_support_or_mixed_fill"

    if packet["label"] in HARD_LABELS:
        return "hard_label_fill"
    if assessment == "mixed":
        return "mixed_fill"
    if assessment == "supporting":
        return "supporting_fill"
    return "remaining_fill"


def _select_packets(
    packets: list[dict[str, Any]],
    *,
    sample_size: int,
    pilot_size: int,
    seed: int,
) -> list[dict[str, Any]]:
    if sample_size < 0:
        raise ValueError("--sample-size must be >= 0")
    if pilot_size < 0:
        raise ValueError("--pilot-size must be >= 0")
    if sample_size > 0 and pilot_size > sample_size:
        raise ValueError("--pilot-size must be <= --sample-size when sample-size > 0")

    if sample_size == 0 or len(packets) <= sample_size:
        selected = [
            dict(packet)
            for packet in sorted(packets, key=_packet_sort_key)
        ]
        for packet in selected:
            packet["sampling_reason"] = "all_changed_packets"

    else:
        selected_by_key: dict[tuple[str, str], dict[str, Any]] = {}

        for packet in sorted(packets, key=_packet_sort_key):
            reasons = _mandatory_reasons(packet)
            if not reasons:
                continue
            selected = dict(packet)
            selected["sampling_reason"] = "|".join(reasons)
            selected_by_key[(packet["study_key"], packet["label"])] = selected

        buckets: dict[str, list[dict[str, Any]]] = {}
        for packet in packets:
            key = (packet["study_key"], packet["label"])
            if key in selected_by_key:
                continue
            buckets.setdefault(_bucket_name(packet), []).append(packet)

        rng = random.Random(seed)
        fill_order = (
            "hard_label_support_or_mixed_fill",
            "hard_label_fill",
            "mixed_fill",
            "supporting_fill",
            "remaining_fill",
        )

        for bucket_name in fill_order:
            bucket = [dict(packet) for packet in buckets.get(bucket_name, [])]
            rng.shuffle(bucket)
            for packet in bucket:
                if len(selected_by_key) >= sample_size:
                    break
                packet["sampling_reason"] = bucket_name
                selected_by_key[(packet["study_key"], packet["label"])] = packet
            if len(selected_by_key) >= sample_size:
                break

        selected = sorted(selected_by_key.values(), key=_packet_sort_key)

    for index, packet in enumerate(selected, start=1):
        packet["sample_rank"] = index
        packet["is_pilot_packet"] = index <= pilot_size

    return selected


def _csv_ready_packet(packet: dict[str, Any]) -> dict[str, Any]:
    row = {column: packet.get(column, "") for column in PACKET_COLUMNS}
    for column in CSV_JSON_COLUMNS:
        row[column] = json.dumps(
            row[column],
            ensure_ascii=True,
            separators=(",", ":"),
        )
    return row


def _write_jsonl(path: Path, packets: list[dict[str, Any]]) -> None:
    with path.open("w") as handle:
        for packet in packets:
            handle.write(json.dumps(packet, ensure_ascii=True, sort_keys=True) + "\n")


def _rubric_text() -> str:
    return """# MEDAGENT-X Optimization Evidence Benchmark Rubric

## Annotation Unit

Each row is one study-label fusion change from Exp 7. The annotator should judge
whether the retrieved evidence supports the final fused label decision.

## Primary Label: human_support_label

Use exactly one value:

- supported: retrieved evidence clearly supports the fused label.
- contradicted: retrieved evidence clearly argues against the fused label.
- mixed: retrieved evidence contains both support and contradiction, or is clinically ambiguous.
- insufficient: retrieved evidence is too weak, indirect, missing, or irrelevant
  to support the fused label.

## Optional Field: human_error_tags

Use zero or more comma-separated tags:

- cross_label_confusion: evidence appears to support a related but different label.
- negation_error: negated evidence was treated as positive, or positive evidence
  was treated as negated.
- historical_or_temporal_error: evidence refers to prior, resolved, changing, or temporal findings.
- irrelevant_retrieval: retrieved cases or snippets are not useful for this label decision.

## Notes

- Retrieved reports are from visually similar training cases, not the target study report.
- Judge evidence quality for the proposed label change, not whether the target
  patient truly has the disease.
- Prefer insufficient when evidence is merely generic, indirect, or absent.
- Use mixed when support and contradiction are both clinically meaningful.
"""


def _write_outputs(
    *,
    output_dir: Path,
    output_prefix: str,
    packets: list[dict[str, Any]],
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = output_dir / f"{output_prefix}.jsonl"
    csv_path = output_dir / f"{output_prefix}.csv"
    rubric_path = output_dir / "annotation_rubric.md"

    _write_jsonl(jsonl_path, packets)
    pd.DataFrame(
        [_csv_ready_packet(packet) for packet in packets],
        columns=PACKET_COLUMNS,
    ).to_csv(csv_path, index=False)
    rubric_path.write_text(_rubric_text())

    return jsonl_path, csv_path, rubric_path


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_run_dir: Path = args.source_run_dir

    fusion_csv = source_run_dir / "fusion_label_predictions.csv"
    audit_csv = source_run_dir / "llm_evidence_policy_audit.csv"
    evidence_json = source_run_dir / "evidence_verification.json"
    graph_jsonl = source_run_dir / "graph_reasoning_results.jsonl"
    run_config_json = source_run_dir / "run_config.json"

    fusion_frame = _read_csv(fusion_csv)
    audit_frame = _read_csv(audit_csv)
    run_config = _read_json(run_config_json)

    if not isinstance(run_config, dict):
        raise ValueError(f"{run_config_json} must contain a JSON object")

    _require_columns(
        fusion_frame,
        (
            "study_key",
            "fusion_policy_version",
            "label",
            "probability",
            "threshold",
            "vision_status",
            "deterministic_status",
            "fused_status",
            "in_gray_zone",
            "positive_count",
            "negative_count",
            "refinement_reason",
        ),
        "fusion_label_predictions.csv",
    )
    _require_columns(
        audit_frame,
        (
            "study_key",
            "label",
            "deterministic_evidence_score",
            "final_evidence_score",
            "deterministic_retrieval_support",
            "final_retrieval_support",
            "deterministic_contradiction_level",
            "final_contradiction_level",
            "llm_reviewed",
            "llm_confidence",
            "llm_evidence_assessment",
            "llm_supporting_case_ids",
            "llm_contradicting_case_ids",
            "final_evidence_summary",
        ),
        "llm_evidence_policy_audit.csv",
    )

    evidence_details, study_meta = _load_evidence_details(evidence_json)
    graph_trace = _load_graph_trace(graph_jsonl)

    packets = _make_packets(
        source_run_dir=source_run_dir,
        fusion_frame=fusion_frame,
        audit_frame=audit_frame,
        evidence_details=evidence_details,
        study_meta=study_meta,
        graph_trace=graph_trace,
        run_config=run_config,
    )
    selected_packets = _select_packets(
        packets,
        sample_size=args.sample_size,
        pilot_size=args.pilot_size,
        seed=args.seed,
    )

    jsonl_path, csv_path, rubric_path = _write_outputs(
        output_dir=args.output_dir,
        output_prefix=args.output_prefix,
        packets=selected_packets,
    )

    assessment_counts = pd.Series(
        [
            packet["llm_evidence_assessment"] or "blank"
            for packet in selected_packets
        ]
    ).value_counts()

    print(f"[EvidenceBenchmark] source_run_dir={source_run_dir}")
    print(f"[EvidenceBenchmark] changed_packet_pool={len(packets)}")
    print(f"[EvidenceBenchmark] selected_packets={len(selected_packets)}")
    print(
        "[EvidenceBenchmark] pilot_packets="
        f"{sum(int(packet['is_pilot_packet']) for packet in selected_packets)}"
    )
    print(
        "[EvidenceBenchmark] fallback_like_packets="
        f"{sum(int(packet['is_fallback_like']) for packet in selected_packets)}"
    )
    print("[EvidenceBenchmark] assessment_counts:")
    for assessment, count in assessment_counts.items():
        print(f"  {assessment}: {count}")
    print(f"[EvidenceBenchmark] wrote JSONL -> {jsonl_path}")
    print(f"[EvidenceBenchmark] wrote CSV -> {csv_path}")
    print(f"[EvidenceBenchmark] wrote rubric -> {rubric_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
