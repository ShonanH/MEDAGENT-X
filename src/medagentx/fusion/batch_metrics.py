from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.medagentx.agents.judge_agent import compute_present_metrics
from src.medagentx.fusion.constants import DISEASE_LABELS


@dataclass
class CorrelationMetrics:
    n: int
    rmse: float | None = None
    plcc: float | None = None
    srcc: float | None = None


@dataclass
class BatchCalibrationReport:
    batch_dir: str
    case_count: int
    label_row_count: int
    gt_prevalence: float | None
    mean_disease_f1: float | None
    mean_disease_precision: float | None
    mean_disease_recall: float | None
    judge_concordant_count: int
    judge_partial_count: int
    judge_discordant_count: int
    ensemble_binary: CorrelationMetrics
    densenet_binary: CorrelationMetrics
    fusion_binary: CorrelationMetrics
    ensemble_ordinal: CorrelationMetrics
    baseline_always_zero: CorrelationMetrics
    baseline_prevalence: CorrelationMetrics
    per_label_ensemble_binary: dict[str, CorrelationMetrics]


def _status_to_binary(status: str | None) -> float:
    if status == "present":
        return 1.0
    if status == "absent":
        return 0.0
    return math.nan


def _status_to_ordinal(status: str | None) -> float:
    if status == "present":
        return 1.0
    if status == "uncertain":
        return 0.5
    if status == "absent":
        return 0.0
    return math.nan


def _pearson(x: np.ndarray, y: np.ndarray) -> float | None:
    if len(x) < 2:
        return None
    if np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def _spearman(x: np.ndarray, y: np.ndarray) -> float | None:
    if len(x) < 2:
        return None
    rx = pd.Series(x).rank(method="average").to_numpy()
    ry = pd.Series(y).rank(method="average").to_numpy()
    return _pearson(rx, ry)


def _rmse(x: np.ndarray, y: np.ndarray) -> float | None:
    if len(x) == 0:
        return None
    return float(np.sqrt(np.mean((x - y) ** 2)))


def correlation_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> CorrelationMetrics:
    mask = np.isfinite(y_true) & np.isfinite(y_pred)
    yt = y_true[mask]
    yp = y_pred[mask]
    if len(yt) < 2:
        return CorrelationMetrics(n=len(yt))
    return CorrelationMetrics(
        n=len(yt),
        rmse=_rmse(yt, yp),
        plcc=_pearson(yt, yp),
        srcc=_spearman(yt, yp),
    )


def _resolve_batch_paths(batch_dir: str | Path, limit: int | None = None) -> dict[str, Path]:
    root = Path(batch_dir)
    suffix = f"first_{limit}" if limit is not None else "first_100"

    judge_path = root / f"judge_results_{suffix}.csv"
    disease_path = root / f"disease_reasoning_results_{suffix}.csv"

    if not judge_path.exists():
        candidates = sorted(root.glob("judge_results*.csv"))
        if candidates:
            judge_path = candidates[-1]
    if not disease_path.exists():
        candidates = sorted(root.glob("disease_reasoning_results*.csv"))
        if candidates:
            disease_path = candidates[-1]

    return {
        "judge_results": judge_path,
        "disease_reasoning_results": disease_path,
        "metrics_json": root / f"batch_calibration_metrics_{suffix}.json",
        "metrics_md": root / f"batch_calibration_metrics_{suffix}.md",
    }


