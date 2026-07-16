from __future__ import annotations
from pathlib import Path 
import argparse
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src.medagentx.agents.image_classifier_agent import run_image_classifier_agent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the MEDAGENT-X Image Classifier Agent."
    )

    parser.add_argument("--study-key", required=True)
    parser.add_argument("--dicom-path", required=True)
    parser.add_argument(
        "--quality-evidence-csv",
        default="outputs/chexpert_plus/quality_evidence_manifest.csv",
    )
    parser.add_argument(
        "--quality-gate-csv",
        default="outputs/chexpert_plus/quality_gate_decisions.csv",
    )
    parser.add_argument(
        "--output-csv",
        default="outputs/chexpert_plus/image_classifier_predictions.csv",
    )
    parser.add_argument(
        "--model-weights",
        default="densenet121-res224-all",
    )
    parser.add_argument(
        "--device",
        default="",
        help="Optional torch device: cpu, cuda, or mps. Empty means auto.",
    )

    args = parser.parse_args()

    result = run_image_classifier_agent(
        study_key=args.study_key,
        dicom_path=args.dicom_path,
        quality_evidence_csv=args.quality_evidence_csv,
        quality_gate_csv=args.quality_gate_csv,
        output_csv=args.output_csv,
        model_weights=args.model_weights,
        device=args.device,
    )

    print(f"Study key: {result['study_key']}")
    print(f"DICOM path: {result['dicom_path']}")
    print(f"Image classifier status: {result['image_classifier_status']}")
    print(f"Output CSV: {result.get('image_classifier_output_csv', '')}")
    print(f"Route next: {result['route_next']}")


if __name__ == "__main__":
    main()