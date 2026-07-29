"""Cohort-relative policy for per-view DICOM quality decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

QualityDecision = Literal["pass", "review_with_technical_warning", "fail"]

QUALITY_POLICY_VERSION = "dicom_quality_policy_v1"
WARNING_Z_THRESHOLD = 3.0
FAIL_Z_THRESHOLD = 6.0

TWO_SIDED_METRICS: tuple[str, ...] = ("intensity_mean",)
LOWER_TAIL_METRICS: tuple[str, ...] = (
    "intensity_std",
    "contrast_proxy",
    "entropy",
    "sharpness_proxy",
)
UPPER_TAIL_METRICS: tuple[str, ...] = ("noise_proxy",)
QUALITY_METRICS: tuple[str, ...] = (
    TWO_SIDED_METRICS + LOWER_TAIL_METRICS + UPPER_TAIL_METRICS
)


@dataclass(frozen=True)
class RobustReference:
    """Median and robust scale for one cohort metric."""

    center: float
    scale: float


def robust_reference(values: pd.Series) -> RobustReference | None:
    """Estimate cohort location/scale using MAD, then IQR/std fallbacks."""
    numeric = pd.to_numeric(values, errors="coerce").to_numpy(dtype=np.float64)
    finite = numeric[np.isfinite(numeric)]
    if finite.size == 0:
        return None

    center = float(np.median(finite))
    mad = float(np.median(np.abs(finite - center)))
    scale = 1.4826 * mad

    if scale <= 0.0:
        q25, q75 = np.percentile(finite, [25.0, 75.0])
        scale = float((q75 - q25) / 1.349)
    if scale <= 0.0:
        scale = float(np.std(finite))
    if scale <= 0.0:
        scale = 1.0
    return RobustReference(center=center, scale=scale)


def _evidence_z(
    values: pd.Series,
    reference: RobustReference | None,
    *,
    direction: Literal["two_sided", "lower", "upper"],
) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if reference is None:
        return pd.Series(np.nan, index=values.index, dtype=float)

    standardized = (numeric - reference.center) / reference.scale
    if direction == "two_sided":
        return standardized.abs()
    if direction == "lower":
        return (-standardized).clip(lower=0.0)
    return standardized.clip(lower=0.0)


def score_quality_metrics(
    metrics_df: pd.DataFrame,
    *,
    warning_z_threshold: float = WARNING_Z_THRESHOLD,
    fail_z_threshold: float = FAIL_Z_THRESHOLD,
) -> pd.DataFrame:
    """Add cohort-relative evidence z-scores and per-view decisions."""
    if warning_z_threshold <= 0:
        raise ValueError("warning_z_threshold must be > 0")
    if fail_z_threshold <= warning_z_threshold:
        raise ValueError("fail_z_threshold must exceed warning_z_threshold")

    missing = [metric for metric in QUALITY_METRICS if metric not in metrics_df]
    if missing:
        raise ValueError(f"metrics_df missing quality metrics: {missing}")

    out = metrics_df.copy()
    for metric in TWO_SIDED_METRICS:
        out[f"{metric}_evidence_z"] = _evidence_z(
            out[metric], robust_reference(out[metric]), direction="two_sided"
        )
    for metric in LOWER_TAIL_METRICS:
        out[f"{metric}_evidence_z"] = _evidence_z(
            out[metric], robust_reference(out[metric]), direction="lower"
        )
    for metric in UPPER_TAIL_METRICS:
        out[f"{metric}_evidence_z"] = _evidence_z(
            out[metric], robust_reference(out[metric]), direction="upper"
        )

    evidence_columns = [f"{metric}_evidence_z" for metric in QUALITY_METRICS]
    out["max_quality_evidence_z"] = out[evidence_columns].max(axis=1)

    decisions: list[str] = []
    reasons: list[str] = []
    for _, row in out.iterrows():
        decision, reason = _decide_view(
            row,
            evidence_columns=evidence_columns,
            warning_z_threshold=warning_z_threshold,
            fail_z_threshold=fail_z_threshold,
        )
        decisions.append(decision)
        reasons.append(reason)

    out["quality_decision"] = decisions
    out["quality_reason"] = reasons
    out["quality_policy_version"] = QUALITY_POLICY_VERSION
    return out


def _decide_view(
    row: pd.Series,
    *,
    evidence_columns: list[str],
    warning_z_threshold: float,
    fail_z_threshold: float,
) -> tuple[QualityDecision, str]:
    if not bool(row.get("readable", False)):
        detail = str(row.get("quality_error", "")).strip()
        return "fail", f"unreadable_dicom{': ' + detail if detail else ''}"
    if not bool(row.get("finite_pixels", False)):
        return "fail", "non_finite_or_empty_pixels"

    missing_metrics = [
        metric for metric in QUALITY_METRICS if pd.isna(row.get(metric))
    ]
    if missing_metrics:
        return "fail", f"missing_quality_metrics: {','.join(missing_metrics)}"

    failed = [
        column.removesuffix("_evidence_z")
        for column in evidence_columns
        if float(row[column]) >= fail_z_threshold
    ]
    if failed:
        return "fail", f"extreme_quality_outlier: {','.join(failed)}"

    warned = [
        column.removesuffix("_evidence_z")
        for column in evidence_columns
        if float(row[column]) >= warning_z_threshold
    ]
    if warned:
        return (
            "review_with_technical_warning",
            f"quality_outlier: {','.join(warned)}",
        )

    return "pass", "within_cohort_quality_range"
