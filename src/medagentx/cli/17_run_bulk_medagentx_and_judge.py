from __future__ import annotations

import argparse
import re
from pathlib import Path
import sys
from typing import Any

import pandas as pd


from medagentx._bootstrap import ensure_src_on_path
from medagentx.paths import CHEXPERT_OUTPUT_DIR, DATA_DIR, FUSION_OUTPUT_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR, SRC_ROOT, VECTOR_DB_DIR

ensure_src_on_path()

from medagentx.fusion.constants import (
    AGENT_EVAL_MIN_CASES,
    AGENT_EVAL_SPLIT,
    DEFAULT_SPLIT_METADATA,
)
from medagentx.fusion.splits import (
    assert_cohort_split_integrity,
    filter_quality_gate_eligible,
    get_patients_for_split,
    load_patient_split_table,
)
from medagentx.graphs.medagentx_graph import run_medagentx_graph
from medagentx.agents.judge_agent import run_judge_agent


DEFAULT_QUALITY_GATE_CSV = str(CHEXPERT_OUTPUT_DIR / "quality_gate_decisions.csv")
DEFAULT_QUALITY_EVIDENCE_CSV = str(CHEXPERT_OUTPUT_DIR / "quality_evidence_manifest.csv")
DEFAULT_GROUND_TRUTH_CSV = str(CHEXPERT_OUTPUT_DIR / "redivis_chexpert_plus_filtered_rows.csv")
DEFAULT_BATCH_DIR = str(CHEXPERT_OUTPUT_DIR / "batch_agent_eval")
DEFAULT_CLASSIFIER_PREDICTIONS_CSV = (
    str(FUSION_OUTPUT_DIR / "ensemble_classifier_predictions.csv")
)


