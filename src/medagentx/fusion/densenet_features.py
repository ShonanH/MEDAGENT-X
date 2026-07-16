from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.medagentx.fusion.constants import DEFAULT_DENSENET_PREDICTIONS, DISEASE_LABELS, snake_label
from src.medagentx.fusion.paths import clean_dicom_path


def _safe_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(out):
        return None
    return out


def densenet_prob_vector_from_row(row: pd.Series) -> np.ndarray:
    values = []
    for label in DISEASE_LABELS:
        slug = snake_label(label)
        prob = _safe_float(row.get(f"classifier_prob_{slug}"))
        values.append(0.0 if prob is None else prob)
    return np.asarray(values, dtype=np.float32)


def load_densenet_prediction_table(
    densenet_csv: str | Path = DEFAULT_DENSENET_PREDICTIONS,
) -> pd.DataFrame:
    path = Path(densenet_csv)
    if not path.exists():
        raise FileNotFoundError(f"DenseNet predictions not found: {path}")

    df = pd.read_csv(path, dtype=str)
    df["dicom_path"] = df["dicom_path"].map(clean_dicom_path)
    return df


def densenet_prob_lookup(
    densenet_df: pd.DataFrame,
) -> dict[str, np.ndarray]:
    lookup: dict[str, np.ndarray] = {}
    for _, row in densenet_df.iterrows():
        lookup[clean_dicom_path(row["dicom_path"])] = densenet_prob_vector_from_row(row)
    return lookup


def attach_densenet_prob_columns(df: pd.DataFrame, densenet_lookup: dict[str, np.ndarray]) -> pd.DataFrame:
    out = df.copy()
    vectors = []
    for _, row in out.iterrows():
        dicom_path = clean_dicom_path(row["dicom_path"])
        vectors.append(densenet_lookup.get(dicom_path, np.zeros(len(DISEASE_LABELS), dtype=np.float32)))
    out["densenet_prob_vector_json"] = [vec.astype(float).tolist() for vec in vectors]
    return out
