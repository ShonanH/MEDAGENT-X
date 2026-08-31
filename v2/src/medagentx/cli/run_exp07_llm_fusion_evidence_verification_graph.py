"""Run Experiment 7: pure LLM evidence verification over Experiment 5 outputs."""

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
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label
from medagentx.labels.statuses import LabelStatus
from medagentx.llm.ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_TIMEOUT_SECONDS,
    OllamaClient,
    OllamaConfig,
)
from medagentx.reasoning.fuse import FusedLabelPrediction, FusionStudyResult
from medagentx.vision.inference_output import VisionLabelOutput, VisionStudyOutput


DEFAULT_INPUT_DIR = Path(
    "v2/experiments/exp05_llm_fusion_with_retrieval_graph/qwen3_14b"
)
DEFAULT_OUTPUT_DIR = Path("v2/experiments/exp07_llm_fusion_evidence_verification_graph")
OUTPUT_FILENAMES = (
    "run_config.json",
    "llm_evidence_verification_results.jsonl",
    "vision_study_predictions.csv",
    "fusion_label_predictions.csv",
    "evidence_verification.json",
    "evidence_verification.csv",
    "llm_evidence_policy_audit.csv",
    "llm_evidence_policy_summary.csv",
)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _require_existing_file(path: Path, *, name: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{name} does not exist: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{name} is not a file: {path}")


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


def _require_columns(
    frame: pd.DataFrame,
    required: Iterable[str],
    frame_name: str,
) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(
            f"{frame_name} missing required columns {missing}. "
            f"Available columns: {list(frame.columns)}"
        )


def _require_vision_columns(frame: pd.DataFrame) -> None:
    required = [
        "study_key",
        "deid_patient_id",
        "split",
        "view_count",
        "dicom_paths",
        "vision_backend_id",
    ]
    for label in DISEASE_LABELS:
        slug = snake_label(label)
        required.extend(
            [
                f"probability_{slug}",
                f"threshold_{slug}",
                f"status_{slug}",
            ]
        )
    _require_columns(frame, required, "vision_study_predictions.csv")


def _require_fusion_columns(frame: pd.DataFrame) -> None:
    _require_columns(
        frame,
        [
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
            "llm_action",
            "llm_confidence",
            "llm_evidence_assessment",
            "llm_applied",
            "llm_policy_reason",
            "refinement_reason",
        ],
        "fusion_label_predictions.csv",
    )


def _parse_status(value: Any) -> LabelStatus:
    return LabelStatus(str(value).strip().lower())


def _parse_optional_status(value: Any) -> LabelStatus | None:
    text = str(value or "").strip().lower()
    if not text or text == "nan":
        return None
    return LabelStatus(text)


def _parse_optional_bool(value: Any) -> bool | None:
    text = str(value or "").strip().lower()
    if not text or text == "nan":
        return None
    return text == "true"


def _parse_bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _parse_int(value: Any) -> int:
    return int(float(value))


def _vision_output_from_row(row: pd.Series) -> VisionStudyOutput:
    labels = []
    for label in DISEASE_LABELS:
        slug = snake_label(label)
        labels.append(
            VisionLabelOutput(
                label=label,
                probability=float(row[f"probability_{slug}"]),
                threshold=float(row[f"threshold_{slug}"]),
                status=_parse_status(row[f"status_{slug}"]),
            )
        )

    return VisionStudyOutput(
        study_key=str(row["study_key"]),
        deid_patient_id=str(row["deid_patient_id"]),
        split=str(row["split"]),
        view_count=int(row["view_count"]),
        dicom_paths=tuple(
            item for item in str(row["dicom_paths"]).split("|") if item
        ),
        vision_backend_id=str(row["vision_backend_id"]),
        study_embedding=(),
        labels=tuple(labels),
    )


def _fusion_result_from_frame(study_key: str, frame: pd.DataFrame) -> FusionStudyResult:
    labels: list[FusedLabelPrediction] = []
    policy_versions = sorted(set(frame["fusion_policy_version"].astype(str)))
    if len(policy_versions) != 1:
        raise ValueError(
            f"{study_key} has multiple fusion policy versions: {policy_versions}"
        )

    for row in frame.itertuples(index=False):
        labels.append(
            FusedLabelPrediction(
                label=str(row.label),
                vision_status=_parse_status(row.vision_status),
                fused_status=_parse_status(row.fused_status),
                probability=float(row.probability),
                threshold=float(row.threshold),
                in_gray_zone=_parse_bool(row.in_gray_zone),
                positive_count=_parse_int(row.positive_count),
                negative_count=_parse_int(row.negative_count),
                refinement_reason=str(row.refinement_reason),
                deterministic_status=_parse_optional_status(row.deterministic_status),
                llm_action=str(row.llm_action or ""),
                llm_confidence=str(row.llm_confidence or ""),
                llm_evidence_assessment=str(row.llm_evidence_assessment or ""),
                llm_applied=_parse_optional_bool(row.llm_applied),
                llm_policy_reason=str(row.llm_policy_reason or ""),
            )
        )

    observed_labels = {item.label for item in labels}
    missing_labels = sorted(set(DISEASE_LABELS) - observed_labels)
    if missing_labels:
        raise ValueError(f"{study_key} missing fusion labels: {missing_labels}")

    return FusionStudyResult(
        study_key=study_key,
        fusion_policy_version=policy_versions[0],
        labels=tuple(labels),
    )


def _load_inputs(
    *,
    vision_csv: Path,
    fusion_csv: Path,
) -> tuple[list[VisionStudyOutput], list[FusionStudyResult], pd.DataFrame, pd.DataFrame]:
    vision_frame = pd.read_csv(vision_csv, dtype=str)
    fusion_frame = pd.read_csv(fusion_csv, dtype=str)
    _require_vision_columns(vision_frame)
    _require_fusion_columns(fusion_frame)

    vision_outputs = [
        _vision_output_from_row(row)
        for _, row in vision_frame.iterrows()
    ]
    vision_keys = [output.study_key for output in vision_outputs]
    if len(set(vision_keys)) != len(vision_keys):
        raise ValueError("vision_study_predictions.csv contains duplicate study_key rows")

    fusion_results = [
        _fusion_result_from_frame(str(study_key), group)
        for study_key, group in fusion_frame.groupby("study_key", sort=False)
    ]
    fusion_keys = [result.study_key for result in fusion_results]
    if set(vision_keys) != set(fusion_keys):
        raise ValueError(
            "Vision and fusion inputs have different study keys: "
            f"vision_only={sorted(set(vision_keys) - set(fusion_keys))[:5]}, "
            f"fusion_only={sorted(set(fusion_keys) - set(vision_keys))[:5]}"
        )

    fusion_by_key = {result.study_key: result for result in fusion_results}
    ordered_fusion_results = [fusion_by_key[key] for key in vision_keys]
    return vision_outputs, ordered_fusion_results, vision_frame, fusion_frame


def _predicted_label_count(fusion_result: FusionStudyResult) -> int:
    return sum(
        item.fused_status is not LabelStatus.ABSENT
        for item in fusion_result.labels
    )


def _result_row(
    *,
    index: int,
    total: int,
    elapsed_seconds: float,
    agent_result: Any,
    predicted_label_count: int,
) -> dict[str, Any]:
    verification = agent_result.final_result
    return {
        "index": index,
        "total": total,
        "elapsed_seconds": elapsed_seconds,
        "study_key": agent_result.study_key,
        "predicted_label_count": predicted_label_count,
        "final_predicted_labels": list(verification.predicted_labels),
        "overall_evidence_score": verification.overall_evidence_score,
        "llm": {
            "requested": agent_result.llm_requested,
            "succeeded": agent_result.llm_succeeded,
            "fallback_used": agent_result.fallback_used,
            "fallback_reasons": list(agent_result.fallback_reasons),
            "reviewed_labels": list(agent_result.reviewed_labels),
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
            if label_result.fused_status is LabelStatus.ABSENT:
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
                    "retrieval_positive_count": (
                        label_result.retrieval_positive_count
                    ),
                    "retrieval_negative_count": (
                        label_result.retrieval_negative_count
                    ),
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
            "Run Experiment 7 pure LLM evidence verification over saved "
            "Experiment 5 vision and fusion outputs. This command does not run "
            "RAD-DINO, retrieval, label fusion, or LangGraph."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Experiment 5 output folder containing saved vision and fusion CSVs.",
    )
    parser.add_argument("--vision-csv", type=Path, default=None)
    parser.add_argument("--fusion-csv", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-studies", type=int, default=None)
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
            "Continue when pure LLM evidence verification fails for a study. "
            "No deterministic evidence-verification fallback is used."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_studies is not None and args.max_studies <= 0:
        raise ValueError("--max-studies must be > 0")
    if args.progress_every <= 0:
        raise ValueError("--progress-every must be > 0")

    vision_csv = args.vision_csv or (args.input_dir / "vision_study_predictions.csv")
    fusion_csv = args.fusion_csv or (args.input_dir / "fusion_label_predictions.csv")
    _require_existing_file(vision_csv, name="Experiment 5 vision CSV")
    _require_existing_file(fusion_csv, name="Experiment 5 fusion CSV")
    _prepare_output_dir(args.output_dir, overwrite=args.overwrite)

    print(
        "[Exp07LLMOnlyEvidence] "
        f"input_dir={args.input_dir} output_dir={args.output_dir} "
        f"model={args.ollama_model}"
    )
    vision_outputs, fusion_results, vision_frame, fusion_frame = _load_inputs(
        vision_csv=vision_csv,
        fusion_csv=fusion_csv,
    )
    if args.max_studies is not None:
        keep_keys = {result.study_key for result in fusion_results[: args.max_studies]}
        vision_outputs = vision_outputs[: args.max_studies]
        fusion_results = fusion_results[: args.max_studies]
        vision_frame = vision_frame[
            vision_frame["study_key"].astype(str).isin(keep_keys)
        ].copy()
        fusion_frame = fusion_frame[
            fusion_frame["study_key"].astype(str).isin(keep_keys)
        ].copy()

    total = len(vision_outputs)
    if not total:
        raise ValueError("No studies found in Experiment 5 inputs")

    llm_client = OllamaClient(
        OllamaConfig(
            model=args.ollama_model,
            base_url=args.ollama_base_url,
            temperature=args.ollama_temperature,
            timeout_seconds=args.ollama_timeout_seconds,
        )
    )
    agent = LLMOnlyEvidenceVerificationAgent(llm_client=llm_client)

    result_jsonl = args.output_dir / "llm_evidence_verification_results.jsonl"
    verification_results = []
    agent_results = []
    llm_request_count = 0
    llm_success_count = 0
    fallback_count = 0
    predicted_label_total = 0
    start = time.perf_counter()

    with result_jsonl.open("w") as handle:
        for index, (vision_output, fusion_result) in enumerate(
            zip(vision_outputs, fusion_results, strict=True),
            start=1,
        ):
            study_start = time.perf_counter()
            predicted_label_count = _predicted_label_count(fusion_result)
            predicted_label_total += predicted_label_count
            agent_result = agent.verify(
                vision_output=vision_output,
                fusion_result=fusion_result,
                retrieved_cases=(),
            )
            verification_results.append(agent_result.final_result)
            agent_results.append(agent_result)
            llm_request_count += int(agent_result.llm_requested)
            llm_success_count += int(agent_result.llm_succeeded)
            fallback_count += int(agent_result.fallback_used)

            handle.write(
                json.dumps(
                    _result_row(
                        index=index,
                        total=total,
                        elapsed_seconds=time.perf_counter() - study_start,
                        agent_result=agent_result,
                        predicted_label_count=predicted_label_count,
                    ),
                    sort_keys=True,
                )
                + "\n"
            )
            handle.flush()

            if index == 1 or index % args.progress_every == 0 or index == total:
                elapsed = time.perf_counter() - start
                print(
                    "[Exp07LLMOnlyEvidence] "
                    f"{index}/{total} study_key={fusion_result.study_key} "
                    f"predicted_labels={predicted_label_count} "
                    f"llm_requested={agent_result.llm_requested} "
                    f"llm_succeeded={agent_result.llm_succeeded} "
                    f"fallback_used={agent_result.fallback_used} "
                    f"evidence_score="
                    f"{agent_result.final_result.overall_evidence_score} "
                    f"elapsed={elapsed:.1f}s"
                )

    elapsed = time.perf_counter() - start
    run_config = {
        "experiment": "exp07_llm_only_evidence_verification",
        "input_experiment": str(args.input_dir),
        "vision_csv": str(vision_csv),
        "fusion_csv": str(fusion_csv),
        "output_dir": str(args.output_dir),
        "max_studies": args.max_studies,
        "ollama_model": args.ollama_model,
        "ollama_base_url": args.ollama_base_url,
        "ollama_temperature": args.ollama_temperature,
        "ollama_timeout_seconds": args.ollama_timeout_seconds,
        "vision_rerun": False,
        "retrieval_rerun": False,
        "fusion_rerun": False,
        "langgraph_used": False,
        "evidence_verification_mode": "llm_only",
        "evidence_verification_llm_enabled": True,
        "evidence_verification_policy_version": (
            LLM_ONLY_EVIDENCE_VERIFICATION_POLICY_VERSION
        ),
        "deterministic_evidence_verification_used": False,
        "deterministic_evidence_verification_fallback_used": False,
        "study_count": total,
        "predicted_label_total": predicted_label_total,
        "evidence_llm_requested": llm_request_count,
        "evidence_llm_succeeded": llm_success_count,
        "evidence_fallback_used": fallback_count,
        "elapsed_seconds": elapsed,
    }
    _write_json(args.output_dir / "run_config.json", run_config)
    vision_frame.to_csv(args.output_dir / "vision_study_predictions.csv", index=False)
    fusion_frame.to_csv(args.output_dir / "fusion_label_predictions.csv", index=False)
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

    audit_frame = pd.DataFrame(_evidence_audit_rows(agent_results))
    audit_frame.to_csv(args.output_dir / "llm_evidence_policy_audit.csv", index=False)
    _evidence_policy_summary_frame(audit_frame).to_csv(
        args.output_dir / "llm_evidence_policy_summary.csv",
        index=False,
    )

    print(
        "[Exp07LLMOnlyEvidence] summary "
        f"studies={total} predicted_labels={predicted_label_total} "
        f"evidence_llm_requested={llm_request_count} "
        f"evidence_llm_succeeded={llm_success_count} "
        f"evidence_fallback_used={fallback_count}"
    )
    print(f"[Exp07LLMOnlyEvidence] wrote outputs -> {args.output_dir}")

    if fallback_count and not args.allow_llm_fallback:
        raise RuntimeError(
            "At least one pure LLM evidence verification failed. Outputs were "
            "saved; inspect llm_evidence_verification_results.jsonl or pass "
            "--allow-llm-fallback. No deterministic evidence fallback was used."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
