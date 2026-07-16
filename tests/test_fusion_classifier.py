from __future__ import annotations

import json

import numpy as np
import pandas as pd
import torch

from src.medagentx.fusion.features import aggregate_study_features, merge_label_and_feature_tables
from src.medagentx.fusion.labels import build_report_text_for_weak_labels, infer_weak_label_status
from src.medagentx.fusion.metrics import masked_bce_with_logits_loss
from src.medagentx.fusion.paths import clean_dicom_path, parse_study_key_from_dcm
from src.medagentx.fusion.splits import assert_patient_level_integrity, build_patient_split_table


def test_path_normalization_joins_train_prefix():
    raw = "train/patient00003/study1/view1_frontal.dcm"
    assert clean_dicom_path(raw) == "patient00003/study1/view1_frontal.dcm"
    assert parse_study_key_from_dcm(raw) == "patient00003/study1"


def test_report_label_generation_handles_missing_findings():
    row = pd.Series(
        {
            "section_findings": "",
            "section_impression": "No pneumothorax.",
            "section_summary": "",
            "report": "Full report fallback.",
        }
    )
    text, source = build_report_text_for_weak_labels(row)
    assert "No pneumothorax" in text
    assert source == "section_findings_plus_impression_plus_summary"
    assert infer_weak_label_status(text, "Pneumothorax") == "absent"


def test_patient_level_split_integrity():
    df = pd.DataFrame(
        {
            "deid_patient_id": ["p1", "p1", "p2", "p3"],
            "study_key": ["p1/s1", "p1/s2", "p2/s1", "p3/s1"],
        }
    )
    split_table = build_patient_split_table(df)
    merged = df.merge(split_table, on="deid_patient_id", how="left")
    assert_patient_level_integrity(merged)


def test_masked_bce_ignores_uncertain_labels():
    logits = torch.tensor([[0.0, 0.0]], dtype=torch.float32)
    targets = torch.tensor([[1.0, 0.0]], dtype=torch.float32)
    mask = torch.tensor([[1.0, 0.0]], dtype=torch.float32)
    loss = masked_bce_with_logits_loss(logits, targets, mask)
    assert torch.isfinite(loss)


def test_ensemble_present_requires_agreement_for_rare_labels():
    from src.medagentx.fusion.calibration import ensemble_present_status

    status = ensemble_present_status(
        label="Lung Lesion",
        d_prob=0.80,
        f_prob=0.30,
        e_prob=0.55,
        d_threshold=0.75,
        f_threshold=0.80,
        e_threshold=0.80,
        require_agreement=True,
    )
    assert status == "uncertain"


def test_recall_lenient_label_allows_weak_present():
    from src.medagentx.fusion.calibration import ensemble_present_status

    status = ensemble_present_status(
        label="Edema",
        d_prob=0.62,
        f_prob=0.99,
        e_prob=0.805,
        d_threshold=0.60,
        f_threshold=0.60,
        e_threshold=0.60,
        require_agreement=True,
    )
    assert status == "present"


def test_conflict_blend_shrinks_fusion_inflation():
    from src.medagentx.fusion.calibration import ensemble_prob_blend

    assert ensemble_prob_blend("Edema", 0.20, 0.99) == 0.20


def test_atelectasis_requires_strong_present_and_densenet_floor():
    from src.medagentx.fusion.calibration import ensemble_present_status

    weak_present = ensemble_present_status(
        label="Atelectasis",
        d_prob=0.70,
        f_prob=0.30,
        e_prob=0.55,
        d_threshold=0.65,
        f_threshold=0.80,
        e_threshold=0.65,
        require_agreement=True,
    )
    assert weak_present == "uncertain"

    strong_present = ensemble_present_status(
        label="Atelectasis",
        d_prob=0.72,
        f_prob=0.74,
        e_prob=0.73,
        d_threshold=0.65,
        f_threshold=0.70,
        e_threshold=0.65,
        require_agreement=True,
    )
    assert strong_present == "present"


def test_pneumonia_is_not_recall_lenient():
    from src.medagentx.fusion.calibration import RECALL_LENIENT_LABELS, ensemble_present_status

    assert "Pneumonia" not in RECALL_LENIENT_LABELS
    status = ensemble_present_status(
        label="Pneumonia",
        d_prob=0.80,
        f_prob=0.30,
        e_prob=0.55,
        d_threshold=0.75,
        f_threshold=0.75,
        e_threshold=0.75,
        require_agreement=True,
    )
    assert status == "uncertain"


