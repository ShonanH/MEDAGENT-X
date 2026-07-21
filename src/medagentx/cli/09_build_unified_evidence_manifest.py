#!/usr/bin/env python3
"""
Build the unified MEDAGENT-X Workflow A evidence manifest.

This script joins the completed evidence artifacts:

  1. Original study manifest
  2. ConvNeXt local feature manifest
  3. RAD-DINO Transformer/global feature manifest
  4. Optional DICOM validation/preprocessing manifest
  5. Optional handcrafted quality/artifact metrics manifest

It does NOT train a model.
It does NOT create labels.
It does NOT make Quality Gate Agent decisions.

Output:
  src/outputs/chexpert_plus/unified_evidence_manifest.csv
"""

import argparse
from pathlib import Path

import pandas as pd

from medagentx.paths import CHEXPERT_OUTPUT_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR



DEFAULT_OUTPUT_DIR = CHEXPERT_OUTPUT_DIR

DEFAULT_STUDY_MANIFEST = (
    PROCESSED_DATA_DIR
    / "chexpert_plus"
    / "chexpert_plus_v2_manifest.csv"
)

DEFAULT_DICOM_ROOT = (
    RAW_DATA_DIR
    / "chexpert_plus"
    / "dicom_train"
)

DEFAULT_CONVNEXT_MANIFEST = (
    DEFAULT_OUTPUT_DIR / "convnext_feature_manifest.csv"
)

DEFAULT_RADDINO_MANIFEST = (
    DEFAULT_OUTPUT_DIR / "raddino_feature_manifest.csv"
)

VALIDATION_CANDIDATES = [
    DEFAULT_OUTPUT_DIR / "dicom_validation_manifest.csv",
    DEFAULT_OUTPUT_DIR / "dicom_preprocessing_validation_manifest.csv",
    DEFAULT_OUTPUT_DIR / "preprocessing_validation_manifest.csv",
    DEFAULT_OUTPUT_DIR / "chexpert_plus_dicom_validation_manifest.csv",
]

METRIC_CANDIDATES = [
    DEFAULT_OUTPUT_DIR / "artifact_feature_manifest.csv",
    DEFAULT_OUTPUT_DIR / "handcrafted_quality_metrics.csv",
    DEFAULT_OUTPUT_DIR / "dicom_quality_metrics.csv",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build unified MEDAGENT-X Workflow A evidence manifest."
    )

    parser.add_argument(
        "--study-manifest-path",
        type=Path,
        default=DEFAULT_STUDY_MANIFEST,
    )

    parser.add_argument(
        "--dicom-root",
        type=Path,
        default=DEFAULT_DICOM_ROOT,
    )

    parser.add_argument(
        "--convnext-manifest-path",
        type=Path,
        default=DEFAULT_CONVNEXT_MANIFEST,
    )

    parser.add_argument(
        "--raddino-manifest-path",
        type=Path,
        default=DEFAULT_RADDINO_MANIFEST,
    )

    parser.add_argument(
        "--validation-manifest-path",
        type=Path,
        default=None,
        help="Optional validation manifest. If omitted, common output names are searched.",
    )

    parser.add_argument(
        "--metrics-manifest-path",
        type=Path,
        default=None,
        help="Optional handcrafted/artifact metrics manifest. If omitted, common output names are searched.",
    )

    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "unified_evidence_manifest.csv",
    )

    return parser.parse_args()


def clean_dicom_path(path):
    path = str(path).strip()

    if path.startswith("train/"):
        path = path.removeprefix("train/")

    return path


def find_optional_path(explicit_path, candidates):
    if explicit_path is not None:
        explicit_path = explicit_path.resolve()
        return explicit_path if explicit_path.exists() else None

    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate.exists():
            return candidate

    return None


def build_base_manifest(study_manifest_path, dicom_root):
    manifest = pd.read_csv(study_manifest_path)

    if "dicom_paths" not in manifest.columns:
        raise KeyError(
            "Study manifest must contain a 'dicom_paths' column. "
            f"Found columns: {manifest.columns.tolist()}"
        )

    rows = []
    seen = set()

    for manifest_row_index, row in manifest.iterrows():
        for dicom_path in str(row["dicom_paths"]).split("|"):
            dicom_path = clean_dicom_path(dicom_path)

            if not dicom_path:
                continue

            key = (manifest_row_index, dicom_path)

            if key in seen:
                continue

            seen.add(key)

            rows.append(
                {
                    "manifest_row_index": manifest_row_index,
                    "study_key": row.get("study_key", None),
                    "dicom_path": dicom_path,
                    "local_dicom_path": str((dicom_root / dicom_path).resolve()),
                }
            )

    return pd.DataFrame(rows)


