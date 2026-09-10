"""Recompute aggregate Judge metrics for a selected label subset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from medagentx.labels.constants import CHEXPERT_COMPETITION_LABELS


DEFAULT_INPUT = Path(
    "v2/experiments/exp05_llm_fusion_with_retrieval_graph/"
    "judge_evaluation/per_label_metrics.csv"
)
DEFAULT_RUN_CONFIG = Path(
    "v2/experiments/exp05_llm_fusion_with_retrieval_graph/run_config.json"
)
DEFAULT_OUTPUT_DIR = Path(
    "v2/experiments/exp15_competition_exp05_fusion/exp05_reference"
)
DEFAULT_RUNS = ("vision_full", "fusion_full")


def _safe_div(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None
    return 2.0 * precision * recall / (precision + recall)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize_label_subset(
    metrics: pd.DataFrame,
    *,
    labels: tuple[str, ...],
    run_names: tuple[str, ...],
    study_count: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Filter per-label rows and recompute macro/micro aggregate metrics."""
    required = {
        "run_name",
        "label",
        "eval_scope",
        "scoreable_cells",
        "tp",
        "fp",
        "fn",
        "precision",
        "recall",
        "f1",
    }
    missing = sorted(required - set(metrics.columns))
    if missing:
        raise ValueError(f"per-label metrics missing columns: {missing}")
    if study_count <= 0:
        raise ValueError("study_count must be > 0")

    selected = metrics[
        metrics["run_name"].isin(run_names) & metrics["label"].isin(labels)
    ].copy()
    expected = {(run_name, label) for run_name in run_names for label in labels}
    actual = set(zip(selected["run_name"], selected["label"]))
    if actual != expected:
        raise ValueError(
            "Missing or unexpected run/label rows: "
            f"missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )

    selected["label"] = pd.Categorical(
        selected["label"], categories=labels, ordered=True
    )
    selected["run_name"] = pd.Categorical(
        selected["run_name"], categories=run_names, ordered=True
    )
    selected = selected.sort_values(["run_name", "label"]).reset_index(drop=True)

    summary_rows: list[dict[str, object]] = []
    for run_name in run_names:
        rows = selected[selected["run_name"] == run_name]
        tp = int(pd.to_numeric(rows["tp"]).sum())
        fp = int(pd.to_numeric(rows["fp"]).sum())
        fn = int(pd.to_numeric(rows["fn"]).sum())
        scoreable = int(pd.to_numeric(rows["scoreable_cells"]).sum())
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        summary_rows.append(
            {
                "run_name": run_name,
                "label_count": len(labels),
                "study_count": study_count,
                "total_cells": study_count * len(labels),
                "scoreable_cells": scoreable,
                "coverage": scoreable / (study_count * len(labels)),
                "macro_precision": _mean(rows["precision"].dropna().astype(float).tolist()),
                "macro_recall": _mean(rows["recall"].dropna().astype(float).tolist()),
                "macro_f1": _mean(rows["f1"].dropna().astype(float).tolist()),
                "micro_precision": precision,
                "micro_recall": recall,
                "micro_f1": _f1(precision, recall),
                "tp": tp,
                "fp": fp,
                "fn": fn,
            }
        )
    return selected, pd.DataFrame(summary_rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recompute Judge aggregates for the five competition labels."
    )
    parser.add_argument("--per-label-metrics", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--run-config", type=Path, default=DEFAULT_RUN_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-names", nargs="+", default=list(DEFAULT_RUNS))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.per_label_metrics.is_file():
        raise FileNotFoundError(args.per_label_metrics)
    if not args.run_config.is_file():
        raise FileNotFoundError(args.run_config)
    run_config = json.loads(args.run_config.read_text(encoding="utf-8"))
    study_count = int(run_config["study_count"])
    selected, summary = summarize_label_subset(
        pd.read_csv(args.per_label_metrics),
        labels=CHEXPERT_COMPETITION_LABELS,
        run_names=tuple(args.run_names),
        study_count=study_count,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    selected.to_csv(args.output_dir / "per_label_metrics.csv", index=False)
    summary.to_csv(args.output_dir / "summary.csv", index=False)
    payload = {
        "source_per_label_metrics": str(args.per_label_metrics),
        "source_run_config": str(args.run_config),
        "labels": list(CHEXPERT_COMPETITION_LABELS),
        "study_count": study_count,
        "runs": summary.to_dict(orient="records"),
        "comparison_limitations": [
            "Ground truth is report-derived rather than expert image labels.",
            "Uncertain and unmentioned ground-truth cells are not binary-scoreable.",
            "Coverage is therefore lower than the competition test coverage.",
        ],
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for row in summary.to_dict(orient="records"):
        print(
            f"[JudgeSubset] {row['run_name']}: "
            f"macro_f1={row['macro_f1']:.4f} "
            f"macro_precision={row['macro_precision']:.4f} "
            f"macro_recall={row['macro_recall']:.4f} "
            f"coverage={row['coverage']:.4f}",
            flush=True,
        )
    print(f"[JudgeSubset] wrote results -> {args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
