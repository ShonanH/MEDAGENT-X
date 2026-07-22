from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from medagentx.fusion.constants import (
    AGENT_EVAL_PATIENT_COUNT,
    AGENT_EVAL_SPLIT,
    FUSION_TEST_SPLIT,
    FUSION_TRAIN_SPLIT,
    FUSION_VAL_SPLIT,
    SPLIT_SEED,
    TEST_RATIO,
    TRAIN_RATIO,
    VAL_RATIO,
)


def assign_patient_split(patient_id: str, seed: int = SPLIT_SEED) -> str:
    digest = hashlib.md5(f"{seed}:{patient_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF

    if bucket < TRAIN_RATIO:
        return FUSION_TRAIN_SPLIT
    if bucket < TRAIN_RATIO + VAL_RATIO:
        return FUSION_VAL_SPLIT
    return FUSION_TEST_SPLIT


def patient_id_from_study_key(study_key: str) -> str:
    key = str(study_key).strip()
    if not key:
        return ""
    return key.split("/", 1)[0]


def deterministic_patient_sample(
    patient_ids: list[str],
    count: int,
    seed: int,
    salt: str,
) -> list[str]:
    keyed = [
        (hashlib.md5(f"{seed}:{salt}:{patient_id}".encode("utf-8")).hexdigest(), patient_id)
        for patient_id in patient_ids
    ]
    keyed.sort()
    return [patient_id for _, patient_id in keyed[:count]]


def build_patient_split_table(df: pd.DataFrame, patient_col: str = "deid_patient_id") -> pd.DataFrame:
    """Legacy hash-only train/validation/test split (no agent_eval holdout)."""
    patients = sorted(df[patient_col].dropna().astype(str).str.strip().unique())
    patients = [patient_id for patient_id in patients if patient_id]
    rows = [
        {"deid_patient_id": patient_id, "split": assign_patient_split(patient_id)}
        for patient_id in patients
    ]
    return pd.DataFrame(rows)


def build_cohort_split_table(
    df: pd.DataFrame,
    patient_col: str = "deid_patient_id",
    agent_eval_count: int = AGENT_EVAL_PATIENT_COUNT,
    seed: int = SPLIT_SEED,
) -> pd.DataFrame:
    """
  Assign every patient exactly one split:
    - agent_eval: fixed-size holdout for script 16 (never train/val)
    - train / validation / test: remaining patients for fusion classifier
    """
    patients = sorted(df[patient_col].dropna().astype(str).str.strip().unique())
    patients = [patient_id for patient_id in patients if patient_id]

    if len(patients) < agent_eval_count:
        raise ValueError(
            f"Need at least {agent_eval_count} unique patients for agent_eval holdout; "
            f"found {len(patients)}"
        )

    agent_eval_patients = set(
        deterministic_patient_sample(patients, agent_eval_count, seed, AGENT_EVAL_SPLIT)
    )
    remaining_patients = [patient_id for patient_id in patients if patient_id not in agent_eval_patients]

    rows: list[dict[str, str]] = []
    for patient_id in sorted(agent_eval_patients):
        rows.append({"deid_patient_id": patient_id, "split": AGENT_EVAL_SPLIT})
    for patient_id in remaining_patients:
        rows.append(
            {
                "deid_patient_id": patient_id,
                "split": assign_patient_split(patient_id, seed=seed),
            }
        )

    split_table = pd.DataFrame(rows)
    assert_cohort_split_integrity(split_table, agent_eval_count=agent_eval_count)
    return split_table


def load_patient_split_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Patient split metadata not found: {path}")

    split_table = pd.read_csv(path, dtype=str)
    required = {"deid_patient_id", "split"}
    missing = required - set(split_table.columns)
    if missing:
        raise ValueError(f"Split metadata missing columns {sorted(missing)}: {path}")

    split_table = split_table.copy()
    split_table["deid_patient_id"] = split_table["deid_patient_id"].astype(str).str.strip()
    split_table["split"] = split_table["split"].astype(str).str.strip()
    return split_table


def save_patient_split_artifacts(
    split_table: pd.DataFrame,
    split_metadata_path: Path,
    agent_eval_manifest_path: Path,
    *,
    cohort_patient_count: int,
    seed: int,
) -> None:
    split_metadata_path.parent.mkdir(parents=True, exist_ok=True)
    split_table.to_csv(split_metadata_path, index=False)

    agent_eval = split_table[split_table["split"] == AGENT_EVAL_SPLIT].copy()
    agent_eval = agent_eval.sort_values("deid_patient_id").reset_index(drop=True)
    agent_eval["selection_seed"] = str(seed)
    agent_eval["cohort_patient_count"] = str(cohort_patient_count)
    agent_eval.to_csv(agent_eval_manifest_path, index=False)


def get_patients_for_split(split_table: pd.DataFrame, split_name: str) -> set[str]:
    return set(
        split_table.loc[split_table["split"] == split_name, "deid_patient_id"]
        .astype(str)
        .str.strip()
    )


def assert_patient_level_integrity(
    df: pd.DataFrame,
    patient_col: str = "deid_patient_id",
    split_col: str = "split",
) -> None:
    bad = (
        df.groupby(patient_col)[split_col]
        .nunique()
        .reset_index(name="n_splits")
    )
    bad = bad[bad["n_splits"] > 1]
    if not bad.empty:
        raise ValueError(f"Patient leakage detected: {bad.to_dict(orient='records')}")


def assert_cohort_split_integrity(
    split_table: pd.DataFrame,
    agent_eval_count: int = AGENT_EVAL_PATIENT_COUNT,
) -> None:
    allowed_splits = {
        AGENT_EVAL_SPLIT,
        FUSION_TRAIN_SPLIT,
        FUSION_VAL_SPLIT,
        FUSION_TEST_SPLIT,
    }
    observed_splits = set(split_table["split"].astype(str).str.strip())
    unknown = observed_splits - allowed_splits
    if unknown:
        raise ValueError(f"Unexpected split values: {sorted(unknown)}")

    duplicate_patients = split_table["deid_patient_id"].duplicated().sum()
    if duplicate_patients:
        raise ValueError(f"Duplicate patient ids in split metadata: {int(duplicate_patients)}")

    agent_eval_patients = get_patients_for_split(split_table, AGENT_EVAL_SPLIT)
    if len(agent_eval_patients) != agent_eval_count:
        raise ValueError(
            f"Expected {agent_eval_count} agent_eval patients, found {len(agent_eval_patients)}"
        )

    fusion_patients = split_table[split_table["split"] != AGENT_EVAL_SPLIT]["deid_patient_id"]
    overlap = agent_eval_patients & set(fusion_patients.astype(str))
    if overlap:
        raise ValueError(
            f"agent_eval patients overlap fusion splits: {sorted(overlap)[:5]} ..."
        )


def assert_patients_not_in_splits(
    patient_ids: set[str] | list[str],
    split_table: pd.DataFrame,
    forbidden_splits: set[str],
    *,
    context: str,
) -> None:
    lookup = split_table.set_index("deid_patient_id")["split"].to_dict()
    violations = []
    for patient_id in patient_ids:
        patient_id = str(patient_id).strip()
        split_name = lookup.get(patient_id)
        if split_name in forbidden_splits:
            violations.append({"deid_patient_id": patient_id, "split": split_name})

    if violations:
        raise ValueError(
            f"{context}: found {len(violations)} patients in forbidden splits "
            f"{sorted(forbidden_splits)} (example: {violations[0]})"
        )


def attach_patient_ids(df: pd.DataFrame, patient_col: str = "deid_patient_id") -> pd.DataFrame:
    out = df.copy()
    if patient_col not in out.columns:
        if "study_key" not in out.columns:
            raise ValueError(f"Need {patient_col} or study_key to attach patient ids")
        out[patient_col] = out["study_key"].map(patient_id_from_study_key)
    out[patient_col] = out[patient_col].astype(str).str.strip()
    return out