def _extract_classifier_rows(
    judge_df: pd.DataFrame,
    disease_df: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for _, judge_row in judge_df.iterrows():
        gt_map = {item["label"]: item["status"] for item in json.loads(judge_row["ground_truth_labels_json"])}
        disease_matches = disease_df[disease_df["dicom_path"] == judge_row["dicom_path"]]
        if disease_matches.empty:
            continue

        classifier = json.loads(disease_matches.iloc[0]["classifier_evidence_json"])
        label_map = {item["label"]: item for item in classifier.get("labels", [])}

        for label in DISEASE_LABELS:
            gt_status = gt_map.get(label)
            info = label_map.get(label, {})
            rows.append(
                {
                    "dicom_path": judge_row["dicom_path"],
                    "label": label,
                    "gt_status": gt_status,
                    "gt_binary": _status_to_binary(gt_status),
                    "gt_ordinal": _status_to_ordinal(gt_status),
                    "ensemble_prob": info.get("probability"),
                    "densenet_prob": info.get("densenet_probability"),
                    "fusion_prob": info.get("fusion_probability"),
                }
            )

    return pd.DataFrame(rows)


def build_batch_calibration_report(
    batch_dir: str | Path,
    limit: int | None = None,
) -> BatchCalibrationReport:
    paths = _resolve_batch_paths(batch_dir, limit=limit)
    judge_df = pd.read_csv(paths["judge_results"])
    disease_df = pd.read_csv(paths["disease_reasoning_results"])

    label_df = _extract_classifier_rows(judge_df, disease_df)

    binary_mask = label_df["gt_binary"].notna()
    ordinal_mask = label_df["gt_ordinal"].notna()

    y_binary = label_df.loc[binary_mask, "gt_binary"].to_numpy(dtype=float)
    y_ordinal = label_df.loc[ordinal_mask, "gt_ordinal"].to_numpy(dtype=float)

    prevalence = float(y_binary.mean()) if len(y_binary) else None

    per_label: dict[str, CorrelationMetrics] = {}
    for label in DISEASE_LABELS:
        sub = label_df[(label_df["label"] == label) & label_df["gt_binary"].notna() & label_df["ensemble_prob"].notna()]
        per_label[label] = correlation_metrics(
            sub["gt_binary"].to_numpy(dtype=float),
            sub["ensemble_prob"].to_numpy(dtype=float),
        )

    decision_counts = judge_df["judge_decision"].value_counts().to_dict() if "judge_decision" in judge_df else {}

    return BatchCalibrationReport(
        batch_dir=str(batch_dir),
        case_count=int(len(judge_df)),
        label_row_count=int(len(label_df)),
        gt_prevalence=prevalence,
        mean_disease_f1=float(judge_df["disease_f1"].mean()) if "disease_f1" in judge_df else None,
        mean_disease_precision=float(judge_df["disease_precision"].mean())
        if "disease_precision" in judge_df
        else None,
        mean_disease_recall=float(judge_df["disease_recall"].mean()) if "disease_recall" in judge_df else None,
        judge_concordant_count=int(decision_counts.get("concordant", 0)),
        judge_partial_count=int(decision_counts.get("partially_concordant", 0)),
        judge_discordant_count=int(decision_counts.get("discordant", 0)),
        ensemble_binary=correlation_metrics(
            y_binary,
            label_df.loc[binary_mask, "ensemble_prob"].to_numpy(dtype=float),
        ),
        densenet_binary=correlation_metrics(
            y_binary,
            label_df.loc[binary_mask, "densenet_prob"].to_numpy(dtype=float),
        ),
        fusion_binary=correlation_metrics(
            y_binary,
            label_df.loc[binary_mask, "fusion_prob"].to_numpy(dtype=float),
        ),
        ensemble_ordinal=correlation_metrics(
            y_ordinal,
            label_df.loc[ordinal_mask, "ensemble_prob"].to_numpy(dtype=float),
        ),
        baseline_always_zero=correlation_metrics(y_binary, np.zeros_like(y_binary)),
        baseline_prevalence=correlation_metrics(
            y_binary,
            np.full_like(y_binary, y_binary.mean() if len(y_binary) else 0.0),
        ),
        per_label_ensemble_binary=per_label,
    )


def format_metrics_markdown(report: BatchCalibrationReport) -> str:
    def fmt_corr(name: str, metrics: CorrelationMetrics) -> str:
        if metrics.rmse is None:
            return f"- **{name}:** n={metrics.n}, insufficient variance for correlation"
        plcc = f"{metrics.plcc:.4f}" if metrics.plcc is not None else "n/a"
        srcc = f"{metrics.srcc:.4f}" if metrics.srcc is not None else "n/a"
        return f"- **{name}:** n={metrics.n}, RMSE={metrics.rmse:.4f}, PLCC={plcc}, SRCC={srcc}"

    lines = [
        "# Batch Calibration Metrics",
        "",
        f"- Batch dir: `{report.batch_dir}`",
        f"- Cases: {report.case_count}",
        f"- Disease label rows: {report.label_row_count}",
        "",
        "## Workflow disease F1",
        f"- Mean disease F1: **{report.mean_disease_f1:.4f}**" if report.mean_disease_f1 is not None else "- Mean disease F1: n/a",
        f"- Mean disease precision: {report.mean_disease_precision:.4f}" if report.mean_disease_precision is not None else "- Mean disease precision: n/a",
        f"- Mean disease recall: {report.mean_disease_recall:.4f}" if report.mean_disease_recall is not None else "- Mean disease recall: n/a",
        f"- Judge decisions: concordant={report.judge_concordant_count}, partial={report.judge_partial_count}, discordant={report.judge_discordant_count}",
        "",
        "## Pooled probability calibration (binary GT: present=1, absent=0)",
        fmt_corr("Ensemble", report.ensemble_binary),
        fmt_corr("DenseNet", report.densenet_binary),
        fmt_corr("Fusion", report.fusion_binary),
        "",
        "## Baselines (binary GT)",
        fmt_corr("Always predict 0", report.baseline_always_zero),
        fmt_corr("Always predict prevalence", report.baseline_prevalence),
        "",
        "## Ordinal GT (present=1, uncertain=0.5, absent=0)",
        fmt_corr("Ensemble", report.ensemble_ordinal),
        "",
        "## Per-label ensemble vs binary GT",
        "",
        "| Label | n | RMSE | PLCC | SRCC |",
        "|---|---:|---:|---:|---:|",
    ]

    for label in DISEASE_LABELS:
        metrics = report.per_label_ensemble_binary[label]
        plcc = f"{metrics.plcc:.3f}" if metrics.plcc is not None else "n/a"
        srcc = f"{metrics.srcc:.3f}" if metrics.srcc is not None else "n/a"
        rmse = f"{metrics.rmse:.3f}" if metrics.rmse is not None else "n/a"
        lines.append(f"| {label} | {metrics.n} | {rmse} | {plcc} | {srcc} |")

    lines.extend(
        [
            "",
            "## Notes",
            "- RMSE below the always-zero / prevalence baselines indicates better probability calibration.",
            "- Disease F1 is the primary workflow metric; correlation metrics measure probability ranking/calibration only.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_batch_calibration_report(
    batch_dir: str | Path,
    limit: int | None = None,
) -> BatchCalibrationReport:
    paths = _resolve_batch_paths(batch_dir, limit=limit)
    report = build_batch_calibration_report(batch_dir, limit=limit)

    payload = asdict(report)
    payload["per_label_ensemble_binary"] = {
        label: asdict(metrics) for label, metrics in report.per_label_ensemble_binary.items()
    }

    paths["metrics_json"].parent.mkdir(parents=True, exist_ok=True)
    paths["metrics_json"].write_text(json.dumps(payload, indent=2), encoding="utf-8")
    paths["metrics_md"].write_text(format_metrics_markdown(report), encoding="utf-8")
    return report


def print_batch_calibration_summary(report: BatchCalibrationReport) -> None:
    print("[Batch Metrics] Summary", flush=True)
    if report.mean_disease_f1 is not None:
        print(f"  Mean disease F1: {report.mean_disease_f1:.4f}", flush=True)
    if report.ensemble_binary.rmse is not None:
        plcc = report.ensemble_binary.plcc
        srcc = report.ensemble_binary.srcc
        plcc_text = f"{plcc:.4f}" if plcc is not None else "n/a"
        srcc_text = f"{srcc:.4f}" if srcc is not None else "n/a"
        print(
            "  Ensemble (binary GT): "
            f"RMSE={report.ensemble_binary.rmse:.4f}, "
            f"PLCC={plcc_text}, "
            f"SRCC={srcc_text}",
            flush=True,
        )
    if report.baseline_always_zero.rmse is not None:
        print(f"  Baseline always-0 RMSE: {report.baseline_always_zero.rmse:.4f}", flush=True)
