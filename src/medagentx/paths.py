from __future__ import annotations

from pathlib import Path

# src/medagentx/paths.py -> src/ is parents[1], repo root is parents[2]
SRC_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SRC_ROOT.parent

DATA_DIR = SRC_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"

OUTPUTS_DIR = SRC_ROOT / "outputs"
CHEXPERT_OUTPUT_DIR = OUTPUTS_DIR / "chexpert_plus"
FUSION_OUTPUT_DIR = CHEXPERT_OUTPUT_DIR / "fusion_classifier"
VECTOR_DB_DIR = CHEXPERT_OUTPUT_DIR / "vector_db" / "chroma"

TESTS_DIR = SRC_ROOT / "tests"
