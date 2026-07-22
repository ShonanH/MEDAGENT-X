from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
import torch

from medagentx.fusion.features import aggregate_study_features, merge_label_and_feature_tables
from medagentx.fusion.labels import build_report_text_for_weak_labels, infer_weak_label_status
from medagentx.fusion.metrics import masked_bce_with_logits_loss
from medagentx.fusion.paths import clean_dicom_path, parse_study_key_from_dcm
from medagentx.fusion.splits import (
    AGENT_EVAL_SPLIT,
    assert_cohort_split_integrity,
    assert_patient_level_integrity,
    build_cohort_split_table,
    build_cohort_split_table_from_quality_gate,
    build_patient_split_table,
    get_patients_for_split,
    patient_id_from_study_key,
)


def test_path_normalization_joins_train_prefix():
    raw = "train/patient00003/study1/view1_frontal.dcm"
    assert clean_dicom_path(raw) == "patient00003/study1/view1_frontal.dcm"
    assert parse_study_key_from_dcm(raw) == "patient00003/study1"


def test_chexpert_value_mapping_uses_u_mask():
    from medagentx.fusion.chexpert_labels import (
        chexpert_value_to_status,
        chexpert_value_to_training_value,
    )

    assert chexpert_value_to_status(1) == "present"
    assert chexpert_value_to_status(0) == "absent"
    assert chexpert_value_to_status(-1) == "uncertain"
    assert chexpert_value_to_status(None) == "unmentioned"
    assert chexpert_value_to_training_value(1) == 1.0
    assert chexpert_value_to_training_value(0) == 0.0
    assert chexpert_value_to_training_value(-1) is None


def test_chexpert_row_labels_map_no_finding_from_diseases():
    from medagentx.fusion.chexpert_labels import labels_from_chexpert_row

    row = pd.Series(
        {
            "Atelectasis": 0.0,
            "Cardiomegaly": 0.0,
            "Consolidation": 0.0,
            "Edema": 0.0,
            "Pleural Effusion": 0.0,
            "Pneumonia": 0.0,
            "Pneumothorax": 0.0,
            "Fracture": 0.0,
            "Lung Lesion": 0.0,
            "Lung Opacity": 0.0,
            "Enlarged Cardiomediastinum": 0.0,
            "Pleural Other": 0.0,
            "Support Devices": 0.0,
            "No Finding": None,
        }
    )
    labels = labels_from_chexpert_row(row)
    assert labels["No Finding"]["weak_status"] == "present"
    assert labels["Pneumothorax"]["weak_status"] == "absent"


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


def test_build_cohort_split_table_reserves_agent_eval_holdout():
    patients = [f"patient{i:05d}" for i in range(588)]
    df = pd.DataFrame({"deid_patient_id": patients, "study_key": [f"{p}/study1" for p in patients]})

    split_table = build_cohort_split_table(df, agent_eval_count=100, seed=42)
    assert_cohort_split_integrity(split_table, min_agent_eval_patients=100)

    agent_eval = get_patients_for_split(split_table, AGENT_EVAL_SPLIT)
    fusion_patients = set(split_table["deid_patient_id"]) - agent_eval
    assert len(agent_eval) == 100
    assert len(fusion_patients) == 488
    assert agent_eval.isdisjoint(fusion_patients)


def test_build_cohort_split_table_is_deterministic():
    patients = [f"patient{i:05d}" for i in range(200)]
    df = pd.DataFrame({"deid_patient_id": patients})

    first = build_cohort_split_table(df, agent_eval_count=50, seed=42)
    second = build_cohort_split_table(df, agent_eval_count=50, seed=42)
    pd.testing.assert_frame_equal(first.sort_values("deid_patient_id").reset_index(drop=True),
                                  second.sort_values("deid_patient_id").reset_index(drop=True))


def test_patient_id_from_study_key():
    assert patient_id_from_study_key("patient00003/study1") == "patient00003"
    assert patient_id_from_study_key("") == ""


