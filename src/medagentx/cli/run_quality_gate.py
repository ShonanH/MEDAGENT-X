from __future__ import annotations
import sys
from pathlib import Path

from medagentx._bootstrap import ensure_src_on_path

ensure_src_on_path()

from medagentx.agents.quality_gate_agent import run_quality_gate

if __name__ == "__main__":
    result = run_quality_gate()

    print(f"Quality Gate input: {result['input_csv']}")
    print(f"Quality Gate output: {result['output_csv']}")
    print(f"Decisions written: {len(result['decisions'])}")