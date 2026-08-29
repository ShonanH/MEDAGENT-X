"""Orchestrate DICOM metric extraction, scoring, and cohort filtering."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Callable

import pandas as pd

from medagentx.data.dicoms import local_dicom_path
from medagentx.quality.cohort import (
    apply_view_quality_filter,
    write_quality_artifacts,
)
from medagentx.quality.metrics import (
    ViewQualityMetrics,
    read_dicom_quality_metrics,
)
from medagentx.quality.policy import score_quality_metrics

MetricReader = Callable[[str | Path], ViewQualityMetrics]

_REQUIRED_COLUMNS = ("study_key", "deid_patient_id", "dicom_path")


def build_view_quality_metrics(
    eligible_rows: pd.DataFrame,
    *,
    dicom_root: str | Path,
    metric_reader: MetricReader = read_dicom_quality_metrics,
) -> pd.DataFrame:
    """Compute technical metrics for every eligible DICOM view."""
    missing = [
        column for column in _REQUIRED_COLUMNS if column not in eligible_rows.columns
    ]
    if missing:
        raise ValueError(
            f"eligible_rows missing required columns {missing}. "
            f"Available: {list(eligible_rows.columns)}"
        )
    if eligible_rows.empty:
        raise ValueError("eligible_rows must be non-empty")

    output_rows: list[dict[str, object]] = []
    total = len(eligible_rows)
    progress_interval = max(1, min(100, total // 10))

    for position, (_, row) in enumerate(eligible_rows.iterrows(), start=1):
        dicom_path = str(row["dicom_path"]).strip()
        path = local_dicom_path(dicom_root, dicom_path)
        metrics = metric_reader(path)
        metric_values = asdict(metrics)
        metric_values["quality_error"] = metric_values.pop("error")
        output_rows.append(
            {
                "study_key": str(row["study_key"]).strip(),
                "deid_patient_id": str(row["deid_patient_id"]).strip(),
                "dicom_path": dicom_path,
                "local_dicom_path": str(path),
                **metric_values,
            }
        )

        if position % progress_interval == 0 or position == total:
            print(f"[Quality] measured {position}/{total} views")

    return pd.DataFrame(output_rows)


def run_quality_pipeline(
    eligible_rows: pd.DataFrame,
    *,
    dicom_root: str | Path,
    output_root: str | Path,
    metric_reader: MetricReader = read_dicom_quality_metrics,
) -> tuple[pd.DataFrame, dict[str, Path]]:
    """Run the complete locked quality stage and persist its artifacts."""
    metrics = build_view_quality_metrics(
        eligible_rows,
        dicom_root=dicom_root,
        metric_reader=metric_reader,
    )
    decisions = score_quality_metrics(metrics)
    quality_eligible, failed_views, study_summary = apply_view_quality_filter(
        eligible_rows,
        decisions,
    )
    paths = write_quality_artifacts(
        output_root,
        decisions=decisions,
        quality_eligible_rows=quality_eligible,
        failed_views=failed_views,
        study_summary=study_summary,
    )
    return quality_eligible, paths
