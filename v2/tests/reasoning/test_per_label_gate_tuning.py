"""Focused tests for sparse per-label gate calibration."""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pandas as pd


def _load_module(name: str):
    root = (
        Path(__file__).resolve().parents[2]
        / "experiments"
        / "optimization_prior_fusion_inputs"
    )
    path = root / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_tuner():
    _load_module("retrieval_prior")
    _load_module("prior_fusion")
    return _load_module("tune_prior_fusion_per_label_gates")


def _frame(gt_statuses: list[str], *, label: str = "Synthetic") -> pd.DataFrame:
    size = len(gt_statuses)
    return pd.DataFrame(
        {
            "study_key": [f"patient{i}/study1" for i in range(size)],
            "patient_key": [f"patient{i}" for i in range(size)],
            "label": [label] * size,
            "gt_status": gt_statuses,
            "probability": [0.45] * size,
            "threshold": [0.50] * size,
            "vision_status": ["absent"] * size,
            "retrieval_present_prior": [0.90] * size,
            "retrieval_absent_prior": [0.10] * size,
            "retrieval_confidence": [0.50] * size,
        }
    )


def test_partial_pooling_shrinks_sparse_local_precision() -> None:
    tuner = _load_tuner()

    pool_rate, pooled = tuner._partially_pooled_precision(
        beneficial=5,
        harmful=0,
        pool_beneficial=6,
        pool_harmful=4,
        strength=10.0,
    )

    assert math.isclose(pool_rate, 0.6)
    assert math.isclose(pooled, 11 / 15)
    assert pooled < 1.0


def test_patient_folds_require_changes_in_distinct_patients() -> None:
    tuner = _load_tuner()
    frame = _frame(["present"] * 5)

    folds, improvement_rate, harm_rate = tuner._patient_fold_rates(
        frame,
        selected_predictions=pd.Series(["present"] * 5).to_numpy(),
        changed=pd.Series([True] * 5).to_numpy(),
        folds=5,
        seed=17,
    )

    assert folds == 5
    assert improvement_rate == 1.0
    assert harm_rate == 0.0


def test_pooling_cannot_rescue_low_raw_intervention_precision() -> None:
    tuner = _load_tuner()
    label_frame = _frame(["present"] * 6 + ["absent"] * 4)
    pool_frame = _frame(["present"] * 10, label="Pool")
    constraints = tuner.TuningConstraints(
        min_scoreable_opportunities=1,
        min_scoreable_changes=1,
        partial_pooling_strength=10.0,
        cross_validation_folds=2,
        min_cv_folds_with_changes=1,
        min_cv_improvement_rate=0.0,
        max_cv_harm_rate=1.0,
        bootstrap_iterations=2,
        min_bootstrap_improvement_rate=0.0,
    )
    candidate = tuner.DirectionalGateCandidate(
        direction=tuner.PROMOTION,
        prior_threshold=0.80,
        min_retrieval_confidence=0.10,
    )

    row = tuner._candidate_row(
        label_frame,
        pool_frame=pool_frame,
        label="Synthetic",
        candidate=candidate,
        constraints=constraints,
    )

    assert math.isclose(row["intervention_precision"], 0.6)
    assert row["pooled_intervention_precision"] > 0.7
    assert row["accepted"] is False
    assert "raw_intervention_precision_below_min" in row["rejection_reasons"]
