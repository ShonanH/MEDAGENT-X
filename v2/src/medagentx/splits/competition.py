"""Build an immutable patient-level development split for CheXpert competition data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from medagentx.evaluation.chexpert_competition import competition_study_key
from medagentx.labels.constants import CHEXPERT_COMPETITION_LABELS


COMPETITION_SPLIT_POLICY_VERSION = "chexpert_competition_patient_dev_v1"
DEFAULT_COMPETITION_SPLIT_SEED = 42
DEFAULT_DEV_FRACTION = 0.05
EXPECTED_VALIDATION_PATIENTS = 200
EXPECTED_TEST_PATIENTS = 500


class CompetitionSplitError(ValueError):
    """Raised when competition split inputs or invariants are invalid."""


def _require_columns(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    frame_name: str,
) -> None:
    missing = [column for column in columns if column not in frame]
    if missing:
        raise CompetitionSplitError(
            f"{frame_name} missing required columns {missing}; "
            f"available={list(frame.columns)}"
        )


def _slug(label: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in label).strip("_")


def _stable_rank(patient_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{patient_id}".encode("utf-8")).hexdigest()


def _positive_patient_strata(
    train_views: pd.DataFrame,
    study_labels: pd.DataFrame,
) -> pd.DataFrame:
    """Return one row per patient with a five-label positive bitmask."""
    _require_columns(train_views, ("patient_id", "study_key"), "train_views")
    _require_columns(study_labels, ("patient_id", "study_key"), "study_labels")
    if train_views.empty or study_labels.empty:
        raise CompetitionSplitError("train_views and study_labels must be non-empty")

    views = train_views[["patient_id", "study_key"]].copy()
    views["patient_id"] = views["patient_id"].astype(str).str.strip()
    views["study_key"] = views["study_key"].astype(str).str.strip()
    if views["patient_id"].isin({"", "nan"}).any():
        raise CompetitionSplitError("train_views contains blank patient_id values")

    labels = study_labels[["patient_id", "study_key"]].copy()
    labels["patient_id"] = labels["patient_id"].astype(str).str.strip()
    labels["study_key"] = labels["study_key"].astype(str).str.strip()
    if labels["study_key"].duplicated().any():
        raise CompetitionSplitError("study_labels contains duplicate study_key values")

    view_studies = set(views["study_key"])
    label_studies = set(labels["study_key"])
    if view_studies != label_studies:
        raise CompetitionSplitError(
            "train_views/study_labels study sets differ: "
            f"views_missing={len(view_studies - label_studies)}, "
            f"labels_missing={len(label_studies - view_studies)}"
        )

    for label in CHEXPERT_COMPETITION_LABELS:
        slug = _slug(label)
        for prefix in ("target", "mask"):
            column = f"{prefix}_{slug}"
            if column not in study_labels:
                raise CompetitionSplitError(
                    f"study_labels missing required competition column {column!r}"
                )

    study_patient = labels.set_index("study_key")["patient_id"].to_dict()
    view_patient = views.set_index("study_key")["patient_id"].to_dict()
    if any(study_patient[key] != view_patient[key] for key in view_studies):
        raise CompetitionSplitError(
            "train_views and study_labels disagree on study patient ownership"
        )

    patient_summary = (
        views.groupby("patient_id", sort=True)
        .agg(study_count=("study_key", "nunique"), view_count=("study_key", "size"))
        .reset_index()
    )
    label_patient_sets: dict[str, set[str]] = {}
    for label in CHEXPERT_COMPETITION_LABELS:
        slug = _slug(label)
        mask = pd.to_numeric(study_labels[f"mask_{slug}"], errors="coerce")
        target = pd.to_numeric(study_labels[f"target_{slug}"], errors="coerce")
        positive_studies = set(
            study_labels.loc[(mask == 1) & (target == 1), "study_key"].astype(str)
        )
        label_patient_sets[slug] = {
            study_patient[study_key] for study_key in positive_studies
        }

    patient_summary["stratum"] = 0
    for bit, label in enumerate(CHEXPERT_COMPETITION_LABELS):
        slug = _slug(label)
        patient_summary["stratum"] += patient_summary["patient_id"].isin(
            label_patient_sets[slug]
        ).astype(int) * (1 << bit)
    return patient_summary


def _allocate_stratum_counts(
    strata: pd.Series,
    desired_count: int,
) -> dict[int, int]:
    counts = strata.value_counts().sort_index().to_dict()
    total = int(sum(counts.values()))
    if total == 0:
        raise CompetitionSplitError("No patients available for split assignment")

    raw = {int(key): value * desired_count / total for key, value in counts.items()}
    allocation = {key: int(value) for key, value in raw.items()}
    remainder = desired_count - sum(allocation.values())
    order = sorted(
        raw,
        key=lambda key: (raw[key] - allocation[key], -key),
        reverse=True,
    )
    for key in order[:remainder]:
        allocation[key] += 1
    return allocation


def build_competition_patient_split(
    train_views: pd.DataFrame,
    study_labels: pd.DataFrame,
    *,
    seed: int = DEFAULT_COMPETITION_SPLIT_SEED,
    dev_fraction: float = DEFAULT_DEV_FRACTION,
) -> pd.DataFrame:
    """Assign every training patient deterministically to train or dev."""
    if seed < 0:
        raise CompetitionSplitError("seed must be >= 0")
    if not 0 < dev_fraction < 1:
        raise CompetitionSplitError("dev_fraction must be between 0 and 1")

    patients = _positive_patient_strata(train_views, study_labels)
    desired_dev = max(1, round(len(patients) * dev_fraction))
    if desired_dev >= len(patients):
        raise CompetitionSplitError("dev_fraction leaves no training patients")
    allocations = _allocate_stratum_counts(patients["stratum"], desired_dev)

    patients["stable_rank"] = patients["patient_id"].map(
        lambda patient_id: _stable_rank(patient_id, seed)
    )
    patients["split"] = "train"
    for stratum, count in allocations.items():
        selected = (
            patients[patients["stratum"] == stratum]
            .sort_values(["stable_rank", "patient_id"], kind="stable")
            .head(count)
            .index
        )
        patients.loc[selected, "split"] = "dev"

    patients["split_seed"] = seed
    patients["dev_fraction"] = dev_fraction
    patients["split_policy_version"] = COMPETITION_SPLIT_POLICY_VERSION
    return patients[
        [
            "patient_id",
            "split",
            "study_count",
            "view_count",
            "stratum",
            "split_seed",
            "dev_fraction",
            "split_policy_version",
        ]
    ].sort_values(["split", "patient_id"], kind="stable").reset_index(drop=True)


def _load_external_patients(
    excluded_rows_path: str | Path,
    expert_test_groundtruth: str | Path,
) -> tuple[set[str], set[str]]:
    excluded = pd.read_csv(excluded_rows_path, dtype=str)
    _require_columns(excluded, ("split", "patient_id"), "excluded_rows")
    valid_patients = set(
        excluded.loc[excluded["split"].astype(str).str.lower() == "valid", "patient_id"]
        .astype(str)
        .str.strip()
    )
    if len(valid_patients) != EXPECTED_VALIDATION_PATIENTS:
        raise CompetitionSplitError(
            "Released validation patient count mismatch: "
            f"expected={EXPECTED_VALIDATION_PATIENTS}, observed={len(valid_patients)}"
        )

    groundtruth = pd.read_csv(expert_test_groundtruth, dtype=str)
    _require_columns(groundtruth, ("Study",), "expert_test_groundtruth")
    test_studies = {
        competition_study_key(value, field_name="Study")
        for value in groundtruth["Study"]
    }
    test_patients = {study_key.split("/", maxsplit=1)[0] for study_key in test_studies}
    if len(test_studies) != 500 or len(test_patients) != EXPECTED_TEST_PATIENTS:
        raise CompetitionSplitError(
            "Expert test patient/study count mismatch: "
            f"studies={len(test_studies)}, patients={len(test_patients)}"
        )
    return valid_patients, test_patients


def build_competition_split_artifacts(
    *,
    train_views_path: str | Path,
    study_labels_path: str | Path,
    excluded_rows_path: str | Path,
    expert_test_groundtruth: str | Path,
    output_root: str | Path,
    seed: int = DEFAULT_COMPETITION_SPLIT_SEED,
    dev_fraction: float = DEFAULT_DEV_FRACTION,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Build and persist immutable competition split tables and audit."""
    train_views = pd.read_csv(train_views_path, dtype=str)
    study_labels = pd.read_csv(study_labels_path, dtype=str)
    patients = build_competition_patient_split(
        train_views,
        study_labels,
        seed=seed,
        dev_fraction=dev_fraction,
    )
    valid_patients, test_patients = _load_external_patients(
        excluded_rows_path,
        expert_test_groundtruth,
    )

    train_patients = set(patients.loc[patients["split"] == "train", "patient_id"])
    dev_patients = set(patients.loc[patients["split"] == "dev", "patient_id"])
    if train_patients & dev_patients:
        raise CompetitionSplitError("Internal train/dev patient overlap detected")
    if (train_patients | dev_patients) & (valid_patients | test_patients):
        raise CompetitionSplitError("Internal split overlaps released patients")

    patient_lookup = patients[["patient_id", "split"]]
    studies = study_labels[["study_key", "patient_id"]].drop_duplicates("study_key")
    study_splits = studies.merge(
        patient_lookup,
        on="patient_id",
        how="left",
        validate="many_to_one",
    )
    views = train_views.merge(
        patient_lookup,
        on="patient_id",
        how="left",
        validate="many_to_one",
        suffixes=("", "_assignment"),
    )
    if "split_assignment" in views.columns:
        views["split"] = views.pop("split_assignment")
    if study_splits["split"].isna().any() or views["split"].isna().any():
        raise CompetitionSplitError("Split assignment missing for study or view rows")

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "patient_splits": root / "patient_splits.csv",
        "study_splits": root / "study_splits.csv",
        "view_splits": root / "view_splits.csv",
        "split_summary": root / "split_summary.csv",
        "split_audit": root / "split_audit.json",
    }
    if not overwrite:
        existing = [path for path in paths.values() if path.exists()]
        if existing:
            raise FileExistsError(
                "Competition split artifacts already exist; refusing to overwrite: "
                f"{[str(path) for path in existing]}"
            )

    summary: dict[str, Any] = {
        "patients": int(len(patients)),
        "studies": int(len(study_splits)),
        "views": int(len(views)),
        "patients_train": int((patients["split"] == "train").sum()),
        "patients_dev": int((patients["split"] == "dev").sum()),
        "studies_train": int((study_splits["split"] == "train").sum()),
        "studies_dev": int((study_splits["split"] == "dev").sum()),
        "views_train": int((views["split"] == "train").sum()),
        "views_dev": int((views["split"] == "dev").sum()),
        "seed": seed,
        "dev_fraction": dev_fraction,
        "split_policy_version": COMPETITION_SPLIT_POLICY_VERSION,
    }
    audit = {
        "schema_version": "chexpert_competition_split_audit_v1",
        "split_policy_version": COMPETITION_SPLIT_POLICY_VERSION,
        "seed": seed,
        "dev_fraction": dev_fraction,
        "inputs": {
            "train_views": str(train_views_path),
            "study_labels": str(study_labels_path),
            "excluded_rows": str(excluded_rows_path),
            "expert_test_groundtruth": str(expert_test_groundtruth),
        },
        "counts": summary,
        "leakage_checks": {
            "train_dev_patient_overlap": len(train_patients & dev_patients),
            "internal_released_validation_overlap": len(
                (train_patients | dev_patients) & valid_patients
            ),
            "internal_released_test_overlap": len(
                (train_patients | dev_patients) & test_patients
            ),
        },
        "positive_patient_counts": {},
    }
    for label in CHEXPERT_COMPETITION_LABELS:
        slug = _slug(label)
        mask = pd.to_numeric(study_labels[f"mask_{slug}"], errors="coerce")
        target = pd.to_numeric(study_labels[f"target_{slug}"], errors="coerce")
        positive_patients = set(
            study_labels.loc[
                (mask == 1) & (target == 1), "patient_id"
            ].astype(str)
        )
        audit["positive_patient_counts"][slug] = {
            split: int(
                patients.loc[
                    (patients["split"] == split)
                    & patients["patient_id"].isin(positive_patients),
                    "patient_id",
                ].nunique()
            )
            for split in ("train", "dev")
        }

    patients.to_csv(paths["patient_splits"], index=False)
    study_splits.to_csv(paths["study_splits"], index=False)
    views.to_csv(paths["view_splits"], index=False)
    pd.DataFrame([summary]).to_csv(paths["split_summary"], index=False)
    paths["split_audit"].write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    return paths