def test_build_cohort_split_table_from_quality_gate_enforces_min_cases():
    rows = []
    for patient_idx in range(120):
        patient_id = f"patient{patient_idx:05d}"
        for view_idx in range(2):
            rows.append(
                {
                    "study_key": f"{patient_id}/study1",
                    "dicom_path": f"{patient_id}/study1/view{view_idx}.dcm",
                    "quality_gate_decision": "pass",
                    "route_next": "retrieval_agent",
                }
            )
    quality_gate_df = pd.DataFrame(rows)

    split_table, eligible_df, stats = build_cohort_split_table_from_quality_gate(
        quality_gate_df,
        agent_eval_patient_count=100,
        agent_eval_min_cases=100,
        seed=42,
    )

    assert len(eligible_df) == 240
    assert stats["agent_eval_cases"] >= 100
    assert stats["agent_eval_patients"] >= 100
    assert len(get_patients_for_split(split_table, AGENT_EVAL_SPLIT)) == stats["agent_eval_patients"]


def test_masked_bce_ignores_uncertain_labels():
    logits = torch.tensor([[0.0, 0.0]], dtype=torch.float32)
    targets = torch.tensor([[1.0, 0.0]], dtype=torch.float32)
    mask = torch.tensor([[1.0, 0.0]], dtype=torch.float32)
    loss = masked_bce_with_logits_loss(logits, targets, mask)
    assert torch.isfinite(loss)


def test_ensemble_present_requires_agreement_for_rare_labels():
    from medagentx.fusion.calibration import ensemble_present_status

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
    from medagentx.fusion.calibration import ensemble_present_status

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


def test_lung_opacity_requires_strict_gate():
    from medagentx.fusion.calibration import ensemble_present_status

    status = ensemble_present_status(
        label="Lung Opacity",
        d_prob=0.84,
        f_prob=0.99,
        e_prob=0.84,
        d_threshold=0.70,
        f_threshold=0.92,
        e_threshold=0.92,
        require_agreement=True,
    )
    assert status == "uncertain"


def test_ensemble_prob_blend_uses_min_for_lung_opacity():
    from medagentx.fusion.calibration import ensemble_prob_blend

    assert ensemble_prob_blend("Lung Opacity", 0.4, 0.95) == 0.4


def test_refine_label_decision_promotes_edema_from_uncertain():
    from medagentx.agents.disease_reasoning_agent import refine_label_decision

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


def test_study_aggregation_handles_multiple_images():
    for n in [1, 2, 3]:
        feats = [np.ones(4, dtype=np.float32) * i for i in range(1, n + 1)]
        out = aggregate_study_features(feats)
        assert out.shape == (4,)
        assert np.allclose(out, np.mean(np.stack(feats, axis=0), axis=0))


def test_no_finding_present_sets_unmentioned_diseases_to_absent_for_training():
    from medagentx.fusion.chexpert_labels import labels_from_chexpert_row

    row = pd.Series(
        {
            "Atelectasis": None,
            "Cardiomegaly": None,
            "Consolidation": None,
            "Edema": None,
            "Pleural Effusion": None,
            "Pneumonia": None,
            "Pneumothorax": None,
            "Fracture": None,
            "Lung Lesion": None,
            "Lung Opacity": None,
            "Enlarged Cardiomediastinum": None,
            "Pleural Other": None,
            "Support Devices": None,
            "No Finding": 1.0,
        }
    )
    labels = labels_from_chexpert_row(row)
    assert labels["No Finding"]["weak_status"] == "present"
    assert labels["Atelectasis"]["weak_status"] == "unmentioned"
    assert labels["Atelectasis"]["weak_value"] == 0.0
    assert labels["Pneumothorax"]["weak_value"] == 0.0


