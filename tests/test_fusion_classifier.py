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