"""Deterministic patient-level selection for a label-enriched cohort."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import pandas as pd

from medagentx.data.balanced_constants import (
    BALANCED_COHORT_POLICY_VERSION,
    BALANCED_EVAL_MODE,
    NEGATIVE_TO_POSITIVE_RATIO,
    PRE_QUALITY_POSITIVE_TARGETS,
    SOFT_PATIENT_CAP,
)
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import label_column_names
from medagentx.splits.build import build_patient_split_table
from medagentx.splits.constants import (
    ALL_SPLITS,
    SPLIT_SEED,
    TEST_RATIO,
    TRAIN_RATIO,
    VAL_RATIO,
)

_IDENTITY_COLUMNS = ("study_key", "deid_patient_id")


@dataclass(frozen=True)
class EnrichedCohortSelection:
    """All auditable outputs from one enriched-cohort selection."""

    eligible_rows: pd.DataFrame
    patient_selection: pd.DataFrame
    reserve_patients: pd.DataFrame
    patient_splits: pd.DataFrame
    label_audit: pd.DataFrame


def _require_columns(
    frame: pd.DataFrame,
    columns: Sequence[str],
    name: str,
) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(
            f"{name} missing required columns {missing}. "
            f"Available: {list(frame.columns)}"
        )


def _feature_column(label: str, outcome: str) -> str:
    slug = label_column_names(label)["training_target"].removeprefix(
        "training_target_"
    )
    return f"{outcome}_studies_{slug}"


def _validate_targets(targets: Mapping[str, int]) -> dict[str, int]:
    unexpected = sorted(set(targets) - set(ALL_SPLITS))
    missing = sorted(set(ALL_SPLITS) - set(targets))
    if unexpected or missing:
        raise ValueError(
            "positive_targets must contain exactly train/val/test; "
            f"missing={missing}, unexpected={unexpected}"
        )
    normalized = {split: int(targets[split]) for split in ALL_SPLITS}
    if any(value <= 0 for value in normalized.values()):
        raise ValueError("positive_targets values must all be > 0")
    return normalized


def _validate_study_alignment(
    eligible_rows: pd.DataFrame,
    study_labels: pd.DataFrame,
) -> None:
    eligible_identity = eligible_rows[
        ["study_key", "deid_patient_id"]
    ].astype(str)
    if (
        eligible_identity.groupby("study_key")["deid_patient_id"].nunique()
        > 1
    ).any():
        raise ValueError("eligible_rows maps a study_key to multiple patients")
    eligible_identity = eligible_identity.drop_duplicates("study_key")

    label_identity = study_labels[
        ["study_key", "deid_patient_id"]
    ].astype(str)
    if label_identity["study_key"].duplicated().any():
        raise ValueError("study_labels must contain one row per study_key")
    aligned = eligible_identity.merge(
        label_identity,
        on="study_key",
        how="outer",
        suffixes=("_eligible", "_labels"),
        indicator=True,
        validate="one_to_one",
    )
    if not (aligned["_merge"] == "both").all():
        raise ValueError(
            "eligible_rows and study_labels must contain the same study_keys"
        )
    mismatched = (
        aligned["deid_patient_id_eligible"]
        != aligned["deid_patient_id_labels"]
    )
    if mismatched.any():
        raise ValueError(
            "eligible_rows and study_labels disagree on deid_patient_id"
        )


def build_patient_label_features(
    study_labels: pd.DataFrame,
    patient_splits: pd.DataFrame,
) -> pd.DataFrame:
    """Count supervised positive/negative studies for each patient and label."""
    _require_columns(study_labels, _IDENTITY_COLUMNS, "study_labels")
    _require_columns(
        patient_splits,
        ("deid_patient_id", "split"),
        "patient_splits",
    )
    if study_labels.empty:
        raise ValueError("study_labels must be non-empty")
    if study_labels["study_key"].astype(str).duplicated().any():
        raise ValueError("study_labels must contain one row per study_key")

    labels = study_labels.copy()
    labels["study_key"] = labels["study_key"].astype(str).str.strip()
    labels["deid_patient_id"] = (
        labels["deid_patient_id"].astype(str).str.strip()
    )

    lookup = patient_splits[["deid_patient_id", "split"]].copy()
    lookup["deid_patient_id"] = (
        lookup["deid_patient_id"].astype(str).str.strip()
    )
    lookup = lookup.drop_duplicates("deid_patient_id", keep="first")
    labels = labels.merge(
        lookup,
        on="deid_patient_id",
        how="left",
        validate="many_to_one",
    )
    if labels["split"].isna().any():
        missing = labels.loc[
            labels["split"].isna(), "deid_patient_id"
        ].unique()
        raise ValueError(f"Missing patient splits for: {missing[:10].tolist()}")

    feature_columns: list[str] = []
    for label in DISEASE_LABELS:
        columns = label_column_names(label)
        target_column = columns["training_target"]
        mask_column = columns["training_mask"]
        _require_columns(labels, (target_column, mask_column), "study_labels")

        masks = pd.to_numeric(labels[mask_column], errors="raise")
        targets = pd.to_numeric(labels[target_column], errors="coerce")
        if not masks.isin((0, 1)).all():
            raise ValueError(f"{mask_column} must contain only 0 or 1")
        supervised_targets = targets[masks == 1]
        if supervised_targets.isna().any() or not supervised_targets.isin(
            (0.0, 1.0)
        ).all():
            raise ValueError(
                f"{target_column} must be binary whenever {mask_column}=1"
            )

        positive_column = _feature_column(label, "positive")
        negative_column = _feature_column(label, "negative")
        labels[positive_column] = (
            (masks == 1) & (targets == 1.0)
        ).astype(int)
        labels[negative_column] = (
            (masks == 1) & (targets == 0.0)
        ).astype(int)
        feature_columns.extend((positive_column, negative_column))

    features = (
        labels.groupby(["deid_patient_id", "split"], as_index=False)[
            feature_columns
        ]
        .sum()
        .sort_values(["split", "deid_patient_id"], kind="stable")
        .reset_index(drop=True)
    )
    return features


def _split_patient_caps(patient_cap: int) -> dict[str, int]:
    train_cap = int(patient_cap * TRAIN_RATIO)
    val_cap = int(patient_cap * VAL_RATIO)
    return {
        "train": train_cap,
        "val": val_cap,
        "test": patient_cap - train_cap - val_cap,
    }


def _positive_sort_key(
    row: pd.Series,
    *,
    availability: Mapping[str, int],
    target: int,
) -> tuple[float, int, int, str]:
    weighted_score = 0.0
    covered_labels = 0
    positive_studies = 0
    for label in DISEASE_LABELS:
        count = int(row[_feature_column(label, "positive")])
        if count <= 0:
            continue
        covered_labels += 1
        positive_studies += count
        weighted_score += min(count, target) * target / max(
            int(availability[label]),
            1,
        )
    return (
        -weighted_score,
        -covered_labels,
        -positive_studies,
        str(row["deid_patient_id"]),
    )


def _select_positive_patients(
    split_features: pd.DataFrame,
    *,
    target: int,
    patient_cap: int,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    availability = {
        label: int(
            split_features[_feature_column(label, "positive")].sum()
        )
        for label in DISEASE_LABELS
    }
    deficits = {label: target for label in DISEASE_LABELS}
    records = split_features.to_dict(orient="records")
    records.sort(
        key=lambda row: _positive_sort_key(
            pd.Series(row),
            availability=availability,
            target=target,
        )
    )

    selected: list[dict[str, object]] = []
    for row in records:
        if len(selected) >= patient_cap or not any(deficits.values()):
            break
        contributed = [
            label
            for label in DISEASE_LABELS
            if deficits[label] > 0
            and int(row[_feature_column(label, "positive")]) > 0
        ]
        if not contributed:
            continue
        selected.append(row)
        for label in DISEASE_LABELS:
            count = int(row[_feature_column(label, "positive")])
            deficits[label] = max(0, deficits[label] - count)

    return selected, deficits


def _select_background_patients(
    split_features: pd.DataFrame,
    *,
    selected: list[dict[str, object]],
    patient_cap: int,
    negative_ratio: int,
) -> list[dict[str, object]]:
    selected_ids = {
        str(row["deid_patient_id"])
        for row in selected
    }
    positive_totals = {
        label: sum(
            int(row[_feature_column(label, "positive")])
            for row in selected
        )
        for label in DISEASE_LABELS
    }
    negative_totals = {
        label: sum(
            int(row[_feature_column(label, "negative")])
            for row in selected
        )
        for label in DISEASE_LABELS
    }
    deficits = {
        label: max(
            0,
            negative_ratio * positive_totals[label] - negative_totals[label],
        )
        for label in DISEASE_LABELS
    }
    if not any(deficits.values()) or len(selected) >= patient_cap:
        return []

    candidates: list[dict[str, object]] = []
    for row in split_features.to_dict(orient="records"):
        patient_id = str(row["deid_patient_id"])
        if patient_id in selected_ids:
            continue
        total_positives = sum(
            int(row[_feature_column(label, "positive")])
            for label in DISEASE_LABELS
        )
        if total_positives == 0:
            candidates.append(row)

    def background_key(row: dict[str, object]) -> tuple[int, int, str]:
        useful_labels = sum(
            int(deficits[label] > 0)
            for label in DISEASE_LABELS
            if int(row[_feature_column(label, "negative")]) > 0
        )
        useful_negatives = sum(
            min(
                deficits[label],
                int(row[_feature_column(label, "negative")]),
            )
            for label in DISEASE_LABELS
        )
        return (
            -useful_labels,
            -useful_negatives,
            str(row["deid_patient_id"]),
        )

    candidates.sort(key=background_key)
    background: list[dict[str, object]] = []
    for row in candidates:
        if not any(deficits.values()):
            break
        useful = any(
            deficits[label] > 0
            and int(row[_feature_column(label, "negative")]) > 0
            for label in DISEASE_LABELS
        )
        if not useful:
            continue
        if len(selected) + len(background) >= patient_cap:
            break
        background.append(row)
        for label in DISEASE_LABELS:
            count = int(row[_feature_column(label, "negative")])
            deficits[label] = max(0, deficits[label] - count)

    return background


def build_label_count_audit(
    patient_features: pd.DataFrame,
    *,
    positive_targets: Mapping[str, int],
    negative_ratio: int = NEGATIVE_TO_POSITIVE_RATIO,
    stage: str,
    available_patient_features: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Summarize available/selected label counts and explicit shortages."""
    targets = _validate_targets(positive_targets)
    if negative_ratio < 0:
        raise ValueError("negative_ratio must be >= 0")
    rows: list[dict[str, object]] = []
    available = (
        available_patient_features
        if available_patient_features is not None
        else patient_features
    )
    for split in ALL_SPLITS:
        split_features = patient_features[
            patient_features["split"].astype(str) == split
        ]
        split_available = available[
            available["split"].astype(str) == split
        ]
        for label in DISEASE_LABELS:
            positives = int(
                split_features[_feature_column(label, "positive")].sum()
            )
            negatives = int(
                split_features[_feature_column(label, "negative")].sum()
            )
            positive_target = targets[split]
            negative_target = negative_ratio * positives
            positive_shortage = max(0, positive_target - positives)
            negative_shortage = max(0, negative_target - negatives)
            available_positives = int(
                split_available[
                    _feature_column(label, "positive")
                ].sum()
            )
            available_negatives = int(
                split_available[
                    _feature_column(label, "negative")
                ].sum()
            )
            if positive_shortage == 0:
                positive_shortage_reason = ""
            elif available_positives < positive_target:
                positive_shortage_reason = "insufficient_available_positives"
            else:
                positive_shortage_reason = "patient_cap_or_constraints"
            if negative_shortage == 0:
                negative_shortage_reason = ""
            elif available_negatives < negative_target:
                negative_shortage_reason = "insufficient_available_negatives"
            else:
                negative_shortage_reason = "patient_cap_or_constraints"
            rows.append(
                {
                    "stage": stage,
                    "split": split,
                    "label": label,
                    "positive_target": positive_target,
                    "positive_studies": positives,
                    "positive_shortage": positive_shortage,
                    "positive_shortage_reason": positive_shortage_reason,
                    "available_positive_studies": available_positives,
                    "negative_target": negative_target,
                    "negative_studies": negatives,
                    "negative_shortage": negative_shortage,
                    "negative_shortage_reason": negative_shortage_reason,
                    "available_negative_studies": available_negatives,
                    "target_met": (
                        positive_shortage == 0 and negative_shortage == 0
                    ),
                    "policy_version": BALANCED_COHORT_POLICY_VERSION,
                    "eval_mode": BALANCED_EVAL_MODE,
                }
            )
    return pd.DataFrame(rows)


