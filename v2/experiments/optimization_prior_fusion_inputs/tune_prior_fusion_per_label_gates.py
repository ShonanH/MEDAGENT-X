"""Tune conservative per-label retrieval-prior fusion gates on validation data.

The tuner consumes saved validation features; it never reruns vision or
retrieval. Promotion and demotion are selected independently for each label.
Candidates must improve over vision-only while satisfying intervention-risk,
support, and patient-bootstrap stability constraints. If no candidate is
defensible, that label/action is explicitly disabled.
"""

# ruff: noqa: E402 -- local experiment imports require the v2/src path bootstrap.

from __future__ import annotations

import argparse
import json
import sys
import time
import zlib
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd


EXPERIMENT_DIR = Path(__file__).resolve().parent
V2_ROOT = Path(__file__).resolve().parents[2]
V2_SRC = V2_ROOT / "src"
if str(V2_SRC) not in sys.path:
    sys.path.insert(0, str(V2_SRC))
if str(EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_DIR))

from medagentx.data.balanced_constants import DEFAULT_BALANCED_COHORT_ROOT
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.statuses import LabelStatus
from prior_fusion import PRIOR_FUSION_POLICY_VERSION
from retrieval_prior import snake_label


PRESENT = LabelStatus.PRESENT.value
ABSENT = LabelStatus.ABSENT.value
UNCERTAIN = LabelStatus.UNCERTAIN.value
UNMENTIONED = LabelStatus.UNMENTIONED.value
PROMOTION = "promotion"
DEMOTION = "demotion"
TUNING_POLICY_VERSION = "retrieval_prior_per_label_gate_tuning_v1"

DEFAULT_FEATURES_CSV = (
    V2_ROOT
    / "experiments"
    / "exp10_prior_fusion_val_features"
    / "prior_fusion_label_predictions.csv"
)
DEFAULT_SOURCE_RUN_CONFIG = DEFAULT_FEATURES_CSV.parent / "run_config.json"
DEFAULT_STUDY_LABELS_CSV = EXPERIMENT_DIR / "splits" / "study_label_table.csv"
DEFAULT_OUTPUT_DIR = V2_ROOT / "experiments" / "exp11_prior_fusion_per_label_tuning"

OUTPUT_FILENAMES = (
    "run_config.json",
    "per_label_gate_grid_results.csv",
    "per_label_gate_selection.csv",
    "best_prior_fusion_policy.json",
    "best_changed_cells.csv",
)


@dataclass(frozen=True)
class DirectionalGateCandidate:
    """One label/action-specific retrieval gate."""

    direction: str
    prior_threshold: float
    min_retrieval_confidence: float


@dataclass(frozen=True)
class TuningConstraints:
    """Guardrails for selecting one directional gate."""

    gray_zone_margin: float = 0.15
    max_opposing_prior: float = 0.20
    absent_demotion_prior_threshold: float = 0.90
    min_opportunities_per_outcome: int = 10
    min_scoreable_changes: int = 5
    min_intervention_precision: float = 0.70
    min_label_f1_gain: float = 0.001
    max_label_precision_drop: float = 0.02
    bootstrap_iterations: int = 500
    min_bootstrap_improvement_rate: float = 0.80
    random_seed: int = 17


@dataclass(frozen=True)
class DirectionSelection:
    """Selected gate, or an explicit disabled result, for one label/action."""

    label: str
    direction: str
    enabled: bool
    reason: str
    prior_threshold: float | None
    min_retrieval_confidence: float | None
    eligible_benefit_opportunities: int
    eligible_harm_opportunities: int
    scoreable_changes: int
    beneficial_changes: int
    harmful_changes: int
    unscored_changes: int
    intervention_precision: float | None
    intervention_coverage: float
    baseline_f1: float
    selected_f1: float
    f1_gain: float
    baseline_precision: float | None
    selected_precision: float | None
    bootstrap_improvement_rate: float | None


