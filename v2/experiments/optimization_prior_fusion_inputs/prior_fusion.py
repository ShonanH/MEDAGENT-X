"""Deterministic gray-zone fusion using retrieval label priors.

This is the second Topic 2 building block. It consumes vision predictions plus
RetrievalLabelPrior values and proposes keep/promote/demote decisions. The
thresholds here are initial auditable defaults, not validation-tuned constants.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:
    from retrieval_prior import DISEASE_LABELS, RetrievalLabelPrior
except ModuleNotFoundError:
    _RETRIEVAL_PRIOR_PATH = Path(__file__).with_name("retrieval_prior.py")
    _SPEC = importlib.util.spec_from_file_location(
        "optimization_retrieval_prior",
        _RETRIEVAL_PRIOR_PATH,
    )
    if _SPEC is None or _SPEC.loader is None:
        raise ImportError(f"Could not load {_RETRIEVAL_PRIOR_PATH}")
    _MODULE = importlib.util.module_from_spec(_SPEC)
    sys.modules[_SPEC.name] = _MODULE
    _SPEC.loader.exec_module(_MODULE)
    DISEASE_LABELS = _MODULE.DISEASE_LABELS
    RetrievalLabelPrior = _MODULE.RetrievalLabelPrior


PRESENT = "present"
ABSENT = "absent"
UNCERTAIN = "uncertain"
PRIOR_FUSION_POLICY_VERSION = "retrieval_prior_fusion_v1_unvalidated"
GRAY_ZONE_MARGIN = 0.15

DEFAULT_PROMOTION_PRIOR_THRESHOLD = 0.70
DEFAULT_DEMOTION_PRIOR_THRESHOLD = 0.80
DEFAULT_ABSENT_DEMOTION_PRIOR_THRESHOLD = 0.90
DEFAULT_MIN_RETRIEVAL_CONFIDENCE = 0.60
DEFAULT_MAX_OPPOSING_PRIOR = 0.20


@dataclass(frozen=True)
class PriorVisionLabelPrediction:
    """One disease prediction from the vision model."""

    label: str
    probability: float
    threshold: float
    status: str | None = None

    @property
    def vision_status(self) -> str:
        """Return explicit status when provided, else threshold the probability."""
        if self.status is not None:
            return normalize_binary_status(self.status)
        return vision_status_from_probability(self.probability, self.threshold)


@dataclass(frozen=True)
class PriorFusionRule:
    """Per-label retrieval-prior fusion thresholds."""

    promotion_enabled: bool = True
    demotion_enabled: bool = True
    promotion_prior_threshold: float = DEFAULT_PROMOTION_PRIOR_THRESHOLD
    demotion_prior_threshold: float = DEFAULT_DEMOTION_PRIOR_THRESHOLD
    absent_demotion_prior_threshold: float = DEFAULT_ABSENT_DEMOTION_PRIOR_THRESHOLD
    min_retrieval_confidence: float = DEFAULT_MIN_RETRIEVAL_CONFIDENCE
    promotion_min_retrieval_confidence: float | None = None
    demotion_min_retrieval_confidence: float | None = None
    max_opposing_prior: float = DEFAULT_MAX_OPPOSING_PRIOR

    @property
    def promotion_confidence_threshold(self) -> float:
        value = self.promotion_min_retrieval_confidence
        return self.min_retrieval_confidence if value is None else value

    @property
    def demotion_confidence_threshold(self) -> float:
        value = self.demotion_min_retrieval_confidence
        return self.min_retrieval_confidence if value is None else value


@dataclass(frozen=True)
class PriorFusionPolicy:
    """Validated frozen per-label policy loaded from a tuning artifact."""

    policy_version: str
    gray_zone_margin: float
    rule_overrides: Mapping[str, Mapping[str, Any]]


@dataclass(frozen=True)
class PriorFusedLabelPrediction:
    """One prior-fusion label decision with audit metadata."""

    label: str
    vision_status: str
    fused_status: str
    probability: float
    threshold: float
    probability_minus_threshold: float
    in_gray_zone: bool
    retrieval_present_prior: float
    retrieval_absent_prior: float
    retrieval_uncertain_rate: float
    retrieval_unmentioned_rate: float
    retrieval_confidence: float
    retrieval_contradiction_signal: float
    vision_retrieval_agreement: bool
    retrieval_scoreable_weight: float
    retrieval_total_weight: float
    retrieval_mean_similarity: float
    retrieval_scoreable_count: int
    retrieval_count: int
    top_supporting_cases: tuple[str, ...]
    top_contradicting_cases: tuple[str, ...]
    refinement_reason: str


@dataclass(frozen=True)
class PriorFusionStudyResult:
    """Prior-fusion output for one study."""

    study_key: str
    fusion_policy_version: str
    labels: tuple[PriorFusedLabelPrediction, ...]


def normalize_binary_status(value: Any) -> str:
    """Normalize a vision status to present or absent."""
    raw_value = getattr(value, "value", value)
    status = str(raw_value or "").strip().lower()
    if status not in {PRESENT, ABSENT}:
        raise ValueError(f"Vision status must be present or absent, got {value!r}")
    return status


def vision_status_from_probability(probability: float, threshold: float) -> str:
    """Map a vision probability to present/absent using its label threshold."""
    return PRESENT if float(probability) >= float(threshold) else ABSENT


def is_gray_zone(
    probability: float,
    threshold: float,
    *,
    margin: float = GRAY_ZONE_MARGIN,
) -> bool:
    """Return True when fusion is allowed to override the vision status."""
    return abs(float(probability) - float(threshold)) <= float(margin)


def _probability_value(value: Any, *, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric, got {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric, got {value!r}") from exc
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be in [0, 1], got {number}")
    return number


def _enabled_value(value: Any, *, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true or false, got {value!r}")
    return value


def load_prior_fusion_policy(path: Path) -> PriorFusionPolicy:
    """Load and validate a frozen per-label tuning policy."""
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    if payload.get("scope") != "per_label_directional":
        raise ValueError(f"{path} is not a per-label directional policy")
    if payload.get("tuned_on") != "validation":
        raise ValueError(f"{path} must declare tuned_on='validation'")

    policy_version = payload.get("policy_version")
    if not isinstance(policy_version, str) or not policy_version.strip():
        raise ValueError(f"{path} must contain a non-empty policy_version")
    constraints = payload.get("global_constraints")
    if not isinstance(constraints, dict):
        raise ValueError(f"{path} must contain global_constraints")
    margin = _probability_value(
        constraints.get("gray_zone_margin"),
        name="global_constraints.gray_zone_margin",
    )
    absent_threshold = _probability_value(
        constraints.get("absent_demotion_prior_threshold"),
        name="global_constraints.absent_demotion_prior_threshold",
    )
    max_opposing = _probability_value(
        constraints.get("max_opposing_prior"),
        name="global_constraints.max_opposing_prior",
    )

    label_rules = payload.get("label_rules")
    if not isinstance(label_rules, dict):
        raise ValueError(f"{path} must contain label_rules")
    missing = sorted(set(DISEASE_LABELS) - set(label_rules))
    unexpected = sorted(set(label_rules) - set(DISEASE_LABELS))
    if missing or unexpected:
        raise ValueError(
            f"{path} label_rules mismatch; missing={missing}, unexpected={unexpected}"
        )

    overrides: dict[str, dict[str, Any]] = {}
    for label in DISEASE_LABELS:
        raw_rule = label_rules[label]
        if not isinstance(raw_rule, dict):
            raise ValueError(f"label_rules.{label} must be an object")
        promotion_enabled = _enabled_value(
            raw_rule.get("promotion_enabled"),
            name=f"label_rules.{label}.promotion_enabled",
        )
        demotion_enabled = _enabled_value(
            raw_rule.get("demotion_enabled"),
            name=f"label_rules.{label}.demotion_enabled",
        )
        rule: dict[str, Any] = {
            "promotion_enabled": promotion_enabled,
            "demotion_enabled": demotion_enabled,
            "absent_demotion_prior_threshold": absent_threshold,
            "max_opposing_prior": max_opposing,
        }
        if promotion_enabled:
            rule["promotion_prior_threshold"] = _probability_value(
                raw_rule.get("promotion_prior_threshold"),
                name=f"label_rules.{label}.promotion_prior_threshold",
            )
            rule["promotion_min_retrieval_confidence"] = _probability_value(
                raw_rule.get("promotion_min_retrieval_confidence"),
                name=f"label_rules.{label}.promotion_min_retrieval_confidence",
            )
        if demotion_enabled:
            rule["demotion_prior_threshold"] = _probability_value(
                raw_rule.get("demotion_prior_threshold"),
                name=f"label_rules.{label}.demotion_prior_threshold",
            )
            rule["demotion_min_retrieval_confidence"] = _probability_value(
                raw_rule.get("demotion_min_retrieval_confidence"),
                name=f"label_rules.{label}.demotion_min_retrieval_confidence",
            )
        overrides[label] = rule

    return PriorFusionPolicy(
        policy_version=policy_version.strip(),
        gray_zone_margin=margin,
        rule_overrides=overrides,
    )


def prior_rule_for_label(
    label: str,
    *,
    overrides: Mapping[str, Mapping[str, Any]] | None = None,
) -> PriorFusionRule:
    """Return the default prior-fusion rule plus optional label overrides."""
    if label not in DISEASE_LABELS:
        raise ValueError(f"Unsupported disease label: {label!r}")

    label_overrides = dict((overrides or {}).get(label, {}))
    allowed = set(PriorFusionRule.__dataclass_fields__)
    unexpected = sorted(set(label_overrides) - allowed)
    if unexpected:
        raise ValueError(f"Unexpected prior-fusion rule keys for {label}: {unexpected}")
    rule = PriorFusionRule(**label_overrides)
    for name in ("promotion_enabled", "demotion_enabled"):
        _enabled_value(getattr(rule, name), name=f"{label}.{name}")
    for name in (
        "promotion_prior_threshold",
        "demotion_prior_threshold",
        "absent_demotion_prior_threshold",
        "min_retrieval_confidence",
        "max_opposing_prior",
    ):
        _probability_value(getattr(rule, name), name=f"{label}.{name}")
    for name in (
        "promotion_min_retrieval_confidence",
        "demotion_min_retrieval_confidence",
    ):
        value = getattr(rule, name)
        if value is not None:
            _probability_value(value, name=f"{label}.{name}")
    return rule


def retrieval_contradiction_signal(
    *,
    vision_status: str,
    prior: RetrievalLabelPrior,
) -> float:
    """Return the retrieval prior mass opposing the current vision status."""
    if vision_status == PRESENT:
        return float(prior.absent_prior)
    return float(prior.present_prior)


def vision_retrieval_agrees(
    *,
    vision_status: str,
    prior: RetrievalLabelPrior,
) -> bool:
    """Return True when the larger retrieval prior supports vision."""
    if prior.present_prior == prior.absent_prior:
        return False
    if vision_status == PRESENT:
        return prior.present_prior > prior.absent_prior
    return prior.absent_prior > prior.present_prior


def retrieval_supports_promotion(
    prior: RetrievalLabelPrior,
    rule: PriorFusionRule,
) -> bool:
    """Return True when retrieval prior supports absent -> present."""
    return (
        rule.promotion_enabled
        and prior.present_prior >= rule.promotion_prior_threshold
        and prior.retrieval_confidence >= rule.promotion_confidence_threshold
        and prior.absent_prior <= rule.max_opposing_prior
    )


def retrieval_supports_demotion(
    prior: RetrievalLabelPrior,
    rule: PriorFusionRule,
) -> bool:
    """Return True when retrieval prior supports present -> uncertain/absent."""
    return (
        rule.demotion_enabled
        and prior.absent_prior >= rule.demotion_prior_threshold
        and prior.retrieval_confidence >= rule.demotion_confidence_threshold
        and prior.present_prior <= rule.max_opposing_prior
    )


def retrieval_strongly_absent(
    prior: RetrievalLabelPrior,
    rule: PriorFusionRule,
) -> bool:
    """Return True when demotion can go all the way to absent."""
    return (
        prior.absent_prior >= rule.absent_demotion_prior_threshold
        and prior.present_prior <= rule.max_opposing_prior
    )


def _prediction_value(prediction: Any, key: str) -> Any:
    if isinstance(prediction, Mapping):
        return prediction.get(key)
    return getattr(prediction, key, None)


def _coerce_prediction(prediction: Any) -> PriorVisionLabelPrediction:
    if isinstance(prediction, PriorVisionLabelPrediction):
        return prediction

    label = _prediction_value(prediction, "label")
    probability = _prediction_value(prediction, "probability")
    threshold = _prediction_value(prediction, "threshold")
    status = _prediction_value(prediction, "status")

    if label is None:
        raise ValueError(f"Vision prediction is missing label: {prediction!r}")
    if probability is None:
        raise ValueError(f"Vision prediction is missing probability: {prediction!r}")
    if threshold is None:
        raise ValueError(f"Vision prediction is missing threshold: {prediction!r}")

    return PriorVisionLabelPrediction(
        label=str(label),
        probability=float(probability),
        threshold=float(threshold),
        status=None if status is None else normalize_binary_status(status),
    )


def fuse_label_with_prior(
    prediction: Any,
    prior: RetrievalLabelPrior,
    *,
    margin: float = GRAY_ZONE_MARGIN,
    rule: PriorFusionRule | None = None,
) -> PriorFusedLabelPrediction:
    """Apply retrieval-prior fusion to one disease label."""
    vision_prediction = _coerce_prediction(prediction)
    if vision_prediction.label not in DISEASE_LABELS:
        raise ValueError(f"Unsupported disease label: {vision_prediction.label!r}")
    if prior.label != vision_prediction.label:
        raise ValueError(
            f"Prior label {prior.label!r} does not match "
            f"prediction label {vision_prediction.label!r}"
        )

    active_rule = rule or prior_rule_for_label(vision_prediction.label)
    vision_status = vision_prediction.vision_status
    gray_zone = is_gray_zone(
        vision_prediction.probability,
        vision_prediction.threshold,
        margin=margin,
    )
    fused_status = vision_status
    reason = "vision kept (strong zone)"

    if gray_zone:
        reason = "vision kept (gray zone, insufficient retrieval-prior signal)"
        if (
            vision_status == ABSENT
            and retrieval_supports_promotion(prior, active_rule)
        ):
            fused_status = PRESENT
            reason = (
                "promoted absent to present by retrieval prior: "
                f"present_prior={prior.present_prior:.3f}, "
                f"absent_prior={prior.absent_prior:.3f}, "
                f"confidence={prior.retrieval_confidence:.3f}"
            )
        elif (
            vision_status == PRESENT
            and retrieval_supports_demotion(prior, active_rule)
        ):
            if retrieval_strongly_absent(prior, active_rule):
                fused_status = ABSENT
                reason = (
                    "demoted present to absent by retrieval prior: "
                    f"absent_prior={prior.absent_prior:.3f}, "
                    f"present_prior={prior.present_prior:.3f}, "
                    f"confidence={prior.retrieval_confidence:.3f}"
                )
            else:
                fused_status = UNCERTAIN
                reason = (
                    "demoted present to uncertain by retrieval prior: "
                    f"absent_prior={prior.absent_prior:.3f}, "
                    f"present_prior={prior.present_prior:.3f}, "
                    f"confidence={prior.retrieval_confidence:.3f}"
                )

    probability = float(vision_prediction.probability)
    threshold = float(vision_prediction.threshold)
    return PriorFusedLabelPrediction(
        label=vision_prediction.label,
        vision_status=vision_status,
        fused_status=fused_status,
        probability=probability,
        threshold=threshold,
        probability_minus_threshold=probability - threshold,
        in_gray_zone=gray_zone,
        retrieval_present_prior=float(prior.present_prior),
        retrieval_absent_prior=float(prior.absent_prior),
        retrieval_uncertain_rate=float(prior.uncertain_rate),
        retrieval_unmentioned_rate=float(prior.unmentioned_rate),
        retrieval_confidence=float(prior.retrieval_confidence),
        retrieval_contradiction_signal=retrieval_contradiction_signal(
            vision_status=vision_status,
            prior=prior,
        ),
        vision_retrieval_agreement=vision_retrieval_agrees(
            vision_status=vision_status,
            prior=prior,
        ),
        retrieval_scoreable_weight=float(prior.scoreable_weight),
        retrieval_total_weight=float(prior.total_weight),
        retrieval_mean_similarity=float(prior.mean_similarity),
        retrieval_scoreable_count=int(prior.scoreable_count),
        retrieval_count=int(prior.retrieved_count),
        top_supporting_cases=tuple(prior.top_supporting_cases),
        top_contradicting_cases=tuple(prior.top_contradicting_cases),
        refinement_reason=reason,
    )


def fuse_study_labels_with_priors(
    vision_predictions: Mapping[str, Any],
    retrieval_priors: Mapping[str, RetrievalLabelPrior],
    *,
    study_key: str = "",
    margin: float = GRAY_ZONE_MARGIN,
    rule_overrides: Mapping[str, Mapping[str, Any]] | None = None,
    policy_version: str = PRIOR_FUSION_POLICY_VERSION,
) -> PriorFusionStudyResult:
    """Fuse all disease labels for one study using retrieval priors."""
    missing_predictions = [
        label for label in DISEASE_LABELS if label not in vision_predictions
    ]
    missing_priors = [
        label for label in DISEASE_LABELS if label not in retrieval_priors
    ]
    if missing_predictions:
        raise ValueError(
            "Missing vision predictions for labels: "
            + ", ".join(missing_predictions)
        )
    if missing_priors:
        raise ValueError(
            "Missing retrieval priors for labels: " + ", ".join(missing_priors)
        )

    fused_labels = []
    for label in DISEASE_LABELS:
        fused_labels.append(
            fuse_label_with_prior(
                vision_predictions[label],
                retrieval_priors[label],
                margin=margin,
                rule=prior_rule_for_label(label, overrides=rule_overrides),
            )
        )

    return PriorFusionStudyResult(
        study_key=study_key,
        fusion_policy_version=policy_version,
        labels=tuple(fused_labels),
    )
