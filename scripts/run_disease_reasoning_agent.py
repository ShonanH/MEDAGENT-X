from __future__ import annotations
from pathlib import Path
import sys
import argparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


from src.medagentx.agents.disease_reasoning_agent import run_disease_reasoning_agent


if __name__ == "__main__":
    run_disease_reasoning_agent(
        retrieval_results_path="outputs/chexpert_plus/retrieval_results.csv",
        image_classifier_predictions_path="outputs/chexpert_plus/image_classifier_predictions.csv",
        output_path="outputs/chexpert_plus/disease_reasoning_results.csv",
        model="llama3.1:8b",
        ollama_url="http://localhost:11434",
        top_k=5,
        temperature=0.0,
        timeout_seconds=180,
        verbose=True,
    )