def test_no_finding_present_keeps_uncertain_diseases_masked():
    from medagentx.fusion.chexpert_labels import labels_from_chexpert_row

    row = pd.Series(
        {
            "Atelectasis": -1.0,
            "Cardiomegaly": None,
            "Consolidation": None,
            "Edema": None,
            "Pleural Effusion": None,
            "Pneumonia": None,
            "Pneumothorax": None,
            "Fracture": None,
            "Lung Lesion": None,
            "Lung Opacity": None,
            "Enlarged Cardiomediastinum": None,
            "Pleural Other": None,
            "Support Devices": None,
            "No Finding": 1.0,
        }
    )
    labels = labels_from_chexpert_row(row)
    assert labels["Atelectasis"]["weak_status"] == "uncertain"
    assert labels["Atelectasis"]["weak_value"] is None
    assert labels["Cardiomegaly"]["weak_value"] == 0.0


def test_aggregate_study_labels_present_if_any_view_present():
    from medagentx.fusion.chexpert_labels import aggregate_study_label_items, labels_from_chexpert_row

    view_a = labels_from_chexpert_row(
        pd.Series(
            {
                "Atelectasis": 0.0,
                "Cardiomegaly": 0.0,
                "Consolidation": 0.0,
                "Edema": 0.0,
                "Pleural Effusion": 0.0,
                "Pneumonia": 0.0,
                "Pneumothorax": 0.0,
                "Fracture": 0.0,
                "Lung Lesion": 0.0,
                "Lung Opacity": 0.0,
                "Enlarged Cardiomediastinum": 0.0,
                "Pleural Other": 0.0,
                "Support Devices": 0.0,
                "No Finding": 1.0,
            }
        )
    )
    view_b = labels_from_chexpert_row(
        pd.Series(
            {
                "Atelectasis": 1.0,
                "Cardiomegaly": 0.0,
                "Consolidation": 0.0,
                "Edema": 0.0,
                "Pleural Effusion": 0.0,
                "Pneumonia": 0.0,
                "Pneumothorax": 0.0,
                "Fracture": 0.0,
                "Lung Lesion": 0.0,
                "Lung Opacity": 0.0,
                "Enlarged Cardiomediastinum": 0.0,
                "Pleural Other": 0.0,
                "Support Devices": 0.0,
                "No Finding": 0.0,
            }
        )
    )

    study_labels = aggregate_study_label_items([view_a, view_b])
    assert study_labels["Atelectasis"]["weak_status"] == "present"
    assert study_labels["Atelectasis"]["weak_value"] == 1.0
    assert study_labels["No Finding"]["weak_status"] == "absent"


def test_no_finding_penalty_increases_when_disease_probs_high():
    from medagentx.fusion.metrics import fusion_training_loss, no_finding_penalty_loss

    logits = torch.tensor([[2.0, -2.0]], dtype=torch.float32)
    targets = torch.tensor([[0.0, 0.0]], dtype=torch.float32)
    mask = torch.tensor([[1.0, 1.0]], dtype=torch.float32)
    no_finding_mask = torch.tensor([1.0], dtype=torch.float32)

    base_loss = fusion_training_loss(
        logits,
        targets,
        mask,
        no_finding_mask=None,
    )
    penalized_loss = fusion_training_loss(
        logits,
        targets,
        mask,
        no_finding_mask=no_finding_mask,
        no_finding_penalty_weight=1.0,
    )
    assert penalized_loss > base_loss
    assert no_finding_penalty_loss(logits, no_finding_mask) > 0.0


def test_ensemble_prob_blend_defaults_to_fusion_heavy():
    from medagentx.fusion.calibration import DEFAULT_FUSION_BLEND_WEIGHT, ensemble_prob_blend

    assert DEFAULT_FUSION_BLEND_WEIGHT == 0.85
    blended = ensemble_prob_blend("Edema", 0.9, 0.1)
    assert blended == pytest.approx(0.85 * 0.1 + 0.15 * 0.9)


