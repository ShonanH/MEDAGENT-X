from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


CHEXPERT_LABELS = [
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
    "Pneumonia",
    "Pneumothorax",
    "Fracture",
    "Lung Lesion",
    "Lung Opacity",
    "Enlarged Cardiomediastinum",
    "Pleural Other",
    "Support Devices",
    "No Finding",
]

NON_DISEASE_LABELS = {"Support Devices", "No Finding"}

STATUS_ORDER = ["present", "absent", "uncertain"]
DECISION_ORDER = ["concordant", "partially_concordant", "discordant"]


DEFAULT_OUTPUT_DIR = "outputs/chexpert_plus/paper_figures"
DEFAULT_BATCH_DIR = "outputs/chexpert_plus/batch_first_100"
DEFAULT_ENSEMBLE_PREDICTIONS = (
    "outputs/chexpert_plus/fusion_classifier/ensemble_classifier_predictions.csv"
)
DEFAULT_FUSION_TRAINING_METRICS = (
    "outputs/chexpert_plus/fusion_classifier/fusion_training_metrics.csv"
)


def clean_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def parse_json_cell(value: Any, default: Any) -> Any:
    text = clean_string(value)
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def read_optional_csv(path: str) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()

    csv_path = Path(path)
    if not csv_path.exists():
        print(f"[WARN] Missing optional CSV: {csv_path}")
        return pd.DataFrame()

    return pd.read_csv(csv_path, dtype=str)


def as_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def ensure_output_dirs(output_dir: str) -> tuple[Path, Path, Path]:
    base = Path(output_dir)
    figures = base / "figures"
    tables = base / "tables"
    base.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    return base, figures, tables


def save_figure(fig: plt.Figure, figures_dir: Path, name: str) -> None:
    pdf_path = figures_dir / f"{name}.pdf"
    png_path = figures_dir / f"{name}.png"

    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=600, bbox_inches="tight")
    plt.close(fig)

    print(f"[FIG] {pdf_path}")
    print(f"[FIG] {png_path}")


def setup_plot_style() -> None:
    sns.set_theme(
        context="paper",
        style="whitegrid",
        font="DejaVu Sans",
        rc={
            "figure.dpi": 160,
            "savefig.dpi": 600,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        },
    )


def load_batch_retrieval_results(batch_dir: str) -> pd.DataFrame:
    tmp_dir = Path(batch_dir) / "tmp"
    if not tmp_dir.exists():
        return pd.DataFrame()

    files = sorted(tmp_dir.glob("*_retrieval_results.csv"))
    if not files:
        return pd.DataFrame()

    frames = [pd.read_csv(path, dtype=str) for path in files]
    combined = pd.concat(frames, ignore_index=True)
    print(f"[INFO] Combined {len(files)} batch retrieval CSVs ({len(combined)} rows)")
    return combined


def resolve_batch_paths(batch_dir: str) -> dict[str, str]:
    batch_path = Path(batch_dir)
    return {
        "judge_results": str(batch_path / "judge_results_first_100.csv"),
        "disease_reasoning": str(batch_path / "disease_reasoning_results_first_100.csv"),
    }


