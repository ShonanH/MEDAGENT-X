#!/usr/bin/env python3
"""
Deprecated: patient splits are built after the quality gate.

Run:
  python src/medagentx/cli/11_build_patient_splits.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from medagentx._bootstrap import ensure_src_on_path

ensure_src_on_path()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "legacy_args",
        nargs="*",
        help="Forwarded to 11_build_patient_splits.py",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    script = Path(__file__).with_name("11_build_patient_splits.py")
    cmd = [sys.executable, str(script), *args.legacy_args]
    print(
        "03a_build_patient_splits.py is deprecated. "
        "Forwarding to 11_build_patient_splits.py (run after script 10).",
        flush=True,
    )
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