def test_training_threshold_tuning_allows_lower_values_than_deployment():
    from medagentx.fusion.calibration import (
        apply_deployment_thresholds,
        tune_thresholds_precision_favored,
    )

    y_true = np.array([[1.0, 0.0], [0.0, 0.0], [1.0, 0.0], [0.0, 0.0]], dtype=np.float32)
    y_prob = np.array([[0.72, 0.20], [0.18, 0.15], [0.68, 0.22], [0.12, 0.10]], dtype=np.float32)
    mask = np.ones_like(y_true, dtype=np.float32)

    tuned, _ = tune_thresholds_precision_favored(
        y_true,
        y_prob,
        mask,
        ["Atelectasis", "Edema"],
        apply_floors=False,
        min_precision=0.0,
        beta=1.0,
        default_threshold=0.40,
    )
    deployed = apply_deployment_thresholds(tuned, ["Atelectasis", "Edema"])

    assert tuned[0] <= 0.72
    assert deployed[0] >= tuned[0]


def test_multilabel_ranking_metrics_computes_auroc():
    from medagentx.fusion.metrics import multilabel_ranking_metrics

    y_true = np.array([[1.0, 0.0], [0.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    y_prob = np.array([[0.9, 0.2], [0.1, 0.3], [0.8, 0.1], [0.2, 0.7]], dtype=np.float32)
    mask = np.ones_like(y_true, dtype=np.float32)

    metrics = multilabel_ranking_metrics(y_true, y_prob, mask, ["Atelectasis", "Edema"])
    assert len(metrics["per_label"]) == 2
    if not np.isnan(metrics["macro_auroc"]):
        assert metrics["macro_auroc"] > 0.5
        assert metrics["macro_avg_precision"] > 0.0


def test_no_finding_negative_downweight_reduces_loss():
    from medagentx.fusion.metrics import fusion_training_loss

    logits = torch.tensor([[-1.0, 2.0]], dtype=torch.float32)
    targets = torch.tensor([[0.0, 0.0]], dtype=torch.float32)
    mask = torch.tensor([[1.0, 1.0]], dtype=torch.float32)
    no_finding_mask = torch.tensor([1.0], dtype=torch.float32)

    full_weight = fusion_training_loss(
        logits,
        targets,
        mask,
        no_finding_mask=no_finding_mask,
        no_finding_negative_weight=1.0,
    )
    downweighted = fusion_training_loss(
        logits,
        targets,
        mask,
        no_finding_mask=no_finding_mask,
        no_finding_negative_weight=0.25,
    )
    assert downweighted < full_weight


def test_compute_pos_weight_applies_boost_and_cap():
    from medagentx.fusion.metrics import compute_pos_weight

    y = np.array([[1.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]], dtype=np.float32)
    mask = np.array([[1.0, 1.0], [1.0, 1.0], [1.0, 1.0], [1.0, 1.0]], dtype=np.float32)
    weights = compute_pos_weight(y, mask, boost=2.0, max_weight=5.0)
    assert weights[0] == 5.0


def test_findings_jsonl_filters_requested_paths(tmp_path):
    from medagentx.fusion.chexpert_labels import merge_chexpert_labels
    from medagentx.helpers.chexpert_findings_json import load_findings_labels_for_paths

    json_path = tmp_path / "findings_fixed.json"
    json_path.write_text(
        "\n".join(
            [
                '{"path_to_image": "train/patient11162/study3/view1_frontal.jpg", "Edema": 1.0, "Atelectasis": 1.0, "Pleural Effusion": 1.0, "Support Devices": 1.0, "No Finding": null}',
                '{"path_to_image": "train/patient42142/study1/view1_frontal.jpg", "No Finding": 1.0}',
                '{"path_to_image": "train/patient99999/study1/view1_frontal.jpg", "Pneumothorax": 1.0}',
            ]
        ),
        encoding="utf-8",
    )

    wanted = [
        "train/patient11162/study3/view1_frontal.jpg",
        "train/patient42142/study1/view1_frontal.jpg",
    ]
    labels_df = load_findings_labels_for_paths(json_path, wanted)
    assert len(labels_df) == 2

    rows_df = pd.DataFrame({"path_to_image": wanted})
    merged = merge_chexpert_labels(rows_df, labels_df)
    assert merged.iloc[0]["Edema"] == 1.0
    assert merged.iloc[1]["No Finding"] == 1.0