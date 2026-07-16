"""
Deprecated: use src.medagentx.classifiers.densenet_classifier and
scripts/11_run_densenet_predictions.py instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.medagentx.classifiers.densenet_classifier import (
    DEFAULT_OUTPUT_CSV,
    DEFAULT_QUALITY_EVIDENCE_CSV,
    DEFAULT_QUALITY_GATE_CSV,
    build_output_row,
    choose_device,
    classify_image_with_model,
    find_image_path,
    load_classifier,
    load_quality_gate_row,
)

__all__ = [
    "DEFAULT_OUTPUT_CSV",
    "DEFAULT_QUALITY_EVIDENCE_CSV",
    "DEFAULT_QUALITY_GATE_CSV",
    "run_image_classifier_agent",
]


def run_image_classifier_agent(
    study_key: str,
    dicom_path: str,
    quality_evidence_csv: str = str(DEFAULT_QUALITY_EVIDENCE_CSV),
    quality_gate_csv: str = str(DEFAULT_QUALITY_GATE_CSV),
    output_csv: str = str(DEFAULT_OUTPUT_CSV),
    model_weights: str = "densenet121-res224-all",
    device: str = "",
) -> dict[str, Any]:
    """Run DenseNet inference for a single case. Prefer scripts/11_run_densenet_predictions.py."""
    gate_row = load_quality_gate_row(study_key, dicom_path, Path(quality_gate_csv))
    if gate_row.get("quality_gate_decision") == "fail":
        return {
            "study_key": study_key,
            "dicom_path": dicom_path,
            "image_classifier_status": "skipped_quality_gate_fail",
            "image_classifier_output_csv": output_csv,
            "route_next": "stop_unreliable",
        }

    torch_device = choose_device(device)
    model = load_classifier(model_weights, torch_device)
    image_path = find_image_path(study_key, dicom_path, Path(quality_evidence_csv))
    raw_predictions, model_pathologies = classify_image_with_model(
        model=model,
        image_path=image_path,
        device=torch_device,
    )
    output_row = build_output_row(
        study_key=study_key,
        dicom_path=dicom_path,
        image_path=image_path,
        weights=model_weights,
        device=torch_device,
        raw_predictions=raw_predictions,
        model_pathologies=model_pathologies,
    )

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([output_row]).to_csv(output_path, index=False)

    return {
        "study_key": study_key,
        "dicom_path": dicom_path,
        "image_classifier_status": "complete",
        "image_classifier_output_csv": str(output_path),
        "image_classifier_predictions": output_row,
        "route_next": "retrieval_agent",
    }
