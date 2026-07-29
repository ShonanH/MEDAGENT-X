"""Contract tests for the offline DICOM quality stage."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from medagentx.quality.cohort import apply_view_quality_filter
from medagentx.quality.metrics import (
    ViewQualityMetrics,
    compute_pixel_quality_metrics,
)
from medagentx.quality.pipeline import build_view_quality_metrics
from medagentx.quality.policy import QUALITY_METRICS, score_quality_metrics


def test_pixel_metrics_are_finite_for_valid_image() -> None:
    pixels = np.tile(np.linspace(0.0, 4095.0, 64), (64, 1))
    metrics = compute_pixel_quality_metrics(pixels)

    assert metrics.readable is True
    assert metrics.finite_pixels is True
    assert metrics.rows == 64
    assert metrics.columns == 64
    for metric in QUALITY_METRICS:
        assert np.isfinite(getattr(metrics, metric))


def test_structural_failure_always_fails() -> None:
    frame = pd.DataFrame(
        [
            {
                "readable": False,
                "finite_pixels": False,
                "quality_error": "cannot decode",
                **{metric: None for metric in QUALITY_METRICS},
            }
        ]
    )

    scored = score_quality_metrics(frame)

    assert scored.iloc[0]["quality_decision"] == "fail"
    assert "unreadable_dicom" in scored.iloc[0]["quality_reason"]


def test_extreme_cohort_outlier_fails_at_six_robust_deviations() -> None:
    rows = []
    for value in np.linspace(0.9, 1.1, 100):
        rows.append(
            {
                "readable": True,
                "finite_pixels": True,
                "quality_error": "",
                "intensity_mean": 0.5,
                "intensity_std": value,
                "contrast_proxy": value,
                "entropy": value,
                "sharpness_proxy": value,
                "noise_proxy": 0.1,
            }
        )
    rows.append(
        {
            "readable": True,
            "finite_pixels": True,
            "quality_error": "",
            "intensity_mean": 0.5,
            "intensity_std": 0.0,
            "contrast_proxy": 0.0,
            "entropy": 0.0,
            "sharpness_proxy": 0.0,
            "noise_proxy": 10.0,
        }
    )

    scored = score_quality_metrics(pd.DataFrame(rows))

    assert scored.iloc[-1]["quality_decision"] == "fail"
    assert scored.iloc[-1]["max_quality_evidence_z"] >= 6.0


def test_failed_view_does_not_drop_study_when_another_view_is_usable() -> None:
    eligible = pd.DataFrame(
        [
            {
                "study_key": "patient1/study1",
                "deid_patient_id": "patient1",
                "dicom_path": "patient1/study1/frontal.dcm",
            },
            {
                "study_key": "patient1/study1",
                "deid_patient_id": "patient1",
                "dicom_path": "patient1/study1/lateral.dcm",
            },
            {
                "study_key": "patient2/study1",
                "deid_patient_id": "patient2",
                "dicom_path": "patient2/study1/frontal.dcm",
            },
        ]
    )
    decisions = pd.DataFrame(
        [
            {
                **eligible.iloc[0].to_dict(),
                "quality_decision": "pass",
                "quality_reason": "ok",
                "quality_policy_version": "test",
            },
            {
                **eligible.iloc[1].to_dict(),
                "quality_decision": "fail",
                "quality_reason": "bad",
                "quality_policy_version": "test",
            },
            {
                **eligible.iloc[2].to_dict(),
                "quality_decision": "fail",
                "quality_reason": "bad",
                "quality_policy_version": "test",
            },
        ]
    )

    kept, failed, studies = apply_view_quality_filter(eligible, decisions)

    assert kept["dicom_path"].tolist() == ["patient1/study1/frontal.dcm"]
    assert len(failed) == 2
    patient1 = studies[studies["study_key"] == "patient1/study1"].iloc[0]
    patient2 = studies[studies["study_key"] == "patient2/study1"].iloc[0]
    assert patient1["study_quality_status"] == "kept_with_failed_views"
    assert bool(patient1["all_views_failed"]) is False
    assert bool(patient2["all_views_failed"]) is True


def test_metric_reader_is_injectable_without_real_dicoms() -> None:
    eligible = pd.DataFrame(
        [
            {
                "study_key": "patient1/study1",
                "deid_patient_id": "patient1",
                "dicom_path": "patient1/study1/frontal.dcm",
            }
        ]
    )

    def reader(_: str | Path) -> ViewQualityMetrics:
        return compute_pixel_quality_metrics(np.arange(64).reshape(8, 8))

    metrics = build_view_quality_metrics(
        eligible,
        dicom_root="/tmp/dicoms",
        metric_reader=reader,
    )

    assert len(metrics) == 1
    assert metrics.iloc[0]["readable"]