def build_parser() -> argparse.ArgumentParser:
    """Build the validation-only per-label gate tuning CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Tune promotion and demotion gates independently for each label "
            "using saved validation features."
        )
    )
    parser.add_argument("--features-csv", type=Path, default=DEFAULT_FEATURES_CSV)
    parser.add_argument(
        "--source-run-config",
        type=Path,
        default=DEFAULT_SOURCE_RUN_CONFIG,
        help="Source feature-run config; must explicitly identify the validation split.",
    )
    parser.add_argument(
        "--study-labels-csv",
        type=Path,
        default=DEFAULT_STUDY_LABELS_CSV,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--promotion-prior-thresholds",
        default="0.60,0.70,0.80,0.90",
    )
    parser.add_argument(
        "--demotion-prior-thresholds",
        default="0.70,0.80,0.90",
    )
    parser.add_argument(
        "--min-retrieval-confidences",
        default="0.10,0.20,0.30,0.40,0.50,0.60",
    )
    parser.add_argument("--gray-zone-margin", type=float, default=0.15)
    parser.add_argument("--max-opposing-prior", type=float, default=0.20)
    parser.add_argument(
        "--absent-demotion-prior-threshold",
        type=float,
        default=0.90,
    )
    parser.add_argument("--min-opportunities-per-outcome", type=int, default=10)
    parser.add_argument("--min-scoreable-changes", type=int, default=5)
    parser.add_argument("--min-intervention-precision", type=float, default=0.70)
    parser.add_argument("--min-label-f1-gain", type=float, default=0.001)
    parser.add_argument("--max-label-precision-drop", type=float, default=0.02)
    parser.add_argument("--bootstrap-iterations", type=int, default=500)
    parser.add_argument(
        "--min-bootstrap-improvement-rate",
        type=float,
        default=0.80,
    )
    parser.add_argument("--random-seed", type=int, default=17)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing per-label tuning outputs.",
    )
    return parser


def _parse_float_list(raw: str) -> tuple[float, ...]:
    values = tuple(float(item.strip()) for item in raw.split(",") if item.strip())
    if not values:
        raise ValueError("Grid lists must contain at least one number")
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError("Grid values must be in [0, 1]")
    return tuple(sorted(set(values)))


def _validate_constraints(constraints: TuningConstraints) -> None:
    unit_interval_fields = (
        "gray_zone_margin",
        "max_opposing_prior",
        "absent_demotion_prior_threshold",
        "min_intervention_precision",
        "max_label_precision_drop",
        "min_bootstrap_improvement_rate",
    )
    for field in unit_interval_fields:
        value = float(getattr(constraints, field))
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{field} must be in [0, 1]")
    if constraints.min_label_f1_gain < 0.0:
        raise ValueError("min_label_f1_gain must be >= 0")
    if constraints.min_opportunities_per_outcome < 1:
        raise ValueError("min_opportunities_per_outcome must be >= 1")
    if constraints.min_scoreable_changes < 1:
        raise ValueError("min_scoreable_changes must be >= 1")
    if constraints.bootstrap_iterations < 1:
        raise ValueError("bootstrap_iterations must be >= 1")


def _require_existing_paths(paths: dict[str, Path]) -> None:
    missing = [f"{name}: {path}" for name, path in paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Required tuning inputs are missing:\n" + "\n".join(missing)
        )


def _prepare_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [
        output_dir / name for name in OUTPUT_FILENAMES if (output_dir / name).exists()
    ]
    if existing and not overwrite:
        raise FileExistsError(
            "Per-label tuning outputs already exist. Pass --overwrite to replace:\n"
            + "\n".join(str(path) for path in existing)
        )
    if overwrite:
        for path in existing:
            path.unlink()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _load_validation_source_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    split = str(payload.get("split", "")).strip().lower()
    if split not in {"val", "validation"}:
        raise ValueError(
            f"Refusing to tune on source split {split or '<missing>'!r}; "
            f"{path} must declare split='val'"
        )
    return payload


def _load_feature_frame(features_csv: Path) -> pd.DataFrame:
    frame = pd.read_csv(features_csv, dtype={"study_key": str, "label": str})
    required_columns = {
        "study_key",
        "label",
        "probability",
        "threshold",
        "vision_status",
        "retrieval_present_prior",
        "retrieval_absent_prior",
        "retrieval_confidence",
    }
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise ValueError(f"{features_csv} is missing required columns: {missing}")

    frame = frame.copy()
    frame["study_key"] = frame["study_key"].astype(str).str.strip()
    frame["label"] = frame["label"].astype(str).str.strip()
    for column in (
        "probability",
        "threshold",
        "retrieval_present_prior",
        "retrieval_absent_prior",
        "retrieval_confidence",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if not frame[column].between(0.0, 1.0).all():
            raise ValueError(
                f"Feature column {column!r} contains values outside [0, 1]"
            )

    frame["vision_status"] = frame["vision_status"].astype(str).str.strip().str.lower()
    if not frame["vision_status"].isin({PRESENT, ABSENT}).all():
        bad = sorted(
            set(
                frame.loc[
                    ~frame["vision_status"].isin({PRESENT, ABSENT}), "vision_status"
                ]
            )
        )
        raise ValueError(f"Feature table has non-binary vision statuses: {bad}")
    if frame[["study_key", "label"]].duplicated().any():
        raise ValueError("Feature table contains duplicate study_key + label rows")
    unexpected_labels = sorted(set(frame["label"]) - set(DISEASE_LABELS))
    if unexpected_labels:
        raise ValueError(
            f"Feature table contains unsupported labels: {unexpected_labels}"
        )
    missing_labels = sorted(set(DISEASE_LABELS) - set(frame["label"]))
    if missing_labels:
        raise ValueError(f"Feature table is missing expected labels: {missing_labels}")
    expected_rows = frame["study_key"].nunique() * len(DISEASE_LABELS)
    if len(frame) != expected_rows:
        raise ValueError(
            "Feature table must contain exactly one row for every study and label; "
            f"expected {expected_rows}, found {len(frame)}"
        )
    return frame


def _load_ground_truth_long(
    study_labels_csv: Path,
    *,
    study_keys: Iterable[str],
) -> pd.DataFrame:
    study_labels = pd.read_csv(study_labels_csv, dtype=str)
    if "study_key" not in study_labels:
        raise ValueError(f"{study_labels_csv} is missing study_key")
    key_set = {str(key).strip() for key in study_keys}
    study_labels["study_key"] = study_labels["study_key"].astype(str).str.strip()
    study_labels = study_labels[study_labels["study_key"].isin(key_set)]
    if study_labels.empty:
        raise ValueError("No study-label rows matched the feature study keys")
    if study_labels["study_key"].duplicated().any():
        raise ValueError("Study-label table contains duplicate study_key rows")

    required_status_columns = [
        f"status_{snake_label(label)}" for label in DISEASE_LABELS
    ]
    missing = sorted(set(required_status_columns) - set(study_labels.columns))
    if missing:
        raise ValueError(f"{study_labels_csv} is missing status columns: {missing}")

    rows: list[dict[str, str]] = []
    for _, row in study_labels.iterrows():
        for label in DISEASE_LABELS:
            rows.append(
                {
                    "study_key": str(row["study_key"]),
                    "label": label,
                    "gt_status": str(row[f"status_{snake_label(label)}"])
                    .strip()
                    .lower(),
                }
            )
    return pd.DataFrame(rows)


def _attach_ground_truth(
    features: pd.DataFrame, ground_truth: pd.DataFrame
) -> pd.DataFrame:
    merged = features.merge(ground_truth, on=["study_key", "label"], how="left")
    if merged["gt_status"].isna().any():
        count = int(merged["gt_status"].isna().sum())
        raise ValueError(f"Missing ground truth for {count} feature rows")
    known = {PRESENT, ABSENT, UNCERTAIN, UNMENTIONED}
    if not merged["gt_status"].isin(known).all():
        bad = sorted(set(merged.loc[~merged["gt_status"].isin(known), "gt_status"]))
        raise ValueError(f"Ground truth has unknown statuses: {bad}")
    merged["patient_key"] = merged["study_key"].map(_patient_key)
    return merged


def _patient_key(study_key: str) -> str:
    """Derive a stable patient grouping key from a CheXpert study key."""
    normalized = str(study_key).strip().replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    for part in parts:
        if part.lower().startswith("patient"):
            return part.lower()
    if len(parts) >= 2:
        return "/".join(parts[:-1]).lower()
    return normalized.lower()


def _direction_candidates(
    *,
    direction: str,
    prior_thresholds: Sequence[float],
    confidence_thresholds: Sequence[float],
) -> tuple[DirectionalGateCandidate, ...]:
    if direction not in {PROMOTION, DEMOTION}:
        raise ValueError(f"Unsupported direction: {direction!r}")
    return tuple(
        DirectionalGateCandidate(
            direction=direction,
            prior_threshold=prior_threshold,
            min_retrieval_confidence=confidence,
        )
        for prior_threshold, confidence in product(
            prior_thresholds, confidence_thresholds
        )
    )


def _safe_div(numerator: float, denominator: float) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _binary_metrics(
    gt: np.ndarray, predicted: np.ndarray
) -> dict[str, float | int | None]:
    scoreable = np.isin(gt, [PRESENT, ABSENT])
    gt_present = gt == PRESENT
    gt_absent = gt == ABSENT
    pred_present = predicted == PRESENT
    pred_absent = predicted == ABSENT
    pred_uncertain = predicted == UNCERTAIN

    tp = int(np.sum(scoreable & gt_present & pred_present))
    fp = int(np.sum(scoreable & gt_absent & pred_present))
    fn = int(np.sum(scoreable & gt_present & pred_absent))
    tn = int(np.sum(scoreable & gt_absent & pred_absent))
    miss_uncertain = int(np.sum(scoreable & gt_present & pred_uncertain))
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn + miss_uncertain)
    if precision is None or recall is None or precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2.0 * precision * recall / (precision + recall)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "miss_uncertain": miss_uncertain,
        "precision": precision,
        "recall": recall,
        "f1": float(f1),
        "scoreable_cells": int(np.sum(scoreable)),
    }


def _eligible_action_mask(
    label_frame: pd.DataFrame,
    *,
    direction: str,
    constraints: TuningConstraints,
) -> np.ndarray:
    gray = (
        (label_frame["probability"] - label_frame["threshold"]).abs()
        <= constraints.gray_zone_margin
    ).to_numpy()
    vision = label_frame["vision_status"].to_numpy()
    if direction == PROMOTION:
        return gray & (vision == ABSENT)
    if direction == DEMOTION:
        return gray & (vision == PRESENT)
    raise ValueError(f"Unsupported direction: {direction!r}")


def _candidate_change_mask(
    label_frame: pd.DataFrame,
    candidate: DirectionalGateCandidate,
    constraints: TuningConstraints,
) -> np.ndarray:
    eligible = _eligible_action_mask(
        label_frame,
        direction=candidate.direction,
        constraints=constraints,
    )
    confidence = (
        label_frame["retrieval_confidence"].to_numpy()
        >= candidate.min_retrieval_confidence
    )
    if candidate.direction == PROMOTION:
        prior = label_frame["retrieval_present_prior"].to_numpy()
        opposing = label_frame["retrieval_absent_prior"].to_numpy()
    else:
        prior = label_frame["retrieval_absent_prior"].to_numpy()
        opposing = label_frame["retrieval_present_prior"].to_numpy()
    return (
        eligible
        & confidence
        & (prior >= candidate.prior_threshold)
        & (opposing <= constraints.max_opposing_prior)
    )


def _apply_direction(
    label_frame: pd.DataFrame,
    candidate: DirectionalGateCandidate,
    constraints: TuningConstraints,
) -> tuple[np.ndarray, np.ndarray]:
    predicted = label_frame["vision_status"].to_numpy(copy=True)
    changed = _candidate_change_mask(label_frame, candidate, constraints)
    if candidate.direction == PROMOTION:
        predicted[changed] = PRESENT
    else:
        absent_prior = label_frame["retrieval_absent_prior"].to_numpy()
        predicted[changed] = UNCERTAIN
        predicted[
            changed & (absent_prior >= constraints.absent_demotion_prior_threshold)
        ] = ABSENT
    return predicted, changed


def _opportunity_counts(
    label_frame: pd.DataFrame,
    *,
    direction: str,
    constraints: TuningConstraints,
) -> tuple[int, int, int]:
    eligible = _eligible_action_mask(
        label_frame,
        direction=direction,
        constraints=constraints,
    )
    gt = label_frame["gt_status"].to_numpy()
    benefit_status = PRESENT if direction == PROMOTION else ABSENT
    harm_status = ABSENT if direction == PROMOTION else PRESENT
    benefit = int(np.sum(eligible & (gt == benefit_status)))
    harm = int(np.sum(eligible & (gt == harm_status)))
    return benefit, harm, benefit + harm


def _bootstrap_improvement_rate(
    label_frame: pd.DataFrame,
    selected_predictions: np.ndarray,
    *,
    iterations: int,
    seed: int,
) -> float:
    patient_values = label_frame["patient_key"].to_numpy()
    unique_patients = np.unique(patient_values)
    patient_indices = {
        patient: np.flatnonzero(patient_values == patient)
        for patient in unique_patients
    }
    gt = label_frame["gt_status"].to_numpy()
    baseline = label_frame["vision_status"].to_numpy()
    rng = np.random.default_rng(seed)
    improved = 0
    comparable = 0

    for _ in range(iterations):
        sampled_patients = rng.choice(
            unique_patients, size=len(unique_patients), replace=True
        )
        sampled_indices = np.concatenate(
            [patient_indices[patient] for patient in sampled_patients]
        )
        sampled_gt = gt[sampled_indices]
        if not np.any(sampled_gt == PRESENT):
            continue
        baseline_f1 = float(
            _binary_metrics(sampled_gt, baseline[sampled_indices])["f1"]
        )
        selected_f1 = float(
            _binary_metrics(sampled_gt, selected_predictions[sampled_indices])["f1"]
        )
        comparable += 1
        improved += int(selected_f1 > baseline_f1)
    return improved / comparable if comparable else 0.0


def _candidate_row(
    label_frame: pd.DataFrame,
    *,
    label: str,
    candidate: DirectionalGateCandidate,
    constraints: TuningConstraints,
) -> dict[str, Any]:
    gt = label_frame["gt_status"].to_numpy()
    baseline_predictions = label_frame["vision_status"].to_numpy()
    selected_predictions, changed = _apply_direction(
        label_frame, candidate, constraints
    )
    baseline_metrics = _binary_metrics(gt, baseline_predictions)
    selected_metrics = _binary_metrics(gt, selected_predictions)

    benefit_status = PRESENT if candidate.direction == PROMOTION else ABSENT
    harm_status = ABSENT if candidate.direction == PROMOTION else PRESENT
    scoreable_changed = changed & np.isin(gt, [PRESENT, ABSENT])
    beneficial = int(np.sum(changed & (gt == benefit_status)))
    harmful = int(np.sum(changed & (gt == harm_status)))
    scoreable_changes = beneficial + harmful
    unscored = int(np.sum(changed & ~np.isin(gt, [PRESENT, ABSENT])))
    (
        benefit_opportunities,
        harm_opportunities,
        scoreable_opportunities,
    ) = _opportunity_counts(
        label_frame,
        direction=candidate.direction,
        constraints=constraints,
    )
    intervention_precision = _safe_div(beneficial, scoreable_changes)
    intervention_coverage = (
        scoreable_changes / scoreable_opportunities if scoreable_opportunities else 0.0
    )
    baseline_f1 = float(baseline_metrics["f1"])
    selected_f1 = float(selected_metrics["f1"])
    f1_gain = selected_f1 - baseline_f1
    baseline_precision = baseline_metrics["precision"]
    selected_precision = selected_metrics["precision"]

    bootstrap_rate: float | None = None
    rejection_reasons: list[str] = []
    if benefit_opportunities < constraints.min_opportunities_per_outcome:
        rejection_reasons.append("insufficient_benefit_opportunities")
    if harm_opportunities < constraints.min_opportunities_per_outcome:
        rejection_reasons.append("insufficient_harm_opportunities")
    if scoreable_changes < constraints.min_scoreable_changes:
        rejection_reasons.append("insufficient_scoreable_changes")
    if intervention_precision is None or (
        intervention_precision < constraints.min_intervention_precision
    ):
        rejection_reasons.append("intervention_precision_below_min")
    if beneficial <= harmful:
        rejection_reasons.append("nonpositive_net_benefit")
    if f1_gain < constraints.min_label_f1_gain:
        rejection_reasons.append("f1_gain_below_min")
    if baseline_precision is not None:
        selected_precision_value = (
            selected_precision if selected_precision is not None else 0.0
        )
        if (
            baseline_precision - selected_precision_value
            > constraints.max_label_precision_drop
        ):
            rejection_reasons.append("label_precision_drop_too_large")

    if not rejection_reasons:
        candidate_seed = (
            constraints.random_seed
            + zlib.crc32(f"{label}:{candidate.direction}".encode("utf-8"))
            + int(round(candidate.prior_threshold * 1000))
            + int(round(candidate.min_retrieval_confidence * 10000))
        )
        bootstrap_rate = _bootstrap_improvement_rate(
            label_frame,
            selected_predictions,
            iterations=constraints.bootstrap_iterations,
            seed=candidate_seed,
        )
        if bootstrap_rate < constraints.min_bootstrap_improvement_rate:
            rejection_reasons.append("bootstrap_improvement_rate_below_min")

    return {
        "label": label,
        **asdict(candidate),
        "eligible_benefit_opportunities": benefit_opportunities,
        "eligible_harm_opportunities": harm_opportunities,
        "eligible_scoreable_opportunities": scoreable_opportunities,
        "total_changes": int(np.sum(changed)),
        "scoreable_changes": int(np.sum(scoreable_changed)),
        "beneficial_changes": beneficial,
        "harmful_changes": harmful,
        "unscored_changes": unscored,
        "net_benefit": beneficial - harmful,
        "intervention_precision": intervention_precision,
        "intervention_coverage": intervention_coverage,
        "baseline_precision": baseline_precision,
        "selected_precision": selected_precision,
        "baseline_recall": baseline_metrics["recall"],
        "selected_recall": selected_metrics["recall"],
        "baseline_f1": baseline_f1,
        "selected_f1": selected_f1,
        "f1_gain": f1_gain,
        "bootstrap_improvement_rate": bootstrap_rate,
        "accepted": not rejection_reasons,
        "rejection_reasons": "|".join(rejection_reasons),
    }


def _best_candidate_row(candidate_rows: pd.DataFrame) -> pd.Series | None:
    accepted = candidate_rows[candidate_rows["accepted"]].copy()
    if accepted.empty:
        return None
    return accepted.sort_values(
        [
            "intervention_coverage",
            "f1_gain",
            "intervention_precision",
            "prior_threshold",
            "min_retrieval_confidence",
        ],
        ascending=[False, False, False, False, False],
    ).iloc[0]


def _disabled_reason(candidate_rows: pd.DataFrame) -> str:
    reasons: list[str] = []
    for raw in candidate_rows["rejection_reasons"].astype(str):
        reasons.extend(item for item in raw.split("|") if item)
    if not reasons:
        return "no_candidate_accepted"
    counts = pd.Series(reasons).value_counts()
    return "no_candidate_accepted:" + ",".join(
        f"{reason}={int(count)}" for reason, count in counts.items()
    )


def _selection_from_rows(
    *,
    label: str,
    direction: str,
    candidate_rows: pd.DataFrame,
) -> DirectionSelection:
    best = _best_candidate_row(candidate_rows)
    if best is None:
        benefit_opportunities = int(
            candidate_rows["eligible_benefit_opportunities"].iloc[0]
        )
        harm_opportunities = int(candidate_rows["eligible_harm_opportunities"].iloc[0])
        baseline_f1 = float(candidate_rows["baseline_f1"].iloc[0])
        baseline_precision = candidate_rows["baseline_precision"].iloc[0]
        return DirectionSelection(
            label=label,
            direction=direction,
            enabled=False,
            reason=_disabled_reason(candidate_rows),
            prior_threshold=None,
            min_retrieval_confidence=None,
            eligible_benefit_opportunities=benefit_opportunities,
            eligible_harm_opportunities=harm_opportunities,
            scoreable_changes=0,
            beneficial_changes=0,
            harmful_changes=0,
            unscored_changes=0,
            intervention_precision=None,
            intervention_coverage=0.0,
            baseline_f1=baseline_f1,
            selected_f1=baseline_f1,
            f1_gain=0.0,
            baseline_precision=(
                None if pd.isna(baseline_precision) else float(baseline_precision)
            ),
            selected_precision=(
                None if pd.isna(baseline_precision) else float(baseline_precision)
            ),
            bootstrap_improvement_rate=None,
        )

    def optional_float(key: str) -> float | None:
        value = best[key]
        return None if pd.isna(value) else float(value)

    return DirectionSelection(
        label=label,
        direction=direction,
        enabled=True,
        reason="accepted",
        prior_threshold=float(best["prior_threshold"]),
        min_retrieval_confidence=float(best["min_retrieval_confidence"]),
        eligible_benefit_opportunities=int(best["eligible_benefit_opportunities"]),
        eligible_harm_opportunities=int(best["eligible_harm_opportunities"]),
        scoreable_changes=int(best["scoreable_changes"]),
        beneficial_changes=int(best["beneficial_changes"]),
        harmful_changes=int(best["harmful_changes"]),
        unscored_changes=int(best["unscored_changes"]),
        intervention_precision=optional_float("intervention_precision"),
        intervention_coverage=float(best["intervention_coverage"]),
        baseline_f1=float(best["baseline_f1"]),
        selected_f1=float(best["selected_f1"]),
        f1_gain=float(best["f1_gain"]),
        baseline_precision=optional_float("baseline_precision"),
        selected_precision=optional_float("selected_precision"),
        bootstrap_improvement_rate=optional_float("bootstrap_improvement_rate"),
    )


def tune_per_label_gates(
    frame: pd.DataFrame,
    *,
    promotion_prior_thresholds: Sequence[float],
    demotion_prior_thresholds: Sequence[float],
    confidence_thresholds: Sequence[float],
    constraints: TuningConstraints,
    labels: Sequence[str] = DISEASE_LABELS,
) -> tuple[pd.DataFrame, tuple[DirectionSelection, ...]]:
    """Score and select independent promotion/demotion rules per label."""
    _validate_constraints(constraints)
    grid_rows: list[dict[str, Any]] = []
    selections: list[DirectionSelection] = []

    for label in labels:
        label_frame = frame[frame["label"] == label].reset_index(drop=True)
        if label_frame.empty:
            raise ValueError(f"No validation feature rows found for label={label!r}")
        for direction, prior_thresholds in (
            (PROMOTION, promotion_prior_thresholds),
            (DEMOTION, demotion_prior_thresholds),
        ):
            rows = [
                _candidate_row(
                    label_frame,
                    label=label,
                    candidate=candidate,
                    constraints=constraints,
                )
                for candidate in _direction_candidates(
                    direction=direction,
                    prior_thresholds=prior_thresholds,
                    confidence_thresholds=confidence_thresholds,
                )
            ]
            direction_frame = pd.DataFrame(rows)
            grid_rows.extend(rows)
            selections.append(
                _selection_from_rows(
                    label=label,
                    direction=direction,
                    candidate_rows=direction_frame,
                )
            )
    return pd.DataFrame(grid_rows), tuple(selections)


def _selection_lookup(
    selections: Sequence[DirectionSelection],
) -> dict[tuple[str, str], DirectionSelection]:
    return {
        (selection.label, selection.direction): selection for selection in selections
    }


def _apply_selections(
    frame: pd.DataFrame,
    selections: Sequence[DirectionSelection],
    constraints: TuningConstraints,
) -> pd.Series:
    fused = frame["vision_status"].copy()
    lookup = _selection_lookup(selections)
    selected_labels = [
        label for label in DISEASE_LABELS if (label, PROMOTION) in lookup
    ]
    for label in selected_labels:
        label_indices = frame.index[frame["label"] == label]
        label_frame = frame.loc[label_indices].reset_index(drop=True)
        for direction in (PROMOTION, DEMOTION):
            selection = lookup[(label, direction)]
            if not selection.enabled:
                continue
            candidate = DirectionalGateCandidate(
                direction=direction,
                prior_threshold=float(selection.prior_threshold),
                min_retrieval_confidence=float(selection.min_retrieval_confidence),
            )
            predictions, changed = _apply_direction(label_frame, candidate, constraints)
            changed_indices = label_indices[changed]
            fused.loc[changed_indices] = predictions[changed]
    return fused


def _changed_cells_frame(
    frame: pd.DataFrame,
    fused_statuses: pd.Series,
) -> pd.DataFrame:
    changed = frame.loc[fused_statuses != frame["vision_status"]].copy()
    columns = [
        "study_key",
        "patient_key",
        "label",
        "gt_status",
        "vision_status",
        "tuned_fused_status",
        "change_type",
        "probability",
        "threshold",
        "retrieval_present_prior",
        "retrieval_absent_prior",
        "retrieval_confidence",
    ]
    if changed.empty:
        return pd.DataFrame(columns=columns)
    changed["tuned_fused_status"] = fused_statuses.loc[changed.index]
    changed["change_type"] = np.where(
        changed["vision_status"] == ABSENT,
        PROMOTION,
        DEMOTION,
    )
    return changed[columns].sort_values(["label", "study_key"])


def _policy_payload(
    *,
    selections: Sequence[DirectionSelection],
    constraints: TuningConstraints,
    run_config: dict[str, Any],
) -> dict[str, Any]:
    lookup = _selection_lookup(selections)
    label_rules: dict[str, dict[str, Any]] = {}
    for label in DISEASE_LABELS:
        promotion = lookup[(label, PROMOTION)]
        demotion = lookup[(label, DEMOTION)]
        label_rules[label] = {
            "promotion_enabled": promotion.enabled,
            "demotion_enabled": demotion.enabled,
            "promotion_prior_threshold": promotion.prior_threshold,
            "demotion_prior_threshold": demotion.prior_threshold,
            "promotion_min_retrieval_confidence": (promotion.min_retrieval_confidence),
            "demotion_min_retrieval_confidence": demotion.min_retrieval_confidence,
            "promotion_selection_reason": promotion.reason,
            "demotion_selection_reason": demotion.reason,
        }
    return {
        "policy_version": TUNING_POLICY_VERSION,
        "base_fusion_policy_version": PRIOR_FUSION_POLICY_VERSION,
        "scope": "per_label_directional",
        "tuned_on": "validation",
        "ground_truth_policy": "present_absent_only",
        "selection_objective": "maximize_coverage_subject_to_intervention_risk",
        "global_constraints": asdict(constraints),
        "label_rules": label_rules,
        "run_config": run_config,
    }


def main(argv: list[str] | None = None) -> int:
    """Tune per-label gates and write auditable validation artifacts."""
    args = build_parser().parse_args(argv)
    constraints = TuningConstraints(
        gray_zone_margin=args.gray_zone_margin,
        max_opposing_prior=args.max_opposing_prior,
        absent_demotion_prior_threshold=args.absent_demotion_prior_threshold,
        min_opportunities_per_outcome=args.min_opportunities_per_outcome,
        min_scoreable_changes=args.min_scoreable_changes,
        min_intervention_precision=args.min_intervention_precision,
        min_label_f1_gain=args.min_label_f1_gain,
        max_label_precision_drop=args.max_label_precision_drop,
        bootstrap_iterations=args.bootstrap_iterations,
        min_bootstrap_improvement_rate=args.min_bootstrap_improvement_rate,
        random_seed=args.random_seed,
    )
    _validate_constraints(constraints)
    promotion_thresholds = _parse_float_list(args.promotion_prior_thresholds)
    demotion_thresholds = _parse_float_list(args.demotion_prior_thresholds)
    confidence_thresholds = _parse_float_list(args.min_retrieval_confidences)

    _require_existing_paths(
        {
            "features_csv": args.features_csv,
            "source_run_config": args.source_run_config,
            "study_labels_csv": args.study_labels_csv,
        }
    )
    source_run_config = _load_validation_source_config(args.source_run_config)

    started = time.perf_counter()
    features = _load_feature_frame(args.features_csv)
    ground_truth = _load_ground_truth_long(
        args.study_labels_csv,
        study_keys=features["study_key"].unique(),
    )
    frame = _attach_ground_truth(features, ground_truth)
    _prepare_output_dir(args.output_dir, overwrite=args.overwrite)
    print(
        "[PerLabelGateTuning] "
        f"features={len(frame)} studies={frame['study_key'].nunique()} "
        f"bootstrap_iterations={constraints.bootstrap_iterations}"
    )

    grid_results, selections = tune_per_label_gates(
        frame,
        promotion_prior_thresholds=promotion_thresholds,
        demotion_prior_thresholds=demotion_thresholds,
        confidence_thresholds=confidence_thresholds,
        constraints=constraints,
    )
    fused_statuses = _apply_selections(frame, selections, constraints)
    elapsed = time.perf_counter() - started
    enabled_count = sum(selection.enabled for selection in selections)

    run_config = {
        "experiment": args.output_dir.name,
        "policy_version": TUNING_POLICY_VERSION,
        "base_fusion_policy_version": PRIOR_FUSION_POLICY_VERSION,
        "cohort_root": DEFAULT_BALANCED_COHORT_ROOT,
        "features_csv": str(args.features_csv),
        "source_run_config": str(args.source_run_config),
        "source_experiment": source_run_config.get("experiment"),
        "study_labels_csv": str(args.study_labels_csv),
        "source_split": str(source_run_config["split"]),
        "feature_rows": len(frame),
        "study_count": int(frame["study_key"].nunique()),
        "candidate_count": len(grid_results),
        "enabled_direction_count": enabled_count,
        "constraints": asdict(constraints),
        "promotion_prior_thresholds": list(promotion_thresholds),
        "demotion_prior_thresholds": list(demotion_thresholds),
        "min_retrieval_confidences": list(confidence_thresholds),
        "elapsed_seconds": elapsed,
    }

    sorted_grid = grid_results.sort_values(
        ["label", "direction", "accepted", "intervention_coverage", "f1_gain"],
        ascending=[True, True, False, False, False],
    )
    sorted_grid.to_csv(
        args.output_dir / "per_label_gate_grid_results.csv",
        index=False,
    )
    pd.DataFrame([asdict(selection) for selection in selections]).to_csv(
        args.output_dir / "per_label_gate_selection.csv",
        index=False,
    )
    _changed_cells_frame(frame, fused_statuses).to_csv(
        args.output_dir / "best_changed_cells.csv",
        index=False,
    )
    _write_json(args.output_dir / "run_config.json", run_config)
    _write_json(
        args.output_dir / "best_prior_fusion_policy.json",
        _policy_payload(
            selections=selections,
            constraints=constraints,
            run_config=run_config,
        ),
    )

    print(
        "[PerLabelGateTuning] "
        f"enabled={enabled_count}/{len(selections)} directional gates "
        f"elapsed={elapsed:.1f}s"
    )
    for selection in selections:
        status = "enabled" if selection.enabled else "disabled"
        gate = (
            f"prior>={selection.prior_threshold:.2f} "
            f"retrieval_confidence>={selection.min_retrieval_confidence:.2f}"
            if selection.enabled
            else selection.reason
        )
        print(
            f"[PerLabelGateTuning] {selection.label} {selection.direction}: "
            f"{status} ({gate})"
        )
    print(f"[PerLabelGateTuning] wrote outputs -> {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
