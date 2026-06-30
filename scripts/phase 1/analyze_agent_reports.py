import argparse
from pathlib import Path

import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[1]

def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze MEDAGENT-X agent report summary outputs."
    )

    parser.add_argument(
        "--summary-path",
        type=Path,
        default=PROJECT_ROOT / "experiments" / "reports" / "agent_report_summary.csv",
        help="Path to agent_report_summary.csv.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "experiments" / "agent_evaluation",
        help="Directory where analysis CSVs will be saved.",
    )

    parser.add_argument(
        "--low-confidence-threshold",
        type=float,
        default=0.60,
        help="Cases below this confidence are flagged as low confidence.",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary = pd.read_csv(args.summary_path)

    routing_counts = (
        summary["diagnosis_gate"]
        .value_counts()
        .rename_axis("diagnosis_gate")
        .reset_index(name="count")
    )

    human_review_cases = summary[
        summary["requires_human_review"] == True
    ].copy()

    low_confidence_cases = summary[
        summary["confidence"] < args.low_confidence_threshold
    ].copy()

    clinical_level_vs_routing = pd.crosstab(
        summary["clinical_usability_level"],
        summary["diagnosis_gate"],
    )

    artifact_severity_counts = (
        summary["artifact_severity"]
        .value_counts()
        .rename_axis("artifact_severity")
        .reset_index(name="count")
    )

    routing_counts.to_csv(args.output_dir / "routing_counts.csv", index=False)
    human_review_cases.to_csv(args.output_dir / "human_review_cases.csv", index=False)
    low_confidence_cases.to_csv(args.output_dir / "low_confidence_cases.csv", index=False)
    clinical_level_vs_routing.to_csv(args.output_dir / "clinical_level_vs_routing.csv")
    artifact_severity_counts.to_csv(args.output_dir / "artifact_severity_counts.csv", index=False)

    print(f"Loaded reports: {len(summary)}")
    print(f"Saved analysis CSVs to: {args.output_dir}")
    print("\nRouting counts:")
    print(routing_counts.to_string(index=False))
    print(f"\nHuman-review cases: {len(human_review_cases)}")
    print(f"Low-confidence cases: {len(low_confidence_cases)}")

if __name__ == "__main__":
    main()