def select_enriched_cohort(
    eligible_rows: pd.DataFrame,
    study_labels: pd.DataFrame,
    *,
    positive_targets: Mapping[str, int] = PRE_QUALITY_POSITIVE_TARGETS,
    negative_ratio: int = NEGATIVE_TO_POSITIVE_RATIO,
    patient_cap: int = SOFT_PATIENT_CAP,
    seed: int = SPLIT_SEED,
) -> EnrichedCohortSelection:
    """Select whole patients inside fixed split buckets without crashing on shortages."""
    _require_columns(eligible_rows, _IDENTITY_COLUMNS, "eligible_rows")
    if eligible_rows.empty:
        raise ValueError("eligible_rows must be non-empty")
    targets = _validate_targets(positive_targets)
    if negative_ratio < 0:
        raise ValueError("negative_ratio must be >= 0")
    if patient_cap <= 0:
        raise ValueError("patient_cap must be > 0")

    _validate_study_alignment(eligible_rows, study_labels)
    patient_splits = build_patient_split_table(eligible_rows, seed=seed)
    features = build_patient_label_features(study_labels, patient_splits)
    split_caps = _split_patient_caps(patient_cap)

    selection_rows: list[dict[str, object]] = []
    selected_feature_rows: list[dict[str, object]] = []
    selection_order = 0
    for split in ALL_SPLITS:
        split_features = features[
            features["split"].astype(str) == split
        ].copy()
        positives, _ = _select_positive_patients(
            split_features,
            target=targets[split],
            patient_cap=split_caps[split],
        )
        background = _select_background_patients(
            split_features,
            selected=positives,
            patient_cap=split_caps[split],
            negative_ratio=negative_ratio,
        )

        for reason, records in (
            ("positive_enrichment", positives),
            ("background", background),
        ):
            for row in records:
                selection_order += 1
                positive_labels = [
                    label
                    for label in DISEASE_LABELS
                    if int(row[_feature_column(label, "positive")]) > 0
                ]
                selection_rows.append(
                    {
                        "deid_patient_id": str(row["deid_patient_id"]),
                        "split": split,
                        "selection_reason": reason,
                        "selection_order": selection_order,
                        "positive_labels": "|".join(positive_labels),
                        "positive_study_count": sum(
                            int(row[_feature_column(label, "positive")])
                            for label in DISEASE_LABELS
                        ),
                        "negative_study_count": sum(
                            int(row[_feature_column(label, "negative")])
                            for label in DISEASE_LABELS
                        ),
                        "split_seed": seed,
                        "policy_version": BALANCED_COHORT_POLICY_VERSION,
                        "eval_mode": BALANCED_EVAL_MODE,
                    }
                )
                selected_feature_rows.append(row)

    patient_selection = pd.DataFrame(selection_rows)
    if patient_selection.empty:
        raise ValueError("Enriched cohort selection produced no patients")
    if len(patient_selection) > patient_cap:
        raise AssertionError("patient selection exceeded the soft patient cap")

    selected_ids = set(
        patient_selection["deid_patient_id"].astype(str).tolist()
    )
    reserve_rows: list[dict[str, object]] = []
    for row in features.to_dict(orient="records"):
        patient_id = str(row["deid_patient_id"])
        if patient_id in selected_ids:
            continue
        positive_labels = [
            label
            for label in DISEASE_LABELS
            if int(row[_feature_column(label, "positive")]) > 0
        ]
        reserve_record: dict[str, object] = {
            "deid_patient_id": patient_id,
            "split": str(row["split"]),
            "positive_labels": "|".join(positive_labels),
            "positive_study_count": sum(
                int(row[_feature_column(label, "positive")])
                for label in DISEASE_LABELS
            ),
            "negative_study_count": sum(
                int(row[_feature_column(label, "negative")])
                for label in DISEASE_LABELS
            ),
            "policy_version": BALANCED_COHORT_POLICY_VERSION,
        }
        for label in DISEASE_LABELS:
            positive_column = _feature_column(label, "positive")
            negative_column = _feature_column(label, "negative")
            reserve_record[positive_column] = int(row[positive_column])
            reserve_record[negative_column] = int(row[negative_column])
        reserve_rows.append(reserve_record)
    reserve_patients = pd.DataFrame(reserve_rows)
    if not reserve_patients.empty:
        reserve_patients = reserve_patients.sort_values(
            ["split", "positive_study_count", "deid_patient_id"],
            ascending=[True, False, True],
            kind="stable",
        ).reset_index(drop=True)

    selected_rows = eligible_rows[
        eligible_rows["deid_patient_id"].astype(str).isin(selected_ids)
    ].copy()
    selected_features = pd.DataFrame(
        selected_feature_rows,
        columns=features.columns,
    )
    audit = build_label_count_audit(
        selected_features,
        positive_targets=targets,
        negative_ratio=negative_ratio,
        stage="pre_quality_selection",
        available_patient_features=features,
    )

    return EnrichedCohortSelection(
        eligible_rows=selected_rows.reset_index(drop=True),
        patient_selection=patient_selection.reset_index(drop=True),
        reserve_patients=reserve_patients,
        patient_splits=patient_splits[
            patient_splits["deid_patient_id"].astype(str).isin(selected_ids)
        ].reset_index(drop=True),
        label_audit=audit,
    )
