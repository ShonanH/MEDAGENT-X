from __future__ import annotations

import hashlib

import pandas as pd

from src.medagentx.fusion.constants import SPLIT_SEED, TEST_RATIO, TRAIN_RATIO, VAL_RATIO


def assign_patient_split(patient_id: str, seed: int = SPLIT_SEED) -> str:
    digest = hashlib.md5(f"{seed}:{patient_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF

    if bucket < TRAIN_RATIO:
        return "train"
    if bucket < TRAIN_RATIO + VAL_RATIO:
        return "validation"
    return "test"


def build_patient_split_table(df: pd.DataFrame, patient_col: str = "deid_patient_id") -> pd.DataFrame:
    patients = sorted(df[patient_col].dropna().unique())
    rows = [{"deid_patient_id": pid, "split": assign_patient_split(pid)} for pid in patients]
    return pd.DataFrame(rows)


def assert_patient_level_integrity(df: pd.DataFrame, patient_col: str = "deid_patient_id", split_col: str = "split") -> None:
    bad = (
        df.groupby(patient_col)[split_col]
        .nunique()
        .reset_index(name="n_splits")
    )
    bad = bad[bad["n_splits"] > 1]
    if not bad.empty:
        raise ValueError(f"Patient leakage detected: {bad.to_dict(orient='records')}")