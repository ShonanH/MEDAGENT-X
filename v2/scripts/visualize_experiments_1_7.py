"""Create a publication-oriented visualization pack for Experiments 1--6.

The repository does not retain a complete, independent evaluation directory for
every numbered experiment.  This script uses the experiment mapping documented
in ``v2/experiments/results_so_far.md`` and records missing/aliased artifacts in
the generated README instead of silently inventing values.

Examples
--------
python v2/scripts/visualize_experiments_1_7.py
python v2/scripts/visualize_experiments_1_7.py --output-dir /tmp/exp1_7_figures
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "medagentx_mplconfig")
)
os.environ.setdefault(
    "XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "medagentx_cache")
)

import matplotlib  # noqa: E402

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    auc,
    average_precision_score,
    precision_recall_curve,
    roc_curve,
)


COLORS = {
    "blue": "#2864A5",
    "orange": "#E67E22",
    "green": "#238636",
    "red": "#C0392B",
    "purple": "#7E57C2",
    "teal": "#168A8A",
    "gray": "#697386",
    "light_gray": "#D9DEE7",
}
EXPERIMENT_COLORS = {
    1: "#4C78A8",
    2: "#A0CBE8",
    3: "#BAB0AC",
    4: "#F58518",
    5: "#E45756",
    6: "#72B7B2",
    7: "#B279A2",
}
STATUS_ORDER = ("present", "absent", "uncertain", "unmentioned")
SUPPORT_ORDER = ("strong", "moderate", "weak", "none", "mixed", "contradictory")
SUPPORT_COLORS = {
    "strong": "#1B7837",
    "moderate": "#7FBF7B",
    "weak": "#DFC27D",
    "none": "#BDBDBD",
    "mixed": "#80CDC1",
    "contradictory": "#B2182B",
}
POLICY_DISPLAY_NAMES = {
    "evidence_verification_policy_v1": "evidence_verification_without_LLM",
    "llm_evidence_verification_review_v1": "llm_evidence_verification",
}


@dataclass(frozen=True)
class ExperimentSpec:
    number: int
    name: str
    eval_dir: Path | None
    final_run: str | None
    note: str = ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate comparison, ROC/PR, label, confusion, and evidence figures."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="MEDAGENT-X repository root (auto-detected by default).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Defaults to v2/experiments/visualizations_exp01_exp06.",
    )
    parser.add_argument("--dpi", type=int, default=220)
    return parser


def experiment_specs(root: Path) -> list[ExperimentSpec]:
    """Map historical experiment folders 1, 3, 4, 5, 6, 7 to paper 1--6."""
    return [
        ExperimentSpec(
            1,
            "Vision only",
            root / "v2/experiments/exp01_vision_only",
            "vision_full",
        ),
        ExperimentSpec(
            2,
            "Fusion, no retrieval",
            root / "v2/experiments/exp03_fusion_no_retrieval",
            "fusion_no_retrieval_full",
            "Paper Experiment 2 is stored in the historical exp03 directory.",
        ),
        ExperimentSpec(
            3,
            "Deterministic retrieval fusion",
            root / "v2/artifactsLocal/Evaluation_output_last4_blocks_top10/test",
            "fusion_full",
        ),
        ExperimentSpec(
            4,
            "LLM retrieval fusion (Llama)",
            root
            / "v2/experiments/exp05_llm_fusion_with_retrieval_graph/judge_evaluation",
            "fusion_full",
            "This is the best saved full-test macro-F1 run.",
        ),
        ExperimentSpec(
            5,
            "Deterministic fusion + evidence",
            root / "v2/artifactsLocal/Evaluation_output_last4_blocks_top10/test",
            "fusion_full",
            "Evidence verification does not edit labels; confusion counts inherit paper Experiment 3.",
        ),
        ExperimentSpec(
            6,
            "Qwen fusion + evidence",
            root
            / "v2/experiments/exp05_llm_fusion_with_retrieval_graph/judge_evaluation",
            "fusion_full",
            "Historical Experiment 7. Evidence verification does not edit the upstream Qwen predictions.",
        ),
    ]


def _set_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#4B5563",
            "axes.grid": False,
            "grid.color": "#E5E7EB",
            "grid.linewidth": 0.8,
            "axes.axisbelow": True,
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.titlepad": 14,
        }
    )


def _save(fig: plt.Figure, path: Path, dpi: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _save_paper(fig: plt.Figure, base_path: Path, dpi: int) -> None:
    """Save one paper figure as a high-resolution PNG and vector PDF."""
    base_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(
        base_path.with_suffix(".png"),
        dpi=max(dpi, 300),
        bbox_inches="tight",
        facecolor="white",
    )
    fig.savefig(base_path.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _load_metric_artifacts(
    specs: Iterable[ExperimentSpec],
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    macro_rows: list[dict[str, Any]] = []
    label_frames: list[pd.DataFrame] = []
    messages: list[str] = []
    for spec in specs:
        if spec.eval_dir is None or spec.final_run is None:
            messages.append(f"Experiment {spec.number}: {spec.note}")
            continue
        summary_path = spec.eval_dir / "judge_summary.json"
        label_path = spec.eval_dir / "per_label_metrics.csv"
        if not summary_path.exists() or not label_path.exists():
            messages.append(
                f"Experiment {spec.number}: missing {summary_path} or {label_path}."
            )
            continue

        summary = _read_json(summary_path)
        selected = [
            row
            for row in summary.get("runs", [])
            if row.get("name") == spec.final_run and row.get("eval_scope") == "full"
        ]
        if not selected:
            messages.append(
                f"Experiment {spec.number}: run {spec.final_run!r} not found in {summary_path}."
            )
            continue
        row = dict(selected[0])
        row.update(
            experiment=spec.number,
            experiment_name=spec.name,
            source=str(summary_path),
            note=spec.note,
        )
        macro_rows.append(row)

        labels = pd.read_csv(label_path)
        labels = labels[
            labels["run_name"].eq(spec.final_run) & labels["eval_scope"].eq("full")
        ].copy()
        labels["experiment"] = spec.number
        labels["experiment_name"] = spec.name
        label_frames.append(labels)

    macro = pd.DataFrame(macro_rows).sort_values("experiment")
    per_label = (
        pd.concat(label_frames, ignore_index=True) if label_frames else pd.DataFrame()
    )
    return macro, per_label, messages


def _replace_exp6_with_qwen_metrics(
    root: Path,
    macro: pd.DataFrame,
    per_label: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate historical Exp. 7's Qwen predictions for paper Experiment 6."""
    qwen_path = (
        root
        / "v2/experiments/exp05_llm_fusion_with_retrieval_graph/qwen3_14b/fusion_label_predictions.csv"
    )
    matches_path = root / "v2/experiments/exp01_vision_only/judge_matches.csv"
    if not qwen_path.exists() or not matches_path.exists():
        return macro, per_label

    predictions = pd.read_csv(qwen_path)[
        ["study_key", "label", "fused_status"]
    ]
    ground_truth = pd.read_csv(matches_path)
    ground_truth = ground_truth[
        ground_truth.run_name.eq("vision_full")
        & ground_truth.eval_scope.eq("full")
    ][["study_key", "label", "ground_truth_status"]]
    merged = ground_truth.merge(
        predictions,
        on=["study_key", "label"],
        how="inner",
        validate="one_to_one",
    )
    if len(merged) != len(ground_truth):
        raise ValueError("Qwen predictions do not cover every full-test Judge row.")

    rows: list[dict[str, Any]] = []
    for label, group in merged.groupby("label", sort=True):
        gt = group.ground_truth_status
        pred = group.fused_status
        tp = int(((gt == "present") & (pred == "present")).sum())
        tn = int(((gt == "absent") & (pred == "absent")).sum())
        fp = int(((gt == "absent") & (pred == "present")).sum())
        fn = int(((gt == "present") & (pred == "absent")).sum())
        miss_uncertain = int(((gt == "present") & (pred == "uncertain")).sum())
        gt_present = int((gt == "present").sum())
        gt_absent = int((gt == "absent").sum())
        precision = tp / (tp + fp) if tp + fp else np.nan
        recall = tp / (tp + fn + miss_uncertain) if tp + fn + miss_uncertain else np.nan
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else np.nan
        )
        rows.append(
            {
                "run_name": "fusion_full",
                "label": label,
                "eval_scope": "full",
                "scoreable_cells": gt_present + gt_absent,
                "gt_present": gt_present,
                "gt_absent": gt_absent,
                "pred_present": int((pred == "present").sum()),
                "pred_absent": int((pred == "absent").sum()),
                "tp": tp,
                "tn": tn,
                "fp": fp,
                "fn": fn + miss_uncertain,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "specificity": tn / (tn + fp) if tn + fp else np.nan,
                "coverage_rate": (gt_present + gt_absent) / len(group),
                "experiment": 6,
                "experiment_name": "Qwen fusion + evidence",
            }
        )
    qwen_labels = pd.DataFrame(rows)

    tp = int(qwen_labels.tp.sum())
    fp = int(qwen_labels.fp.sum())
    fn = int(qwen_labels.fn.sum())
    micro_precision = tp / (tp + fp)
    micro_recall = tp / (tp + fn)
    micro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall)
    template = macro[macro.experiment.eq(6)].iloc[0].to_dict()
    template.update(
        macro_f1=float(qwen_labels.f1.mean()),
        macro_precision=float(qwen_labels.precision.mean()),
        macro_recall=float(qwen_labels.recall.mean()),
        micro_f1=micro_f1,
        micro_precision=micro_precision,
        micro_recall=micro_recall,
        coverage=float(qwen_labels.scoreable_cells.sum() / len(merged)),
        experiment_name="Qwen fusion + evidence",
        source=str(qwen_path),
        note="Historical Experiment 7; evaluated from its upstream Qwen fusion predictions.",
    )
    macro = pd.concat(
        [macro[~macro.experiment.eq(6)], pd.DataFrame([template])],
        ignore_index=True,
    ).sort_values("experiment")
    per_label = pd.concat(
        [per_label[~per_label.experiment.eq(6)], qwen_labels],
        ignore_index=True,
    )
    return macro, per_label


