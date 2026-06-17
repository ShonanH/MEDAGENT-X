import argparse
import json
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.agents.case_builder import build_case_state_from_row
from src.medagentx.agents.graph import build_medagentx_graph


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export MEDAGENT-X agent reports as JSON and Markdown."
    )

    parser.add_argument(
        "--csv-path",
        type=Path,
        default=(
            PROJECT_ROOT
            / "experiments"
            / "predictions"
            / "convnext_multitask_val_agent_inputs.csv"
        ),
        help="Path to the combined validation agent-input CSV.",
    )

    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="First CSV row index to export.",
    )

    parser.add_argument(
        "--num-cases",
        type=int,
        default=1,
        help="Number of cases to export.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "experiments" / "reports",
        help="Directory where reports will be saved.",
    )

    return parser.parse_args()


def main():
   args = parse_args()
   df = pd.read_csv(args.csv_path)

   if args.start_index < 0 or args.start_index >= len(df):
      raise IndexError(
         f"start-index must be between 0 and {len(df) - 1}. "
         f"Received: {args.start_index}"
      )

   end_index = min(args.start_index + args.num_cases, len(df))

   args.output_dir.mkdir(parents=True, exist_ok=True)

   graph = build_medagentx_graph()

   exported_count = 0

   summary_rows = []
    
   for row_index in range(args.start_index, end_index):
      row = df.iloc[row_index]

      initial_state = build_case_state_from_row(row)
      final_state = graph.invoke(initial_state)

      summary_rows.append(
         {
            "case_id": final_state["case_metadata"]["case_id"],
            "image_file": final_state["case_metadata"]["image_file"],
            "quality_score": final_state["final_report"]["quality_score"],
            "clinical_usability_level": final_state["final_report"]["clinical_usability_level"],
            "clinical_usability_label": final_state["final_report"]["clinical_usability_label"],
            "confidence": final_state["final_report"]["confidence"],
            "diagnosis_gate": final_state["final_report"]["diagnosis_gate"],
            "requires_human_review": final_state["final_report"]["requires_human_review"],
            "artifact_severity": final_state["artifact_assessment"]["artifact_severity"],
            "artifact_flags": ";".join(final_state["artifact_assessment"]["artifact_flags"]),
         }
      )

      case_id = final_state["case_metadata"]["case_id"]

      json_path = args.output_dir / f"{case_id}_agent_report.json"
      markdown_path = args.output_dir / f"{case_id}_agent_report.md"

      with open(json_path, "w") as f:
         json.dump(final_state, f, indent=2)

      with open(markdown_path, "w") as f:
         f.write(final_state["markdown_report"]["content"])
         f.write("\n")

      exported_count += 1

      print(f"[{exported_count}] Saved: {case_id}")
   

   summary_path = args.output_dir / "agent_report_summary.csv"
   summary_df = pd.DataFrame(summary_rows)
   summary_df.to_csv(summary_path, index=False)

   print(f"Saved summary CSV to: {summary_path}")
   print(f"Exported {exported_count} report(s) to: {args.output_dir}")


if __name__ == "__main__":
    main()