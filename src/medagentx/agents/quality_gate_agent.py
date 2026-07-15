from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph


QualityDecision = Literal["pass", "review_with_technical_warning", "fail"]
RouteNext = Literal["retrieval_agent", "stop_unreliable"]


class QualityGateState(TypedDict):
    input_csv: str
    output_csv: str
    decisions: list[dict[str, Any]]


@dataclass(frozen=True)
class QualityGateConfig:
    input_csv: Path = Path("outputs/chexpert_plus/quality_evidence_manifest.csv")
    output_csv: Path = Path("outputs/chexpert_plus/quality_gate_decisions.csv")

    warning_z_threshold: float = 2.0
    critical_z_threshold: float = 3.0
    severe_z_threshold: float = 6.0
    fail_critical_threshold: int = 3

    dicom_path_column: str = "dicom_path"
    study_key_column: str = "study_key"


PRIMARY_Z_METRICS: dict[str, str] = {
    "low_contrast_evidence_z": "low contrast evidence",
    "low_sharpness_evidence_z": "low sharpness evidence",
    "low_entropy_evidence_z": "low entropy evidence",
    "high_blur_evidence_z": "high blur evidence",
    "high_noise_evidence_z": "high noise evidence",
    "convnext_embedding_outlier_z": "ConvNeXt embedding outlier evidence",
    "raddino_embedding_outlier_z": "RAD-DINO embedding outlier evidence",
    "raddino_patch_variability_outlier_z": "RAD-DINO patch variability outlier evidence",
    "validation_edge_density_outlier_z": "edge density outlier evidence",
    "validation_intensity_mean_outlier_z": "intensity mean outlier evidence",
    "validation_intensity_std_outlier_z": "intensity standard deviation outlier evidence",
    "validation_contrast_proxy_outlier_z": "contrast proxy outlier evidence",
    "validation_noise_proxy_outlier_z": "noise proxy outlier evidence",
    "validation_entropy_outlier_z": "entropy outlier evidence",
}


HARD_CRITICAL_BOOLEAN_CHECKS: dict[str, str] = {
    "evidence_complete": "evidence incomplete",
    "convnext_vector_valid": "ConvNeXt vector invalid",
    "raddino_vector_valid": "RAD-DINO vector invalid",
}


HARD_CRITICAL_COUNT_CHECKS: dict[str, str] = {
    "convnext_embedding_nan_count": "ConvNeXt embedding contains NaN values",
    "convnext_embedding_inf_count": "ConvNeXt embedding contains infinite values",
    "raddino_embedding_nan_count": "RAD-DINO embedding contains NaN values",
    "raddino_embedding_inf_count": "RAD-DINO embedding contains infinite values",
}


def _is_missing(value: Any) -> bool:
    return pd.isna(value)


