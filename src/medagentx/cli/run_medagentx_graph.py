from __future__ import annotations

import argparse

from medagentx._bootstrap import ensure_src_on_path
from medagentx.paths import CHEXPERT_OUTPUT_DIR, FUSION_OUTPUT_DIR
from medagentx.graphs.medagentx_graph import run_medagentx_graph

ensure_src_on_path()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the continuous MEDAGENT-X LangGraph pipeline."
    )

    parser.add_argument("--study-key", required=True)
    parser.add_argument("--dicom-path", required=True)
    parser.add_argument("--top-k", type=int, default=5)

    parser.add_argument(
        "--quality-evidence-csv",
        default=str(CHEXPERT_OUTPUT_DIR / "quality_evidence_manifest.csv"),
    )
    parser.add_argument(
        "--quality-gate-csv",
        default=str(CHEXPERT_OUTPUT_DIR / "quality_gate_decisions.csv"),
    )
    parser.add_argument(
        "--retrieval-results-csv",
        default=str(CHEXPERT_OUTPUT_DIR / "retrieval_results.csv"),
    )
    parser.add_argument(
        "--disease-reasoning-results-csv",
        default=str(CHEXPERT_OUTPUT_DIR / "disease_reasoning_results.csv"),
    )
    parser.add_argument(
        "--reasoning-model",
        default="",
        help="Ollama reasoning model. Defaults to the disease reasoning agent default/env var.",
    )

    parser.add_argument(
        "--ground-truth-csv",
        default=str(CHEXPERT_OUTPUT_DIR / "redivis_chexpert_plus_filtered_rows.csv"),
    )
    parser.add_argument(
        "--judge-results-csv",
        default=str(CHEXPERT_OUTPUT_DIR / "judge_results.csv"),
    )
    parser.add_argument(
        "--judge-report-path",
        default=str(CHEXPERT_OUTPUT_DIR / "judge_report.md"),
    )

    parser.add_argument(
        "--classifier-predictions-csv",
        default=str(FUSION_OUTPUT_DIR / "ensemble_classifier_predictions.csv"),
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