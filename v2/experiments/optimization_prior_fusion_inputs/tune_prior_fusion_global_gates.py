"""Tune global retrieval-prior fusion gates on validation outputs.

This script does not rerun vision or retrieval. It expects a validation
prior_fusion_label_predictions.csv produced by run_prior_fusion_eval.py, then
sweeps global gate values and scores each candidate against validation labels.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Any, Iterable, Sequence

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
DEFAULT_FEATURES_CSV = (
    V2_ROOT
    / "experiments"
    / "exp10_prior_fusion_val_features"
    / "prior_fusion_label_predictions.csv"
)
DEFAULT_STUDY_LABELS_CSV = EXPERIMENT_DIR / "splits" / "study_label_table.csv"
DEFAULT_OUTPUT_DIR = V2_ROOT / "experiments" / "exp10_prior_fusion_gate_tuning"
TUNING_POLICY_VERSION = "retrieval_prior_global_gate_tuning_v1"
OUTPUT_FILENAMES = (
    "run_config.json",
    "global_gate_grid_results.csv",
    "best_prior_fusion_policy.json",
    "best_changed_cells.csv",
)


@dataclass(frozen=True)
class GateCandidate:
    """One global prior-fusion gate setting."""

    promotion_prior_threshold: float
    demotion_prior_threshold: float
    absent_demotion_prior_threshold: float
    min_retrieval_confidence: float
    max_opposing_prior: float
    gray_zone_margin: float


def build_parser() -> argparse.ArgumentParser:
    """Build the global gate tuning CLI."""
    parser = argparse.ArgumentParser(
        description=(
            "Tune global retrieval-prior fusion gates on validation features. "
            "Run run_prior_fusion_eval.py on --split val first."
        )
    )
    parser.add_argument("--features-csv", type=Path, default=DEFAULT_FEATURES_CSV)
    parser.add_argument(
        "--study-labels-csv",
        type=Path,
        default=DEFAULT_STUDY_LABELS_CSV,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--objective",
        choices=(
            "gray_macro_f1",
            "full_macro_f1",
            "gray_micro_f1",
            "full_micro_f1",
        ),
        default="gray_macro_f1",
    )
    parser.add_argument(
        "--promotion-prior-thresholds",
        default="0.50,0.55,0.60,0.65,0.70,0.75,0.80,0.85,0.90",
    )
    parser.add_argument(
        "--demotion-prior-thresholds",
        default="0.70,0.75,0.80,0.85,0.90",
    )
    parser.add_argument(
        "--absent-demotion-prior-thresholds",
        default="0.85,0.90,0.95",
    )
    parser.add_argument(
        "--min-retrieval-confidences",
        default="0.00,0.05,0.10,0.15,0.20,0.25,0.30,0.35,0.40,0.45,0.50,0.55,0.60",
    )
    parser.add_argument("--max-opposing-priors", default="0.10,0.20,0.30,0.40")
    parser.add_argument("--gray-zone-margins", default="0.15")
    parser.add_argument(
        "--top-n",
        type=int,
        default=25,
        help="Number of top rows to print after tuning.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing tuning output files in --output-dir.",
    )
    return parser


def _parse_float_list(raw: str) -> tuple[float, ...]:
    values: list[float] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        values.append(float(item))
    if not values:
        raise ValueError("Grid lists must contain at least one number")
    return tuple(values)


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
            "Prior-fusion tuning output files already exist. "
            "Pass --overwrite to replace:\n"
            + "\n".join(str(path) for path in existing)
        )
    if overwrite:
        for path in existing:
            path.unlink()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


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
    for column in (
        "probability",
        "threshold",
        "retrieval_present_prior",
        "retrieval_absent_prior",
        "retrieval_confidence",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame["vision_status"] = frame["vision_status"].astype(str).str.strip().str.lower()
    if not frame["vision_status"].isin({PRESENT, ABSENT}).all():
        bad = sorted(
            set(
                frame.loc[
                    ~frame["vision_status"].isin({PRESENT, ABSENT}),
                    "vision_status",
                ]
            )
        )
        raise ValueError(f"Feature table has non-binary vision statuses: {bad}")
    return frame


def _load_ground_truth_long(
    study_labels_csv: Path,
    *,
    study_keys: Iterable[str],
) -> pd.DataFrame:
    study_labels = pd.read_csv(study_labels_csv, dtype=str)
    key_set = {str(key) for key in study_keys}
    study_labels = study_labels[study_labels["study_key"].astype(str).isin(key_set)]
    if study_labels.empty:
        raise ValueError("No study_label_table rows matched the feature study keys")

    rows: list[dict[str, str]] = []
    for _, row in study_labels.iterrows():
        study_key = str(row["study_key"])
        for label in DISEASE_LABELS:
            rows.append(
                {
                    "study_key": study_key,
                    "label": label,
                    "gt_status": (
                        str(row[f"status_{snake_label(label)}"]).strip().lower()
                    ),
                }
            )
    return pd.DataFrame(rows)


def _attach_ground_truth(
    features: pd.DataFrame,
    ground_truth: pd.DataFrame,
) -> pd.DataFrame:
    merged = features.merge(ground_truth, on=["study_key", "label"], how="left")
    missing_gt = merged["gt_status"].isna().sum()
    if missing_gt:
        raise ValueError(f"Missing ground truth for {missing_gt} feature rows")
    known = {PRESENT, ABSENT, UNCERTAIN, UNMENTIONED}
    if not merged["gt_status"].isin(known).all():
        bad = sorted(set(merged.loc[~merged["gt_status"].isin(known), "gt_status"]))
        raise ValueError(f"Ground truth has unknown statuses: {bad}")
    return merged


def _iter_candidates(args: argparse.Namespace) -> Sequence[GateCandidate]:
    promotion_values = _parse_float_list(args.promotion_prior_thresholds)
    demotion_values = _parse_float_list(args.demotion_prior_thresholds)
    absent_demotion_values = _parse_float_list(args.absent_demotion_prior_thresholds)
    confidence_values = _parse_float_list(args.min_retrieval_confidences)
    opposing_values = _parse_float_list(args.max_opposing_priors)
    margin_values = _parse_float_list(args.gray_zone_margins)

    candidates: list[GateCandidate] = []
    for promotion, demotion, absent_demotion, confidence, opposing, margin in product(
        promotion_values,
        demotion_values,
        absent_demotion_values,
        confidence_values,
        opposing_values,
        margin_values,
    ):
        if absent_demotion < demotion:
            continue
        candidates.append(
            GateCandidate(
                promotion_prior_threshold=promotion,
                demotion_prior_threshold=demotion,
                absent_demotion_prior_threshold=absent_demotion,
                min_retrieval_confidence=confidence,
                max_opposing_prior=opposing,
                gray_zone_margin=margin,
            )
        )
    if not candidates:
        raise ValueError("No valid gate candidates were generated")
    return tuple(candidates)


def _fused_statuses(frame: pd.DataFrame, candidate: GateCandidate) -> pd.Series:
    fused = frame["vision_status"].copy()
    gray_zone = (
        (frame["probability"] - frame["threshold"]).abs()
        <= candidate.gray_zone_margin
    )
    promote = (
        gray_zone
        & (frame["vision_status"] == ABSENT)
        & (
            frame["retrieval_present_prior"]
            >= candidate.promotion_prior_threshold
        )
        & (frame["retrieval_confidence"] >= candidate.min_retrieval_confidence)
        & (frame["retrieval_absent_prior"] <= candidate.max_opposing_prior)
    )
    demote = (
        gray_zone
        & (frame["vision_status"] == PRESENT)
        & (frame["retrieval_absent_prior"] >= candidate.demotion_prior_threshold)
        & (frame["retrieval_confidence"] >= candidate.min_retrieval_confidence)
        & (frame["retrieval_present_prior"] <= candidate.max_opposing_prior)
    )
    demote_to_absent = demote & (
        frame["retrieval_absent_prior"]
        >= candidate.absent_demotion_prior_threshold
    )

    fused.loc[promote] = PRESENT
    fused.loc[demote] = UNCERTAIN
    fused.loc[demote_to_absent] = ABSENT
    return fused


def _safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    return _safe_div(2.0 * precision * recall, precision + recall)


def _mean_present(values: Sequence[float | None]) -> float | None:
    present_values = [value for value in values if value is not None]
    if not present_values:
        return None
    return sum(present_values) / len(present_values)


def _score_predictions(
    frame: pd.DataFrame,
    fused_statuses: pd.Series,
    *,
    gray_zone_margin: float,
) -> dict[str, float | int | None]:
    full_metrics = _score_scope(frame, fused_statuses)
    gray_mask = (frame["probability"] - frame["threshold"]).abs() <= gray_zone_margin
    gray_metrics = _score_scope(frame.loc[gray_mask], fused_statuses.loc[gray_mask])
    return {
        "full_macro_precision": full_metrics["macro_precision"],
        "full_macro_recall": full_metrics["macro_recall"],
        "full_macro_f1": full_metrics["macro_f1"],
        "full_micro_precision": full_metrics["micro_precision"],
        "full_micro_recall": full_metrics["micro_recall"],
        "full_micro_f1": full_metrics["micro_f1"],
        "full_coverage": full_metrics["coverage"],
        "gray_macro_precision": gray_metrics["macro_precision"],
        "gray_macro_recall": gray_metrics["macro_recall"],
        "gray_macro_f1": gray_metrics["macro_f1"],
        "gray_micro_precision": gray_metrics["micro_precision"],
        "gray_micro_recall": gray_metrics["micro_recall"],
        "gray_micro_f1": gray_metrics["micro_f1"],
        "gray_coverage": gray_metrics["coverage"],
        "gray_zone_rows": int(gray_mask.sum()),
    }


def _score_scope(
    frame: pd.DataFrame,
    fused_statuses: pd.Series,
) -> dict[str, float | None]:
    per_label: list[dict[str, int | float | None]] = []
    for label in sorted(DISEASE_LABELS):
        label_frame = frame[frame["label"] == label]
        label_predictions = fused_statuses.loc[label_frame.index]
        gt = label_frame["gt_status"]

        gt_present = gt == PRESENT
        gt_absent = gt == ABSENT
        pred_present = label_predictions == PRESENT
        pred_absent = label_predictions == ABSENT
        pred_uncertain = label_predictions == UNCERTAIN

        tp = int((gt_present & pred_present).sum())
        fp = int((gt_absent & pred_present).sum())
        fn = int((gt_present & pred_absent).sum())
        tn = int((gt_absent & pred_absent).sum())
        miss_uncertain = int((gt_present & pred_uncertain).sum())
        scored = tp + fp + fn + tn + miss_uncertain
        total = int(len(label_frame))

        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn + miss_uncertain)
        per_label.append(
            {
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "miss_uncertain": miss_uncertain,
                "scored": scored,
                "total": total,
                "precision": precision,
                "recall": recall,
                "f1": _f1(precision, recall),
            }
        )

    tp = sum(int(item["tp"]) for item in per_label)
    fp = sum(int(item["fp"]) for item in per_label)
    fn = sum(int(item["fn"]) for item in per_label)
    miss_uncertain = sum(int(item["miss_uncertain"]) for item in per_label)
    scored = sum(int(item["scored"]) for item in per_label)
    total = sum(int(item["total"]) for item in per_label)
    micro_precision = _safe_div(tp, tp + fp)
    micro_recall = _safe_div(tp, tp + fn + miss_uncertain)

    return {
        "macro_precision": _mean_present([item["precision"] for item in per_label]),
        "macro_recall": _mean_present([item["recall"] for item in per_label]),
        "macro_f1": _mean_present([item["f1"] for item in per_label]),
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "micro_f1": _f1(micro_precision, micro_recall),
        "coverage": scored / total if total else 0.0,
    }


def _change_counts(
    frame: pd.DataFrame,
    fused_statuses: pd.Series,
) -> dict[str, int]:
    changed = fused_statuses != frame["vision_status"]
    promote = changed & (frame["vision_status"] == ABSENT) & (fused_statuses == PRESENT)
    demote = changed & (frame["vision_status"] == PRESENT)
    changed_frame = frame.loc[changed]
    return {
        "changed_cells": int(changed.sum()),
        "promotions": int(promote.sum()),
        "demotions": int(demote.sum()),
        "promotion_tp": int((promote & (frame["gt_status"] == PRESENT)).sum()),
        "promotion_fp": int((promote & (frame["gt_status"] == ABSENT)).sum()),
        "promotion_unscored": int(
            (promote & frame["gt_status"].isin({UNCERTAIN, UNMENTIONED})).sum()
        ),
        "demotion_tp": int((demote & (frame["gt_status"] == ABSENT)).sum()),
        "demotion_fp": int((demote & (frame["gt_status"] == PRESENT)).sum()),
        "demotion_unscored": int(
            (demote & frame["gt_status"].isin({UNCERTAIN, UNMENTIONED})).sum()
        ),
        "changed_scoreable_cells": int(
            changed_frame["gt_status"].isin({PRESENT, ABSENT}).sum()
        ),
    }


def _changed_cells_frame(
    frame: pd.DataFrame,
    fused_statuses: pd.Series,
) -> pd.DataFrame:
    changed = frame.loc[fused_statuses != frame["vision_status"]].copy()
    if changed.empty:
        return pd.DataFrame(
            columns=[
                "study_key",
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
        )

    changed["tuned_fused_status"] = fused_statuses.loc[changed.index]
    changed["change_type"] = "other"
    changed.loc[
        (changed["vision_status"] == ABSENT)
        & (changed["tuned_fused_status"] == PRESENT),
        "change_type",
    ] = "promotion"
    changed.loc[
        (changed["vision_status"] == PRESENT)
        & changed["tuned_fused_status"].isin({ABSENT, UNCERTAIN}),
        "change_type",
    ] = "demotion"

    columns = [
        "study_key",
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
    return changed[columns].sort_values(["label", "study_key"])


def _row_for_candidate(
    frame: pd.DataFrame,
    candidate: GateCandidate,
) -> dict[str, float | int | None]:
    fused_statuses = _fused_statuses(frame, candidate)
    return {
        **asdict(candidate),
        **_score_predictions(
            frame,
            fused_statuses,
            gray_zone_margin=candidate.gray_zone_margin,
        ),
        **_change_counts(frame, fused_statuses),
    }


def _best_row(results: pd.DataFrame, *, objective: str) -> pd.Series:
    sort_columns = [
        objective,
        "full_macro_f1",
        "gray_macro_f1",
        "full_micro_f1",
        "gray_micro_f1",
        "changed_scoreable_cells",
        "changed_cells",
    ]
    ascending = [False, False, False, False, False, False, True]
    return results.sort_values(sort_columns, ascending=ascending).iloc[0]


def _policy_payload(
    *,
    best: pd.Series,
    args: argparse.Namespace,
    run_config: dict[str, Any],
) -> dict[str, Any]:
    gate_keys = tuple(GateCandidate.__dataclass_fields__)
    gates = {key: float(best[key]) for key in gate_keys}
    return {
        "policy_version": TUNING_POLICY_VERSION,
        "base_fusion_policy_version": PRIOR_FUSION_POLICY_VERSION,
        "scope": "global",
        "tuned_on": "validation",
        "objective": args.objective,
        "global_gates": gates,
        "selected_metrics": {
            "full_macro_f1": float(best["full_macro_f1"]),
            "full_micro_f1": float(best["full_micro_f1"]),
            "gray_macro_f1": float(best["gray_macro_f1"]),
            "gray_micro_f1": float(best["gray_micro_f1"]),
            "changed_cells": int(best["changed_cells"]),
            "promotions": int(best["promotions"]),
            "demotions": int(best["demotions"]),
            "promotion_tp": int(best["promotion_tp"]),
            "promotion_fp": int(best["promotion_fp"]),
            "demotion_tp": int(best["demotion_tp"]),
            "demotion_fp": int(best["demotion_fp"]),
        },
        "run_config": run_config,
    }


def main(argv: list[str] | None = None) -> int:
    """Tune global prior-fusion gates and write audit artifacts."""
    args = build_parser().parse_args(argv)
    if args.top_n <= 0:
        raise ValueError("--top-n must be > 0")

    _require_existing_paths(
        {
            "features_csv": args.features_csv,
            "study_labels_csv": args.study_labels_csv,
        }
    )
    _prepare_output_dir(args.output_dir, overwrite=args.overwrite)

    start = time.perf_counter()
    features = _load_feature_frame(args.features_csv)
    ground_truth = _load_ground_truth_long(
        args.study_labels_csv,
        study_keys=features["study_key"].unique(),
    )
    frame = _attach_ground_truth(features, ground_truth)
    candidates = _iter_candidates(args)

    print(
        "[PriorFusionGateTuning] "
        f"features={len(frame)} studies={frame['study_key'].nunique()} "
        f"candidates={len(candidates)} objective={args.objective}"
    )

    rows: list[dict[str, float | int | None]] = []
    for index, candidate in enumerate(candidates, start=1):
        rows.append(_row_for_candidate(frame, candidate))
        if index == 1 or index % 250 == 0 or index == len(candidates):
            print(f"[PriorFusionGateTuning] scored {index}/{len(candidates)}")

    results = pd.DataFrame(rows)
    best = _best_row(results, objective=args.objective)
    sorted_results = results.sort_values(
        [args.objective, "full_macro_f1", "changed_cells"],
        ascending=[False, False, True],
    )

    run_config = {
        "experiment": args.output_dir.name,
        "policy_version": TUNING_POLICY_VERSION,
        "base_fusion_policy_version": PRIOR_FUSION_POLICY_VERSION,
        "cohort_root": DEFAULT_BALANCED_COHORT_ROOT,
        "features_csv": str(args.features_csv),
        "study_labels_csv": str(args.study_labels_csv),
        "objective": args.objective,
        "candidate_count": len(candidates),
        "study_count": int(frame["study_key"].nunique()),
        "feature_rows": len(frame),
        "elapsed_seconds": time.perf_counter() - start,
    }

    sorted_results.to_csv(args.output_dir / "global_gate_grid_results.csv", index=False)
    best_fused_statuses = _fused_statuses(
        frame,
        GateCandidate(
            promotion_prior_threshold=float(best["promotion_prior_threshold"]),
            demotion_prior_threshold=float(best["demotion_prior_threshold"]),
            absent_demotion_prior_threshold=float(
                best["absent_demotion_prior_threshold"]
            ),
            min_retrieval_confidence=float(best["min_retrieval_confidence"]),
            max_opposing_prior=float(best["max_opposing_prior"]),
            gray_zone_margin=float(best["gray_zone_margin"]),
        ),
    )
    _changed_cells_frame(frame, best_fused_statuses).to_csv(
        args.output_dir / "best_changed_cells.csv",
        index=False,
    )
    _write_json(args.output_dir / "run_config.json", run_config)
    _write_json(
        args.output_dir / "best_prior_fusion_policy.json",
        _policy_payload(best=best, args=args, run_config=run_config),
    )

    print(f"[PriorFusionGateTuning] wrote outputs -> {args.output_dir}")
    print("[PriorFusionGateTuning] best global gates:")
    for key in GateCandidate.__dataclass_fields__:
        print(f"  {key}={float(best[key]):.4f}")
    print(
        "[PriorFusionGateTuning] best metrics: "
        f"gray_macro_f1={float(best['gray_macro_f1']):.4f} "
        f"full_macro_f1={float(best['full_macro_f1']):.4f} "
        f"changed_cells={int(best['changed_cells'])}"
    )
    print("[PriorFusionGateTuning] top rows:")
    print(sorted_results.head(args.top_n).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
