from __future__ import annotations

import argparse
import re
from pathlib import Path
import sys
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.graphs.medagentx_graph import run_medagentx_graph
from src.medagentx.agents.judge_agent import build_judge_markdown
from src.medagentx.fusion.batch_metrics import print_batch_calibration_summary, write_batch_calibration_report


DEFAULT_QUALITY_GATE_CSV = "outputs/chexpert_plus/quality_gate_decisions.csv"
DEFAULT_QUALITY_EVIDENCE_CSV = "outputs/chexpert_plus/quality_evidence_manifest.csv"
DEFAULT_GROUND_TRUTH_CSV = "outputs/chexpert_plus/redivis_chexpert_plus_filtered_rows.csv"
DEFAULT_BATCH_DIR = "outputs/chexpert_plus/batch_first_100"
DEFAULT_CLASSIFIER_PREDICTIONS_CSV = (
    "outputs/chexpert_plus/fusion_classifier/ensemble_classifier_predictions.csv"
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


def load_first_eligible_cases(
    quality_gate_csv: str,
    limit: int,
) -> pd.DataFrame:
    gate_df = pd.read_csv(quality_gate_csv, dtype=str)

    required_columns = {
        "study_key",
        "dicom_path",
        "quality_gate_decision",
        "route_next",
    }
    missing = required_columns - set(gate_df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns in {quality_gate_csv}: {sorted(missing)}"
        )

    eligible = gate_df[
        gate_df["quality_gate_decision"].isin(
            ["pass", "review_with_technical_warning"]
        )
        & gate_df["route_next"].eq("retrieval_agent")
    ].copy()

    if eligible.empty:
        raise RuntimeError("No eligible pass/review cases found.")

    return eligible.head(limit).reset_index(drop=True)


def append_csv_if_present(csv_path: Path, collected_rows: list[pd.DataFrame]) -> None:
    if not csv_path.exists():
        return

    df = pd.read_csv(csv_path, dtype=str)
    if not df.empty:
        collected_rows.append(df)


def run_batch(
    limit: int,
    top_k: int,
    quality_gate_csv: str,
    quality_evidence_csv: str,
    ground_truth_csv: str,
    batch_dir: str,
    reasoning_model: str,
    classifier_predictions_csv: str,
) -> None:
    batch_path = Path(batch_dir)
    tmp_path = batch_path / "tmp"
    tmp_path.mkdir(parents=True, exist_ok=True)

    suffix = f"first_{limit}"
    combined_disease_reasoning_csv = batch_path / f"disease_reasoning_results_{suffix}.csv"
    combined_judge_results_csv = batch_path / f"judge_results_{suffix}.csv"
    combined_judge_report_md = batch_path / f"judge_report_{suffix}.md"
    batch_status_csv = batch_path / f"batch_status_{suffix}.csv"

    cases = load_first_eligible_cases(
        quality_gate_csv=quality_gate_csv,
        limit=limit,
    )

    disease_outputs: list[pd.DataFrame] = []
    judge_outputs: list[pd.DataFrame] = []
    status_rows: list[dict[str, Any]] = []

    total = len(cases)

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
            append_csv_if_present(judge_csv, judge_outputs)

            status_rows.append(
                {
                    "case_number": case_number,
                    "study_key": study_key,
                    "dicom_path": dicom_path,
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

    if not judge_outputs:
        raise RuntimeError(
            "Batch finished, but no Judge outputs were produced. "
            "Confirm that judge_agent is part of medagentx_graph.py. "
            f"See {batch_status_csv}."
        )

    combined_disease_df = pd.concat(disease_outputs, ignore_index=True)
    combined_disease_df.to_csv(combined_disease_reasoning_csv, index=False)

    combined_judge_df = pd.concat(judge_outputs, ignore_index=True)
    combined_judge_df.to_csv(combined_judge_results_csv, index=False)
    combined_judge_report_md.write_text(
        build_judge_markdown(combined_judge_df),
        encoding="utf-8",
    )

    print("[Batch] Complete.", flush=True)
    print(f"[Batch] Status CSV: {batch_status_csv}", flush=True)
    print(f"[Batch] Disease reasoning CSV: {combined_disease_reasoning_csv}", flush=True)
    print(f"[Batch] Judge results CSV: {combined_judge_results_csv}", flush=True)
    print(f"[Batch] Judge report: {combined_judge_report_md}", flush=True)

    try:
        metrics_report = write_batch_calibration_report(batch_path, limit=limit)
        print_batch_calibration_summary(metrics_report)
        print(
            f"[Batch] Calibration metrics JSON: {batch_path / f'batch_calibration_metrics_{suffix}.json'}",
            flush=True,
        )
        print(
            f"[Batch] Calibration metrics MD: {batch_path / f'batch_calibration_metrics_{suffix}.md'}",
            flush=True,
        )
    except Exception as exc:
        print(f"[Batch] Calibration metrics logging skipped: {exc}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full MEDAGENT-X LangGraph pipeline, including Judge Agent, "
            "for the first N eligible cases."
        )
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--quality-gate-csv", default=DEFAULT_QUALITY_GATE_CSV)
    parser.add_argument("--quality-evidence-csv", default=DEFAULT_QUALITY_EVIDENCE_CSV)
    parser.add_argument("--ground-truth-csv", default=DEFAULT_GROUND_TRUTH_CSV)
    parser.add_argument("--batch-dir", default=DEFAULT_BATCH_DIR)
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
        limit=args.limit,
        top_k=args.top_k,
        quality_gate_csv=args.quality_gate_csv,
        quality_evidence_csv=args.quality_evidence_csv,
        ground_truth_csv=args.ground_truth_csv,
        batch_dir=args.batch_dir,
        reasoning_model=args.reasoning_model,
        classifier_predictions_csv=args.classifier_predictions_csv,
    )


if __name__ == "__main__":
    main()