def _as_float(value: Any) -> float | None:
    if _is_missing(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_normalized_text(value: Any) -> str:
    if _is_missing(value):
        return ""
    return str(value).strip().lower()


def _is_false_like(value: Any) -> bool:
    if _is_missing(value):
        return True

    if isinstance(value, bool):
        return not value

    normalized = _as_normalized_text(value)
    return normalized in {"false", "0", "no", "n", "invalid", "failed", "fail"}


def _is_positive_count(value: Any) -> bool:
    numeric_value = _as_float(value)
    if numeric_value is None:
        return False
    return numeric_value > 0


def _collect_numeric_quality_flags(
    row: pd.Series,
    config: QualityGateConfig,
) -> tuple[list[str], list[str], list[str]]:
    critical_metrics: list[str] = []
    warning_metrics: list[str] = []
    severe_metrics: list[str] = []

    for column_name, metric_label in PRIMARY_Z_METRICS.items():
        if column_name not in row.index:
            continue

        z_value = _as_float(row[column_name])
        if z_value is None:
            continue

        formatted_metric = f"{metric_label} ({column_name}={z_value:.3f})"

        if z_value >= config.severe_z_threshold:
            severe_metrics.append(formatted_metric)
            critical_metrics.append(formatted_metric)
        elif z_value >= config.critical_z_threshold:
            critical_metrics.append(formatted_metric)
        elif z_value >= config.warning_z_threshold:
            warning_metrics.append(formatted_metric)

    return critical_metrics, warning_metrics, severe_metrics


def _collect_hard_critical_flags(row: pd.Series) -> list[str]:
    critical_metrics: list[str] = []

    validation_status = _as_normalized_text(row.get("validation_status", "ok"))
    if validation_status and validation_status != "ok":
        critical_metrics.append(f"validation status is {validation_status}")

    for column_name, metric_label in HARD_CRITICAL_BOOLEAN_CHECKS.items():
        if column_name not in row.index:
            continue

        if _is_false_like(row[column_name]):
            critical_metrics.append(metric_label)

    for column_name, metric_label in HARD_CRITICAL_COUNT_CHECKS.items():
        if column_name not in row.index:
            continue

        if _is_positive_count(row[column_name]):
            critical_metrics.append(metric_label)

    return critical_metrics


def _make_quality_decision(
    critical_flag_count: int,
    severe_flag_count: int,
    warning_flag_count: int,
    config: QualityGateConfig,
) -> tuple[QualityDecision, RouteNext]:
    if (
        critical_flag_count >= config.fail_critical_threshold
        or severe_flag_count > 0
    ):
        return "fail", "stop_unreliable"

    if critical_flag_count > 0 or warning_flag_count > 0:
        return "review_with_technical_warning", "retrieval_agent"

    return "pass", "retrieval_agent"


def _build_explanation(
    decision: QualityDecision,
    critical_metrics: list[str],
    warning_metrics: list[str],
    severe_metrics: list[str],
    evidence_notes: Any,
) -> str:
    if decision == "pass":
        return "No warning, critical, or severe quality evidence exceeded the configured thresholds."

    explanation_parts: list[str] = []

    if severe_metrics:
        explanation_parts.append(
            "Severe evidence: " + "; ".join(severe_metrics) + "."
        )

    if critical_metrics:
        explanation_parts.append(
            "Critical evidence: " + "; ".join(critical_metrics) + "."
        )

    if warning_metrics:
        explanation_parts.append(
            "Warning evidence: " + "; ".join(warning_metrics) + "."
        )

    normalized_notes = _as_normalized_text(evidence_notes)
    if normalized_notes:
        explanation_parts.append(f"Manifest evidence note: {normalized_notes}.")

    if decision == "fail":
        explanation_parts.append(
            "Image is marked unreliable because it has either three or more critical quality flags or at least one severe quality outlier."
        )
    else:
        explanation_parts.append(
            "Image may continue downstream, but this technical warning should be preserved in later reasoning."
        )

    return " ".join(explanation_parts)


def evaluate_quality_row(
    row: pd.Series,
    config: QualityGateConfig,
) -> dict[str, Any]:
    numeric_critical_metrics, warning_metrics, severe_metrics = (
        _collect_numeric_quality_flags(row=row, config=config)
    )
    hard_critical_metrics = _collect_hard_critical_flags(row)

    critical_metrics = hard_critical_metrics + numeric_critical_metrics

    critical_flag_count = len(critical_metrics)
    warning_flag_count = len(warning_metrics)
    severe_flag_count = len(severe_metrics)

    decision, route_next = _make_quality_decision(
        critical_flag_count=critical_flag_count,
        severe_flag_count=severe_flag_count,
        warning_flag_count=warning_flag_count,
        config=config,
    )

    flagged_metrics = [
        *(f"severe: {metric}" for metric in severe_metrics),
        *(f"critical: {metric}" for metric in critical_metrics),
        *(f"warning: {metric}" for metric in warning_metrics),
    ]

    return {
        "dicom_path": row.get(config.dicom_path_column, ""),
        "study_key": row.get(config.study_key_column, ""),
        "quality_gate_decision": decision,
        "critical_flag_count": critical_flag_count,
        "warning_flag_count": warning_flag_count,
        "flagged_metrics": "; ".join(flagged_metrics),
        "technical_explanation": _build_explanation(
            decision=decision,
            critical_metrics=critical_metrics,
            warning_metrics=warning_metrics,
            severe_metrics=severe_metrics,
            evidence_notes=row.get("evidence_notes", ""),
        ),
        "route_next": route_next,
    }


def quality_gate_node(state: QualityGateState) -> QualityGateState:
    config = QualityGateConfig(
        input_csv=Path(state["input_csv"]),
        output_csv=Path(state["output_csv"]),
    )

    manifest = pd.read_csv(config.input_csv)

    decisions = [
        evaluate_quality_row(row=row, config=config)
        for _, row in manifest.iterrows()
    ]

    output_df = pd.DataFrame(
        decisions,
        columns=[
            "dicom_path",
            "study_key",
            "quality_gate_decision",
            "critical_flag_count",
            "warning_flag_count",
            "flagged_metrics",
            "technical_explanation",
            "route_next",
        ],
    )

    config.output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(config.output_csv, index=False)

    return {
        "input_csv": str(config.input_csv),
        "output_csv": str(config.output_csv),
        "decisions": decisions,
    }


def build_quality_gate_graph():
    graph = StateGraph(QualityGateState)

    graph.add_node("quality_gate_agent", quality_gate_node)
    graph.add_edge(START, "quality_gate_agent")
    graph.add_edge("quality_gate_agent", END)

    return graph.compile()


def run_quality_gate(
    input_csv: str = "outputs/chexpert_plus/quality_evidence_manifest.csv",
    output_csv: str = "outputs/chexpert_plus/quality_gate_decisions.csv",
) -> QualityGateState:
    graph = build_quality_gate_graph()

    return graph.invoke(
        {
            "input_csv": input_csv,
            "output_csv": output_csv,
            "decisions": [],
        }
    )