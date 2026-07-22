from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from medagentx.fusion.constants import (
    AGENT_EVAL_MIN_CASES,
    AGENT_EVAL_PATIENT_COUNT,
    AGENT_EVAL_SPLIT,
    FUSION_TEST_SPLIT,
    FUSION_TRAIN_SPLIT,
    FUSION_VAL_SPLIT,
    QUALITY_GATE_PASS_DECISIONS,
    QUALITY_GATE_ROUTE_RETRIEVAL,
    SPLIT_SEED,
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


def deterministic_patient_order(patient_ids: list[str], seed: int, salt: str) -> list[str]:
    keyed = [
        (hashlib.md5(f"{seed}:{salt}:{patient_id}".encode("utf-8")).hexdigest(), patient_id)
        for patient_id in patient_ids
    ]
    keyed.sort()
    return [patient_id for _, patient_id in keyed]


def deterministic_patient_sample(
    patient_ids: list[str],
    count: int,
    seed: int,
    salt: str,
) -> list[str]:
    return deterministic_patient_order(patient_ids, seed, salt)[:count]


def attach_patient_ids(df: pd.DataFrame, patient_col: str = "deid_patient_id") -> pd.DataFrame:
    out = df.copy()
    if patient_col not in out.columns:
        if "study_key" not in out.columns:
            raise ValueError(f"Need {patient_col} or study_key to attach patient ids")
        out[patient_col] = out["study_key"].map(patient_id_from_study_key)
    out[patient_col] = out[patient_col].astype(str).str.strip()
    return out


def filter_quality_gate_eligible(
    quality_gate_df: pd.DataFrame,
    *,
    pass_decisions: tuple[str, ...] = QUALITY_GATE_PASS_DECISIONS,
    route_next: str = QUALITY_GATE_ROUTE_RETRIEVAL,
) -> pd.DataFrame:
    required_columns = {
        "study_key",
        "dicom_path",
        "quality_gate_decision",
        "route_next",
    }
    missing = required_columns - set(quality_gate_df.columns)
    if missing:
        raise ValueError(
            f"Quality gate table missing required columns: {sorted(missing)}"
        )

    eligible = attach_patient_ids(quality_gate_df)
    eligible = eligible[
        eligible["quality_gate_decision"].isin(pass_decisions)
        & eligible["route_next"].eq(route_next)
        & eligible["deid_patient_id"].ne("")
    ].copy()
    return eligible.reset_index(drop=True)


def load_quality_gate_eligible_cases(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Quality gate decisions not found: {path}. Run script 10 first."
        )
    return filter_quality_gate_eligible(pd.read_csv(path, dtype=str))


def eligible_study_keys(eligible_df: pd.DataFrame) -> set[str]:
    return set(eligible_df["study_key"].astype(str).str.strip())


def select_agent_eval_patients(
    eligible_df: pd.DataFrame,
    *,
    target_patient_count: int = AGENT_EVAL_PATIENT_COUNT,
    min_case_count: int = AGENT_EVAL_MIN_CASES,
    seed: int = SPLIT_SEED,
    patient_col: str = "deid_patient_id",
) -> tuple[set[str], int]:
    eligible_df = attach_patient_ids(eligible_df, patient_col=patient_col)
    case_counts = eligible_df.groupby(patient_col).size().to_dict()
    patients = sorted(case_counts)
    if not patients:
        raise ValueError("No quality-gate eligible patients found.")

    ordered = deterministic_patient_order(patients, seed, AGENT_EVAL_SPLIT)
    selected: list[str] = []
    total_cases = 0

    for patient_id in ordered:
        selected.append(patient_id)
        total_cases += int(case_counts[patient_id])
        if len(selected) >= target_patient_count and total_cases >= min_case_count:
            break

    if total_cases < min_case_count:
        for patient_id in ordered[len(selected) :]:
            selected.append(patient_id)
            total_cases += int(case_counts[patient_id])
            if total_cases >= min_case_count:
                break

    if total_cases < min_case_count:
        raise ValueError(
            f"Quality-gate passing cohort has only {total_cases} eligible cases across "
            f"{len(patients)} patients; need at least {min_case_count}. "
            "Expand the study manifest and re-run scripts 04-10."
        )

    return set(selected), total_cases


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
    Assign every patient exactly one split from a patient list (legacy helper).

    Prefer build_cohort_split_table_from_quality_gate() after script 11.
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
    assert_cohort_split_integrity(split_table)
    return split_table


def build_cohort_split_table_from_quality_gate(
    quality_gate_df: pd.DataFrame,
    *,
    agent_eval_patient_count: int = AGENT_EVAL_PATIENT_COUNT,
    agent_eval_min_cases: int = AGENT_EVAL_MIN_CASES,
    seed: int = SPLIT_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """
    Build frozen splits from quality-gate-passing cases only.

    Returns:
      - patient split metadata
      - eligible cohort snapshot (passing views)
      - summary stats
    """
    eligible_df = filter_quality_gate_eligible(quality_gate_df)
    if eligible_df.empty:
        raise ValueError(
            "No quality-gate eligible cases found. "
            "Run scripts 08-10 and ensure cases pass with route_next=retrieval_agent."
        )

    agent_eval_patients, agent_eval_cases = select_agent_eval_patients(
        eligible_df,
        target_patient_count=agent_eval_patient_count,
        min_case_count=agent_eval_min_cases,
        seed=seed,
    )
    all_patients = sorted(eligible_df["deid_patient_id"].unique())
    remaining_patients = [
        patient_id for patient_id in all_patients if patient_id not in agent_eval_patients
    ]

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
    assert_cohort_split_integrity(
        split_table,
        min_agent_eval_patients=1,
        min_agent_eval_cases=agent_eval_min_cases,
        eligible_df=eligible_df,
    )

    stats = {
        "eligible_cases": len(eligible_df),
        "eligible_patients": eligible_df["deid_patient_id"].nunique(),
        "agent_eval_patients": len(agent_eval_patients),
        "agent_eval_cases": agent_eval_cases,
        "train_patients": int((split_table["split"] == FUSION_TRAIN_SPLIT).sum()),
        "validation_patients": int((split_table["split"] == FUSION_VAL_SPLIT).sum()),
        "test_patients": int((split_table["split"] == FUSION_TEST_SPLIT).sum()),
    }
    return split_table, eligible_df, stats


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
    stats: dict[str, int] | None = None,
) -> None:
    split_metadata_path.parent.mkdir(parents=True, exist_ok=True)
    split_table.to_csv(split_metadata_path, index=False)

    agent_eval = split_table[split_table["split"] == AGENT_EVAL_SPLIT].copy()
    agent_eval = agent_eval.sort_values("deid_patient_id").reset_index(drop=True)
    agent_eval["selection_seed"] = str(seed)
    agent_eval["cohort_patient_count"] = str(cohort_patient_count)
    if stats:
        for key, value in stats.items():
            agent_eval[f"cohort_{key}"] = str(value)
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
    *,
    min_agent_eval_patients: int = 1,
    min_agent_eval_cases: int = AGENT_EVAL_MIN_CASES,
    eligible_df: pd.DataFrame | None = None,
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
    if len(agent_eval_patients) < min_agent_eval_patients:
        raise ValueError(
            f"Expected at least {min_agent_eval_patients} agent_eval patients, "
            f"found {len(agent_eval_patients)}"
        )

    fusion_patients = split_table[split_table["split"] != AGENT_EVAL_SPLIT]["deid_patient_id"]
    overlap = agent_eval_patients & set(fusion_patients.astype(str))
    if overlap:
        raise ValueError(
            f"agent_eval patients overlap fusion splits: {sorted(overlap)[:5]} ..."
        )

    if eligible_df is not None and min_agent_eval_cases > 0:
        agent_eval_cases = eligible_df[
            eligible_df["deid_patient_id"].isin(agent_eval_patients)
        ]
        if len(agent_eval_cases) < min_agent_eval_cases:
            raise ValueError(
                f"agent_eval holdout has {len(agent_eval_cases)} eligible cases; "
                f"need at least {min_agent_eval_cases}"
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
