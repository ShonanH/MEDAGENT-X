from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from torch.utils.data import Dataset

from src.medagentx.fusion.constants import DISEASE_LABELS, snake_label
from src.medagentx.fusion.densenet_features import (
    attach_densenet_prob_columns,
    densenet_prob_lookup,
    load_densenet_prediction_table,
)
from src.medagentx.fusion.features import (
    aggregate_study_features,
    attention_aggregate_study_features,
    concat_image_features,
    merge_label_and_feature_tables,
)
from src.medagentx.fusion.labels import LABEL_MODE_JUDGE, training_value_from_row


def vector_from_jsonish(value) -> np.ndarray:
    if isinstance(value, (list, tuple, np.ndarray)):
        return np.asarray(value, dtype=np.float32)
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.zeros(len(DISEASE_LABELS), dtype=np.float32)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return np.zeros(len(DISEASE_LABELS), dtype=np.float32)
        return np.asarray(json.loads(text), dtype=np.float32)
    raise TypeError(f"Unsupported vector value type: {type(value)}")


class FusionFeatureDataset(Dataset):
    def __init__(
        self,
        X: np.ndarray,
        y: np.ndarray,
        mask: np.ndarray,
        densenet_probs: np.ndarray | None = None,
    ):
        self.X = X.astype(np.float32)
        self.y = y.astype(np.float32)
        self.mask = mask.astype(np.float32)
        self.densenet_probs = None if densenet_probs is None else densenet_probs.astype(np.float32)

    def __len__(self) -> int:
        return self.X.shape[0]

    def __getitem__(self, idx: int):
        if self.densenet_probs is None:
            return self.X[idx], self.y[idx], self.mask[idx]
        return self.X[idx], self.densenet_probs[idx], self.y[idx], self.mask[idx]


def build_image_training_table(
    label_df: pd.DataFrame,
    feature_df: pd.DataFrame,
    feature_mode: str,
    densenet_csv: Path | None,
    label_mode: str = LABEL_MODE_JUDGE,
) -> pd.DataFrame:
    merged = merge_label_and_feature_tables(label_df, feature_df)
    if densenet_csv is not None and Path(densenet_csv).exists():
        merged = attach_densenet_prob_columns(
            merged,
            densenet_prob_lookup(load_densenet_prediction_table(densenet_csv)),
        )
    else:
        merged["densenet_prob_vector_json"] = [
            [0.0] * len(DISEASE_LABELS) for _ in range(len(merged))
        ]

    rows = []
    for _, row in merged.iterrows():
        embedding = concat_image_features(
            row["convnext_feature_path"],
            row["raddino_feature_path"],
            feature_mode=feature_mode,
        )
        out = {
            "study_key": row["study_key"],
            "dicom_path": row["dicom_path"],
            "deid_patient_id": row["deid_patient_id"],
            "feature_vector_json": json.dumps(embedding.astype(float).tolist()),
            "densenet_prob_vector_json": json.dumps(
                vector_from_jsonish(row["densenet_prob_vector_json"]).astype(float).tolist()
            ),
        }
        for label in DISEASE_LABELS:
            slug = snake_label(label)
            out[f"label_value_{slug}"] = training_value_from_row(row, label, label_mode)
        rows.append(out)

    return pd.DataFrame(rows)


def build_study_training_table(
    image_table: pd.DataFrame,
    pool_mode: str = "attention",
) -> pd.DataFrame:
    rows = []
    for study_key, group in image_table.groupby("study_key", sort=False):
        embeddings = [vector_from_jsonish(v) for v in group["feature_vector_json"]]
        densenet_vectors = [vector_from_jsonish(v) for v in group["densenet_prob_vector_json"]]
        if pool_mode == "attention":
            x_study = attention_aggregate_study_features(embeddings)
            d_study = attention_aggregate_study_features(densenet_vectors)
        else:
            x_study = aggregate_study_features(embeddings)
            d_study = aggregate_study_features(densenet_vectors)

        first = group.iloc[0]
        out = {
            "study_key": study_key,
            "deid_patient_id": first["deid_patient_id"],
            "image_count": len(group),
            "feature_vector_json": json.dumps(x_study.astype(float).tolist()),
            "densenet_prob_vector_json": json.dumps(d_study.astype(float).tolist()),
        }
        for label in DISEASE_LABELS:
            slug = snake_label(label)
            values = []
            for _, row in group.iterrows():
                value = row.get(f"label_value_{slug}")
                if value is None or value == "" or (isinstance(value, float) and np.isnan(value)):
                    continue
                values.append(float(value))
            if not values:
                out[f"label_value_{slug}"] = np.nan
            else:
                out[f"label_value_{slug}"] = float(np.mean(values))
        rows.append(out)
    return pd.DataFrame(rows)


def arrays_from_training_table(
    table_df: pd.DataFrame,
    include_densenet_probs: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]:
    X = np.stack(
        [vector_from_jsonish(v) for v in table_df["feature_vector_json"]],
        axis=0,
    )

    densenet_probs = None
    if include_densenet_probs:
        densenet_probs = np.stack(
            [vector_from_jsonish(v) for v in table_df["densenet_prob_vector_json"]],
            axis=0,
        )

    y = []
    mask = []
    for _, row in table_df.iterrows():
        y_row = []
        m_row = []
        for label in DISEASE_LABELS:
            slug = snake_label(label)
            value = row.get(f"label_value_{slug}")
            if value is None or value == "" or (isinstance(value, float) and np.isnan(value)):
                y_row.append(0.0)
                m_row.append(0.0)
            else:
                y_row.append(float(value))
                m_row.append(1.0)
        y.append(y_row)
        mask.append(m_row)

    return (
        X,
        np.asarray(y, dtype=np.float32),
        np.asarray(mask, dtype=np.float32),
        densenet_probs,
    )
