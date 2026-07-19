#!/usr/bin/env python3
"""
Build MEDAGENT-X Workflow A quality evidence signals.

This script reads:
  outputs/chexpert_plus/unified_evidence_manifest.csv

Then it computes unsupervised evidence from:
  - DICOM preprocessing / validation metrics (optional; from script 04)
  - ConvNeXt local visual features
  - RAD-DINO Transformer/global features

It does NOT train a model.
It does NOT require labels.
It does NOT make final Quality Gate Agent decisions.

Output:
  outputs/chexpert_plus/quality_evidence_manifest.csv
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_UNIFIED_MANIFEST = (
    PROJECT_ROOT / "outputs" / "chexpert_plus" / "unified_evidence_manifest.csv"
)

DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "outputs" / "chexpert_plus" / "quality_evidence_manifest.csv"
)


VALIDATION_METRIC_COLUMNS = [
    "validation_intensity_mean",
    "validation_intensity_std",
    "validation_contrast_proxy",
    "validation_noise_proxy",
    "validation_blur_proxy",
    "validation_sharpness_proxy",
    "validation_edge_density",
    "validation_entropy",
]

BASE_EVIDENCE_COLUMNS = [
    "manifest_row_index",
    "study_key",
    "dicom_path",
    "local_dicom_path",
    "workflow_a_feature_ready",
    "convnext_feature_path",
    "raddino_feature_path",
]

OPTIONAL_VALIDATION_ID_COLUMNS = [
    "validation_status",
    "validation_preview_path",
    "validation_metadata_path",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build unsupervised quality evidence manifest."
    )

    parser.add_argument(
        "--unified-manifest-path",
        type=Path,
        default=DEFAULT_UNIFIED_MANIFEST,
    )

    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
    )

    return parser.parse_args()


def as_bool(value):
    return str(value).strip().lower() in {"true", "1", "yes", "ok", "success", "exists"}


def safe_float(value):
    try:
        if pd.isna(value):
            return np.nan
        return float(value)
    except Exception:
        return np.nan


def robust_location_scale(values):
    values = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=np.float64)
    finite = values[np.isfinite(values)]

    if len(finite) == 0:
        return np.nan, np.nan

    median = float(np.median(finite))
    mad = float(np.median(np.abs(finite - median)))

    if mad > 0:
        return median, 1.4826 * mad

    q25, q75 = np.percentile(finite, [25, 75])
    iqr = float(q75 - q25)

    if iqr > 0:
        return median, iqr / 1.349

    std = float(np.std(finite))

    if std > 0:
        return median, std

    return median, 1.0


def robust_z(values):
    values = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=np.float64)
    center, scale = robust_location_scale(values)

    if not np.isfinite(center) or not np.isfinite(scale) or scale == 0:
        return np.full(values.shape, np.nan, dtype=np.float64)

    return np.abs((values - center) / scale)


def upper_tail_z(values):
    values = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=np.float64)
    center, scale = robust_location_scale(values)

    if not np.isfinite(center) or not np.isfinite(scale) or scale == 0:
        return np.full(values.shape, np.nan, dtype=np.float64)

    return np.maximum((values - center) / scale, 0.0)


def lower_tail_z(values):
    values = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=np.float64)
    center, scale = robust_location_scale(values)

    if not np.isfinite(center) or not np.isfinite(scale) or scale == 0:
        return np.full(values.shape, np.nan, dtype=np.float64)

    return np.maximum((center - values) / scale, 0.0)


def load_npz(path):
    path = Path(str(path))

    if not path.exists():
        return None

    try:
        with np.load(path, allow_pickle=False) as data:
            return {key: data[key] for key in data.files}
    except Exception:
        return None


def finite_stats(array):
    array = np.asarray(array)
    nan_count = int(np.isnan(array).sum()) if np.issubdtype(array.dtype, np.number) else 0
    inf_count = int(np.isinf(array).sum()) if np.issubdtype(array.dtype, np.number) else 0

    numeric = np.asarray(array, dtype=np.float32).reshape(-1)
    finite = numeric[np.isfinite(numeric)]

    if len(finite) == 0:
        return {
            "valid": False,
            "dim": int(numeric.size),
            "norm": np.nan,
            "mean": np.nan,
            "std": np.nan,
            "min": np.nan,
            "max": np.nan,
            "nan_count": nan_count,
            "inf_count": inf_count,
        }

    return {
        "valid": nan_count == 0 and inf_count == 0,
        "dim": int(numeric.size),
        "norm": float(np.linalg.norm(finite)),
        "mean": float(np.mean(finite)),
        "std": float(np.std(finite)),
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "nan_count": nan_count,
        "inf_count": inf_count,
    }


def global_pool_feature_map(feature_map):
    feature_map = np.asarray(feature_map, dtype=np.float32)

    if feature_map.ndim == 4 and feature_map.shape[0] == 1:
        feature_map = feature_map[0]

    if feature_map.ndim == 3:
        return feature_map.mean(axis=(1, 2))

    return feature_map.reshape(-1)


def extract_convnext_vector(payload):
    if payload is None:
        return None, "missing_npz"

    for key in ["pooled_embedding", "embedding", "features", "feature_vector"]:
        if key in payload:
            return np.asarray(payload[key], dtype=np.float32).reshape(-1), key

    if "feature_map" in payload:
        return global_pool_feature_map(payload["feature_map"]), "feature_map_global_pool"

    return None, "no_supported_key"


def extract_raddino_vector(payload):
    if payload is None:
        return None, "missing_npz"

    if "cls_embedding" in payload:
        return np.asarray(payload["cls_embedding"], dtype=np.float32).reshape(-1), "cls_embedding"

    if "patch_embeddings" in payload:
        patch_embeddings = np.asarray(payload["patch_embeddings"], dtype=np.float32)

        if patch_embeddings.ndim >= 2:
            return patch_embeddings.mean(axis=0).reshape(-1), "patch_embeddings_mean"

        return patch_embeddings.reshape(-1), "patch_embeddings_flat"

    return None, "no_supported_key"


def patch_embedding_stats(payload):
    if payload is None or "patch_embeddings" not in payload:
        return {
            "raddino_patch_token_count": np.nan,
            "raddino_patch_dim": np.nan,
            "raddino_patch_mean": np.nan,
            "raddino_patch_std": np.nan,
            "raddino_patch_variability": np.nan,
        }

    patch_embeddings = np.asarray(payload["patch_embeddings"], dtype=np.float32)

    if patch_embeddings.ndim != 2:
        flat = patch_embeddings.reshape(-1)

        return {
            "raddino_patch_token_count": np.nan,
            "raddino_patch_dim": np.nan,
            "raddino_patch_mean": float(np.nanmean(flat)),
            "raddino_patch_std": float(np.nanstd(flat)),
            "raddino_patch_variability": float(np.nanstd(flat)),
        }

    token_norms = np.linalg.norm(patch_embeddings, axis=1)

    return {
        "raddino_patch_token_count": int(patch_embeddings.shape[0]),
        "raddino_patch_dim": int(patch_embeddings.shape[1]),
        "raddino_patch_mean": float(np.nanmean(patch_embeddings)),
        "raddino_patch_std": float(np.nanstd(patch_embeddings)),
        "raddino_patch_variability": float(np.nanstd(token_norms)),
    }


def build_matrix(vectors):
    valid_indices = []
    valid_vectors = []

    dims = [len(vector) for vector in vectors if vector is not None]

    if not dims:
        return None, []

    target_dim = max(set(dims), key=dims.count)

    for index, vector in enumerate(vectors):
        if vector is None:
            continue

        vector = np.asarray(vector, dtype=np.float32).reshape(-1)

        if len(vector) != target_dim:
            continue

        if not np.all(np.isfinite(vector)):
            continue

        valid_indices.append(index)
        valid_vectors.append(vector)

    if not valid_vectors:
        return None, []

    return np.stack(valid_vectors, axis=0), valid_indices


def robust_vector_distance(matrix):
    if matrix is None or len(matrix) == 0:
        return np.array([], dtype=np.float64)

    matrix = np.asarray(matrix, dtype=np.float64)

    center = np.median(matrix, axis=0)
    q25 = np.percentile(matrix, 25, axis=0)
    q75 = np.percentile(matrix, 75, axis=0)
    scale = (q75 - q25) / 1.349

    fallback_scale = np.std(matrix, axis=0)
    scale = np.where(scale > 1e-8, scale, fallback_scale)
    scale = np.where(scale > 1e-8, scale, 1.0)

    scaled = (matrix - center) / scale

    return np.sqrt(np.mean(np.square(scaled), axis=1))


def add_vector_outlier_scores(output_df, vectors, prefix):
    matrix, valid_indices = build_matrix(vectors)

    distance_col = f"{prefix}_embedding_outlier_distance"
    z_col = f"{prefix}_embedding_outlier_z"

    output_df[distance_col] = np.nan
    output_df[z_col] = np.nan

    if matrix is None or not valid_indices:
        return output_df

    distances = robust_vector_distance(matrix)
    distance_z = robust_z(distances)

    output_df.loc[valid_indices, distance_col] = distances
    output_df.loc[valid_indices, z_col] = distance_z

    return output_df


def main():
    args = parse_args()

    unified_path = args.unified_manifest_path.resolve()
    output_path = args.output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    unified = pd.read_csv(unified_path)

    required_columns = [
        "dicom_path",
        "study_key",
        "workflow_a_feature_ready",
        "convnext_feature_path",
        "raddino_feature_path",
    ]

    missing_required = [column for column in required_columns if column not in unified.columns]

    if missing_required:
        raise KeyError(f"Unified manifest is missing required columns: {missing_required}")

    print("Unified manifest:", unified_path)
    print("Rows:", len(unified))
    print("Output:", output_path)

    has_validation_manifest = "validation_status" in unified.columns
    if not has_validation_manifest:
        print("Note: no validation manifest columns (script 04 skipped); using ConvNeXt/RAD-DINO evidence only.")

    evidence_columns = [column for column in BASE_EVIDENCE_COLUMNS if column in unified.columns]
    evidence = unified[evidence_columns].copy()

    for column in OPTIONAL_VALIDATION_ID_COLUMNS:
        if column in unified.columns:
            evidence[column] = unified[column]
        elif column == "validation_status":
            evidence[column] = "not_run"
        else:
            evidence[column] = ""

    for column in VALIDATION_METRIC_COLUMNS:
        if column in unified.columns:
            evidence[column] = pd.to_numeric(unified[column], errors="coerce")
            evidence[f"{column}_outlier_z"] = robust_z(evidence[column])
        else:
            evidence[column] = np.nan
            evidence[f"{column}_outlier_z"] = np.nan

    if "validation_contrast_proxy" in evidence.columns:
        evidence["low_contrast_evidence_z"] = lower_tail_z(evidence["validation_contrast_proxy"])

    if "validation_sharpness_proxy" in evidence.columns:
        evidence["low_sharpness_evidence_z"] = lower_tail_z(evidence["validation_sharpness_proxy"])

    if "validation_entropy" in evidence.columns:
        evidence["low_entropy_evidence_z"] = lower_tail_z(evidence["validation_entropy"])

    if "validation_blur_proxy" in evidence.columns:
        evidence["high_blur_evidence_z"] = upper_tail_z(evidence["validation_blur_proxy"])

    if "validation_noise_proxy" in evidence.columns:
        evidence["high_noise_evidence_z"] = upper_tail_z(evidence["validation_noise_proxy"])

    convnext_vectors = []
    raddino_vectors = []

    feature_rows = []

    for _, row in tqdm(unified.iterrows(), total=len(unified), desc="Reading feature files"):
        convnext_payload = load_npz(row["convnext_feature_path"])
        raddino_payload = load_npz(row["raddino_feature_path"])

        convnext_vector, convnext_source = extract_convnext_vector(convnext_payload)
        raddino_vector, raddino_source = extract_raddino_vector(raddino_payload)

        convnext_vectors.append(convnext_vector)
        raddino_vectors.append(raddino_vector)

        convnext_stats = finite_stats(convnext_vector) if convnext_vector is not None else {
            "valid": False,
            "dim": np.nan,
            "norm": np.nan,
            "mean": np.nan,
            "std": np.nan,
            "min": np.nan,
            "max": np.nan,
            "nan_count": np.nan,
            "inf_count": np.nan,
        }

        raddino_stats = finite_stats(raddino_vector) if raddino_vector is not None else {
            "valid": False,
            "dim": np.nan,
            "norm": np.nan,
            "mean": np.nan,
            "std": np.nan,
            "min": np.nan,
            "max": np.nan,
            "nan_count": np.nan,
            "inf_count": np.nan,
        }

        patch_stats = patch_embedding_stats(raddino_payload)

        feature_rows.append(
            {
                "convnext_vector_source": convnext_source,
                "convnext_vector_valid": convnext_stats["valid"],
                "convnext_vector_dim": convnext_stats["dim"],
                "convnext_embedding_norm": convnext_stats["norm"],
                "convnext_embedding_mean": convnext_stats["mean"],
                "convnext_embedding_std": convnext_stats["std"],
                "convnext_embedding_min": convnext_stats["min"],
                "convnext_embedding_max": convnext_stats["max"],
                "convnext_embedding_nan_count": convnext_stats["nan_count"],
                "convnext_embedding_inf_count": convnext_stats["inf_count"],
                "raddino_vector_source": raddino_source,
                "raddino_vector_valid": raddino_stats["valid"],
                "raddino_vector_dim": raddino_stats["dim"],
                "raddino_embedding_norm": raddino_stats["norm"],
                "raddino_embedding_mean": raddino_stats["mean"],
                "raddino_embedding_std": raddino_stats["std"],
                "raddino_embedding_min": raddino_stats["min"],
                "raddino_embedding_max": raddino_stats["max"],
                "raddino_embedding_nan_count": raddino_stats["nan_count"],
                "raddino_embedding_inf_count": raddino_stats["inf_count"],
                **patch_stats,
            }
        )

    feature_df = pd.DataFrame(feature_rows)
    evidence = pd.concat([evidence, feature_df], axis=1)

    for column in [
        "convnext_embedding_norm",
        "convnext_embedding_mean",
        "convnext_embedding_std",
        "raddino_embedding_norm",
        "raddino_embedding_mean",
        "raddino_embedding_std",
        "raddino_patch_variability",
    ]:
        evidence[f"{column}_outlier_z"] = robust_z(evidence[column])

    evidence = add_vector_outlier_scores(
        output_df=evidence,
        vectors=convnext_vectors,
        prefix="convnext",
    )

    evidence = add_vector_outlier_scores(
        output_df=evidence,
        vectors=raddino_vectors,
        prefix="raddino",
    )

    validation_ok = (
        evidence["validation_status"].map(as_bool)
        if has_validation_manifest
        else pd.Series(True, index=evidence.index)
    )

    evidence["evidence_complete"] = (
        evidence["workflow_a_feature_ready"].map(as_bool)
        & evidence["convnext_vector_valid"].astype(bool)
        & evidence["raddino_vector_valid"].astype(bool)
        & validation_ok
    )

    evidence["max_handcrafted_quality_outlier_z"] = evidence[
        [
            "validation_intensity_mean_outlier_z",
            "validation_intensity_std_outlier_z",
            "validation_contrast_proxy_outlier_z",
            "validation_noise_proxy_outlier_z",
            "validation_blur_proxy_outlier_z",
            "validation_sharpness_proxy_outlier_z",
            "validation_edge_density_outlier_z",
            "validation_entropy_outlier_z",
        ]
    ].max(axis=1)

    evidence["max_deep_feature_outlier_z"] = evidence[
        [
            "convnext_embedding_outlier_z",
            "raddino_embedding_outlier_z",
            "convnext_embedding_norm_outlier_z",
            "raddino_embedding_norm_outlier_z",
        ]
    ].max(axis=1)

    evidence["max_quality_evidence_z"] = evidence[
        [
            "max_handcrafted_quality_outlier_z",
            "max_deep_feature_outlier_z",
            "low_contrast_evidence_z",
            "low_sharpness_evidence_z",
            "low_entropy_evidence_z",
            "high_blur_evidence_z",
            "high_noise_evidence_z",
        ]
    ].max(axis=1)

    evidence["evidence_notes"] = ""

    evidence.loc[~evidence["evidence_complete"], "evidence_notes"] = "incomplete_evidence"

    evidence.loc[
        evidence["max_quality_evidence_z"] >= 6.0,
        "evidence_notes",
    ] = evidence.loc[
        evidence["max_quality_evidence_z"] >= 6.0,
        "evidence_notes",
    ].map(lambda value: f"{value}|extreme_outlier" if value else "extreme_outlier")

    evidence.loc[
        (evidence["max_quality_evidence_z"] >= 3.5)
        & (evidence["max_quality_evidence_z"] < 6.0),
        "evidence_notes",
    ] = evidence.loc[
        (evidence["max_quality_evidence_z"] >= 3.5)
        & (evidence["max_quality_evidence_z"] < 6.0),
        "evidence_notes",
    ].map(lambda value: f"{value}|moderate_outlier" if value else "moderate_outlier")

    evidence.to_csv(output_path, index=False)

    print()
    print("Quality evidence manifest complete.")
    print("Rows:", len(evidence))
    print("Evidence complete counts:", evidence["evidence_complete"].value_counts(dropna=False).to_dict())
    print("Evidence notes counts:", evidence["evidence_notes"].value_counts(dropna=False).to_dict())
    print("Output:", output_path)


if __name__ == "__main__":
    main()