def load_feature_manifest(path, prefix):
    df = pd.read_csv(path)

    if "dicom_path" not in df.columns:
        raise KeyError(
            f"{prefix} manifest must contain 'dicom_path'. "
            f"Found columns: {df.columns.tolist()}"
        )

    df = df.copy()
    df["dicom_path"] = df["dicom_path"].map(clean_dicom_path)

    keep_columns = ["dicom_path"]

    rename_map = {}

    if "feature_path" in df.columns:
        keep_columns.append("feature_path")
        rename_map["feature_path"] = f"{prefix}_feature_path"

    if "status" in df.columns:
        keep_columns.append("status")
        rename_map["status"] = f"{prefix}_status"

    if "error" in df.columns:
        keep_columns.append("error")
        rename_map["error"] = f"{prefix}_error"

    if "model_name" in df.columns:
        keep_columns.append("model_name")
        rename_map["model_name"] = f"{prefix}_model_name"

    if "local_path" in df.columns:
        keep_columns.append("local_path")
        rename_map["local_path"] = f"{prefix}_local_path"

    df = df[keep_columns].rename(columns=rename_map)

    df = df.drop_duplicates(subset=["dicom_path"], keep="last")

    return df


def load_optional_manifest(path, prefix):
    if path is None:
        return None

    df = pd.read_csv(path)

    if "dicom_path" not in df.columns:
        print(f"Skipping {prefix} manifest because it has no dicom_path column: {path}")
        return None

    df = df.copy()
    df["dicom_path"] = df["dicom_path"].map(clean_dicom_path)

    rename_map = {}

    for column in df.columns:
        if column == "dicom_path":
            continue

        if column.startswith(prefix + "_"):
            continue

        rename_map[column] = f"{prefix}_{column}"

    df = df.rename(columns=rename_map)
    df = df.drop_duplicates(subset=["dicom_path"], keep="last")

    return df


def status_is_ready(value):
    return str(value).strip().lower() in {"success", "exists", "passed", "pass", "ok"}


def main():
    args = parse_args()

    study_manifest_path = args.study_manifest_path.resolve()
    dicom_root = args.dicom_root.resolve()
    convnext_manifest_path = args.convnext_manifest_path.resolve()
    raddino_manifest_path = args.raddino_manifest_path.resolve()
    output_path = args.output_path.resolve()

    validation_manifest_path = find_optional_path(
        args.validation_manifest_path,
        VALIDATION_CANDIDATES,
    )

    metrics_manifest_path = find_optional_path(
        args.metrics_manifest_path,
        METRIC_CANDIDATES,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("Study manifest:", study_manifest_path)
    print("DICOM root:", dicom_root)
    print("ConvNeXt manifest:", convnext_manifest_path)
    print("RAD-DINO manifest:", raddino_manifest_path)
    print("Validation manifest:", validation_manifest_path)
    print("Metrics manifest:", metrics_manifest_path)
    print("Output path:", output_path)

    base = build_base_manifest(
        study_manifest_path=study_manifest_path,
        dicom_root=dicom_root,
    )

    convnext = load_feature_manifest(
        path=convnext_manifest_path,
        prefix="convnext",
    )

    raddino = load_feature_manifest(
        path=raddino_manifest_path,
        prefix="raddino",
    )

    unified = base.merge(convnext, on="dicom_path", how="left")
    unified = unified.merge(raddino, on="dicom_path", how="left")

    validation = load_optional_manifest(
        path=validation_manifest_path,
        prefix="validation",
    )

    if validation is not None:
        unified = unified.merge(validation, on="dicom_path", how="left")

    metrics = load_optional_manifest(
        path=metrics_manifest_path,
        prefix="metrics",
    )

    if metrics is not None:
        unified = unified.merge(metrics, on="dicom_path", how="left")

    unified["local_dicom_exists"] = unified["local_dicom_path"].map(
        lambda path: Path(path).exists()
    )

    unified["convnext_ready"] = unified["convnext_status"].map(status_is_ready)
    unified["raddino_ready"] = unified["raddino_status"].map(status_is_ready)

    unified["workflow_a_feature_ready"] = (
        unified["local_dicom_exists"]
        & unified["convnext_ready"]
        & unified["raddino_ready"]
    )

    unified["missing_evidence"] = ""

    missing_masks = {
        "local_dicom": ~unified["local_dicom_exists"],
        "convnext_features": ~unified["convnext_ready"],
        "raddino_features": ~unified["raddino_ready"],
    }

    for evidence_name, mask in missing_masks.items():
        unified.loc[mask, "missing_evidence"] = unified.loc[
            mask, "missing_evidence"
        ].map(lambda value: f"{value}|{evidence_name}" if value else evidence_name)

    unified = unified.sort_values(
        by=["manifest_row_index", "dicom_path"],
        kind="stable",
    )

    unified.to_csv(output_path, index=False)

    print()
    print("Unified evidence manifest complete.")
    print("Rows:", len(unified))
    print(
        "Workflow A feature-ready counts:",
        unified["workflow_a_feature_ready"].value_counts(dropna=False).to_dict(),
    )
    print("Output:", output_path)

    if not unified["workflow_a_feature_ready"].all():
        print()
        print("Missing evidence counts:")
        print(unified["missing_evidence"].value_counts().to_string())


if __name__ == "__main__":
    main()