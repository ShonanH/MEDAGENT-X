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
      description="TEST one MEDAGENT-X case through the LangGraph pipeline."
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
      "--row-index",
      type=int,
      default=0,
      help="CSV row index to convert into MEDAGENT-X state.",
   )

   return parser.parse_args()

def main():
   args = parse_args()

   df = pd.read_csv(args.csv_path)

   if args.row_index < 0 or args.row_index >= len(df):
      raise IndexError(
         f"row-index must be between 0 and {len(df) - 1}. "
         f"Received: {args.row_index}"
      )

   row = df.iloc[args.row_index]
   initial_state = build_case_state_from_row(row)
   graph = build_medagentx_graph()
   final_state = graph.invoke(initial_state)

   print(json.dumps(final_state, indent=2))

if __name__ == "__main__":
   main()