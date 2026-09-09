"""Demo-style tests for prior-fusion rules."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


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


def _load_prior_fusion_modules():
    retrieval_prior = _load_module("retrieval_prior")
    prior_fusion = _load_module("prior_fusion")
    return retrieval_prior, prior_fusion


def _prior(
    retrieval_prior,
    *,
    label: str,
    present: float,
    absent: float,
    confidence: float = 1.0,
):
    return retrieval_prior.RetrievalLabelPrior(
        label=label,
        present_prior=present,
        absent_prior=absent,
        uncertain_rate=0.0,
        unmentioned_rate=0.0,
        scoreable_weight=1.0,
        total_weight=1.0,
        retrieval_confidence=confidence,
        mean_similarity=0.8,
        retrieved_count=3,
        scoreable_count=3,
        top_supporting_cases=("supporting-study",),
        top_contradicting_cases=("contradicting-study",),
    )


def test_prior_fusion_keeps_strong_zone_vision_prediction() -> None:
    retrieval_prior, prior_fusion = _load_prior_fusion_modules()

    result = prior_fusion.fuse_label_with_prior(
        {
            "label": "Pleural Effusion",
            "probability": 0.10,
            "threshold": 0.50,
            "status": "absent",
        },
        _prior(
            retrieval_prior,
            label="Pleural Effusion",
            present=0.95,
            absent=0.05,
        ),
    )

    assert result.in_gray_zone is False
    assert result.vision_status == "absent"
    assert result.fused_status == "absent"


def test_prior_fusion_promotes_gray_zone_absent_prediction() -> None:
    retrieval_prior, prior_fusion = _load_prior_fusion_modules()

    result = prior_fusion.fuse_label_with_prior(
        {
            "label": "Pleural Effusion",
            "probability": 0.48,
            "threshold": 0.52,
            "status": "absent",
        },
        _prior(
            retrieval_prior,
            label="Pleural Effusion",
            present=0.80,
            absent=0.20,
        ),
    )

    assert result.in_gray_zone is True
    assert result.vision_status == "absent"
    assert result.fused_status == "present"


def test_prior_fusion_demotes_gray_zone_present_prediction_to_uncertain() -> None:
    retrieval_prior, prior_fusion = _load_prior_fusion_modules()

    result = prior_fusion.fuse_label_with_prior(
        {
            "label": "Cardiomegaly",
            "probability": 0.53,
            "threshold": 0.50,
            "status": "present",
        },
        _prior(
            retrieval_prior,
            label="Cardiomegaly",
            present=0.10,
            absent=0.85,
        ),
    )

    assert result.in_gray_zone is True
    assert result.vision_status == "present"
    assert result.fused_status == "uncertain"


def test_prior_fusion_demotes_gray_zone_present_prediction_to_absent() -> None:
    retrieval_prior, prior_fusion = _load_prior_fusion_modules()

    result = prior_fusion.fuse_label_with_prior(
        {
            "label": "Cardiomegaly",
            "probability": 0.53,
            "threshold": 0.50,
            "status": "present",
        },
        _prior(
            retrieval_prior,
            label="Cardiomegaly",
            present=0.05,
            absent=0.95,
        ),
    )

    assert result.in_gray_zone is True
    assert result.vision_status == "present"
    assert result.fused_status == "absent"


def test_exp11_policy_loads_only_selected_promotion_gates() -> None:
    _, prior_fusion = _load_prior_fusion_modules()
    policy_path = (
        Path(__file__).resolve().parents[2]
        / "experiments"
        / "exp11_prior_fusion_per_label_tuning"
        / "best_prior_fusion_policy.json"
    )

    policy = prior_fusion.load_prior_fusion_policy(policy_path)
    fracture = prior_fusion.prior_rule_for_label(
        "Fracture",
        overrides=policy.rule_overrides,
    )
    cardiomegaly = prior_fusion.prior_rule_for_label(
        "Cardiomegaly",
        overrides=policy.rule_overrides,
    )

    assert policy.policy_version == "retrieval_prior_per_label_gate_tuning_v2"
    assert policy.gray_zone_margin == 0.15
    assert fracture.promotion_enabled is True
    assert fracture.promotion_prior_threshold == 0.90
    assert fracture.promotion_confidence_threshold == 0.10
    assert fracture.demotion_enabled is False
    assert cardiomegaly.promotion_enabled is False
    assert cardiomegaly.demotion_enabled is False


def test_disabled_exp11_gate_cannot_change_prediction() -> None:
    retrieval_prior, prior_fusion = _load_prior_fusion_modules()
    policy_path = (
        Path(__file__).resolve().parents[2]
        / "experiments"
        / "exp11_prior_fusion_per_label_tuning"
        / "best_prior_fusion_policy.json"
    )
    policy = prior_fusion.load_prior_fusion_policy(policy_path)

    result = prior_fusion.fuse_label_with_prior(
        {
            "label": "Cardiomegaly",
            "probability": 0.48,
            "threshold": 0.50,
            "status": "absent",
        },
        _prior(
            retrieval_prior,
            label="Cardiomegaly",
            present=1.0,
            absent=0.0,
        ),
        rule=prior_fusion.prior_rule_for_label(
            "Cardiomegaly",
            overrides=policy.rule_overrides,
        ),
    )

    assert result.in_gray_zone is True
    assert result.fused_status == "absent"


def test_enabled_exp11_gate_uses_directional_confidence() -> None:
    retrieval_prior, prior_fusion = _load_prior_fusion_modules()
    policy_path = (
        Path(__file__).resolve().parents[2]
        / "experiments"
        / "exp11_prior_fusion_per_label_tuning"
        / "best_prior_fusion_policy.json"
    )
    policy = prior_fusion.load_prior_fusion_policy(policy_path)
    rule = prior_fusion.prior_rule_for_label(
        "Fracture",
        overrides=policy.rule_overrides,
    )
    prediction = {
        "label": "Fracture",
        "probability": 0.48,
        "threshold": 0.50,
        "status": "absent",
    }

    promoted = prior_fusion.fuse_label_with_prior(
        prediction,
        _prior(
            retrieval_prior,
            label="Fracture",
            present=0.90,
            absent=0.10,
            confidence=0.10,
        ),
        rule=rule,
    )
    kept = prior_fusion.fuse_label_with_prior(
        prediction,
        _prior(
            retrieval_prior,
            label="Fracture",
            present=0.90,
            absent=0.10,
            confidence=0.09,
        ),
        rule=rule,
    )

    assert promoted.fused_status == "present"
    assert kept.fused_status == "absent"
