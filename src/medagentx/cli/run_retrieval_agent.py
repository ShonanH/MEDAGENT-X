from __future__ import annotations

import argparse
from pathlib import Path
import sys
import pandas as pd


from medagentx._bootstrap import ensure_src_on_path
from medagentx.paths import CHEXPERT_OUTPUT_DIR, DATA_DIR, FUSION_OUTPUT_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR, SRC_ROOT, VECTOR_DB_DIR

ensure_src_on_path()


from medagentx.agents.retrieval_agent import run_retrieval_agent


DEFAULT_QUALITY_GATE_CSV = Path(str(CHEXPERT_OUTPUT_DIR / "quality_gate_decisions.csv"))


def find_first_retrievable_case(quality_gate_csv: Path) -> tuple[str, str]:
    if not quality_gate_csv.exists():
        raise FileNotFoundError(f"Missing quality gate CSV: {quality_gate_csv}")

    gate_df = pd.read_csv(quality_gate_csv, dtype=str)

    eligible = gate_df[
        gate_df["quality_gate_decision"].isin(["pass", "review_with_technical_warning"])
        & gate_df["route_next"].eq("retrieval_agent")
    ]

    if eligible.empty:
        raise RuntimeError("No retrievable pass/review cases found in the quality gate CSV.")

    row = eligible.iloc[0]

    return row["study_key"], row["dicom_path"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the MEDAGENT-X Retrieval Agent for one DICOM case."
    )
    parser.add_argument("--study-key", default="")
    parser.add_argument("--dicom-path", default="")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--output-csv",
        default=str(CHEXPERT_OUTPUT_DIR / "retrieval_results.csv"),
    )
    parser.add_argument(
        "--first-eligible",
        action="store_true",
        help="Use the first pass/review case from quality_gate_decisions.csv.",
    )

    args = parser.parse_args()

    study_key = args.study_key
    dicom_path = args.dicom_path

    if args.first_eligible:
        study_key, dicom_path = find_first_retrievable_case(DEFAULT_QUALITY_GATE_CSV)

    if not study_key or not dicom_path:
        raise RuntimeError(
            "Provide --study-key and --dicom-path, or use --first-eligible."
        )

    result = run_retrieval_agent(
        study_key=study_key,
        dicom_path=dicom_path,
        top_k=args.top_k,
        output_csv=args.output_csv,
    )

    print(f"Query study_key: {result['study_key']}")
    print(f"Query dicom_path: {result['dicom_path']}")
    print(f"Retrieved cases: {len(result['retrieved_cases'])}")
    print(f"Route next: {result['route_next']}")
    print(f"Output CSV: {result['output_csv']}")


if __name__ == "__main__":
    main()