def plot_experiment_metrics(macro: pd.DataFrame, out: Path, dpi: int) -> None:
    metrics = ("macro_f1", "macro_precision", "macro_recall", "micro_f1")
    labels = ("Macro F1", "Macro precision", "Macro recall", "Micro F1")
    x = np.arange(len(macro))
    width = 0.19
    fig, ax = plt.subplots(figsize=(13, 6.5))
    for index, (metric, label) in enumerate(zip(metrics, labels)):
        positions = x + (index - 1.5) * width
        bars = ax.bar(positions, macro[metric], width, label=label, alpha=0.92)
        if metric == "macro_f1":
            ax.bar_label(bars, fmt="%.3f", fontsize=8, padding=2)
    ax.set_xticks(x)
    ax.set_xticklabels(
        [
            f"Exp {n}\n{name}"
            for n, name in zip(macro.experiment, macro.experiment_name)
        ],
        rotation=15,
        ha="right",
    )
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("Score")
    ax.set_title(
        "Experiments 1–6: Comparable Full-Test Metrics\n"
        "Evidence verification experiments inherit their upstream label predictions"
    )
    ax.legend(ncols=4, frameon=False, loc="upper center")
    _save(fig, out / "01_experiment_metric_comparison.png", dpi)


def plot_macro_f1_progression(macro: pd.DataFrame, out: Path, dpi: int) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.5))
    colors = [EXPERIMENT_COLORS[int(value)] for value in macro.experiment]
    bars = ax.bar(macro.experiment.astype(str), macro.macro_f1, color=colors)
    ax.bar_label(bars, labels=[f"{v:.4f}" for v in macro.macro_f1], padding=3)
    ax.axhline(
        float(macro.loc[macro.experiment.eq(1), "macro_f1"].iloc[0]),
        color=COLORS["blue"],
        linestyle="--",
        linewidth=1.5,
        label="Experiment 1 vision baseline",
    )
    ax.set_ylim(max(0, float(macro.macro_f1.min()) - 0.08), 0.78)
    ax.set_xlabel("Experiment")
    ax.set_ylabel("Full-test macro F1")
    ax.set_title("Headline Performance Progression")
    ax.legend(frameon=False)
    _save(fig, out / "02_macro_f1_progression.png", dpi)


