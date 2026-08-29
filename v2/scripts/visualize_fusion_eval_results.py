"""Create visualization artifacts for MEDAGENT-X fusion evaluation outputs."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "medagentx_mplconfig"),
)
os.environ.setdefault(
    "XDG_CACHE_HOME",
    str(Path(tempfile.gettempdir()) / "medagentx_cache"),
)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


RUN_ORDER = (
    "vision_full",
    "fusion_full",
    "vision_gray_zone",
    "fusion_gray_zone",
)
RUN_LABELS = {
    "vision_full": "Vision Full",
    "fusion_full": "Fusion Full",
    "vision_gray_zone": "Vision Gray Zone",
    "fusion_gray_zone": "Fusion Gray Zone",
}
COLORS = {
    "vision": "#4C78A8",
    "fusion": "#F58518",
    "positive": "#2F7D32",
    "negative": "#B23A48",
    "neutral": "#6E7781",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Visualize vision-vs-fusion evaluation results."
    )
    parser.add_argument(
        "--eval-dir",
        type=Path,
        required=True,
        help="Directory containing judge_summary.json and metric CSVs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Defaults to eval-dir/visualizations.",
    )
    parser.add_argument(
        "--title",
        default="MEDAGENT-X Fusion Evaluation",
        help="Title prefix used in generated figures.",
    )
    return parser


def _save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def _load_inputs(eval_dir: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    judge_path = eval_dir / "judge_summary.json"
    per_label_path = eval_dir / "per_label_metrics.csv"
    changes_path = eval_dir / "fusion_change_analysis.csv"
    status_confusion_path = eval_dir / "status_confusion_by_label.csv"
    required = (
        judge_path,
        per_label_path,
        changes_path,
        status_confusion_path,
    )
    for path in required:
        if not path.exists():
            raise FileNotFoundError(f"Missing required evaluation artifact: {path}")
    judge = json.loads(judge_path.read_text())
    per_label = pd.read_csv(per_label_path)
    changes = pd.read_csv(changes_path)
    status_confusion = pd.read_csv(status_confusion_path)
    return judge, per_label, changes, status_confusion


def _judge_frame(judge: dict) -> pd.DataFrame:
    frame = pd.DataFrame(judge["runs"])
    frame["display_name"] = frame["name"].map(RUN_LABELS).fillna(frame["name"])
    frame["run_order"] = frame["name"].map(
        {name: index for index, name in enumerate(RUN_ORDER)}
    )
    return frame.sort_values("run_order")


def plot_macro_metrics(judge_frame: pd.DataFrame, output_dir: Path, title: str) -> None:
    metrics = [
        ("macro_f1", "Macro F1"),
        ("macro_precision", "Macro Precision"),
        ("macro_recall", "Macro Recall"),
    ]
    x = np.arange(len(metrics))
    width = 0.18
    fig, ax = plt.subplots(figsize=(11, 6))
    offsets = np.linspace(-1.5 * width, 1.5 * width, len(RUN_ORDER))
    for offset, run_name in zip(offsets, RUN_ORDER):
        row = judge_frame[judge_frame["name"].eq(run_name)]
        if row.empty:
            continue
        values = [float(row.iloc[0][metric]) for metric, _ in metrics]
        color = COLORS["fusion"] if run_name.startswith("fusion") else COLORS["vision"]
        alpha = 1.0 if "full" in run_name else 0.55
        bars = ax.bar(
            x + offset,
            values,
            width,
            label=RUN_LABELS[run_name],
            color=color,
            alpha=alpha,
        )
        ax.bar_label(bars, labels=[f"{value:.3f}" for value in values], fontsize=8)
    ax.set_title(f"{title}: Macro Metrics")
    ax.set_ylabel("Score")
    ax.set_ylim(0, 1.0)
    ax.set_xticks(x)
    ax.set_xticklabels([label for _, label in metrics])
    ax.legend(ncols=2, frameon=False)
    ax.grid(axis="y", color="#D8DEE4", linewidth=0.8)
    _save(fig, output_dir / "macro_metrics.png")


def _paired_metric_delta(
    per_label: pd.DataFrame,
    *,
    scope: str,
    metric: str,
) -> pd.DataFrame:
    vision = per_label[
        per_label["run_name"].eq(f"vision_{scope}")
        & per_label["eval_scope"].eq(scope)
    ][["label", metric, "precision", "recall", "tp", "fp", "fn"]]
    fusion = per_label[
        per_label["run_name"].eq(f"fusion_{scope}")
        & per_label["eval_scope"].eq(scope)
    ][["label", metric, "precision", "recall", "tp", "fp", "fn"]]
    merged = vision.merge(
        fusion,
        on="label",
        suffixes=("_vision", "_fusion"),
    )
    merged[f"{metric}_delta"] = merged[f"{metric}_fusion"] - merged[f"{metric}_vision"]
    merged["recall_delta"] = merged["recall_fusion"] - merged["recall_vision"]
    merged["precision_delta"] = (
        merged["precision_fusion"] - merged["precision_vision"]
    )
    merged["tp_delta"] = merged["tp_fusion"] - merged["tp_vision"]
    merged["fp_delta"] = merged["fp_fusion"] - merged["fp_vision"]
    merged["fn_delta"] = merged["fn_fusion"] - merged["fn_vision"]
    return merged.sort_values(f"{metric}_delta", ascending=True)


def plot_label_benefit(
    per_label: pd.DataFrame,
    output_dir: Path,
    title: str,
    *,
    scope: str,
) -> pd.DataFrame:
    deltas = _paired_metric_delta(per_label, scope=scope, metric="f1")
    colors = [
        COLORS["positive"] if value >= 0 else COLORS["negative"]
        for value in deltas["f1_delta"]
    ]
    fig, ax = plt.subplots(figsize=(10, 7))
    bars = ax.barh(deltas["label"], deltas["f1_delta"], color=colors)
    ax.axvline(0, color="#24292F", linewidth=1)
    ax.bar_label(
        bars,
        labels=[f"{value:+.3f}" for value in deltas["f1_delta"]],
        fontsize=8,
        padding=3,
    )
    ax.set_title(f"{title}: Fusion F1 Benefit ({scope.replace('_', ' ').title()})")
    ax.set_xlabel("Fusion F1 minus Vision F1")
    ax.grid(axis="x", color="#D8DEE4", linewidth=0.8)
    _save(fig, output_dir / f"per_label_f1_delta_{scope}.png")
    return deltas


def plot_motivation_graph(
    full_deltas: pd.DataFrame,
    changes: pd.DataFrame,
    output_dir: Path,
    title: str,
) -> None:
    merged = full_deltas.merge(changes, on="label", how="left")
    merged = merged.sort_values("f1_delta", ascending=False)
    x = np.arange(len(merged))
    fig, ax1 = plt.subplots(figsize=(13, 6))
    bars = ax1.bar(
        x,
        merged["f1_delta"],
        color=[
            COLORS["positive"] if value >= 0 else COLORS["negative"]
            for value in merged["f1_delta"]
        ],
        alpha=0.85,
        label="F1 delta",
    )
    ax1.axhline(0, color="#24292F", linewidth=1)
    ax1.bar_label(
        bars,
        labels=[f"{value:+.3f}" for value in merged["f1_delta"]],
        fontsize=8,
        rotation=90,
        padding=2,
    )
    ax1.set_ylabel("Fusion F1 minus Vision F1")
    ax1.set_xticks(x)
    ax1.set_xticklabels(merged["label"], rotation=45, ha="right")
    ax1.grid(axis="y", color="#D8DEE4", linewidth=0.8)

    ax2 = ax1.twinx()
    ax2.plot(
        x,
        merged["net_tp_change"],
        color="#0B7285",
        marker="o",
        linewidth=2,
        label="Net TP change",
    )
    ax2.plot(
        x,
        merged["net_fp_change"],
        color="#C2410C",
        marker="s",
        linewidth=2,
        label="Net FP change",
    )
    ax2.set_ylabel("Cell count change")
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, frameon=False, loc="upper right")
    ax1.set_title(f"{title}: Which Labels Benefitted Most From Fusion")
    _save(fig, output_dir / "fusion_benefit_motivation.png")


def _aggregate_confusion(per_label: pd.DataFrame, run_name: str, scope: str) -> np.ndarray:
    subset = per_label[
        per_label["run_name"].eq(run_name) & per_label["eval_scope"].eq(scope)
    ]
    totals = subset[["tp", "fn", "fp", "tn"]].sum()
    return np.array(
        [
            [totals["tp"], totals["fn"]],
            [totals["fp"], totals["tn"]],
        ],
        dtype=float,
    )


def _plot_heatmap(
    ax: plt.Axes,
    matrix: np.ndarray,
    *,
    title: str,
    row_labels: tuple[str, str],
    col_labels: tuple[str, str],
) -> None:
    im = ax.imshow(matrix, cmap="Blues")
    ax.set_title(title)
    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_xticklabels(col_labels)
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_yticklabels(row_labels)
    total = matrix.sum()
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            value = matrix[row, col]
            pct = value / total if total else 0
            ax.text(
                col,
                row,
                f"{int(value):,}\n{pct:.1%}",
                ha="center",
                va="center",
                color="#0B1F33",
                fontsize=10,
            )
    return im


def plot_binary_confusions(
    per_label: pd.DataFrame,
    output_dir: Path,
    title: str,
    *,
    scope: str,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8))
    matrices = [
        ("vision", _aggregate_confusion(per_label, f"vision_{scope}", scope)),
        ("fusion", _aggregate_confusion(per_label, f"fusion_{scope}", scope)),
    ]
    for ax, (name, matrix) in zip(axes, matrices):
        _plot_heatmap(
            ax,
            matrix,
            title=f"{name.title()} {scope.replace('_', ' ').title()}",
            row_labels=("GT Present", "GT Absent"),
            col_labels=("Pred Present", "Pred Absent"),
        )
    fig.suptitle(f"{title}: Aggregate Confusion Matrices")
    _save(fig, output_dir / f"confusion_matrix_{scope}.png")


def _status_matrix(
    status_confusion: pd.DataFrame,
    *,
    run_name: str,
    scope: str,
) -> pd.DataFrame:
    subset = status_confusion[
        status_confusion["run_name"].eq(run_name)
        & status_confusion["eval_scope"].eq(scope)
    ]
    return subset.pivot_table(
        index="gt_status",
        columns="pred_status",
        values="cell_count",
        aggfunc="sum",
        fill_value=0,
    )


def plot_status_confusions(
    status_confusion: pd.DataFrame,
    output_dir: Path,
    title: str,
    *,
    scope: str,
) -> None:
    gt_order = ["present", "absent", "uncertain", "unmentioned"]
    pred_order = ["present", "absent", "uncertain"]
    matrices = []
    for run_name in (f"vision_{scope}", f"fusion_{scope}"):
        matrix = _status_matrix(status_confusion, run_name=run_name, scope=scope)
        matrix = matrix.reindex(index=gt_order, columns=pred_order, fill_value=0)
        matrices.append((run_name, matrix))

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2))
    vmax = max(matrix.to_numpy().max() for _, matrix in matrices)
    for ax, (run_name, matrix) in zip(axes, matrices):
        im = ax.imshow(matrix.to_numpy(), cmap="Purples", vmax=vmax)
        ax.set_title(RUN_LABELS.get(run_name, run_name))
        ax.set_xticks(np.arange(len(pred_order)))
        ax.set_xticklabels(pred_order, rotation=30, ha="right")
        ax.set_yticks(np.arange(len(gt_order)))
        ax.set_yticklabels(gt_order)
        for row in range(matrix.shape[0]):
            for col in range(matrix.shape[1]):
                ax.text(
                    col,
                    row,
                    f"{int(matrix.iloc[row, col]):,}",
                    ha="center",
                    va="center",
                    color="#0B1F33",
                    fontsize=9,
                )
    fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.85)
    fig.suptitle(f"{title}: Status Confusion ({scope.replace('_', ' ').title()})")
    _save(fig, output_dir / f"status_confusion_{scope}.png")


def write_summary_tables(
    judge_frame: pd.DataFrame,
    full_deltas: pd.DataFrame,
    gray_deltas: pd.DataFrame,
    changes: pd.DataFrame,
    output_dir: Path,
) -> None:
    judge_frame[
        [
            "name",
            "eval_scope",
            "macro_f1",
            "macro_precision",
            "macro_recall",
            "micro_f1",
            "coverage",
        ]
    ].to_csv(output_dir / "macro_summary.csv", index=False)

    full_summary = full_deltas.merge(changes, on="label", how="left")
    full_summary.to_csv(output_dir / "per_label_fusion_benefit_full.csv", index=False)
    gray_deltas.to_csv(output_dir / "per_label_fusion_benefit_gray_zone.csv", index=False)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    eval_dir = args.eval_dir.resolve()
    output_dir = (args.output_dir or (eval_dir / "visualizations")).resolve()
    judge, per_label, changes, status_confusion = _load_inputs(eval_dir)
    judge_frame = _judge_frame(judge)

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_macro_metrics(judge_frame, output_dir, args.title)
    full_deltas = plot_label_benefit(
        per_label,
        output_dir,
        args.title,
        scope="full",
    )
    gray_deltas = plot_label_benefit(
        per_label,
        output_dir,
        args.title,
        scope="gray_zone",
    )
    plot_motivation_graph(full_deltas, changes, output_dir, args.title)
    plot_binary_confusions(per_label, output_dir, args.title, scope="full")
    plot_binary_confusions(per_label, output_dir, args.title, scope="gray_zone")
    plot_status_confusions(status_confusion, output_dir, args.title, scope="full")
    plot_status_confusions(
        status_confusion,
        output_dir,
        args.title,
        scope="gray_zone",
    )
    write_summary_tables(
        judge_frame,
        full_deltas,
        gray_deltas,
        changes,
        output_dir,
    )
    print(f"[Visualize] wrote figures and summary tables -> {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
