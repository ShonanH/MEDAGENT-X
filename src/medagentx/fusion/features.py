from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.medagentx.fusion.constants import DEFAULT_CONVNEXT_MANIFEST, DEFAULT_RADDINO_MANIFEST
from src.medagentx.fusion.paths import clean_dicom_path


CONVNEXT_OK_STATUSES = {"ok"}
RADDINO_OK_STATUSES = {"success", "exists"}


def load_npz_vector(feature_path: str | Path, key: str) -> np.ndarray:
    payload = np.load(feature_path, allow_pickle=True)
    if key not in payload:
        raise KeyError(f"Missing key '{key}' in {feature_path}")
    vector = np.asarray(payload[key], dtype=np.float32).reshape(-1)
    return vector


def load_convnext_pooled(feature_path: str | Path) -> np.ndarray:
    return load_npz_vector(feature_path, "pooled_embedding")


def load_raddino_cls(feature_path: str | Path) -> np.ndarray:
    return load_npz_vector(feature_path, "cls_embedding")


def concat_image_features(
    convnext_path: str | Path,
    raddino_path: str | Path,
    feature_mode: str = "fusion",
) -> np.ndarray:
    if feature_mode == "convnext_only":
        return load_convnext_pooled(convnext_path)

    if feature_mode == "raddino_only":
        return load_raddino_cls(raddino_path)

    if feature_mode == "fusion":
        conv = load_convnext_pooled(convnext_path)
        rad = load_raddino_cls(raddino_path)
        return np.concatenate([conv, rad], axis=0)

    raise ValueError(f"Unknown feature_mode: {feature_mode}")


def feature_dim_for_mode(feature_mode: str) -> int:
    if feature_mode in {"convnext_only", "raddino_only"}:
        return 768
    if feature_mode == "fusion":
        return 1536
    raise ValueError(feature_mode)


def load_feature_manifests(
    convnext_manifest_path: str | Path = DEFAULT_CONVNEXT_MANIFEST,
    raddino_manifest_path: str | Path = DEFAULT_RADDINO_MANIFEST,
) -> pd.DataFrame:
    conv = pd.read_csv(convnext_manifest_path, dtype=str)
    rad = pd.read_csv(raddino_manifest_path, dtype=str)

    conv = conv.copy()
    rad = rad.copy()

    conv["dicom_path"] = conv["dicom_path"].map(clean_dicom_path)
    rad["dicom_path"] = rad["dicom_path"].map(clean_dicom_path)

    merged = conv.merge(
        rad[["dicom_path", "feature_path", "status"]],
        on="dicom_path",
        how="inner",
        suffixes=("_convnext", "_raddino"),
    )

    merged = merged.rename(
        columns={
            "feature_path_convnext": "convnext_feature_path",
            "status_convnext": "convnext_status",
            "feature_path_raddino": "raddino_feature_path",
            "status_raddino": "raddino_status",
        }
    )

    merged["feature_ready"] = (
        merged["convnext_status"].isin(CONVNEXT_OK_STATUSES)
        & merged["raddino_status"].isin(RADDINO_OK_STATUSES)
    )

    return merged


def aggregate_study_features(
    image_features: list[np.ndarray],
) -> np.ndarray:
    if not image_features:
        raise ValueError("No image features to aggregate")
    stacked = np.stack(image_features, axis=0)
    return stacked.mean(axis=0)