def _annotated_heatmap(
    ax: plt.Axes,
    values: np.ndarray,
    row_labels: list[str],
    col_labels: list[str],
    *,
    cmap: str,
    value_format: str = ".3f",
    center: float | None = None,
) -> None:
    finite = values[np.isfinite(values)]
    if center is None or finite.size == 0:
        image = ax.imshow(values, cmap=cmap, aspect="auto")
    else:
        bound = max(
            abs(float(finite.min()) - center), abs(float(finite.max()) - center)
        )
        image = ax.imshow(
            values,
            cmap=cmap,
            aspect="auto",
            vmin=center - bound,
            vmax=center + bound,
        )
    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_xticklabels(col_labels, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_yticklabels(row_labels)
    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            value = values[row, col]
            text = "—" if not np.isfinite(value) else format(value, value_format)
            ax.text(col, row, text, ha="center", va="center", fontsize=8)
    plt.colorbar(image, ax=ax, shrink=0.82)


def plot_per_label_heatmaps(per_label: pd.DataFrame, out: Path, dpi: int) -> None:
    pivot = per_label.pivot(index="label", columns="experiment", values="f1")
    pivot = pivot.sort_values(4 if 4 in pivot.columns else pivot.columns[-1])
    fig, ax = plt.subplots(figsize=(10.5, 8))
    _annotated_heatmap(
        ax,
        pivot.to_numpy(dtype=float),
        pivot.index.tolist(),
        [f"Exp {col}" for col in pivot.columns],
        cmap="YlGnBu",
    )
    ax.set_title("Per-Label F1 Across Experiments")
    ax.set_xlabel("")
    ax.set_ylabel("")
    _save(fig, out / "03_per_label_f1_heatmap.png", dpi)

    baseline = pivot[1]
    delta = pivot.subtract(baseline, axis=0).drop(columns=1, errors="ignore")
    fig, ax = plt.subplots(figsize=(10.5, 8))
    _annotated_heatmap(
        ax,
        delta.to_numpy(dtype=float),
        delta.index.tolist(),
        [f"Exp {col}" for col in delta.columns],
        cmap="RdYlGn",
        value_format="+.3f",
        center=0.0,
    )
    ax.set_title("Per-Label F1 Change vs Experiment 1")
    ax.set_xlabel("")
    ax.set_ylabel("")
    _save(fig, out / "04_per_label_f1_delta_vs_exp01.png", dpi)


def _confusion_matrix_from_rows(frame: pd.DataFrame) -> np.ndarray:
    totals = frame[["tn", "fp", "fn", "tp"]].sum(numeric_only=True)
    return np.array([[totals["tn"], totals["fp"]], [totals["fn"], totals["tp"]]])


def plot_experiment_confusions(per_label: pd.DataFrame, out: Path, dpi: int) -> None:
    experiments = sorted(per_label.experiment.unique())
    cols = 3
    rows = int(np.ceil(len(experiments) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(12, 4 * rows), squeeze=False)
    matrices = {
        exp: _confusion_matrix_from_rows(per_label[per_label.experiment.eq(exp)])
        for exp in experiments
    }
    vmax = max(float(matrix.max()) for matrix in matrices.values())
    for ax, exp in zip(axes.flat, experiments):
        matrix = matrices[exp]
        ax.imshow(matrix, cmap="Blues", vmin=0, vmax=vmax)
        ax.set_title(f"Experiment {exp}")
        ax.set_xticks((0, 1), ("Pred absent", "Pred present"))
        ax.set_yticks((0, 1), ("GT absent", "GT present"))
        for row in range(2):
            for col in range(2):
                ax.text(
                    col, row, f"{int(matrix[row, col]):,}", ha="center", va="center"
                )
    for ax in axes.flat[len(experiments) :]:
        ax.axis("off")
    fig.suptitle(
        "Aggregate Judge-Compatible Confusion Matrices", fontsize=15, fontweight="bold"
    )
    _save(fig, out / "05_experiment_confusion_matrices.png", dpi)


def plot_paper_confusions(
    per_label: pd.DataFrame,
    specs: Iterable[ExperimentSpec],
    out: Path,
    dpi: int,
) -> None:
    """Write one independently usable confusion matrix per paper experiment."""
    spec_by_number = {spec.number: spec for spec in specs}
    vmax = max(
        float(_confusion_matrix_from_rows(group).max())
        for _, group in per_label.groupby("experiment")
    )
    for experiment, group in per_label.groupby("experiment"):
        experiment = int(experiment)
        spec = spec_by_number[experiment]
        matrix = _confusion_matrix_from_rows(group)
        fig, ax = plt.subplots(figsize=(5.2, 4.6))
        image = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=vmax)
        ax.grid(False)
        ax.set_xticks((0, 1), ("Predicted absent", "Predicted present"))
        ax.set_yticks((0, 1), ("GT absent", "GT present"))
        for row in range(2):
            for col in range(2):
                color = "white" if matrix[row, col] > 0.55 * vmax else "#111827"
                ax.text(
                    col,
                    row,
                    f"{int(matrix[row, col]):,}",
                    ha="center",
                    va="center",
                    color=color,
                    fontsize=11,
                )
        title = f"Experiment {experiment}: {spec.name}"
        if experiment == 5:
            title += "\nLabel predictions inherited from Experiment 3"
        elif experiment == 6:
            title += "\nQwen predictions before evidence verification"
        ax.set_title(title, fontsize=11, pad=16)
        colorbar = fig.colorbar(image, ax=ax, shrink=0.82)
        colorbar.set_label("Count")
        _save_paper(
            fig,
            out / f"exp{experiment:02d}_confusion_matrix",
            dpi,
        )


def plot_paper_label_f1(
    per_label: pd.DataFrame,
    specs: Iterable[ExperimentSpec],
    out: Path,
    dpi: int,
) -> None:
    """Write one label-wise F1 chart per paper experiment."""
    spec_by_number = {spec.number: spec for spec in specs}
    for experiment, group in per_label.groupby("experiment"):
        experiment = int(experiment)
        spec = spec_by_number[experiment]
        frame = group.sort_values("f1")
        fig, ax = plt.subplots(figsize=(7.2, 5.3))
        bars = ax.barh(frame.label, frame.f1, color=EXPERIMENT_COLORS[experiment])
        ax.bar_label(bars, labels=[f"{value:.3f}" for value in frame.f1], padding=3)
        ax.set_xlim(0, 1.04)
        ax.set_xlabel("F1 score")
        ax.set_title(f"Experiment {experiment}: {spec.name} — Label-wise F1")
        ax.grid(False)
        _save_paper(fig, out / f"exp{experiment:02d}_label_f1", dpi)


def plot_best_label_diagnostics(per_label: pd.DataFrame, out: Path, dpi: int) -> None:
    best = per_label[per_label.experiment.eq(4)].copy()
    if best.empty:
        return
    best = best.sort_values("f1")
    fig, axes = plt.subplots(1, 2, figsize=(15, 7))
    axes[0].barh(best.label, best.f1, color=COLORS["teal"])
    axes[0].set_xlim(0, 1)
    axes[0].set_xlabel("F1")
    axes[0].set_title("Experiment 4 F1 by Label")
    for y, value in enumerate(best.f1):
        axes[0].text(value + 0.01, y, f"{value:.3f}", va="center", fontsize=8)

    sizes = 30 + 2.5 * best.gt_present.fillna(0)
    axes[1].scatter(
        best.recall,
        best.precision,
        s=sizes,
        c=best.f1,
        cmap="viridis",
        vmin=0,
        vmax=1,
        alpha=0.8,
        edgecolor="none",
    )
    for _, row in best.iterrows():
        axes[1].annotate(
            row.label,
            (row.recall, row.precision),
            xytext=(4, 3),
            textcoords="offset points",
            fontsize=7,
        )
    axes[1].set_xlim(0, 1.03)
    axes[1].set_ylim(0, 1.03)
    axes[1].set_xlabel("Recall")
    axes[1].set_ylabel("Precision")
    axes[1].set_title("Precision–Recall Trade-off\n(point size = GT-positive count)")
    _save(fig, out / "06_best_experiment_label_diagnostics.png", dpi)


def plot_paper_best_precision_recall(
    per_label: pd.DataFrame, out: Path, dpi: int
) -> None:
    """Write the best experiment's label precision/recall trade-off separately."""
    best = per_label[per_label.experiment.eq(4)].copy()
    if best.empty:
        return
    fig, ax = plt.subplots(figsize=(9.2, 5.3))
    sizes = 30 + 2.5 * best.gt_present.fillna(0)
    ax.scatter(
        best.recall,
        best.precision,
        s=sizes,
        c=best.f1,
        cmap="viridis",
        vmin=0,
        vmax=1,
        alpha=0.85,
        edgecolor="none",
    )
    ax.set_xlim(0, 1.03)
    ax.set_ylim(0, 1.06)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title(
        "Experiment 4: Label Precision–Recall Trade-off\n"
        "Point size represents ground-truth positive count",
        fontsize=12,
        pad=16,
    )
    ax.grid(False)
    cmap = plt.get_cmap("viridis")
    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="none",
            markerfacecolor=cmap(float(row.f1)),
            markeredgecolor="none",
            markersize=7,
            label=f"{row.label} ({row.f1:.3f})",
        )
        for _, row in best.sort_values("f1", ascending=False).iterrows()
    ]
    ax.legend(
        handles=handles,
        title="Label (F1)",
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        frameon=False,
        fontsize=8,
        borderaxespad=0,
    )
    _save_paper(fig, out / "exp04_label_precision_recall", dpi)


