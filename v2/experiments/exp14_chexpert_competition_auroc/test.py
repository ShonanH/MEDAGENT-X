"""Experiment 14 entry point for expert-labeled CheXpert evaluation."""

from __future__ import annotations

import sys
from pathlib import Path


V2_SRC = Path(__file__).resolve().parents[2] / "src"
if str(V2_SRC) not in sys.path:
    sys.path.insert(0, str(V2_SRC))

from medagentx.cli.run_chexpert_competition_eval import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