def clean_string(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def make_case_slug(case_number: int, study_key: str, dicom_path: str) -> str:
    raw_slug = f"{case_number:03d}_{study_key}_{Path(dicom_path).stem}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw_slug).strip("_")


def load_agent_eval_eligible_cases(
    quality_gate_csv: str,
    split_metadata_csv: str,
    *,
    min_cases: int = AGENT_EVAL_MIN_CASES,
    max_cases: int | None = None,
) -> pd.DataFrame:
    split_table = load_patient_split_table(Path(split_metadata_csv))
    assert_cohort_split_integrity(split_table)
    agent_eval_patients = get_patients_for_split(split_table, AGENT_EVAL_SPLIT)

    gate_df = filter_quality_gate_eligible(pd.read_csv(quality_gate_csv, dtype=str))
    eligible = gate_df[gate_df["deid_patient_id"].isin(agent_eval_patients)].copy()

    print(
        "[Batch] Cohort: "
        f"{len(agent_eval_patients)} agent_eval patients in split metadata, "
        f"{eligible['deid_patient_id'].nunique()} with quality-gate-passing cases, "
        f"{len(eligible)} eligible views",
        flush=True,
    )

    if eligible.empty:
        raise RuntimeError(
            "No eligible pass/review cases found for agent_eval patients. "
            f"Re-run scripts 10 and 11 before script 17 ({split_metadata_csv})."
        )

    if len(eligible) < min_cases:
        raise RuntimeError(
            f"Only {len(eligible)} agent_eval cases available; need at least {min_cases}. "
            "Re-run script 11 with a larger quality-gate passing cohort."
        )

    eligible = eligible.sort_values(
        ["deid_patient_id", "study_key", "dicom_path"]
    ).reset_index(drop=True)

    if max_cases is not None and max_cases > 0:
        eligible = eligible.head(max_cases).reset_index(drop=True)

    return eligible


def append_csv_if_present(csv_path: Path, collected_rows: list[pd.DataFrame]) -> None:
    if not csv_path.exists():
        return

    df = pd.read_csv(csv_path, dtype=str)
    if not df.empty:
        collected_rows.append(df)


def run_batch(
    min_cases: int,
    max_cases: int | None,
    top_k: int,
    quality_gate_csv: str,
    quality_evidence_csv: str,
    ground_truth_csv: str,
    batch_dir: str,
    reasoning_model: str,
    classifier_predictions_csv: str,
    split_metadata_csv: str,
) -> None:
    batch_path = Path(batch_dir)
    tmp_path = batch_path / "tmp"
    tmp_path.mkdir(parents=True, exist_ok=True)

    combined_disease_reasoning_csv = batch_path / "disease_reasoning_results_agent_eval.csv"
    combined_judge_results_csv = batch_path / "judge_results_agent_eval.csv"
    combined_judge_report_md = batch_path / "judge_report_agent_eval.md"
    batch_status_csv = batch_path / "batch_status_agent_eval.csv"

    cases = load_agent_eval_eligible_cases(
        quality_gate_csv=quality_gate_csv,
        split_metadata_csv=split_metadata_csv,
        min_cases=min_cases,
        max_cases=max_cases,
    )

    disease_outputs: list[pd.DataFrame] = []
    status_rows: list[dict[str, Any]] = []

    total = len(cases)
    patient_count = cases["deid_patient_id"].nunique()
    print(
        f"[Batch] Running {total} eligible cases across {patient_count} agent_eval patients",
        flush=True,
    )

    for index, row in cases.iterrows():
        case_number = index + 1
        study_key = clean_string(row["study_key"])
        dicom_path = clean_string(row["dicom_path"])
        case_slug = make_case_slug(case_number, study_key, dicom_path)

        retrieval_csv = tmp_path / f"{case_slug}_retrieval_results.csv"
        disease_csv = tmp_path / f"{case_slug}_disease_reasoning_results.csv"
        judge_csv = tmp_path / f"{case_slug}_judge_results.csv"
        judge_report = tmp_path / f"{case_slug}_judge_report.md"

        print(
            f"[Batch] {case_number}/{total}: {study_key} | {dicom_path}",
            flush=True,
        )

        try:
            result = run_medagentx_graph(
                study_key=study_key,
                dicom_path=dicom_path,
                top_k=top_k,
                quality_evidence_csv=quality_evidence_csv,
                quality_gate_csv=quality_gate_csv,
                retrieval_results_csv=str(retrieval_csv),
                disease_reasoning_results_csv=str(disease_csv),
                classifier_predictions_csv=classifier_predictions_csv,
                ground_truth_csv=ground_truth_csv,
                judge_results_csv=str(judge_csv),
                judge_report_path=str(judge_report),
                reasoning_model=reasoning_model,
            )

            append_csv_if_present(disease_csv, disease_outputs)

            status_rows.append(
                {
                    "case_number": case_number,
                    "study_key": study_key,
                    "dicom_path": dicom_path,
                    "deid_patient_id": clean_string(row.get("deid_patient_id", "")),
                    "status": "completed",
                    "quality_gate_decision": result.get("quality_gate_decision", ""),
                    "route_next": result.get("route_next", ""),
                    "completed_steps": " | ".join(result.get("completed_steps", [])),
                    "judge_case_count": result.get("judge_case_count", 0),
                    "retrieval_results_csv": str(retrieval_csv),
                    "disease_reasoning_results_csv": str(disease_csv),
                    "judge_results_csv": str(judge_csv),
                    "judge_report_path": str(judge_report),
                    "error": "",
                }
            )

        except Exception as exc:
            status_rows.append(
                {
                    "case_number": case_number,
                    "study_key": study_key,
                    "dicom_path": dicom_path,
                    "deid_patient_id": clean_string(row.get("deid_patient_id", "")),
                    "status": "failed",
                    "quality_gate_decision": "",
                    "route_next": "",
                    "completed_steps": "",
                    "judge_case_count": 0,
                    "retrieval_results_csv": str(retrieval_csv),
                    "disease_reasoning_results_csv": str(disease_csv),
                    "judge_results_csv": str(judge_csv),
                    "judge_report_path": str(judge_report),
                    "error": repr(exc),
                }
            )
            print(f"[Batch] Failed: {study_key} | {dicom_path}: {exc}", flush=True)

    pd.DataFrame(status_rows).to_csv(batch_status_csv, index=False)

    if not disease_outputs:
        raise RuntimeError(
            "Batch finished, but no disease reasoning outputs were produced. "
            f"See {batch_status_csv}."
        )

    combined_disease_df = pd.concat(disease_outputs, ignore_index=True)
    combined_disease_df.to_csv(combined_disease_reasoning_csv, index=False)

    run_judge_agent(
        disease_reasoning_results_path=str(combined_disease_reasoning_csv),
        ground_truth_path=ground_truth_csv,
        output_path=str(combined_judge_results_csv),
        report_output_path=str(combined_judge_report_md),
        verbose=True,
    )

    print("[Batch] Complete.", flush=True)
    print(f"[Batch] Status CSV: {batch_status_csv}", flush=True)
    print(f"[Batch] Disease reasoning CSV: {combined_disease_reasoning_csv}", flush=True)
    print(f"[Batch] Judge results CSV: {combined_judge_results_csv}", flush=True)
    print(f"[Batch] Judge report: {combined_judge_report_md}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full MEDAGENT-X LangGraph pipeline, including Judge Agent, "
            "for quality-gate-eligible cases from the frozen agent_eval patient holdout."
        )
    )
    parser.add_argument(
        "--min-cases",
        type=int,
        default=AGENT_EVAL_MIN_CASES,
        help="Minimum agent_eval cases required before the batch starts.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Optional cap on eligible cases (views). Default: all eligible agent_eval cases.",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--quality-gate-csv", default=DEFAULT_QUALITY_GATE_CSV)
    parser.add_argument("--quality-evidence-csv", default=DEFAULT_QUALITY_EVIDENCE_CSV)
    parser.add_argument("--ground-truth-csv", default=DEFAULT_GROUND_TRUTH_CSV)
    parser.add_argument("--batch-dir", default=DEFAULT_BATCH_DIR)
    parser.add_argument(
        "--split-metadata-csv",
        default=str(DEFAULT_SPLIT_METADATA),
        help="Frozen patient splits from script 11.",
    )
    parser.add_argument(
        "--reasoning-model",
        default="",
        help="Optional Ollama model override. Empty uses the graph/agent default.",
    )

    parser.add_argument(
        "--classifier-predictions-csv",
        default=DEFAULT_CLASSIFIER_PREDICTIONS_CSV,
        help="Precomputed classifier predictions CSV passed to Disease Reasoning.",
    )

    args = parser.parse_args()

    run_batch(
        min_cases=args.min_cases,
        max_cases=args.max_cases,
        top_k=args.top_k,
        quality_gate_csv=args.quality_gate_csv,
        quality_evidence_csv=args.quality_evidence_csv,
        ground_truth_csv=args.ground_truth_csv,
        batch_dir=args.batch_dir,
        reasoning_model=args.reasoning_model,
        classifier_predictions_csv=args.classifier_predictions_csv,
        split_metadata_csv=args.split_metadata_csv,
    )


if __name__ == "__main__":
    main()
