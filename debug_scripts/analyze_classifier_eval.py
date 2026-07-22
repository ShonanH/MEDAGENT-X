#!/usr/bin/env python3
"""
Analyze DenseNet / fusion / ensemble behavior on agent-eval outputs.

Usage:
  python scripts/analyze_classifier_eval.py \
    --judge-csv ~/Downloads/judge_results_agent_eval.csv \
    --disease-reasoning-csv ~/Downloads/disease_reasoning_results_agent_eval.csv
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze classifier performance on agent eval.")
    parser.add_argument(
        "--judge-csv",
        type=Path,
        required=True,
        help="judge_results_agent_eval.csv from script 17",
    )
    parser.add_argument(
        "--disease-reasoning-csv",
        type=Path,
        required=True,
        help="disease_reasoning_results_agent_eval.csv from script 17",
    )
    return parser.parse_args()


def parse_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text or "")
    if not match:
        return None
    return float(match.group(1).rstrip("."))


def load_judge_label_rows(judge_csv: Path) -> pd.DataFrame:
    jdf = pd.read_csv(judge_csv, dtype=str)
    records: list[dict] = []

    for _, row in jdf.iterrows():
        per_label = json.loads(row["per_label_judgment_json"])
        for item in per_label:
            label = item.get("label")
            if label in {"No Finding"}:
                continue
            evidence = item.get("predicted_evidence", "")
            records.append(
                {
                    "study_key": row["study_key"],
                    "label": label,
                    "gt": item.get("ground_truth_status"),
                    "pred": item.get("predicted_status"),
                    "match": item.get("match_type"),
                    "prob": parse_float(r"Classifier probability=([0-9.]+)", evidence),
                    "thr": parse_float(r"Classifier threshold=([0-9.]+)", evidence),
                    "cls_status": (re.search(r"Classifier status=(\w+)", evidence) or [None, ""])[1],
                    "judge_decision": row.get("judge_decision"),
                    "disease_f1": float(row.get("disease_f1", "nan")),
                }
            )

    return pd.DataFrame(records)


def load_classifier_evidence_rows(disease_reasoning_csv: Path) -> pd.DataFrame:
    ddf = pd.read_csv(disease_reasoning_csv, dtype=str)
    rows: list[dict] = []

    for _, row in ddf.iterrows():
        classifier = json.loads(row["classifier_evidence_json"])
        for item in classifier.get("labels", []):
            label = item.get("label")
            if label in {"No Finding", "Support Devices"}:
                continue
            rows.append(
                {
                    "study_key": row["study_key"],
                    "dicom_path": row["dicom_path"],
                    "label": label,
                    "ensemble_prob": item.get("probability"),
                    "ensemble_status": item.get("status"),
                    "densenet_prob": item.get("densenet_probability"),
                    "fusion_prob": item.get("fusion_probability"),
                    "threshold": item.get("threshold"),
                    "agreement": item.get("ensemble_agreement"),
                }
            )

    cdf = pd.DataFrame(rows)
    for col in ["ensemble_prob", "densenet_prob", "fusion_prob", "threshold"]:
        cdf[col] = pd.to_numeric(cdf[col], errors="coerce")
    return cdf


def print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def main() -> int:
    args = parse_args()
    if not args.judge_csv.exists():
        print(f"Missing judge CSV: {args.judge_csv}", file=sys.stderr)
        return 1
    if not args.disease_reasoning_csv.exists():
        print(f"Missing disease reasoning CSV: {args.disease_reasoning_csv}", file=sys.stderr)
        return 1

    jdf = pd.read_csv(args.judge_csv, dtype=str)
    label_df = load_judge_label_rows(args.judge_csv)
    clf_df = load_classifier_evidence_rows(args.disease_reasoning_csv)

    print_section("COHORT")
    print(f"Judge studies:              {jdf['study_key'].nunique()}")
    print(f"Judge rows:                 {len(jdf)}")
    print(f"Disease-reasoning rows:     {len(pd.read_csv(args.disease_reasoning_csv, dtype=str))}")
    print(f"Label-level judge rows:     {len(label_df)}")
    print(f"Classifier evidence rows:   {len(clf_df)}")

    print_section("JUDGE OUTCOMES")
    print(jdf["judge_decision"].value_counts().to_string())
    jdf["disease_f1"] = pd.to_numeric(jdf["disease_f1"], errors="coerce")
    print(f"\nMean disease F1:            {jdf['disease_f1'].mean():.3f}")
    print(f"Studies with disease F1=1:  {(jdf['disease_f1'] == 1.0).sum()}")
    print(f"Studies with disease F1=0:  {(jdf['disease_f1'] == 0.0).sum()}")

    print_section("DENSENET vs FUSION vs ENSEMBLE")
    print(f"DenseNet mean prob:         {clf_df['densenet_prob'].mean():.3f}")
    print(f"Fusion mean prob:           {clf_df['fusion_prob'].mean():.3f}")
    print(f"Ensemble mean prob:         {clf_df['ensemble_prob'].mean():.3f}")
    print(f"Ensemble mean threshold:    {clf_df['threshold'].mean():.3f}")
    print("\nEnsemble status:")
    print(clf_df["ensemble_status"].value_counts().to_string())
    print("\nAgreement field:")
    print(clf_df["agreement"].value_counts().to_string())
    print("\nAgreement x status:")
    print(pd.crosstab(clf_df["agreement"], clf_df["ensemble_status"]).to_string())

    both_low = ((clf_df["densenet_prob"] <= 0.15) & (clf_df["fusion_prob"] <= 0.15)).mean()
    dn_high_f_low = ((clf_df["densenet_prob"] >= 0.4) & (clf_df["fusion_prob"] <= 0.15)).mean()
    print(f"\nBoth probs <= 0.15:         {both_low:.1%}")
    print(f"DenseNet>=0.4 & fusion<=0.15: {dn_high_f_low:.1%}  <-- fusion suppressing DenseNet")

    print_section("WHEN GROUND TRUTH LABEL = present")
    gt_pos = label_df[label_df["gt"] == "present"]
    print(f"GT-present label rows:      {len(gt_pos)}")
    print("Predicted status:")
    print(gt_pos["pred"].value_counts().to_string())
    print("Classifier status:")
    print(gt_pos["cls_status"].value_counts().to_string())
    print(f"Mean ensemble prob:         {gt_pos['prob'].mean():.3f}")
    print(f"Mean threshold:             {gt_pos['thr'].mean():.3f}")
    print(f"prob >= threshold:          {(gt_pos['prob'] >= gt_pos['thr']).mean():.1%}")
    misses = gt_pos[gt_pos["pred"] != "present"]
    print(f"Missed (pred != present):   {len(misses)}")
    print("Top missed labels:")
    print(misses["label"].value_counts().head(12).to_string())

    print_section("PER-LABEL ENSEMBLE SUMMARY")
    summary = clf_df.groupby("label").agg(
        densenet_mean=("densenet_prob", "mean"),
        fusion_mean=("fusion_prob", "mean"),
        ensemble_mean=("ensemble_prob", "mean"),
        threshold_mean=("threshold", "mean"),
        absent_rate=("ensemble_status", lambda s: (s == "absent").mean()),
        present_rate=("ensemble_status", lambda s: (s == "present").mean()),
    )
    print(summary.round(3).sort_values("absent_rate", ascending=False).to_string())

    print_section("FUSION DIAGNOSIS")
    if clf_df["fusion_prob"].mean() < clf_df["densenet_prob"].mean() * 0.5:
        print("- Fusion is much less confident than DenseNet on agent eval.")
    if dn_high_f_low > 0.3:
        print("- DenseNet sees signal that fusion suppresses on many label-rows.")
    if (clf_df["ensemble_status"] == "absent").mean() > 0.7:
        print("- Ensemble is calling absent on most labels (recall problem).")
    if len(gt_pos) and (gt_pos["pred"] == "present").sum() / len(gt_pos) < 0.2:
        print("- Very few GT-present labels are predicted present (primary failure).")
    print("\nSuggested next steps:")
    print("  1. Retrain fusion on a larger cohort (script 04 study-limit + scripts 12)")
    print("  2. Rebuild ensemble with lower fusion weight, e.g.:")
    print("     python src/medagentx/cli/16_build_ensemble_classifier_predictions.py --fusion-weight 0.35")
    print("  3. Re-run agent eval subset and compare this script's output")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