def test_lung_opacity_allows_weak_present_with_relaxed_gate():
    from src.medagentx.fusion.calibration import ensemble_present_status

    status = ensemble_present_status(
        label="Lung Opacity",
        d_prob=0.86,
        f_prob=0.90,
        e_prob=0.86,
        d_threshold=0.70,
        f_threshold=0.88,
        e_threshold=0.88,
        require_agreement=True,
    )
    assert status == "present"


def test_ensemble_prob_blend_uses_min_for_lung_opacity():
    from src.medagentx.fusion.calibration import ensemble_prob_blend

    assert ensemble_prob_blend("Lung Opacity", 0.4, 0.95) == 0.4


def test_refine_label_decision_promotes_edema_from_uncertain():
    from src.medagentx.agents.disease_reasoning_agent import refine_label_decision

    status, reason = refine_label_decision(
        label="Edema",
        status="uncertain",
        classifier_item={
            "probability": 0.58,
            "ensemble_agreement": "weak_present",
            "threshold": 0.60,
            "densenet_probability": 0.58,
            "fusion_probability": 0.99,
        },
        retrieval_counts={"positive_count": 2, "negative_count": 0},
    )
    assert status == "present"
    assert reason is not None


def test_refine_label_decision_does_not_promote_pneumonia():
    from src.medagentx.agents.disease_reasoning_agent import refine_label_decision

    status, reason = refine_label_decision(
        label="Pneumonia",
        status="uncertain",
        classifier_item={
            "probability": 0.62,
            "ensemble_agreement": "weak_present",
            "threshold": 0.75,
            "densenet_probability": 0.62,
            "fusion_probability": 0.99,
        },
        retrieval_counts={"positive_count": 2, "negative_count": 0},
    )
    assert status == "uncertain"
    assert reason is None


def test_merge_label_and_feature_tables_keeps_deid_patient_id():
    label_df = pd.DataFrame(
        {
            "study_key": ["patient00003/study1"],
            "dicom_path": ["patient00003/study1/view1_frontal.dcm"],
            "deid_patient_id": ["patient00003"],
            "weak_value_atelectasis": [1.0],
        }
    )
    feature_df = pd.DataFrame(
        {
            "study_key": ["patient00003/study1"],
            "dicom_path": ["patient00003/study1/view1_frontal.dcm"],
            "deid_patient_id": ["patient00003"],
            "convnext_feature_path": ["/tmp/conv.npz"],
            "raddino_feature_path": ["/tmp/rad.npz"],
            "convnext_status": ["ok"],
            "raddino_status": ["success"],
            "feature_ready": [True],
        }
    )

    merged = merge_label_and_feature_tables(label_df, feature_df)
    assert "deid_patient_id" in merged.columns
    assert "deid_patient_id_x" not in merged.columns
    assert merged.iloc[0]["deid_patient_id"] == "patient00003"


def test_judge_label_training_value_marks_unmentioned_absent():
    from src.medagentx.fusion.labels import judge_label_to_training_value, training_value_from_status

    assert judge_label_to_training_value("present") == 1.0
    assert judge_label_to_training_value("absent") == 0.0
    assert judge_label_to_training_value("uncertain") is None
    assert training_value_from_status("absent", "judge") == 0.0


def test_fusion_mlp_supports_densenet_stacking():
    from src.medagentx.fusion.model import FusionMLP

    model = FusionMLP(input_dim=128, num_labels=12, densenet_dim=12, per_label_heads=True)
    x = torch.randn(4, 128)
    d = torch.rand(4, 12)
    logits = model(x, densenet_probs=d)
    assert logits.shape == (4, 12)


def test_study_aggregation_handles_multiple_images():
    for n in [1, 2, 3]:
        feats = [np.ones(4, dtype=np.float32) * i for i in range(1, n + 1)]
        out = aggregate_study_features(feats)
        assert out.shape == (4,)
        assert np.allclose(out, np.mean(np.stack(feats, axis=0), axis=0))


def test_attention_aggregate_prefers_nonzero_views():
    from src.medagentx.fusion.features import attention_aggregate_study_features

    out = attention_aggregate_study_features(
        [np.array([1.0, 0.0], dtype=np.float32), np.array([3.0, 0.0], dtype=np.float32)]
    )
    assert out[0] > 1.0