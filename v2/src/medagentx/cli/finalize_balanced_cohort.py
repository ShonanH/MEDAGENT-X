"""Finalize labels, splits, and target audits after DICOM quality filtering."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.data.balanced_constants import (
    BALANCED_COHORT_POLICY_VERSION,
    BALANCED_EVAL_MODE,
    DEFAULT_BALANCED_COHORT_ROOT,
    NEGATIVE_TO_POSITIVE_RATIO,
    POST_QUALITY_POSITIVE_TARGETS,
)
from medagentx.data.balanced_select import (
    build_label_count_audit,
    build_patient_label_features,
)
from medagentx.data.cohort import load_findings_for_cohort
from medagentx.labels.study_table import build_study_label_table
from medagentx.splits.build import (
    build_and_write_splits,
    build_patient_split_table,
)
from medagentx.splits.constants import SPLIT_SEED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Finalize the label-enriched cohort after the quality gate and "
            "audit the locked 200/50/50 positive targets."
        )
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path(DEFAULT_BALANCED_COHORT_ROOT),
    )
    parser.add_argument(
        "--quality-eligible-csv",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--train-positive-target",
        type=int,
        default=POST_QUALITY_POSITIVE_TARGETS["train"],
    )
    parser.add_argument(
        "--val-positive-target",
        type=int,
        default=POST_QUALITY_POSITIVE_TARGETS["val"],
    )
    parser.add_argument(
        "--test-positive-target",
        type=int,
        default=POST_QUALITY_POSITIVE_TARGETS["test"],
    )
    parser.add_argument(
        "--negative-ratio",
        type=int,
        default=NEGATIVE_TO_POSITIVE_RATIO,
    )
    return parser


def _verify_split_stability(
    cohort_root: Path,
    final_splits: pd.DataFrame,
) -> None:
    pre_quality_path = (
        cohort_root / "selection" / "patient_splits_pre_quality.csv"
    )
    if not pre_quality_path.exists():
        return
    pre_quality = pd.read_csv(pre_quality_path, dtype=str)
    expected = pre_quality[["deid_patient_id", "split"]].copy()
    expected = expected.rename(columns={"split": "expected_split"})
    actual = final_splits[["deid_patient_id", "split"]].copy()
    merged = actual.merge(
        expected,
        on="deid_patient_id",
        how="left",
        validate="one_to_one",
    )
    if merged["expected_split"].isna().any():
        raise ValueError("Quality cohort contains a patient absent from selection")
    moved = merged[merged["split"] != merged["expected_split"]]
    if not moved.empty:
        raise ValueError(
            "Patient split assignment changed after quality filtering: "
            f"{moved['deid_patient_id'].tolist()[:10]}"
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cohort_root: Path = args.cohort_root
    quality_csv = args.quality_eligible_csv or (
        cohort_root / "quality" / "eligible_dicom_rows.csv"
    )
    findings_path = (
        cohort_root / "chexpert_labels" / "findings_fixed.json"
    )
    if not quality_csv.exists():
        raise FileNotFoundError(
            f"Quality-passed cohort not found: {quality_csv}. "
            "Run medagentx.cli.run_quality_gate first."
        )
    if not findings_path.exists():
        raise FileNotFoundError(f"Findings asset not found: {findings_path}")

    print(f"[Balanced Finalize] Loading quality cohort -> {quality_csv}")
    quality_rows = pd.read_csv(quality_csv, dtype=str)
    if quality_rows.empty:
        raise ValueError("Quality-passed cohort must be non-empty")
    findings_index = load_findings_for_cohort(findings_path, quality_rows)
    study_labels = build_study_label_table(quality_rows, findings_index)
    labels_path = cohort_root / "study_label_table.csv"
    study_labels.to_csv(labels_path, index=False)

    patient_splits = build_patient_split_table(
        quality_rows,
        seed=SPLIT_SEED,
    )
    _verify_split_stability(cohort_root, patient_splits)
    split_paths = build_and_write_splits(
        quality_rows,
        cohort_root / "splits",
        seed=SPLIT_SEED,
    )

    features = build_patient_label_features(study_labels, patient_splits)
    targets = {
        "train": args.train_positive_target,
        "val": args.val_positive_target,
        "test": args.test_positive_target,
    }
    audit = build_label_count_audit(
        features,
        positive_targets=targets,
        negative_ratio=args.negative_ratio,
        stage="post_quality_final",
    )
    selection_root = cohort_root / "selection"
    selection_root.mkdir(parents=True, exist_ok=True)
    audit_path = selection_root / "post_quality_label_audit.csv"
    audit.to_csv(audit_path, index=False)

    shortages = audit[~audit["target_met"].astype(bool)]
    metadata_path = cohort_root / "cohort_meta.json"
    metadata: dict[str, object] = {}
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "policy_version": BALANCED_COHORT_POLICY_VERSION,
            "eval_mode": BALANCED_EVAL_MODE,
            "post_quality_positive_targets": targets,
            "quality_patients": int(
                quality_rows["deid_patient_id"].astype(str).nunique()
            ),
            "quality_studies": int(
                quality_rows["study_key"].astype(str).nunique()
            ),
            "quality_views": int(len(quality_rows)),
            "post_quality_shortage_rows": int(len(shortages)),
            "post_quality_targets_met": bool(shortages.empty),
        }
    )
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(
        f"[Balanced Finalize] studies={len(study_labels)} "
        f"shortages={len(shortages)}"
    )
    print(f"[Balanced Finalize] Labels -> {labels_path}")
    print(f"[Balanced Finalize] Audit -> {audit_path}")
    print(f"[Balanced Finalize] Splits -> {split_paths['summary']}")
    if not shortages.empty:
        print(
            "[Balanced Finalize] Targets not met after quality filtering; "
            "continuing as locked. See the shortage audit."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
