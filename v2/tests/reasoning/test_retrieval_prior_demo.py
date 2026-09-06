"""Demo-style tests for the prior-fusion retrieval prior artifact."""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path


def _load_retrieval_prior_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "experiments"
        / "optimization_prior_fusion_inputs"
        / "retrieval_prior.py"
    )
    spec = importlib.util.spec_from_file_location("optimization_retrieval_prior", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_four_label_retrieval_prior_demo() -> None:
    retrieval_prior = _load_retrieval_prior_module()

    retrieved_cases = [
        {"study_key": "A", "similarity": 0.9},
        {"study_key": "B", "similarity": 0.8},
        {"study_key": "C", "similarity": 0.7},
    ]
    study_label_statuses = {
        "a": {
            "Pleural Effusion": "present",
            "Pneumonia": "absent",
            "Cardiomegaly": "present",
            "Pneumothorax": "unmentioned",
        },
        "b": {
            "Pleural Effusion": "present",
            "Pneumonia": "uncertain",
            "Cardiomegaly": "absent",
            "Pneumothorax": "absent",
        },
        "c": {
            "Pleural Effusion": "absent",
            "Pneumonia": "absent",
            "Cardiomegaly": "present",
            "Pneumothorax": "absent",
        },
    }

    priors = retrieval_prior.compute_retrieval_priors(
        retrieved_cases=retrieved_cases,
        study_label_statuses=study_label_statuses,
        labels=(
            "Pleural Effusion",
            "Pneumonia",
            "Cardiomegaly",
            "Pneumothorax",
        ),
    )

    assert math.isclose(priors["Pleural Effusion"].present_prior, (0.9 + 0.8) / 2.4)
    assert math.isclose(priors["Pleural Effusion"].absent_prior, 0.7 / 2.4)
    assert priors["Pleural Effusion"].top_supporting_cases == ("a", "b")
    assert priors["Pleural Effusion"].top_contradicting_cases == ("c",)

    assert priors["Pneumonia"].present_prior == 0.0
    assert priors["Pneumonia"].absent_prior == 1.0
    assert math.isclose(priors["Pneumonia"].uncertain_rate, 0.8 / 2.4)
    assert math.isclose(
        priors["Pneumonia"].retrieval_confidence,
        (0.9 + 0.7) / 2.4,
    )

    assert math.isclose(priors["Cardiomegaly"].present_prior, (0.9 + 0.7) / 2.4)
    assert math.isclose(priors["Cardiomegaly"].absent_prior, 0.8 / 2.4)

    assert priors["Pneumothorax"].present_prior == 0.0
    assert priors["Pneumothorax"].absent_prior == 1.0
    assert math.isclose(priors["Pneumothorax"].unmentioned_rate, 0.9 / 2.4)
    assert math.isclose(
        priors["Pneumothorax"].retrieval_confidence,
        (0.8 + 0.7) / 2.4,
    )