def plot_ensemble_figures(classifier_df: pd.DataFrame, figures_dir: Path, tables_dir: Path) -> None:
    if classifier_df.empty:
        return

    agreement_cols = [col for col in classifier_df.columns if col.startswith("ensemble_agreement_")]
    if agreement_cols:
        rows = []
        for col in agreement_cols:
            label = col.replace("ensemble_agreement_", "").replace("_", " ").title()
            for agreement, count in classifier_df[col].fillna("missing").value_counts().items():
                rows.append({"label": label, "agreement": agreement, "count": count})

        agreement_df = pd.DataFrame(rows)
        agreement_df.to_csv(tables_dir / "ensemble_agreement_counts.csv", index=False)

        fig, ax = plt.subplots(figsize=(6.8, 3.2))
        sns.barplot(data=agreement_df, y="label", x="count", hue="agreement", ax=ax, palette="Set2")
        ax.set_title("DenseNet vs Fusion Agreement by Label")
        ax.set_xlabel("Count")
        ax.set_ylabel("")
        ax.legend(title="Agreement", loc="lower right")
        save_figure(fig, figures_dir, "ensemble_agreement_distribution")

    source_cols = {
        "densenet_prob_": "DenseNet",
        "fusion_prob_": "Fusion",
        "ensemble_prob_": "Ensemble",
    }

    long_rows = []
    for prefix, source in source_cols.items():
        prob_cols = [col for col in classifier_df.columns if col.startswith(prefix)]
        for col in prob_cols:
            label = col.replace(prefix, "").replace("_", " ").title()
            values = as_numeric(classifier_df[col]).dropna()
            for value in values:
                long_rows.append({"label": label, "source": source, "probability": value})

    if long_rows:
        compare_df = pd.DataFrame(long_rows)
        compare_df.to_csv(tables_dir / "classifier_source_probability_long.csv", index=False)

        fig, ax = plt.subplots(figsize=(6.8, 3.2))
        sns.boxplot(data=compare_df, y="label", x="probability", hue="source", ax=ax, palette="Set2")
        ax.set_title("Classifier Probability by Source")
        ax.set_xlabel("Probability")
        ax.set_ylabel("")
        ax.set_xlim(-0.02, 1.02)
        ax.legend(title="Source", loc="lower right")
        save_figure(fig, figures_dir, "classifier_source_probability_boxplot")


def plot_fusion_training_figures(metrics_path: str, figures_dir: Path) -> None:
    metrics_file = Path(metrics_path)
    if not metrics_file.exists():
        print(f"[WARN] Missing fusion training metrics: {metrics_file}")
        return

    metrics_df = pd.read_csv(metrics_file)
    if metrics_df.empty:
        return

    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    ax.plot(metrics_df["epoch"], metrics_df["train_loss"], marker="o", label="Train loss")
    ax.set_title("Fusion Training Loss")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Loss")
    ax.legend()
    save_figure(fig, figures_dir, "fusion_training_loss_curve")

    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    ax.plot(metrics_df["epoch"], metrics_df["val_macro_f1"], marker="o", label="Val macro F1")
    ax.plot(metrics_df["epoch"], metrics_df["val_micro_f1"], marker="o", label="Val micro F1")
    ax.set_title("Fusion Validation F1")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("F1")
    ax.legend()
    save_figure(fig, figures_dir, "fusion_validation_f1_curve")


def plot_count_bar(
    counts: pd.Series,
    figures_dir: Path,
    name: str,
    title: str,
    xlabel: str,
    ylabel: str = "Count",
    order: list[str] | None = None,
) -> None:
    if counts.empty:
        return

    if order:
        counts = counts.reindex(order).dropna()

    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    palette = sns.color_palette("Set2", n_colors=max(len(counts), 1))
    sns.barplot(x=counts.index, y=counts.values, ax=ax, palette=palette)

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=25)

    for container in ax.containers:
        ax.bar_label(container, fontsize=7, padding=2)

    save_figure(fig, figures_dir, name)


