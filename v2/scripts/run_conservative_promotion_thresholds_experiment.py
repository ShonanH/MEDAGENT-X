"""Run validation-only conservative promotion threshold variants.

This script does not rerun vision or retrieval. It simulates stricter
absent-to-present promotion thresholds from saved validation fusion outputs.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd

_V2_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.evaluation.fusion_eval import (  # noqa: E402
    named_judge_summary_payload,
    run_named_judge_result,
    study_labels_to_ground_truth,
)
from medagentx.labels.constants import DISEASE_LABELS  # noqa: E402
from medagentx.labels.statuses import LabelStatus  # noqa: E402


SOURCE_DIR = Path("v2/artifactsLocal/val_last4_blocks_0818/val")
OUTPUT_DIR = Path(
    "v2/artifactsLocal/fusion-rule-tuning-2026-08-18/"
    "conservative-promotion-thresholds/val"
)

VARIANT_BASELINE = "baseline"
VARIANT_GLOBAL_4 = "global-positive-threshold-4"
VARIANT_GLOBAL_5 = "global-positive-threshold-5"
VARIANT_LABEL_SPECIFIC = "label-specific-conservative"

VARIANT_ORDER = (
    VARIANT_BASELINE,
    VARIANT_GLOBAL_4,
    VARIANT_GLOBAL_5,
    VARIANT_LABEL_SPECIFIC,
)

DEFAULT_PROMOTION_THRESHOLD = 3
LABEL_SPECIFIC_THRESHOLDS: dict[str, int] = {
    "Atelectasis": 4,
    "Cardiomegaly": 4,
    "Consolidation": 4,
    "Edema": 4,
    "Enlarged Cardiomediastinum": 3,
    "Fracture": 3,
    "Lung Lesion": 3,
    "Lung Opacity": 4,
    "Pleural Effusion": 5,
    "Pleural Other": 3,
    "Pneumonia": 3,
    "Pneumothorax": 5,
}

FULL_F1_DROP_TOLERANCE = 0.005
GRAY_F1_DROP_TOLERANCE = 0.005
PRECISION_DROP_TOLERANCE = 0.005


@dataclass(frozen=True)
class VariantDefinition:
    """One conservative promotion variant."""

    name: str
    promotion_thresholds: Mapping[str, int] | None = None
    global_promotion_threshold: int | None = None


VARIANTS = (
    VariantDefinition(name=VARIANT_BASELINE),
    VariantDefinition(name=VARIANT_GLOBAL_4, global_promotion_threshold=4),
    VariantDefinition(name=VARIANT_GLOBAL_5, global_promotion_threshold=5),
    VariantDefinition(
        name=VARIANT_LABEL_SPECIFIC,
        promotion_thresholds=LABEL_SPECIFIC_THRESHOLDS,
    ),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Simulate conservative absent-to-present promotion thresholds on "
            "saved last-4 validation fusion outputs."
        )
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=SOURCE_DIR,
        help="Folder containing validation fusion outputs and study-label table.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Hyphenated experiment output folder.",
    )
    return parser


def _required_file(source_dir: Path, name: str) -> Path:
    path = source_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")
    return path


def _normalize_status(value: object) -> str:
    return str(value).strip().lower()


def _parse_status(value: object) -> LabelStatus:
    return LabelStatus(_normalize_status(value))


def _status_map(frame: pd.DataFrame, column: str) -> dict[tuple[str, str], LabelStatus]:
    return {
        (str(row.study_key), str(row.label)): _parse_status(getattr(row, column))
        for row in frame.itertuples(index=False)
    }


def _gray_zone_ground_truth(
    ground_truth_records: list,
    prediction_frame: pd.DataFrame,
) -> list:
    gray_keys = {
        (str(row.study_key), str(row.label))
        for row in prediction_frame[
            prediction_frame["in_gray_zone"].astype(bool)
        ].itertuples(index=False)
    }
    return [
        record
        for record in ground_truth_records
        if (record.study_key, record.label) in gray_keys
    ]


def _promotion_threshold_for_row(
    row: object,
    variant: VariantDefinition,
) -> int:
    if variant.global_promotion_threshold is not None:
        return variant.global_promotion_threshold
    if variant.promotion_thresholds is not None:
        return int(
            variant.promotion_thresholds.get(
                str(row.label),
                DEFAULT_PROMOTION_THRESHOLD,
            )
        )
    return DEFAULT_PROMOTION_THRESHOLD


def apply_variant(
    predictions: pd.DataFrame,
    variant: VariantDefinition,
) -> pd.DataFrame:
    """Return predictions with a simulated variant status column."""
    frame = predictions.copy()
    frame["variant"] = variant.name
    frame["variant_status"] = frame["fused_status"].map(_normalize_status)

    if variant.name == VARIANT_BASELINE:
        return frame

    def should_revert(row: object) -> bool:
        is_current_promotion = (
            _normalize_status(row.vision_status) == LabelStatus.ABSENT.value
            and _normalize_status(row.fused_status) == LabelStatus.PRESENT.value
        )
        if not is_current_promotion:
            return False
        threshold = _promotion_threshold_for_row(row, variant)
        return int(row.positive_count) < threshold

    revert_mask = frame.apply(should_revert, axis=1)
    frame.loc[revert_mask, "variant_status"] = frame.loc[
        revert_mask,
        "vision_status",
    ].map(_normalize_status)
    return frame


def _summary_from_run(run) -> dict[str, object]:
    payload = named_judge_summary_payload(run)
    return {
        "macro-precision": payload.get("macro_precision"),
        "macro-recall": payload.get("macro_recall"),
        "macro-f1": payload.get("macro_f1"),
        "micro-precision": payload.get("micro_precision"),
        "micro-recall": payload.get("micro_recall"),
        "micro-f1": payload.get("micro_f1"),
        "coverage": payload.get("coverage"),
        "match-count": payload.get("match_count"),
        "label-count": payload.get("label_count"),
    }


def judge_variant(
    frame: pd.DataFrame,
    *,
    variant_name: str,
    ground_truth_records: list,
    gray_zone_records: list,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    predictions = _status_map(frame, "variant_status")
    full_run = run_named_judge_result(
        name=f"{variant_name}-full",
        eval_scope="full",
        ground_truth_records=ground_truth_records,
        predicted_statuses=predictions,
    )
    gray_run = run_named_judge_result(
        name=f"{variant_name}-gray-zone",
        eval_scope="gray-zone",
        ground_truth_records=gray_zone_records,
        predicted_statuses=predictions,
    )

    summary_rows = []
    for scope, run in (("full", full_run), ("gray-zone", gray_run)):
        summary = _summary_from_run(run)
        summary_rows.append(
            {
                "variant": variant_name,
                "eval-scope": scope,
                **summary,
            }
        )

    per_label_rows: list[dict[str, object]] = []
    for scope, run in (("full", full_run), ("gray-zone", gray_run)):
        if run.result is None:
            continue
        for metrics in run.result.per_label_metrics:
            scoreable_cells = metrics.gt_present + metrics.gt_absent
            per_label_rows.append(
                {
                    "variant": variant_name,
                    "eval-scope": scope,
                    "label": metrics.label,
                    "scoreable-cells": scoreable_cells,
                    "gt-present": metrics.gt_present,
                    "gt-absent": metrics.gt_absent,
                    "pred-present": metrics.pred_present,
                    "pred-absent": metrics.pred_absent,
                    "tp": metrics.tp,
                    "tn": metrics.tn,
                    "fp": metrics.fp,
                    "fn": metrics.fn,
                    "precision": metrics.precision,
                    "recall": metrics.recall,
                    "f1": metrics.f1,
                    "specificity": metrics.specificity,
                }
            )
    return summary_rows, per_label_rows


def _ground_truth_map(study_labels: pd.DataFrame) -> dict[tuple[str, str], str]:
    rows: dict[tuple[str, str], str] = {}
    labels = study_labels.copy()
    labels["study_key"] = labels["study_key"].astype(str)
    for row in labels.itertuples(index=False):
        study_key = str(row.study_key)
        for label in DISEASE_LABELS:
            status_column = f"status_{label.lower().replace(' ', '_')}"
            rows[(study_key, label)] = _normalize_status(getattr(row, status_column))
    return rows


def _score_promotion_cells(
    frame: pd.DataFrame,
    mask: pd.Series,
) -> dict[str, int]:
    statuses = frame.loc[mask, "ground-truth-status"].map(_normalize_status)
    return {
        "promotion-tp": int((statuses == LabelStatus.PRESENT.value).sum()),
        "promotion-fp": int((statuses == LabelStatus.ABSENT.value).sum()),
        "promotion-unscored": int(
            (~statuses.isin([LabelStatus.PRESENT.value, LabelStatus.ABSENT.value])).sum()
        ),
    }


def changed_cell_summary(frame: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    labels = ["all", *DISEASE_LABELS]
    for label in labels:
        subset = frame if label == "all" else frame[frame["label"].eq(label)]
        current_promotion = (
            subset["vision_status"].map(_normalize_status).eq(LabelStatus.ABSENT.value)
            & subset["fused_status"].map(_normalize_status).eq(LabelStatus.PRESENT.value)
        )
        variant_changed = (
            subset["vision_status"].map(_normalize_status)
            != subset["variant_status"].map(_normalize_status)
        )
        variant_promotion = (
            subset["vision_status"].map(_normalize_status).eq(LabelStatus.ABSENT.value)
            & subset["variant_status"].map(_normalize_status).eq(LabelStatus.PRESENT.value)
        )
        variant_demotion = (
            subset["vision_status"].map(_normalize_status).eq(LabelStatus.PRESENT.value)
            & ~subset["variant_status"].map(_normalize_status).eq(LabelStatus.PRESENT.value)
        )
        kept_promotion = current_promotion & variant_promotion
        reverted_promotion = current_promotion & ~variant_promotion

        kept_scores = _score_promotion_cells(subset, kept_promotion)
        reverted_scores = _score_promotion_cells(subset, reverted_promotion)

        rows.append(
            {
                "variant": str(subset["variant"].iloc[0]) if not subset.empty else "",
                "label": label,
                "total-cells": int(len(subset)),
                "gray-zone-cells": int(subset["in_gray_zone"].astype(bool).sum()),
                "changed-cells": int(variant_changed.sum()),
                "promotions-kept": int(kept_promotion.sum()),
                "promotions-reverted": int(reverted_promotion.sum()),
                "variant-promotions": int(variant_promotion.sum()),
                "variant-demotions": int(variant_demotion.sum()),
                "kept-promotion-tp": kept_scores["promotion-tp"],
                "kept-promotion-fp": kept_scores["promotion-fp"],
                "kept-promotion-unscored": kept_scores["promotion-unscored"],
                "reverted-promotion-tp": reverted_scores["promotion-tp"],
                "reverted-promotion-fp": reverted_scores["promotion-fp"],
                "reverted-promotion-unscored": reverted_scores["promotion-unscored"],
            }
        )
    return rows


def add_summary_deltas(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary.copy()
    baseline = frame[frame["variant"].eq(VARIANT_BASELINE)].set_index("eval-scope")
    for metric in (
        "macro-precision",
        "macro-recall",
        "macro-f1",
        "micro-precision",
        "micro-recall",
        "micro-f1",
    ):
        frame[f"{metric}-delta-vs-baseline"] = frame.apply(
            lambda row: row[metric] - baseline.loc[row["eval-scope"], metric],
            axis=1,
        )
    return frame


def add_per_label_deltas(per_label: pd.DataFrame) -> pd.DataFrame:
    frame = per_label.copy()
    baseline = frame[frame["variant"].eq(VARIANT_BASELINE)][
        ["eval-scope", "label", "precision", "recall", "f1"]
    ].rename(
        columns={
            "precision": "baseline-precision",
            "recall": "baseline-recall",
            "f1": "baseline-f1",
        }
    )
    frame = frame.merge(
        baseline,
        on=["eval-scope", "label"],
        how="left",
        validate="many_to_one",
    )
    frame["precision-delta-vs-baseline"] = (
        frame["precision"] - frame["baseline-precision"]
    )
    frame["recall-delta-vs-baseline"] = frame["recall"] - frame["baseline-recall"]
    frame["f1-delta-vs-baseline"] = frame["f1"] - frame["baseline-f1"]
    return frame


def select_variant(summary: pd.DataFrame, changed: pd.DataFrame) -> str:
    baseline_full = summary[
        summary["variant"].eq(VARIANT_BASELINE) & summary["eval-scope"].eq("full")
    ].iloc[0]
    baseline_gray = summary[
        summary["variant"].eq(VARIANT_BASELINE) & summary["eval-scope"].eq("gray-zone")
    ].iloc[0]

    full = summary[summary["eval-scope"].eq("full")].copy()
    gray = summary[summary["eval-scope"].eq("gray-zone")].copy()
    candidates = full.merge(
        gray,
        on="variant",
        suffixes=("-full", "-gray-zone"),
        validate="one_to_one",
    )
    all_changed = changed[changed["label"].eq("all")][
        ["variant", "kept-promotion-fp", "promotions-reverted"]
    ]
    candidates = candidates.merge(all_changed, on="variant", how="left")

    eligible = candidates[
        (
            candidates["macro-f1-full"]
            >= float(baseline_full["macro-f1"]) - FULL_F1_DROP_TOLERANCE
        )
        & (
            candidates["macro-f1-gray-zone"]
            >= float(baseline_gray["macro-f1"]) - GRAY_F1_DROP_TOLERANCE
        )
        & (
            candidates["macro-precision-full"]
            >= float(baseline_full["macro-precision"]) - PRECISION_DROP_TOLERANCE
        )
    ].copy()
    if eligible.empty:
        return VARIANT_BASELINE

    eligible = eligible.sort_values(
        [
            "kept-promotion-fp",
            "macro-f1-gray-zone",
            "macro-f1-full",
            "promotions-reverted",
        ],
        ascending=[True, False, False, True],
        kind="stable",
    )
    return str(eligible.iloc[0]["variant"])


def policy_for_variant(variant_name: str) -> dict[str, object]:
    if variant_name == VARIANT_BASELINE:
        thresholds = {label: DEFAULT_PROMOTION_THRESHOLD for label in DISEASE_LABELS}
    elif variant_name == VARIANT_GLOBAL_4:
        thresholds = {label: 4 for label in DISEASE_LABELS}
    elif variant_name == VARIANT_GLOBAL_5:
        thresholds = {label: 5 for label in DISEASE_LABELS}
    elif variant_name == VARIANT_LABEL_SPECIFIC:
        thresholds = dict(LABEL_SPECIFIC_THRESHOLDS)
    else:
        raise ValueError(f"Unknown variant: {variant_name}")

    return {
        "selected-variant": variant_name,
        "promotion-thresholds-by-label": thresholds,
        "demotion-policy": "unchanged-from-deterministic-gray-zone-fusion-v2",
        "gray-zone-margin": 0.15,
        "retrieval-top-k": 10,
        "selection-criteria": {
            "full-macro-f1-drop-tolerance": FULL_F1_DROP_TOLERANCE,
            "gray-zone-macro-f1-drop-tolerance": GRAY_F1_DROP_TOLERANCE,
            "full-macro-precision-drop-tolerance": PRECISION_DROP_TOLERANCE,
            "sort-order": [
                "fewest-kept-promotion-fp",
                "highest-gray-zone-macro-f1",
                "highest-full-macro-f1",
                "fewest-promotions-reverted",
            ],
        },
    }


def write_notes(
    path: Path,
    *,
    source_dir: Path,
    selected_variant: str,
) -> None:
    path.write_text(
        "\n".join(
            [
                "# Conservative Promotion Thresholds",
                "",
                "This validation-only experiment simulates stricter absent-to-present "
                "promotion thresholds from saved last-4 fusion outputs.",
                "",
                f"Source: `{source_dir}`",
                f"Selected variant: `{selected_variant}`",
                "",
                "Variants:",
                "",
                "- `baseline`: existing fused statuses.",
                "- `global-positive-threshold-4`: revert current promotions with fewer than 4 positive mentions.",
                "- `global-positive-threshold-5`: revert current promotions with fewer than 5 positive mentions.",
                "- `label-specific-conservative`: use label-specific thresholds from `selected-policy.json`.",
                "",
                "Demotions are intentionally unchanged in this experiment.",
                "Strong-zone predictions are unchanged because only current promotions are eligible for reversion.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_dir = args.source_dir
    output_dir = args.output_dir

    predictions = pd.read_csv(
        _required_file(source_dir, "fusion_label_predictions.csv"),
        dtype={"study_key": str, "label": str},
    )
    study_labels = pd.read_csv(
        _required_file(source_dir, "study_label_table.csv"),
        dtype={"study_key": str},
    )
    study_keys = sorted(predictions["study_key"].astype(str).unique())
    ground_truth_records = study_labels_to_ground_truth(
        study_labels,
        study_keys=study_keys,
    )

    label_gt = _ground_truth_map(study_labels)
    predictions["ground-truth-status"] = [
        label_gt.get((str(row.study_key), str(row.label)), "missing")
        for row in predictions.itertuples(index=False)
    ]

    gray_zone_records = _gray_zone_ground_truth(ground_truth_records, predictions)

    variant_frames = [apply_variant(predictions, variant) for variant in VARIANTS]

    summary_rows: list[dict[str, object]] = []
    per_label_rows: list[dict[str, object]] = []
    changed_rows: list[dict[str, object]] = []

    for frame in variant_frames:
        variant_name = str(frame["variant"].iloc[0])
        variant_summary, variant_per_label = judge_variant(
            frame,
            variant_name=variant_name,
            ground_truth_records=ground_truth_records,
            gray_zone_records=gray_zone_records,
        )
        summary_rows.extend(variant_summary)
        per_label_rows.extend(variant_per_label)
        changed_rows.extend(changed_cell_summary(frame))

    summary = add_summary_deltas(pd.DataFrame(summary_rows))
    per_label = add_per_label_deltas(pd.DataFrame(per_label_rows))
    changed = pd.DataFrame(changed_rows)
    selected_variant = select_variant(summary, changed)
    policy = {
        "experiment": "conservative-promotion-thresholds",
        "source-dir": str(source_dir),
        "output-dir": str(output_dir),
        **policy_for_variant(selected_variant),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_dir / "variant-summary.csv", index=False)
    per_label.to_csv(output_dir / "per-label-summary.csv", index=False)
    changed.to_csv(output_dir / "changed-cell-summary.csv", index=False)
    (output_dir / "selected-policy.json").write_text(
        json.dumps(policy, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_notes(
        output_dir / "experiment-notes.md",
        source_dir=source_dir,
        selected_variant=selected_variant,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
