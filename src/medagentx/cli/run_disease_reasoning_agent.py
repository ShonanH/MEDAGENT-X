from __future__ import annotations
from pathlib import Path
import sys
import argparse

from medagentx._bootstrap import ensure_src_on_path
from medagentx.paths import CHEXPERT_OUTPUT_DIR, DATA_DIR, FUSION_OUTPUT_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR, SRC_ROOT, VECTOR_DB_DIR

ensure_src_on_path()


from medagentx.agents.disease_reasoning_agent import (
    DEFAULT_CLASSIFIER_PREDICTIONS_PATH,
    run_disease_reasoning_agent,
)


if __name__ == "__main__":
    run_disease_reasoning_agent(
        retrieval_results_path=str(CHEXPERT_OUTPUT_DIR / "retrieval_results.csv"),
        image_classifier_predictions_path=DEFAULT_CLASSIFIER_PREDICTIONS_PATH,
        output_path=str(CHEXPERT_OUTPUT_DIR / "disease_reasoning_results.csv"),
        model="llama3.1:8b",
        ollama_url="http://localhost:11434",
        top_k=5,
        temperature=0.0,
        timeout_seconds=180,
        verbose=True,
    )