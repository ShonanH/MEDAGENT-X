from __future__ import annotations
from pathlib import Path 
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src.medagentx.graphs.medagentx_graph import run_medagentx_graph


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the continuous MEDAGENT-X LangGraph pipeline."
    )

    parser.add_argument("--study-key", required=True)
    parser.add_argument("--dicom-path", required=True)
    parser.add_argument("--top-k", type=int, default=5)

    parser.add_argument(
        "--quality-evidence-csv",
        default="outputs/chexpert_plus/quality_evidence_manifest.csv",
    )
    parser.add_argument(
        "--quality-gate-csv",
        default="outputs/chexpert_plus/quality_gate_decisions.csv",
    )
    parser.add_argument(
        "--retrieval-results-csv",
        default="outputs/chexpert_plus/retrieval_results.csv",
    )
    parser.add_argument(
        "--disease-reasoning-results-csv",
        default="outputs/chexpert_plus/disease_reasoning_results.csv",
    )
    parser.add_argument(
        "--reasoning-model",
        default="",
        help="Ollama reasoning model. Defaults to the disease reasoning agent default/env var.",
    )

    parser.add_argument(
        "--ground-truth-csv",
        default="outputs/chexpert_plus/redivis_chexpert_plus_filtered_rows.csv",
    )
    parser.add_argument(
        "--judge-results-csv",
        default="outputs/chexpert_plus/judge_results.csv",
    )
    parser.add_argument(
        "--judge-report-path",
        default="outputs/chexpert_plus/judge_report.md",
    )

    parser.add_argument(
        "--classifier-predictions-csv",
        default="outputs/chexpert_plus/fusion_classifier/ensemble_classifier_predictions.csv",
        help="Precomputed classifier predictions CSV (ensemble by default).",
    )

    args = parser.parse_args()

    result = run_medagentx_graph(
        study_key=args.study_key,
        dicom_path=args.dicom_path,
        top_k=args.top_k,
        quality_evidence_csv=args.quality_evidence_csv,
        quality_gate_csv=args.quality_gate_csv,
        retrieval_results_csv=args.retrieval_results_csv,
        disease_reasoning_results_csv=args.disease_reasoning_results_csv,
        classifier_predictions_csv=args.classifier_predictions_csv,
        reasoning_model=args.reasoning_model,
        ground_truth_csv=args.ground_truth_csv,
        judge_results_csv=args.judge_results_csv,
        judge_report_path=args.judge_report_path,
    )

    print("MEDAGENT-X graph run complete.")
    print(f"Study key: {result['study_key']}")
    print(f"DICOM path: {result['dicom_path']}")
    print(f"Quality Gate decision: {result['quality_gate_decision']}")
    print(f"Retrieved cases: {len(result['retrieved_cases'])}")
    print(f"Route next: {result['route_next']}")
    print(f"Completed steps: {result['completed_steps']}")


if __name__ == "__main__":
    main()