#!/usr/bin/env python3
"""
Audit which cohort the fusion classifier was (or would be) trained on.

Replays the filtering logic from script 12 and compares it against on-disk
fusion artifacts. Prints a checklist of CSV files to share for remote debugging.

Usage:
  python debug_scripts/audit_fusion_training_cohort.py

  python debug_scripts/audit_fusion_training_cohort.py \\
    --quality-gate-eligible-cohort ~/Downloads/quality_gate_eligible_cohort.csv \\
    --split-metadata ~/Downloads/patient_split_metadata.csv

  python debug_scripts/audit_fusion_training_cohort.py --json-out ~/Downloads/fusion_cohort_audit.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from medagentx.fusion.constants import (  # noqa: E402
    DEFAULT_CONVNEXT_MANIFEST,
    DEFAULT_MODEL_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_QUALITY_GATE_CSV,
    DEFAULT_QUALITY_GATE_ELIGIBLE_COHORT,
    DEFAULT_RADDINO_MANIFEST,
    DEFAULT_REPORT_LABEL_TABLE,
    DEFAULT_SPLIT_METADATA,
    DEFAULT_TEST_PREDICTIONS,
    DEFAULT_THRESHOLDS_PATH,
    DEFAULT_TRAINING_METRICS,
    DISEASE_LABELS,
    FUSION_MODEL_VERSION,
    snake_label,
)
from medagentx.fusion.features import load_feature_manifests, merge_label_and_feature_tables  # noqa: E402
from medagentx.fusion.splits import (  # noqa: E402
    AGENT_EVAL_SPLIT,
    eligible_study_keys,
    load_patient_split_table,
    load_quality_gate_eligible_cases,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit fusion training cohort and list CSVs to provide for debugging."
    )
    parser.add_argument("--report-label-table", type=Path, default=DEFAULT_REPORT_LABEL_TABLE)
    parser.add_argument("--quality-gate-eligible-cohort", type=Path, default=DEFAULT_QUALITY_GATE_ELIGIBLE_COHORT)
    parser.add_argument("--quality-gate-csv", type=Path, default=DEFAULT_QUALITY_GATE_CSV)
    parser.add_argument("--split-metadata", type=Path, default=DEFAULT_SPLIT_METADATA)
    parser.add_argument("--convnext-manifest", type=Path, default=DEFAULT_CONVNEXT_MANIFEST)
    parser.add_argument("--raddino-manifest", type=Path, default=DEFAULT_RADDINO_MANIFEST)
    parser.add_argument("--fusion-output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model-path", type=Path, default=None)
    parser.add_argument("--thresholds-path", type=Path, default=None)
    parser.add_argument("--training-metrics-path", type=Path, default=None)
    parser.add_argument("--test-predictions-path", type=Path, default=None)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to write machine-readable audit JSON.",
    )
    return parser.parse_args()


def _file_info(path: Path) -> dict:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def _section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _subsection(title: str) -> None:
    print()
    print(f"--- {title} ---")


def _load_eligible_cohort(args: argparse.Namespace) -> tuple[pd.DataFrame, str]:
    if args.quality_gate_eligible_cohort.exists():
        df = pd.read_csv(args.quality_gate_eligible_cohort, dtype=str)
        source = str(args.quality_gate_eligible_cohort.resolve())
        return df, source

    df = load_quality_gate_eligible_cases(args.quality_gate_csv)
    source = str(args.quality_gate_csv.resolve())
    return df, source


def _study_level_from_merged(merged_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for study_key, group in merged_df.groupby("study_key", sort=False):
        first = group.iloc[0]
        row: dict = {
            "study_key": study_key,
            "deid_patient_id": str(first.get("deid_patient_id", "")).strip(),
            "image_count": len(group),
        }
        for label in DISEASE_LABELS + ["No Finding"]:
            slug = snake_label(label)
            row[f"weak_value_{slug}"] = first.get(f"weak_value_{slug}")
            row[f"weak_status_{slug}"] = first.get(f"weak_status_{slug}")
        rows.append(row)
    return pd.DataFrame(rows)


def _label_stats(study_df: pd.DataFrame, split_name: str) -> list[dict]:
    subset = study_df[study_df["split"] == split_name]
    stats: list[dict] = []
    for label in DISEASE_LABELS:
        slug = snake_label(label)
        value_col = f"weak_value_{slug}"
        status_col = f"weak_status_{slug}"
        if value_col not in subset.columns:
            continue

        values = subset[value_col]
        statuses = subset.get(status_col, pd.Series([""] * len(subset), index=subset.index))

        supervised = values.notna() & (values.astype(str).str.strip() != "")
        positives = supervised & (pd.to_numeric(values, errors="coerce") >= 0.5)
        negatives = supervised & (pd.to_numeric(values, errors="coerce") < 0.5)
        present_status = statuses.astype(str).str.strip().str.lower() == "present"

        stats.append(
            {
                "label": label,
                "supervised_studies": int(supervised.sum()),
                "positive_studies": int((positives | present_status).sum()),
                "negative_studies": int(negatives.sum()),
            }
        )
    return stats


def _split_summary(study_df: pd.DataFrame, eligible_df: pd.DataFrame) -> dict:
    eligible_with_split = eligible_df.merge(
        study_df[["study_key", "split"]].drop_duplicates(),
        on="study_key",
        how="left",
    )
    case_counts = eligible_with_split.groupby("split", dropna=False).size().to_dict()
    patient_col = "deid_patient_id" if "deid_patient_id" in eligible_df.columns else None

    out: dict[str, dict] = {}
    for split_name in ["train", "validation", "test", AGENT_EVAL_SPLIT, None]:
        key = split_name if split_name is not None else "unassigned"
        split_studies = study_df if split_name is None else study_df[study_df["split"] == split_name]
        split_cases = (
            eligible_with_split[eligible_with_split["split"].isna()]
            if split_name is None
            else eligible_with_split[eligible_with_split["split"] == split_name]
        )
        out[key] = {
            "studies": int(len(split_studies)),
            "patients": int(split_studies["deid_patient_id"].nunique()) if len(split_studies) else 0,
            "cases_in_eligible_cohort": int(len(split_cases)),
            "patients_in_eligible_cohort": (
                int(split_cases[patient_col].nunique()) if patient_col and len(split_cases) else 0
            ),
            "images_feature_ready": int(split_studies["image_count"].sum()) if len(split_studies) else 0,
        }
    out["case_counts_from_eligible_cohort"] = {
        str(k): int(v) for k, v in case_counts.items()
    }
    return out


def _inspect_model(path: Path) -> dict:
    info = _file_info(path)
    if not info["exists"]:
        return info

    try:
        import torch

        payload = torch.load(path, map_location="cpu", weights_only=False)
        info["model_version"] = payload.get("model_version")
        info["feature_mode"] = payload.get("feature_mode")
        info["input_dim"] = payload.get("input_dim")
        info["num_labels"] = payload.get("num_labels")
        info["labels"] = payload.get("labels")
        info["has_state_dict"] = "model_state_dict" in payload
    except Exception as exc:  # noqa: BLE001
        info["load_error"] = str(exc)
    return info


def _inspect_thresholds(path: Path) -> dict:
    info = _file_info(path)
    if not info["exists"]:
        return info
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        info["model_version"] = payload.get("model_version")
        info["feature_mode"] = payload.get("feature_mode")
        thresholds = payload.get("thresholds", {})
        tuned = payload.get("tuned_thresholds", {})
        info["deployment_threshold_mean"] = (
            round(sum(float(v) for v in thresholds.values()) / max(len(thresholds), 1), 4)
        )
        info["tuned_threshold_mean"] = (
            round(sum(float(v) for v in tuned.values()) / max(len(tuned), 1), 4)
        )
        info["deployment_thresholds"] = thresholds
        info["tuned_thresholds"] = tuned
    except Exception as exc:  # noqa: BLE001
        info["load_error"] = str(exc)
    return info


def _compare_test_predictions(path: Path, expected_test_studies: set[str]) -> dict:
    info = _file_info(path)
    if not info["exists"]:
        return info

    preds = pd.read_csv(path, dtype=str)
    saved_studies = set(preds["study_key"].astype(str).str.strip())
    overlap = saved_studies & expected_test_studies
    only_saved = saved_studies - expected_test_studies
    only_expected = expected_test_studies - saved_studies

    info["saved_test_studies"] = len(saved_studies)
    info["expected_test_studies"] = len(expected_test_studies)
    info["overlap_studies"] = len(overlap)
    info["only_in_saved_predictions"] = len(only_saved)
    info["only_in_reconstructed_test"] = len(only_expected)
    info["cohort_match"] = len(only_saved) == 0 and len(only_expected) == 0
    if only_saved:
        info["example_only_in_saved"] = sorted(only_saved)[:5]
    if only_expected:
        info["example_only_in_reconstructed"] = sorted(only_expected)[:5]
    return info


def _print_split_table(summary: dict) -> None:
    headers = ["split", "studies", "patients", "eligible_cases", "feature_ready_images"]
    print(f"{'split':<14} {'studies':>8} {'patients':>9} {'cases':>8} {'images':>8}")
    print("-" * 52)
    for split_name in ["train", "validation", "test", AGENT_EVAL_SPLIT, "unassigned"]:
        row = summary.get(split_name, {})
        print(
            f"{split_name:<14} "
            f"{row.get('studies', 0):>8} "
            f"{row.get('patients', 0):>9} "
            f"{row.get('cases_in_eligible_cohort', 0):>8} "
            f"{row.get('images_feature_ready', 0):>8}"
        )


def _print_label_table(label_stats: list[dict]) -> None:
    print(f"{'label':<28} {'supervised':>11} {'positive':>10} {'negative':>10}")
    print("-" * 62)
    for row in label_stats:
        print(
            f"{row['label']:<28} "
            f"{row['supervised_studies']:>11} "
            f"{row['positive_studies']:>10} "
            f"{row['negative_studies']:>10}"
        )


def _files_to_provide(args: argparse.Namespace) -> list[dict]:
    candidates = [
        ("report_label_training_table.csv", args.report_label_table, True),
        ("quality_gate_eligible_cohort.csv", args.quality_gate_eligible_cohort, True),
        ("patient_split_metadata.csv", args.split_metadata, True),
        ("convnext_feature_manifest.csv", args.convnext_manifest, True),
        ("raddino_feature_manifest.csv", args.raddino_manifest, True),
        ("fusion_training_metrics.csv", args.training_metrics_path or args.fusion_output_dir / DEFAULT_TRAINING_METRICS.name, False),
        ("fusion_test_predictions.csv", args.test_predictions_path or args.fusion_output_dir / DEFAULT_TEST_PREDICTIONS.name, False),
        ("fusion_thresholds.json", args.thresholds_path or args.fusion_output_dir / DEFAULT_THRESHOLDS_PATH.name, False),
        ("quality_gate_decisions.csv", args.quality_gate_csv, False),
    ]
    rows = []
    for name, path, required in candidates:
        info = _file_info(path)
        rows.append(
            {
                "filename": name,
                "path": info["path"],
                "exists": info["exists"],
                "required_for_cohort_replay": required,
                "priority": "high" if required else "medium",
            }
        )
    return rows


def main() -> int:
    args = parse_args()
    args.fusion_output_dir.mkdir(parents=True, exist_ok=True)

    model_path = args.model_path or args.fusion_output_dir / DEFAULT_MODEL_PATH.name
    thresholds_path = args.thresholds_path or args.fusion_output_dir / DEFAULT_THRESHOLDS_PATH.name
    metrics_path = args.training_metrics_path or args.fusion_output_dir / DEFAULT_TRAINING_METRICS.name
    test_preds_path = args.test_predictions_path or args.fusion_output_dir / DEFAULT_TEST_PREDICTIONS.name

    audit: dict = {
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "fusion_model_version_expected": FUSION_MODEL_VERSION,
        "inputs": {},
        "artifacts": {},
        "reconstructed_cohort": {},
        "diagnosis": [],
        "files_to_provide": [],
    }

    _section("FUSION TRAINING COHORT AUDIT")
    print("Replays script-12 filtering on your current inputs and artifacts.")

    # --- Inputs ---
    _subsection("Input files")
    input_paths = {
        "report_label_table": args.report_label_table,
        "quality_gate_eligible_cohort": args.quality_gate_eligible_cohort,
        "quality_gate_csv_fallback": args.quality_gate_csv,
        "split_metadata": args.split_metadata,
        "convnext_manifest": args.convnext_manifest,
        "raddino_manifest": args.raddino_manifest,
    }
    for key, path in input_paths.items():
        info = _file_info(path)
        audit["inputs"][key] = info
        status = "OK" if info["exists"] else "MISSING"
        print(f"[{status}] {path}")

    missing_required = [
        key
        for key in ("report_label_table", "split_metadata", "convnext_manifest", "raddino_manifest")
        if not audit["inputs"][key]["exists"]
    ]
    if missing_required:
        audit["diagnosis"].append(
            f"Missing required inputs: {', '.join(missing_required)}. "
            "Cannot fully replay fusion training cohort."
        )

    eligible_df = None
    eligible_source = ""
    label_df = None
    study_df = None

    if not missing_required:
        try:
            eligible_df, eligible_source = _load_eligible_cohort(args)
            allowed_studies = eligible_study_keys(eligible_df)

            label_df = pd.read_csv(args.report_label_table, dtype=str)
            before_rows = len(label_df)
            before_studies = label_df["study_key"].nunique()
            label_df = label_df[label_df["study_key"].isin(allowed_studies)].copy()

            feature_df = load_feature_manifests(
                convnext_manifest_path=args.convnext_manifest,
                raddino_manifest_path=args.raddino_manifest,
            )
            merged = merge_label_and_feature_tables(label_df, feature_df)
            study_df = _study_level_from_merged(merged)

            split_table = load_patient_split_table(args.split_metadata)
            study_df = study_df.merge(split_table, on="deid_patient_id", how="left")

            agent_eval_studies = int(study_df["split"].eq(AGENT_EVAL_SPLIT).sum())
            fusion_study_df = study_df[study_df["split"] != AGENT_EVAL_SPLIT].copy()

            split_summary = _split_summary(study_df, eligible_df)
            train_label_stats = _label_stats(fusion_study_df, "train")
            val_label_stats = _label_stats(fusion_study_df, "validation")
            test_label_stats = _label_stats(fusion_study_df, "test")

            coverage = {
                "eligible_cases": int(len(eligible_df)),
                "eligible_studies": int(eligible_df["study_key"].nunique()),
                "eligible_patients": int(eligible_df["deid_patient_id"].nunique())
                if "deid_patient_id" in eligible_df.columns
                else int(eligible_df["study_key"].astype(str).str.split("/").str[0].nunique()),
                "label_rows_before_qg_filter": before_rows,
                "label_studies_before_qg_filter": int(before_studies),
                "label_rows_after_qg_filter": int(len(label_df)),
                "label_studies_after_qg_filter": int(label_df["study_key"].nunique()),
                "feature_ready_image_rows": int(len(merged)),
                "study_rows_for_training": int(len(fusion_study_df)),
                "agent_eval_studies_excluded": agent_eval_studies,
                "studies_missing_split": int(study_df["split"].isna().sum()),
                "eligible_studies_without_labels": int(
                    len(allowed_studies - set(label_df["study_key"].astype(str)))
                ),
                "eligible_studies_without_features": int(
                    len(allowed_studies - set(merged["study_key"].astype(str)))
                ),
            }

            audit["reconstructed_cohort"] = {
                "eligible_source": eligible_source,
                "coverage": coverage,
                "split_summary": split_summary,
                "train_label_stats": train_label_stats,
                "validation_label_stats": val_label_stats,
                "test_label_stats": test_label_stats,
            }

            _section("RECONSTRUCTED TRAINING COHORT (script 12 logic)")
            print(f"Eligible cohort source: {eligible_source}")
            print(
                f"Eligible: {coverage['eligible_cases']} cases | "
                f"{coverage['eligible_studies']} studies | "
                f"{coverage['eligible_patients']} patients"
            )
            print(
                f"Labels after quality-gate filter: {coverage['label_rows_after_qg_filter']} rows | "
                f"{coverage['label_studies_after_qg_filter']} studies "
                f"(was {coverage['label_studies_before_qg_filter']} studies before filter)"
            )
            print(
                f"Feature-ready images: {coverage['feature_ready_image_rows']} | "
                f"Study rows used for fusion (excl agent_eval): {coverage['study_rows_for_training']}"
            )
            print(
                f"Coverage gaps: {coverage['eligible_studies_without_labels']} eligible studies lack labels | "
                f"{coverage['eligible_studies_without_features']} eligible studies lack features"
            )
            if coverage["studies_missing_split"]:
                audit["diagnosis"].append(
                    f"{coverage['studies_missing_split']} studies have patients missing from split metadata."
                )

            _subsection("Split breakdown (studies = fusion training unit)")
            _print_split_table(split_summary)

            train_row = split_summary["train"]
            _subsection("Train split adequacy")
            print(
                f"Train: {train_row['studies']} studies | "
                f"{train_row['patients']} patients | "
                f"{train_row['cases_in_eligible_cohort']} eligible cases"
            )
            if train_row["studies"] < 100:
                audit["diagnosis"].append(
                    f"Train split has only {train_row['studies']} studies — likely too small."
                )
            elif train_row["studies"] >= 500:
                audit["diagnosis"].append(
                    f"Train split has {train_row['studies']} studies — size is adequate; "
                    "if fusion probs are still low, suspect stale checkpoint, thresholds, or label mismatch."
                )
            else:
                audit["diagnosis"].append(
                    f"Train split has {train_row['studies']} studies — moderate size; "
                    "retrain after confirming label coverage."
                )

            _subsection("Train-split label positives (weak_value=1)")
            _print_label_table(train_label_stats)

            rare = [r for r in train_label_stats if r["positive_studies"] < 10]
            if rare:
                audit["diagnosis"].append(
                    "Rare positives in train (<10 studies): "
                    + ", ".join(f"{r['label']}={r['positive_studies']}" for r in rare)
                )

        except Exception as exc:  # noqa: BLE001
            audit["diagnosis"].append(f"Cohort replay failed: {exc}")
            _section("RECONSTRUCTED TRAINING COHORT")
            print(f"ERROR: {exc}")

    # --- Artifacts ---
    _section("ON-DISK FUSION ARTIFACTS")
    model_info = _inspect_model(model_path)
    thresholds_info = _inspect_thresholds(thresholds_path)
    metrics_info = _file_info(metrics_path)
    test_info = _file_info(test_preds_path)

    audit["artifacts"] = {
        "model": model_info,
        "thresholds": thresholds_info,
        "training_metrics": metrics_info,
        "test_predictions": test_info,
    }

    for name, info in audit["artifacts"].items():
        status = "OK" if info.get("exists") else "MISSING"
        print(f"[{status}] {info['path']}")
        if info.get("exists") and name == "model":
            print(
                f"  model_version={info.get('model_version')} "
                f"feature_mode={info.get('feature_mode')} "
                f"input_dim={info.get('input_dim')}"
            )
        if info.get("exists") and name == "thresholds":
            print(
                f"  deployment_threshold_mean={info.get('deployment_threshold_mean')} "
                f"tuned_threshold_mean={info.get('tuned_threshold_mean')}"
            )
        if info.get("exists") and name == "training_metrics":
            try:
                metrics_df = pd.read_csv(metrics_path)
                best = metrics_df.sort_values("val_macro_avg_precision", ascending=False).iloc[0]
                print(
                    f"  epochs_logged={len(metrics_df)} "
                    f"best_epoch={int(best['epoch'])} "
                    f"best_val_macro_ap={float(best['val_macro_avg_precision']):.4f}"
                )
                audit["artifacts"]["training_metrics"]["epochs_logged"] = int(len(metrics_df))
                audit["artifacts"]["training_metrics"]["best_epoch"] = int(best["epoch"])
                audit["artifacts"]["training_metrics"]["best_val_macro_ap"] = float(
                    best["val_macro_avg_precision"]
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  metrics_read_error: {exc}")

    if study_df is not None and test_preds_path.exists():
        expected_test = set(
            study_df.loc[study_df["split"] == "test", "study_key"].astype(str).str.strip()
        )
        comparison = _compare_test_predictions(test_preds_path, expected_test)
        audit["artifacts"]["test_predictions"].update(comparison)

        _subsection("Saved test predictions vs reconstructed test split")
        if comparison.get("cohort_match"):
            print("MATCH: fusion_test_predictions.csv aligns with current inputs.")
            audit["diagnosis"].append(
                "fusion_test_predictions.csv matches reconstructed test split — "
                "checkpoint likely trained on current cohort inputs."
            )
        else:
            print(
                f"MISMATCH: saved={comparison.get('saved_test_studies')} "
                f"expected={comparison.get('expected_test_studies')} "
                f"overlap={comparison.get('overlap_studies')}"
            )
            if comparison.get("example_only_in_saved"):
                print(f"  only in saved predictions: {comparison['example_only_in_saved']}")
            if comparison.get("example_only_in_reconstructed"):
                print(f"  only in reconstructed test: {comparison['example_only_in_reconstructed']}")
            audit["diagnosis"].append(
                "fusion_test_predictions.csv does NOT match reconstructed test split — "
                "model was likely trained on an older/smaller cohort. Re-run script 12."
            )
    elif not test_preds_path.exists():
        audit["diagnosis"].append(
            "fusion_test_predictions.csv missing — fusion may not have been trained yet on this machine."
        )

    if model_info.get("exists") and metrics_info.get("exists"):
        model_mtime = datetime.fromisoformat(model_info["modified_utc"])
        metrics_mtime = datetime.fromisoformat(metrics_info["modified_utc"])
        if eligible_df is not None and _file_info(args.quality_gate_eligible_cohort).get("exists"):
            cohort_mtime = datetime.fromisoformat(
                _file_info(args.quality_gate_eligible_cohort)["modified_utc"]
            )
            if cohort_mtime > model_mtime:
                audit["diagnosis"].append(
                    "Eligible cohort CSV is newer than fusion_model.pt — retrain recommended."
                )

    # --- Files to provide ---
    files_to_provide = _files_to_provide(args)
    audit["files_to_provide"] = files_to_provide

    _section("FILES TO PROVIDE FOR REMOTE DEBUGGING")
    print("Share these paths (attach or copy to Downloads). Required = needed to replay cohort.\n")
    for row in files_to_provide:
        req = "REQUIRED" if row["required_for_cohort_replay"] else "optional"
        status = "found" if row["exists"] else "MISSING"
        print(f"  [{req:8}] [{status:7}] {row['filename']}")
        print(f"             {row['path']}")

    _section("DIAGNOSIS SUMMARY")
    if audit["diagnosis"]:
        for i, item in enumerate(audit["diagnosis"], start=1):
            print(f"{i}. {item}")
    else:
        print("No issues detected from available inputs.")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        print()
        print(f"Wrote JSON audit: {args.json_out.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