def _slug_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")


def _probability_records(
    prediction_csv: Path,
    matches_csv: Path,
    *,
    negative_policy: str,
    min_class_count: int = 5,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    predictions = pd.read_csv(prediction_csv)
    matches = pd.read_csv(matches_csv)
    matches = matches[
        matches["eval_scope"].eq("full")
        & matches["ground_truth_status"].isin(STATUS_ORDER)
    ].copy()
    if negative_policy == "explicit_absent":
        matches = matches[matches.ground_truth_status.isin(("present", "absent"))]
    matches["target"] = matches.ground_truth_status.eq("present").astype(int)

    results: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for label, group in matches.groupby("label"):
        column = f"probability_{_slug_label(label)}"
        if column not in predictions.columns:
            continue
        merged = group.merge(
            predictions[["study_key", column]], on="study_key", how="inner"
        )
        merged = merged.dropna(subset=[column, "target"])
        class_counts = merged.target.value_counts()
        if (
            len(merged)
            and merged.target.nunique() == 2
            and int(class_counts.min()) >= min_class_count
        ):
            results[label] = (
                merged.target.to_numpy(dtype=int),
                merged[column].to_numpy(dtype=float),
            )
    return results


def plot_curves(
    records: dict[str, tuple[np.ndarray, np.ndarray]],
    out: Path,
    dpi: int,
    *,
    stem: str,
    title_suffix: str,
) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    cmap = plt.get_cmap("tab20")
    roc_rows: list[dict[str, Any]] = []
    fig_roc, ax_roc = plt.subplots(figsize=(9, 7))
    fig_pr, ax_pr = plt.subplots(figsize=(9, 7))
    for index, (label, (target, score)) in enumerate(sorted(records.items())):
        fpr, tpr, _ = roc_curve(target, score)
        precision, recall, _ = precision_recall_curve(target, score)
        roc_auc = auc(fpr, tpr)
        ap = average_precision_score(target, score)
        roc_rows.append(
            {
                "label": label,
                "examples": len(target),
                "positives": int(target.sum()),
                "negatives": int((1 - target).sum()),
                "auroc": roc_auc,
                "average_precision": ap,
            }
        )
        color = cmap(index % 20)
        ax_roc.plot(fpr, tpr, color=color, label=f"{label} ({roc_auc:.3f})")
        ax_pr.plot(recall, precision, color=color, label=f"{label} ({ap:.3f})")

    ax_roc.plot((0, 1), (0, 1), linestyle="--", color=COLORS["gray"])
    ax_roc.set(
        xlabel="False-positive rate",
        ylabel="True-positive rate",
        xlim=(0, 1),
        ylim=(0, 1.01),
    )
    ax_roc.set_title(f"RAD-DINO ROC Curves — {title_suffix}")
    ax_roc.legend(fontsize=7, frameon=False, ncols=2)
    _save(fig_roc, out / f"07_roc_curves_{stem}.png", dpi)

    ax_pr.set(xlabel="Recall", ylabel="Precision", xlim=(0, 1), ylim=(0, 1.01))
    ax_pr.set_title(f"RAD-DINO Precision–Recall Curves — {title_suffix}")
    ax_pr.legend(fontsize=7, frameon=False, ncols=2)
    _save(fig_pr, out / f"08_pr_curves_{stem}.png", dpi)
    return pd.DataFrame(roc_rows).sort_values("auroc", ascending=False)


def _find_evidence_json(root: Path) -> Path | None:
    candidates = (
        root
        / "v2/experiments/exp07_llm_fusion_evidence_verification_graph/qwen3_14b/evidence_verification.json",
        root
        / "v2/experiments/exp07_llm_fusion_evidence_verification_graph/qwen3_14b/.ipynb_checkpoints/evidence_verification-checkpoint.json",
        root
        / "v2/experiments/exp06_deterministic_fusion_evidence_verification/evidence_verification.json",
    )
    return next((path for path in candidates if path.exists()), None)


def _load_evidence(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    payload = _read_json(path)
    studies: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for study in payload:
        labels = study.get("label_evidence_details") or []
        raw_policy = study.get("verification_policy_version")
        display_policy = POLICY_DISPLAY_NAMES.get(raw_policy, raw_policy)
        studies.append(
            {
                "study_key": study.get("study_key"),
                "policy": display_policy,
                "policy_raw": raw_policy,
                "overall_evidence_score": study.get("overall_evidence_score"),
                "predicted_label_count": len(study.get("predicted_labels") or []),
                "label_detail_count": len(labels),
                "supporting_snippet_count": len(study.get("supporting_evidence") or []),
                "contradicting_snippet_count": len(
                    study.get("contradicting_evidence") or []
                ),
            }
        )
        for item in labels:
            row = dict(item)
            row["study_key"] = study.get("study_key")
            row["policy"] = display_policy
            row["policy_raw"] = raw_policy
            row["supporting_snippet_count"] = len(item.get("supporting_evidence") or [])
            row["contradicting_snippet_count"] = len(
                item.get("contradicting_evidence") or []
            )
            details.append(row)
    return pd.DataFrame(studies), pd.DataFrame(details)


def plot_evidence_dashboard(
    studies: pd.DataFrame,
    details: pd.DataFrame,
    out: Path,
    dpi: int,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))

    score_counts = (
        studies.assign(
            cohort=np.where(
                studies.predicted_label_count.gt(0),
                "Has predictions",
                "No predicted labels",
            )
        )
        .groupby(["overall_evidence_score", "cohort"])
        .size()
        .unstack(fill_value=0)
        .reindex(range(1, 6), fill_value=0)
    )
    score_counts.plot.bar(
        stacked=True,
        ax=axes[0, 0],
        color=[COLORS["orange"], COLORS["blue"]][: len(score_counts.columns)],
    )
    axes[0, 0].set_title("Study-Level Evidence Scores")
    axes[0, 0].set_xlabel("Evidence score")
    axes[0, 0].set_ylabel("Studies")
    axes[0, 0].legend(frameon=False)

    label_scores = pd.crosstab(details.label, details.evidence_score).reindex(
        columns=range(1, 6), fill_value=0
    )
    label_scores = label_scores.div(label_scores.sum(axis=1), axis=0).sort_values(5)
    label_scores.plot.barh(
        stacked=True,
        ax=axes[0, 1],
        color=plt.get_cmap("RdYlGn")(np.linspace(0.08, 0.92, 5)),
        width=0.82,
    )
    axes[0, 1].set_title("Label Evidence-Score Composition")
    axes[0, 1].set_xlabel("Share of evaluated predicted labels")
    axes[0, 1].legend(title="Score", frameon=False, ncols=5, fontsize=8)

    support = pd.crosstab(details.label, details.retrieval_support).reindex(
        columns=SUPPORT_ORDER, fill_value=0
    )
    support = support.div(support.sum(axis=1), axis=0)
    support.plot.barh(
        stacked=True,
        ax=axes[1, 0],
        color=[SUPPORT_COLORS[name] for name in SUPPORT_ORDER],
        width=0.82,
    )
    axes[1, 0].set_title("Retrieval-Support Composition by Label")
    axes[1, 0].set_xlabel("Share of evaluated predicted labels")
    axes[1, 0].legend(frameon=False, ncols=3, fontsize=8)

    changed_scores = pd.crosstab(
        details.fusion_changed, details.evidence_score
    ).reindex(index=[False, True], columns=range(1, 6), fill_value=0)
    changed_scores.index = ["Unchanged", "Fusion changed"]
    changed_scores = changed_scores.div(changed_scores.sum(axis=1), axis=0)
    changed_scores.plot.barh(
        stacked=True,
        ax=axes[1, 1],
        color=plt.get_cmap("RdYlGn")(np.linspace(0.08, 0.92, 5)),
    )
    axes[1, 1].set_title("Evidence Quality: Changed vs Unchanged Labels")
    axes[1, 1].set_xlabel("Share of evaluated predicted labels")
    axes[1, 1].legend(title="Score", frameon=False, ncols=5, fontsize=8)

    fig.suptitle(
        "Evidence Verification Dashboard\nSeparate no-prediction studies from evidence-bearing studies",
        fontsize=16,
        fontweight="bold",
    )
    _save(fig, out / "09_evidence_verification_dashboard.png", dpi)


def plot_paper_evidence_figures(
    studies: pd.DataFrame,
    details: pd.DataFrame,
    out: Path,
    dpi: int,
    *,
    filename_prefix: str = "",
    title_prefix: str = "",
) -> None:
    """Export each evidence-verification result as an independent figure."""
    score_counts = (
        studies.assign(
            cohort=np.where(
                studies.predicted_label_count.gt(0),
                "Has predictions",
                "No predicted labels",
            )
        )
        .groupby(["overall_evidence_score", "cohort"])
        .size()
        .unstack(fill_value=0)
        .reindex(range(1, 6), fill_value=0)
    )
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    score_counts.plot.bar(
        stacked=True,
        ax=ax,
        color=[COLORS["orange"], COLORS["blue"]][: len(score_counts.columns)],
    )
    ax.set_xlabel("Evidence score")
    ax.set_ylabel("Studies")
    ax.set_title(f"{title_prefix}Study-Level Evidence Scores", pad=16)
    ax.legend(
        title="Study group",
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        frameon=False,
        borderaxespad=0,
    )
    ax.grid(False)
    _save_paper(
        fig, out / f"{filename_prefix}evidence_study_score_distribution", dpi
    )

    label_scores = pd.crosstab(details.label, details.evidence_score).reindex(
        columns=range(1, 6), fill_value=0
    )
    label_scores = label_scores.div(label_scores.sum(axis=1), axis=0).sort_values(5)
    fig, ax = plt.subplots(figsize=(7.2, 5.3))
    label_scores.plot.barh(
        stacked=True,
        ax=ax,
        color=plt.get_cmap("RdYlGn")(np.linspace(0.08, 0.92, 5)),
        width=0.82,
    )
    ax.set_xlabel("Share of evaluated predicted labels")
    ax.set_ylabel("")
    ax.set_title(f"{title_prefix}Label Evidence-Score Composition", pad=16)
    ax.legend(
        title="Score",
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        frameon=False,
        fontsize=8,
        borderaxespad=0,
    )
    ax.grid(False)
    _save_paper(
        fig, out / f"{filename_prefix}evidence_label_score_composition", dpi
    )

    support = pd.crosstab(details.label, details.retrieval_support).reindex(
        columns=SUPPORT_ORDER, fill_value=0
    )
    support = support.div(support.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(7.2, 5.3))
    support.plot.barh(
        stacked=True,
        ax=ax,
        color=[SUPPORT_COLORS[name] for name in SUPPORT_ORDER],
        width=0.82,
    )
    ax.set_xlabel("Share of evaluated predicted labels")
    ax.set_ylabel("")
    ax.set_title(f"{title_prefix}Retrieval-Support Composition by Label", pad=16)
    ax.legend(
        title="Support",
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        frameon=False,
        fontsize=8,
        borderaxespad=0,
    )
    ax.grid(False)
    _save_paper(
        fig, out / f"{filename_prefix}evidence_retrieval_support_by_label", dpi
    )

    changed_scores = pd.crosstab(
        details.fusion_changed, details.evidence_score
    ).reindex(index=[False, True], columns=range(1, 6), fill_value=0)
    changed_scores.index = ["Unchanged", "Fusion changed"]
    changed_scores = changed_scores.div(changed_scores.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    changed_scores.plot.barh(
        stacked=True,
        ax=ax,
        color=plt.get_cmap("RdYlGn")(np.linspace(0.08, 0.92, 5)),
    )
    ax.set_xlabel("Share of evaluated predicted labels")
    ax.set_title(
        f"{title_prefix}Evidence Quality: Changed vs Unchanged Labels", pad=16
    )
    ax.legend(
        title="Score",
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        frameon=False,
        fontsize=8,
        borderaxespad=0,
    )
    ax.grid(False)
    _save_paper(
        fig, out / f"{filename_prefix}evidence_changed_vs_unchanged", dpi
    )


def plot_paper_policy_figures(studies: pd.DataFrame, out: Path, dpi: int) -> None:
    """Export policy provenance figures with manuscript-facing policy names."""
    counts = studies.policy.value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    bars = ax.barh(counts.index, counts.values, color=COLORS["purple"])
    ax.bar_label(bars, labels=[f"{value:,}" for value in counts.values], padding=3)
    ax.set_xlabel("Studies")
    ax.set_title("Records by Evidence-Verification Method")
    ax.grid(False)
    _save_paper(fig, out / "evidence_records_by_method", dpi)

    composition = pd.crosstab(studies.policy, studies.overall_evidence_score).reindex(
        columns=range(1, 6), fill_value=0
    )
    normalized = composition.div(composition.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    normalized.plot.barh(
        stacked=True,
        ax=ax,
        color=plt.get_cmap("RdYlGn")(np.linspace(0.08, 0.92, 5)),
    )
    ax.set_xlabel("Share of studies")
    ax.set_title("Evidence-Score Composition by Verification Method", pad=16)
    ax.legend(
        title="Score",
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        frameon=False,
        fontsize=8,
        borderaxespad=0,
    )
    ax.grid(False)
    _save_paper(fig, out / "evidence_score_composition_by_method", dpi)


def plot_evidence_risk_map(details: pd.DataFrame, out: Path, dpi: int) -> None:
    summary = (
        details.groupby("label")
        .agg(
            evaluated_labels=("label", "size"),
            mean_evidence_score=("evidence_score", "mean"),
            changed_rate=("fusion_changed", "mean"),
            gray_zone_rate=("in_gray_zone", "mean"),
            mean_positive_mentions=("retrieval_positive_count", "mean"),
            mean_negative_mentions=("retrieval_negative_count", "mean"),
        )
        .reset_index()
    )
    contradiction = details.contradiction_level.ne("none").groupby(details.label).mean()
    summary["contradiction_rate"] = summary.label.map(contradiction).fillna(0)

    fig, ax = plt.subplots(figsize=(11, 7))
    points = ax.scatter(
        summary.changed_rate,
        summary.mean_evidence_score,
        s=40 + 5000 * summary.contradiction_rate,
        c=summary.gray_zone_rate,
        cmap="plasma",
        vmin=0,
        vmax=1,
        alpha=0.82,
        edgecolor="none",
    )
    for _, row in summary.iterrows():
        ax.annotate(
            row.label,
            (row.changed_rate, row.mean_evidence_score),
            xytext=(5, 3),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set_xlabel("Fusion-changed rate among evaluated labels")
    ax.set_ylabel("Mean evidence score")
    ax.set_title("Evidence Risk Map\nsize = contradiction rate; color = gray-zone rate")
    plt.colorbar(points, ax=ax, label="Gray-zone rate")
    _save(fig, out / "10_evidence_label_risk_map.png", dpi)
    summary.to_csv(out / "evidence_label_summary.csv", index=False)


def plot_evidence_policy_audit(studies: pd.DataFrame, out: Path, dpi: int) -> None:
    """Expose mixed-policy provenance instead of hiding it in aggregate plots."""
    counts = studies.policy.value_counts().sort_values()
    composition = pd.crosstab(studies.policy, studies.overall_evidence_score).reindex(
        columns=range(1, 6), fill_value=0
    )
    normalized = composition.div(composition.sum(axis=1), axis=0)

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
    bars = axes[0].barh(counts.index, counts.values, color=COLORS["purple"])
    axes[0].bar_label(bars, labels=[f"{value:,}" for value in counts.values], padding=3)
    axes[0].set_xlabel("Studies")
    axes[0].set_title("Records by Verification Policy")

    normalized.plot.barh(
        stacked=True,
        ax=axes[1],
        color=plt.get_cmap("RdYlGn")(np.linspace(0.08, 0.92, 5)),
    )
    axes[1].set_xlabel("Share of studies")
    axes[1].set_title("Evidence-Score Composition by Policy")
    axes[1].legend(title="Score", frameon=False, ncols=5)
    fig.suptitle(
        "Evidence Policy Provenance Audit\n"
        "Descriptive only—the checkpoint is not a randomized policy comparison",
        fontsize=15,
        fontweight="bold",
    )
    _save(fig, out / "11_evidence_policy_provenance.png", dpi)
    composition.to_csv(out / "evidence_policy_score_counts.csv")


def write_readme(
    out: Path,
    macro: pd.DataFrame,
    messages: list[str],
    evidence_path: Path | None,
    curve_notes: list[str],
) -> None:
    metric_table = [
        "| Experiment | Run | Macro F1 | Micro F1 |",
        "|---:|---|---:|---:|",
    ]
    for _, row in macro.iterrows():
        metric_table.append(
            f"| {int(row.experiment)} | {row.experiment_name} | "
            f"{float(row.macro_f1):.4f} | {float(row.micro_f1):.4f} |"
        )
    lines = [
        "# MEDAGENT-X Experiment 1–6 Visualization Pack",
        "",
        "## Interpretation notes",
        "",
        "- Full-test experiment bars use each experiment's final prediction run.",
        "- Paper numbering maps historical experiment folders 1, 3, 4, 5, 6, 7 to Experiments 1–6.",
        "- Experiment 5 inherits Experiment 3 labels because deterministic evidence verification does not edit predictions.",
        "- Experiment 6 uses the historical Experiment 7 Qwen predictions; evidence verification does not edit them.",
        "- ROC/PR curves describe continuous RAD-DINO probabilities, not hard-status fusion outputs.",
        "- Confusion matrices follow the repository's Judge policy and therefore cover only scoreable cells.",
        "",
        "## Artifact availability",
        "",
    ]
    lines.extend(f"- {message}" for message in messages)
    lines.extend(
        [
            f"- Evidence source: `{evidence_path}`"
            if evidence_path
            else "- No evidence JSON found.",
            "",
            "## Generated figures",
            "",
            "1. `01_experiment_metric_comparison.png`: macro precision/recall/F1 and micro F1.",
            "2. `02_macro_f1_progression.png`: headline score progression.",
            "3. `03_per_label_f1_heatmap.png`: label-wise strengths and weaknesses.",
            "4. `04_per_label_f1_delta_vs_exp01.png`: where each experiment helps or hurts.",
            "5. `05_experiment_confusion_matrices.png`: aggregate error counts.",
            "6. `06_best_experiment_label_diagnostics.png`: Experiment 4 label F1 and precision/recall.",
            "7. `07_roc_curves_*.png`: strict and conventional ROC variants.",
            "8. `08_pr_curves_*.png`: recommended for the imbalanced label setting.",
            "9. `09_evidence_verification_dashboard.png`: study and label evidence distributions.",
            "10. `10_evidence_label_risk_map.png`: labels combining intervention, gray-zone, and contradiction risk.",
            "11. `11_evidence_policy_provenance.png`: policy counts and score distributions; provenance audit only.",
            "",
            "## ROC/PR policies",
            "",
        ]
    )
    lines.extend(f"- {note}" for note in curve_notes)
    lines.extend(
        [
            "",
            "## Headline metrics used",
            "",
            *metric_table,
            "",
        ]
    )
    (out / "README.md").write_text("\n".join(lines))


def write_paper_readme(out: Path) -> None:
    lines = [
        "# Atomic conference-paper figures",
        "",
        "Every figure is exported as a 300+ DPI PNG and a vector PDF.",
        "Internal chart gridlines and white scatter-point outlines are disabled.",
        "",
        "## Paper experiment numbering",
        "",
        "| Paper experiment | Configuration | Historical source |",
        "|---:|---|---|",
        "| 1 | Vision only | exp01 |",
        "| 2 | Fusion without retrieval | exp03 |",
        "| 3 | Deterministic retrieval fusion | exp04 artifacts |",
        "| 4 | LLM retrieval fusion | exp05 |",
        "| 5 | Deterministic fusion + evidence verification | exp06; labels inherited from Exp. 3 |",
        "| 6 | Qwen fusion + LLM evidence verification | historical exp07 |",
        "",
        "## Confusion-matrix interpretation",
        "",
        "Each cell shows only the aggregate count across the 12 labels.",
        "Experiments 5 and 6 use their upstream label predictions because evidence verification assesses support but does not modify diagnostic predictions.",
        "",
        "## Evidence method names",
        "",
        "- `evidence_verification_without_LLM`",
        "- `llm_evidence_verification`",
        "",
        "The policy plots are descriptive provenance summaries because the checkpoint mixes the two methods across studies; they are not a randomized head-to-head comparison.",
        "Files beginning `exp06_qwen_` are filtered to the 491 `llm_evidence_verification` records and exclude the 415 non-LLM verification records.",
        "",
    ]
    (out / "README.md").write_text("\n".join(lines))


def write_evidence_module_readme(out: Path, without_count: int, with_count: int) -> None:
    lines = [
        "# Evidence-verification module figures",
        "",
        "The two verification methods are plotted in separate directories.",
        "No figure in these directories mixes policy records.",
        "",
        "| Directory | Paper experiment | Verification method | Studies |",
        "|---|---:|---|---:|",
        f"| `without_llm/` | 5 | `evidence_verification_without_LLM` | {without_count} |",
        f"| `with_llm_qwen/` | 6 | `llm_evidence_verification` | {with_count} |",
        "",
        "Each directory contains separate study-score, label-score, retrieval-support, and changed-vs-unchanged figures as PNG and PDF, plus the filtered study- and label-level CSV files.",
        "",
        "Important: these records come from a mixed checkpoint and represent different study subsets. The figures are descriptive module audits, not a paired or randomized comparison between policies.",
        "",
    ]
    out.mkdir(parents=True, exist_ok=True)
    (out / "README.md").write_text("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.repo_root.resolve()
    out = (
        args.output_dir or root / "v2/experiments/visualizations_exp01_exp06"
    ).resolve()
    out.mkdir(parents=True, exist_ok=True)
    _set_style()

    specs = experiment_specs(root)
    macro, per_label, messages = _load_metric_artifacts(specs)
    macro, per_label = _replace_exp6_with_qwen_metrics(root, macro, per_label)
    if macro.empty or per_label.empty:
        raise FileNotFoundError("No Experiment 1–6 Judge metrics could be loaded.")
    macro.to_csv(out / "experiment_metric_summary.csv", index=False)
    per_label.to_csv(out / "experiment_per_label_summary.csv", index=False)

    plot_experiment_metrics(macro, out, args.dpi)
    plot_macro_f1_progression(macro, out, args.dpi)
    plot_per_label_heatmaps(per_label, out, args.dpi)
    plot_experiment_confusions(per_label, out, args.dpi)
    plot_best_label_diagnostics(per_label, out, args.dpi)
    paper_out = out / "paper_figures"
    plot_paper_confusions(per_label, specs, paper_out, args.dpi)
    plot_paper_label_f1(per_label, specs, paper_out, args.dpi)
    plot_paper_best_precision_recall(per_label, paper_out, args.dpi)

    prediction_csv = (
        root
        / "v2/experiments/exp05_llm_fusion_with_retrieval_graph/vision_study_predictions.csv"
    )
    matches_csv = root / "v2/experiments/exp01_vision_only/judge_matches.csv"
    curve_notes: list[str] = []
    if prediction_csv.exists() and matches_csv.exists():
        strict = _probability_records(
            prediction_csv, matches_csv, negative_policy="explicit_absent"
        )
        strict_summary = plot_curves(
            strict,
            out,
            args.dpi,
            stem="judge_scoreable",
            title_suffix="Explicit Present vs Explicit Absent",
        )
        strict_summary.to_csv(out / "curve_metrics_judge_scoreable.csv", index=False)
        curve_notes.append(
            f"Strict Judge-compatible curves include {len(strict)} labels with at least five explicit-positive and five explicit-negative examples; sparse or single-class labels are omitted."
        )

        conventional = _probability_records(
            prediction_csv, matches_csv, negative_policy="not_present"
        )
        conventional_summary = plot_curves(
            conventional,
            out,
            args.dpi,
            stem="present_vs_not_present",
            title_suffix="Present vs All Other Statuses",
        )
        conventional_summary.to_csv(
            out / "curve_metrics_present_vs_not_present.csv", index=False
        )
        curve_notes.append(
            "Present-vs-not-present curves treat absent, uncertain, and unmentioned as negative; use these for conventional discrimination analysis, not as a reproduction of Judge F1."
        )
    else:
        curve_notes.append("ROC/PR inputs were missing, so curve figures were skipped.")

    evidence_path = _find_evidence_json(root)
    if evidence_path is not None:
        studies, details = _load_evidence(evidence_path)
        studies.to_csv(out / "evidence_study_summary.csv", index=False)
        details.to_csv(out / "evidence_label_details.csv", index=False)
        if not studies.empty and not details.empty:
            plot_evidence_dashboard(studies, details, out, args.dpi)
            plot_evidence_risk_map(details, out, args.dpi)
            plot_evidence_policy_audit(studies, out, args.dpi)
            plot_paper_evidence_figures(studies, details, paper_out, args.dpi)
            qwen_studies = studies[
                studies.policy.eq("llm_evidence_verification")
            ].copy()
            qwen_details = details[
                details.policy.eq("llm_evidence_verification")
            ].copy()
            without_llm_studies = studies[
                studies.policy.eq("evidence_verification_without_LLM")
            ].copy()
            without_llm_details = details[
                details.policy.eq("evidence_verification_without_LLM")
            ].copy()
            if not qwen_studies.empty and not qwen_details.empty:
                plot_paper_evidence_figures(
                    qwen_studies,
                    qwen_details,
                    paper_out,
                    args.dpi,
                    filename_prefix="exp06_qwen_",
                    title_prefix="Experiment 6 Qwen: ",
                )
            evidence_module_out = paper_out / "evidence_module"
            without_llm_out = evidence_module_out / "without_llm"
            with_llm_out = evidence_module_out / "with_llm_qwen"
            if not without_llm_studies.empty and not without_llm_details.empty:
                without_llm_out.mkdir(parents=True, exist_ok=True)
                without_llm_studies.to_csv(
                    without_llm_out / "evidence_studies.csv", index=False
                )
                without_llm_details.to_csv(
                    without_llm_out / "evidence_label_details.csv", index=False
                )
                plot_paper_evidence_figures(
                    without_llm_studies,
                    without_llm_details,
                    without_llm_out,
                    args.dpi,
                    title_prefix="Experiment 5 Without LLM: ",
                )
            if not qwen_studies.empty and not qwen_details.empty:
                with_llm_out.mkdir(parents=True, exist_ok=True)
                qwen_studies.to_csv(
                    with_llm_out / "evidence_studies.csv", index=False
                )
                qwen_details.to_csv(
                    with_llm_out / "evidence_label_details.csv", index=False
                )
                plot_paper_evidence_figures(
                    qwen_studies,
                    qwen_details,
                    with_llm_out,
                    args.dpi,
                    title_prefix="Experiment 6 With LLM (Qwen): ",
                )
            write_evidence_module_readme(
                evidence_module_out,
                without_count=len(without_llm_studies),
                with_count=len(qwen_studies),
            )
            plot_paper_policy_figures(studies, paper_out, args.dpi)
            policy_counts = studies.policy.value_counts()
            messages.append(
                "Evidence checkpoint mixes verification policies: "
                + ", ".join(
                    f"{policy}={int(count)}" for policy, count in policy_counts.items()
                )
                + ". Aggregate evidence plots must be interpreted as descriptive, not as a clean policy comparison."
            )

    write_readme(out, macro, messages, evidence_path, curve_notes)
    write_paper_readme(paper_out)
    print(f"[VisualizeExp01Exp06] wrote visualization pack -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