def summarize_judge_results(judge_df: pd.DataFrame, tables_dir: Path) -> pd.DataFrame:
    if judge_df.empty:
        return pd.DataFrame()

    numeric_cols = [
        "label_macro_score",
        "disease_precision",
        "disease_recall",
        "disease_f1",
        "all_label_precision",
        "all_label_recall",
        "all_label_f1",
        "exact_label_match_count",
        "partial_label_match_count",
        "mismatch_label_count",
        "evaluable_label_count",
    ]

    for col in numeric_cols:
        if col in judge_df.columns:
            judge_df[col] = as_numeric(judge_df[col])

    summary_rows = []

    for col in [
        "label_macro_score",
        "disease_precision",
        "disease_recall",
        "disease_f1",
        "all_label_precision",
        "all_label_recall",
        "all_label_f1",
    ]:
        if col not in judge_df.columns:
            continue

        values = judge_df[col].dropna()
        if values.empty:
            continue

        summary_rows.append(
            {
                "metric": col,
                "n": int(values.shape[0]),
                "mean": values.mean(),
                "std": values.std(ddof=1),
                "median": values.median(),
                "min": values.min(),
                "max": values.max(),
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(tables_dir / "judge_metric_summary.csv", index=False)

    if "judge_decision" in judge_df.columns:
        decision_counts = (
            judge_df["judge_decision"]
            .fillna("missing")
            .value_counts()
            .rename_axis("judge_decision")
            .reset_index(name="count")
        )
        decision_counts.to_csv(tables_dir / "judge_decision_counts.csv", index=False)

    return summary_df


def build_per_label_table(judge_df: pd.DataFrame, tables_dir: Path) -> pd.DataFrame:
    rows = []

    if judge_df.empty or "per_label_judgment_json" not in judge_df.columns:
        return pd.DataFrame()

    for _, case in judge_df.iterrows():
        study_key = clean_string(case.get("study_key"))
        dicom_path = clean_string(case.get("dicom_path"))
        per_label = parse_json_cell(case.get("per_label_judgment_json"), [])

        for item in per_label:
            if not isinstance(item, dict):
                continue

            label = clean_string(item.get("label"))
            if label not in CHEXPERT_LABELS:
                continue

            predicted = clean_string(item.get("predicted_status")).lower()
            ground_truth = clean_string(item.get("ground_truth_status")).lower()
            match_type = clean_string(item.get("match_type")).lower()

            rows.append(
                {
                    "study_key": study_key,
                    "dicom_path": dicom_path,
                    "label": label,
                    "label_group": "non_disease" if label in NON_DISEASE_LABELS else "disease",
                    "predicted_status": predicted,
                    "ground_truth_status": ground_truth,
                    "match_type": match_type,
                    "is_true_positive": int(predicted == "present" and ground_truth == "present"),
                    "is_false_positive": int(predicted == "present" and ground_truth != "present"),
                    "is_false_negative": int(predicted != "present" and ground_truth == "present"),
                    "is_true_negative": int(predicted != "present" and ground_truth != "present"),
                }
            )

    table = pd.DataFrame(rows)
    table.to_csv(tables_dir / "judge_per_label_long.csv", index=False)

    if table.empty:
        return table

    per_label_summary = (
        table.groupby(["label", "label_group"], as_index=False)
        .agg(
            true_positive=("is_true_positive", "sum"),
            false_positive=("is_false_positive", "sum"),
            false_negative=("is_false_negative", "sum"),
            true_negative=("is_true_negative", "sum"),
            exact=("match_type", lambda s: int((s == "exact").sum())),
            partial=("match_type", lambda s: int((s == "partial").sum())),
            mismatch=("match_type", lambda s: int((s == "mismatch").sum())),
            not_evaluable=("match_type", lambda s: int((s == "not_evaluable").sum())),
            cases=("study_key", "count"),
        )
    )

    per_label_summary["precision"] = per_label_summary["true_positive"] / (
        per_label_summary["true_positive"] + per_label_summary["false_positive"]
    ).replace(0, np.nan)

    per_label_summary["recall"] = per_label_summary["true_positive"] / (
        per_label_summary["true_positive"] + per_label_summary["false_negative"]
    ).replace(0, np.nan)

    per_label_summary["f1"] = (
        2
        * per_label_summary["precision"]
        * per_label_summary["recall"]
        / (per_label_summary["precision"] + per_label_summary["recall"]).replace(0, np.nan)
    )

    per_label_summary = per_label_summary.fillna(0.0)
    per_label_summary.to_csv(tables_dir / "judge_per_label_summary.csv", index=False)

    return table


def plot_judge_figures(judge_df: pd.DataFrame, per_label_df: pd.DataFrame, figures_dir: Path) -> None:
    if judge_df.empty:
        return

    if "judge_decision" in judge_df.columns:
        counts = judge_df["judge_decision"].fillna("missing").value_counts()
        plot_count_bar(
            counts=counts,
            figures_dir=figures_dir,
            name="judge_decision_distribution",
            title="Judge Decision Distribution",
            xlabel="Judge Decision",
            order=DECISION_ORDER,
        )

    metric_cols = [
        col
        for col in ["disease_precision", "disease_recall", "disease_f1", "label_macro_score"]
        if col in judge_df.columns
    ]

    if metric_cols:
        metric_df = judge_df[metric_cols].apply(as_numeric)
        long_df = metric_df.melt(var_name="metric", value_name="value").dropna()

        fig, ax = plt.subplots(figsize=(3.4, 2.4))
        sns.boxplot(data=long_df, x="metric", y="value", ax=ax, color="#8fb9a8")
        sns.stripplot(data=long_df, x="metric", y="value", ax=ax, color="#2f3e46", size=2, alpha=0.5)
        ax.set_title("Judge Metric Distribution")
        ax.set_xlabel("")
        ax.set_ylabel("Score")
        ax.set_ylim(-0.05, 1.05)
        ax.tick_params(axis="x", rotation=25)
        save_figure(fig, figures_dir, "judge_metric_boxplot")

    if per_label_df.empty:
        return

    status_matrix = pd.crosstab(
        per_label_df["ground_truth_status"],
        per_label_df["predicted_status"],
    ).reindex(index=STATUS_ORDER, columns=STATUS_ORDER, fill_value=0)

    fig, ax = plt.subplots(figsize=(3.2, 2.8))
    sns.heatmap(status_matrix, annot=True, fmt="d", cmap="Blues", cbar=False, ax=ax)
    ax.set_title("Aggregate Label Status Matrix")
    ax.set_xlabel("Predicted Status")
    ax.set_ylabel("Ground Truth Status")
    save_figure(fig, figures_dir, "judge_status_confusion_matrix")

    disease_df = per_label_df[per_label_df["label_group"] == "disease"].copy()
    if not disease_df.empty:
        match_counts = (
            disease_df.groupby(["label", "match_type"])
            .size()
            .reset_index(name="count")
        )

        fig, ax = plt.subplots(figsize=(6.8, 3.2))
        sns.barplot(
            data=match_counts,
            y="label",
            x="count",
            hue="match_type",
            ax=ax,
            palette="Set2",
        )
        ax.set_title("Per-Label Disease Judgment Outcomes")
        ax.set_xlabel("Count")
        ax.set_ylabel("")
        ax.legend(title="Match Type", loc="lower right")
        save_figure(fig, figures_dir, "judge_per_label_match_outcomes")

        tp_fp_fn = (
            disease_df.groupby("label", as_index=False)
            .agg(
                true_positive=("is_true_positive", "sum"),
                false_positive=("is_false_positive", "sum"),
                false_negative=("is_false_negative", "sum"),
            )
        )
        tp_fp_fn_long = tp_fp_fn.melt(
            id_vars="label",
            value_vars=["true_positive", "false_positive", "false_negative"],
            var_name="outcome",
            value_name="count",
        )

        fig, ax = plt.subplots(figsize=(6.8, 3.2))
        sns.barplot(
            data=tp_fp_fn_long,
            y="label",
            x="count",
            hue="outcome",
            ax=ax,
            palette=["#4c956c", "#d68c45", "#c44900"],
        )
        ax.set_title("Per-Label Present-Finding Errors")
        ax.set_xlabel("Count")
        ax.set_ylabel("")
        ax.legend(title="Outcome", loc="lower right")
        save_figure(fig, figures_dir, "judge_per_label_tp_fp_fn")


def plot_quality_gate_figures(quality_df: pd.DataFrame, figures_dir: Path, tables_dir: Path) -> None:
    if quality_df.empty:
        return

    if "quality_gate_decision" in quality_df.columns:
        counts = quality_df["quality_gate_decision"].fillna("missing").value_counts()
        counts.rename_axis("quality_gate_decision").reset_index(name="count").to_csv(
            tables_dir / "quality_gate_decision_counts.csv",
            index=False,
        )

        plot_count_bar(
            counts=counts,
            figures_dir=figures_dir,
            name="quality_gate_decision_distribution",
            title="Quality Gate Decisions",
            xlabel="Decision",
        )

    numeric_cols = [
        col for col in ["critical_flag_count", "warning_flag_count"] if col in quality_df.columns
    ]

    if numeric_cols:
        plot_df = quality_df[numeric_cols].apply(as_numeric).melt(
            var_name="flag_type",
            value_name="count",
        )

        fig, ax = plt.subplots(figsize=(3.4, 2.4))
        sns.histplot(data=plot_df, x="count", hue="flag_type", multiple="dodge", discrete=True, ax=ax)
        ax.set_title("Quality Flag Count Distribution")
        ax.set_xlabel("Flag Count")
        ax.set_ylabel("Cases")
        save_figure(fig, figures_dir, "quality_flag_count_distribution")


def plot_classifier_figures(classifier_df: pd.DataFrame, figures_dir: Path, tables_dir: Path) -> None:
    if classifier_df.empty:
        return

    status_cols = [col for col in classifier_df.columns if col.startswith("classifier_status_")]
    prob_cols = [col for col in classifier_df.columns if col.startswith("classifier_prob_")]

    if status_cols:
        rows = []
        for col in status_cols:
            label = col.replace("classifier_status_", "").replace("_", " ").title()
            for status, count in classifier_df[col].fillna("missing").value_counts().items():
                rows.append({"label": label, "status": status, "count": count})

        status_df = pd.DataFrame(rows)
        status_df.to_csv(tables_dir / "classifier_status_counts.csv", index=False)

        fig, ax = plt.subplots(figsize=(6.8, 3.2))
        sns.barplot(data=status_df, y="label", x="count", hue="status", ax=ax, palette="Set2")
        ax.set_title("Image Classifier Status Distribution")
        ax.set_xlabel("Count")
        ax.set_ylabel("")
        ax.legend(title="Status", loc="lower right")
        save_figure(fig, figures_dir, "classifier_status_distribution")

    if prob_cols:
        long_rows = []
        for col in prob_cols:
            label = col.replace("classifier_prob_", "").replace("_", " ").title()
            values = as_numeric(classifier_df[col]).dropna()
            for value in values:
                long_rows.append({"label": label, "probability": value})

        prob_df = pd.DataFrame(long_rows)
        prob_df.to_csv(tables_dir / "classifier_probability_long.csv", index=False)

        if not prob_df.empty:
            fig, ax = plt.subplots(figsize=(6.8, 3.2))
            sns.boxplot(data=prob_df, y="label", x="probability", ax=ax, color="#9db4c0")
            ax.set_title("Image Classifier Probability Distribution")
            ax.set_xlabel("Probability")
            ax.set_ylabel("")
            ax.set_xlim(-0.02, 1.02)
            save_figure(fig, figures_dir, "classifier_probability_boxplot")


def plot_retrieval_figures(retrieval_df: pd.DataFrame, figures_dir: Path, tables_dir: Path) -> None:
    if retrieval_df.empty:
        return

    if {"query_study_key", "query_dicom_path"}.issubset(retrieval_df.columns):
        query_counts = (
            retrieval_df.groupby(["query_study_key", "query_dicom_path"])
            .size()
            .reset_index(name="retrieved_case_count")
        )
        query_counts.to_csv(tables_dir / "retrieval_cases_per_query.csv", index=False)

        fig, ax = plt.subplots(figsize=(3.4, 2.4))
        sns.histplot(query_counts["retrieved_case_count"], discrete=True, ax=ax, color="#4f6d7a")
        ax.set_title("Retrieved Cases Per Query")
        ax.set_xlabel("Retrieved Cases")
        ax.set_ylabel("Queries")
        save_figure(fig, figures_dir, "retrieval_cases_per_query")

    if "retrieval_distance" in retrieval_df.columns:
        distances = as_numeric(retrieval_df["retrieval_distance"]).dropna()
        if not distances.empty:
            distances.describe().to_csv(tables_dir / "retrieval_distance_summary.csv")

            fig, ax = plt.subplots(figsize=(3.4, 2.4))
            sns.histplot(distances, bins=20, kde=True, ax=ax, color="#5c677d")
            ax.set_title("Retrieval Distance Distribution")
            ax.set_xlabel("Retrieval Distance")
            ax.set_ylabel("Retrieved Cases")
            save_figure(fig, figures_dir, "retrieval_distance_distribution")


def plot_disease_reasoning_figures(reasoning_df: pd.DataFrame, figures_dir: Path, tables_dir: Path) -> None:
    if reasoning_df.empty or "finding_predictions_json" not in reasoning_df.columns:
        return

    rows = []

    for _, case in reasoning_df.iterrows():
        predictions = parse_json_cell(case.get("finding_predictions_json"), [])
        for item in predictions:
            if not isinstance(item, dict):
                continue

            label = clean_string(item.get("label"))
            status = clean_string(item.get("status")).lower()
            confidence = pd.to_numeric(item.get("confidence"), errors="coerce")

            if label in CHEXPERT_LABELS:
                rows.append(
                    {
                        "study_key": clean_string(case.get("study_key")),
                        "dicom_path": clean_string(case.get("dicom_path")),
                        "label": label,
                        "status": status,
                        "confidence": confidence,
                    }
                )

    pred_df = pd.DataFrame(rows)
    pred_df.to_csv(tables_dir / "disease_reasoning_label_predictions_long.csv", index=False)

    if pred_df.empty:
        return

    status_counts = (
        pred_df.groupby(["label", "status"])
        .size()
        .reset_index(name="count")
    )

    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    sns.barplot(data=status_counts, y="label", x="count", hue="status", ax=ax, palette="Set2")
    ax.set_title("Disease Reasoning Label Status Distribution")
    ax.set_xlabel("Count")
    ax.set_ylabel("")
    ax.legend(title="Status", loc="lower right")
    save_figure(fig, figures_dir, "disease_reasoning_status_distribution")

    confidence_df = pred_df.dropna(subset=["confidence"])
    if not confidence_df.empty:
        fig, ax = plt.subplots(figsize=(6.8, 3.2))
        sns.boxplot(data=confidence_df, y="label", x="confidence", ax=ax, color="#b7b7a4")
        ax.set_title("Disease Reasoning Confidence Distribution")
        ax.set_xlabel("Confidence")
        ax.set_ylabel("")
        ax.set_xlim(-0.02, 1.02)
        save_figure(fig, figures_dir, "disease_reasoning_confidence_boxplot")


def plot_workflow_funnel(
    quality_df: pd.DataFrame,
    classifier_df: pd.DataFrame,
    retrieval_df: pd.DataFrame,
    reasoning_df: pd.DataFrame,
    judge_df: pd.DataFrame,
    figures_dir: Path,
    tables_dir: Path,
) -> None:
    rows = []

    if not quality_df.empty:
        rows.append({"stage": "Quality Gate rows", "count": len(quality_df)})
        if "quality_gate_decision" in quality_df.columns:
            eligible = quality_df["quality_gate_decision"].isin(
                ["pass", "review_with_technical_warning"]
            ).sum()
            rows.append({"stage": "Quality eligible", "count": int(eligible)})

    if not classifier_df.empty:
        rows.append({"stage": "Image classifier rows", "count": len(classifier_df)})

    if not retrieval_df.empty and {"query_study_key", "query_dicom_path"}.issubset(retrieval_df.columns):
        query_count = retrieval_df[["query_study_key", "query_dicom_path"]].drop_duplicates().shape[0]
        rows.append({"stage": "Retrieval queries", "count": int(query_count)})

    if not reasoning_df.empty:
        rows.append({"stage": "Reasoning rows", "count": len(reasoning_df)})

    if not judge_df.empty:
        rows.append({"stage": "Judged rows", "count": len(judge_df)})

    funnel_df = pd.DataFrame(rows)
    funnel_df.to_csv(tables_dir / "workflow_stage_funnel.csv", index=False)

    if funnel_df.empty:
        return

    fig, ax = plt.subplots(figsize=(4.6, 2.8))
    sns.barplot(data=funnel_df, y="stage", x="count", ax=ax, color="#52796f")
    ax.set_title("MEDAGENT-X Workflow Stage Counts")
    ax.set_xlabel("Cases / Rows")
    ax.set_ylabel("")

    for container in ax.containers:
        ax.bar_label(container, fontsize=7, padding=2)

    save_figure(fig, figures_dir, "workflow_stage_funnel")


def write_markdown_report(
    output_dir: Path,
    judge_df: pd.DataFrame,
    per_label_df: pd.DataFrame,
    metric_summary: pd.DataFrame,
) -> None:
    lines = [
        "# MEDAGENT-X Quantitative Figure Summary",
        "",
        "## Inputs",
        "",
        f"- Judged cases: `{len(judge_df)}`",
        f"- Per-label judgment rows: `{len(per_label_df)}`",
        "",
    ]

    if not judge_df.empty and "judge_decision" in judge_df.columns:
        lines.extend(["## Judge Decisions", ""])
        counts = judge_df["judge_decision"].fillna("missing").value_counts()
        for decision, count in counts.items():
            lines.append(f"- {decision}: `{count}`")
        lines.append("")

    if not metric_summary.empty:
        lines.extend(["## Judge Metrics", ""])
        for _, row in metric_summary.iterrows():
            lines.append(
                f"- {row['metric']}: mean `{row['mean']:.3f}`, "
                f"median `{row['median']:.3f}`, range `{row['min']:.3f}-{row['max']:.3f}`"
            )
        lines.append("")

    lines.extend(
        [
            "## Figure Files",
            "",
            "- All figures are saved as both `.pdf` and `.png`.",
            "- Use `.pdf` for IEEE manuscript insertion when possible.",
            "- Use `.png` if the submission system requires raster images.",
            "",
        ]
    )

    (output_dir / "figure_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Quantify MEDAGENT-X workflow and generate paper-ready figures."
    )

    parser.add_argument(
        "--batch-dir",
        default=DEFAULT_BATCH_DIR,
        help="Batch output directory used to auto-resolve judge/disease-reasoning CSVs.",
    )
    parser.add_argument(
        "--judge-results",
        default="",
        help="Override judged-case CSV. Defaults to <batch-dir>/judge_results_first_100.csv",
    )
    parser.add_argument(
        "--quality-gate",
        default="outputs/chexpert_plus/quality_gate_decisions.csv",
    )
    parser.add_argument(
        "--image-classifier",
        default=DEFAULT_ENSEMBLE_PREDICTIONS,
        help="Classifier predictions CSV (ensemble, DenseNet-only, or fusion-only).",
    )
    parser.add_argument(
        "--retrieval-results",
        default="",
        help="Optional retrieval CSV override. Defaults to combined <batch-dir>/tmp/*_retrieval_results.csv",
    )
    parser.add_argument(
        "--disease-reasoning",
        default="",
        help="Override disease reasoning CSV. Defaults to <batch-dir>/disease_reasoning_results_first_100.csv",
    )
    parser.add_argument(
        "--fusion-training-metrics",
        default=DEFAULT_FUSION_TRAINING_METRICS,
        help="Fusion training metrics CSV for learning-curve figures.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/chexpert_plus/paper_figures_ensemble_first_100",
    )

    args = parser.parse_args()

    batch_paths = resolve_batch_paths(args.batch_dir)
    judge_results_path = args.judge_results or batch_paths["judge_results"]
    disease_reasoning_path = args.disease_reasoning or batch_paths["disease_reasoning"]
    retrieval_results_path = args.retrieval_results

    setup_plot_style()
    output_dir, figures_dir, tables_dir = ensure_output_dirs(args.output_dir)

    judge_df = read_optional_csv(judge_results_path)
    quality_df = read_optional_csv(args.quality_gate)
    classifier_df = read_optional_csv(args.image_classifier)
    if retrieval_results_path:
        retrieval_df = read_optional_csv(retrieval_results_path)
    else:
        retrieval_df = load_batch_retrieval_results(args.batch_dir)
    reasoning_df = read_optional_csv(disease_reasoning_path)

    metric_summary = summarize_judge_results(judge_df, tables_dir)
    per_label_df = build_per_label_table(judge_df, tables_dir)

    plot_judge_figures(judge_df, per_label_df, figures_dir)
    plot_quality_gate_figures(quality_df, figures_dir, tables_dir)
    plot_classifier_figures(classifier_df, figures_dir, tables_dir)
    plot_ensemble_figures(classifier_df, figures_dir, tables_dir)
    plot_fusion_training_figures(args.fusion_training_metrics, figures_dir)
    plot_retrieval_figures(retrieval_df, figures_dir, tables_dir)
    plot_disease_reasoning_figures(reasoning_df, figures_dir, tables_dir)

    plot_workflow_funnel(
        quality_df=quality_df,
        classifier_df=classifier_df,
        retrieval_df=retrieval_df,
        reasoning_df=reasoning_df,
        judge_df=judge_df,
        figures_dir=figures_dir,
        tables_dir=tables_dir,
    )

    write_markdown_report(
        output_dir=output_dir,
        judge_df=judge_df,
        per_label_df=per_label_df,
        metric_summary=metric_summary,
    )

    print(f"[DONE] Figures: {figures_dir}")
    print(f"[DONE] Tables: {tables_dir}")
    print(f"[DONE] Summary: {output_dir / 'figure_summary.md'}")


if __name__ == "__main__":
    main()



