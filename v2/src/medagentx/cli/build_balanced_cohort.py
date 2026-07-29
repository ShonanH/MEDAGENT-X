"""Build and download the locked label-enriched patient cohort."""

from __future__ import annotations

import argparse
import json
import os
import shutil
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
    DEFAULT_REUSE_DICOM_ROOT,
    NEGATIVE_TO_POSITIVE_RATIO,
    POST_QUALITY_POSITIVE_TARGETS,
    PRE_QUALITY_POSITIVE_TARGETS,
    SOFT_PATIENT_CAP,
)
from medagentx.data.balanced_select import (
    EnrichedCohortSelection,
    select_enriched_cohort,
)
from medagentx.data.cohort import (
    apply_label_gated_cohort,
    load_findings_for_cohort,
    summarize_label_gated_cohort,
)
from medagentx.data.dicoms import (
    download_eligible_dicoms,
    reuse_existing_dicoms,
    summarize_download_status,
)
from medagentx.data.findings import ensure_findings_fixed_json
from medagentx.data.redivis_client import RedivisClient
from medagentx.data.rows import (
    DEFAULT_INDEX_PAGE_SIZE,
    DEFAULT_METADATA_PAGE_SIZE,
    DEFAULT_REPORT_BATCH_SIZE,
    attach_report_columns,
    fetch_eligible_dicom_rows,
)
from medagentx.labels.study_table import build_study_label_table
from medagentx.splits.constants import SPLIT_SEED

_REUSED_STATUSES = frozenset(
    {"already_exists", "reused_hardlink", "reused_copy"}
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Select whole patients inside deterministic split buckets to meet "
            "buffered CheXpert positive targets, then reuse/download DICOMs."
        )
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(DEFAULT_BALANCED_COHORT_ROOT),
    )
    parser.add_argument(
        "--source-findings-json",
        type=Path,
        default=Path(
            "v2/artifacts/cohort/chexpert_labels/findings_fixed.json"
        ),
        help="Reuse this local findings asset when present.",
    )
    parser.add_argument(
        "--reuse-dicom-root",
        type=Path,
        default=Path(DEFAULT_REUSE_DICOM_ROOT),
        help="Earlier DICOM root used for hardlink/copy reuse.",
    )
    parser.add_argument(
        "--patient-cap",
        type=int,
        default=SOFT_PATIENT_CAP,
    )
    parser.add_argument(
        "--train-positive-target",
        type=int,
        default=PRE_QUALITY_POSITIVE_TARGETS["train"],
    )
    parser.add_argument(
        "--val-positive-target",
        type=int,
        default=PRE_QUALITY_POSITIVE_TARGETS["val"],
    )
    parser.add_argument(
        "--test-positive-target",
        type=int,
        default=PRE_QUALITY_POSITIVE_TARGETS["test"],
    )
    parser.add_argument(
        "--negative-ratio",
        type=int,
        default=NEGATIVE_TO_POSITIVE_RATIO,
    )
    parser.add_argument("--metadata-limit", type=int, default=None)
    parser.add_argument("--index-limit", type=int, default=None)
    parser.add_argument(
        "--metadata-page-size",
        type=int,
        default=DEFAULT_METADATA_PAGE_SIZE,
    )
    parser.add_argument(
        "--index-page-size",
        type=int,
        default=DEFAULT_INDEX_PAGE_SIZE,
    )
    parser.add_argument(
        "--report-batch-size",
        type=int,
        default=DEFAULT_REPORT_BATCH_SIZE,
    )
    parser.add_argument("--skip-reports", action="store_true")
    parser.add_argument("--skip-dicom-download", action="store_true")
    parser.add_argument("--overwrite-dicoms", action="store_true")
    parser.add_argument("--overwrite-findings", action="store_true")
    return parser


def _materialize_findings(
    client: RedivisClient,
    *,
    source: Path,
    destination: Path,
    overwrite: bool,
) -> Path:
    if destination.exists() and not overwrite:
        return destination
    if source.exists() and source.resolve() != destination.resolve():
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            destination.unlink()
        try:
            os.link(source, destination)
        except OSError:
            shutil.copy2(source, destination)
        return destination
    return ensure_findings_fixed_json(
        client,
        destination,
        overwrite=overwrite,
    )


def _write_selection_artifacts(
    output_root: Path,
    *,
    selection: EnrichedCohortSelection,
    pool_labels: pd.DataFrame,
) -> None:
    selection_root = output_root / "selection"
    selection_root.mkdir(parents=True, exist_ok=True)
    selection.patient_selection.to_csv(
        selection_root / "patient_selection.csv",
        index=False,
    )
    selection.reserve_patients.to_csv(
        selection_root / "reserve_patients.csv",
        index=False,
    )
    selection.label_audit.to_csv(
        selection_root / "pre_quality_label_audit.csv",
        index=False,
    )
    selection.patient_splits.to_csv(
        selection_root / "patient_splits_pre_quality.csv",
        index=False,
    )
    selected_studies = set(
        selection.eligible_rows["study_key"].astype(str)
    )
    pool_labels[
        pool_labels["study_key"].astype(str).isin(selected_studies)
    ].to_csv(
        output_root / "study_label_table_pre_quality.csv",
        index=False,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root: Path = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    client = RedivisClient.from_env()

    print("[Balanced Cohort] Fetching the full downloadable train pool...")
    candidate_rows = fetch_eligible_dicom_rows(
        client,
        metadata_limit=args.metadata_limit,
        index_limit=args.index_limit,
        max_patients=None,
        max_studies=None,
        max_rows=None,
        metadata_page_size=args.metadata_page_size,
        index_page_size=args.index_page_size,
        include_reports=False,
    )
    candidate_csv = output_root / "candidate_dicom_rows.csv"
    candidate_rows.to_csv(candidate_csv, index=False)
    print(
        f"[Balanced Cohort] Candidate views={len(candidate_rows)} -> "
        f"{candidate_csv}"
    )

    findings_path = _materialize_findings(
        client,
        source=args.source_findings_json,
        destination=(
            output_root / "chexpert_labels" / "findings_fixed.json"
        ),
        overwrite=args.overwrite_findings,
    )
    print(f"[Balanced Cohort] Findings asset -> {findings_path}")

    print("[Balanced Cohort] Applying the locked study label gate...")
    findings_index = load_findings_for_cohort(
        findings_path,
        candidate_rows,
    )
    label_eligible, dropped = apply_label_gated_cohort(
        candidate_rows,
        findings_index,
    )
    dropped.to_csv(output_root / "pool_dropped_studies.csv", index=False)
    dropped.to_csv(output_root / "dropped_studies.csv", index=False)
    print(
        "[Balanced Cohort] Pool label gate: "
        f"{summarize_label_gated_cohort(candidate_rows, label_eligible, dropped)}"
    )

    print("[Balanced Cohort] Building study labels for cohort selection...")
    pool_labels = build_study_label_table(
        label_eligible,
        findings_index,
    )
    pool_labels.to_csv(
        output_root / "study_label_table_pool.csv",
        index=False,
    )

    targets = {
        "train": args.train_positive_target,
        "val": args.val_positive_target,
        "test": args.test_positive_target,
    }
    selection = select_enriched_cohort(
        label_eligible,
        pool_labels,
        positive_targets=targets,
        negative_ratio=args.negative_ratio,
        patient_cap=args.patient_cap,
        seed=SPLIT_SEED,
    )
    _write_selection_artifacts(
        output_root,
        selection=selection,
        pool_labels=pool_labels,
    )
    pd.DataFrame(
        [
            {
                "candidate_patients": int(
                    candidate_rows["deid_patient_id"].astype(str).nunique()
                ),
                "candidate_studies": int(
                    candidate_rows["study_key"].astype(str).nunique()
                ),
                "candidate_views": int(len(candidate_rows)),
                "label_eligible_patients": int(
                    label_eligible["deid_patient_id"].astype(str).nunique()
                ),
                "label_eligible_studies": int(len(pool_labels)),
                "label_eligible_views": int(len(label_eligible)),
                "selected_patients": int(len(selection.patient_selection)),
                "selected_studies": int(
                    selection.eligible_rows["study_key"]
                    .astype(str)
                    .nunique()
                ),
                "selected_views": int(len(selection.eligible_rows)),
                "patient_cap": int(args.patient_cap),
                "policy_version": BALANCED_COHORT_POLICY_VERSION,
                "eval_mode": BALANCED_EVAL_MODE,
            }
        ]
    ).to_csv(
        output_root / "selection" / "selection_summary.csv",
        index=False,
    )

    selected_rows = selection.eligible_rows
    if not args.skip_reports:
        print("[Balanced Cohort] Fetching reports for selected views...")
        selected_rows = attach_report_columns(
            client,
            selected_rows,
            batch_size=args.report_batch_size,
        )
    selected_rows.to_csv(
        output_root / "eligible_dicom_rows.csv",
        index=False,
    )

    shortages = selection.label_audit[
        ~selection.label_audit["target_met"].astype(bool)
    ]
    print(
        f"[Balanced Cohort] Selected patients={len(selection.patient_selection)} "
        f"studies={selected_rows['study_key'].astype(str).nunique()} "
        f"views={len(selected_rows)} shortages={len(shortages)}"
    )
    if not shortages.empty:
        print(
            "[Balanced Cohort] Some targets were not available under the "
            "locked split/cap; continuing with an explicit shortage audit."
        )

    metadata = {
        "policy_version": BALANCED_COHORT_POLICY_VERSION,
        "eval_mode": BALANCED_EVAL_MODE,
        "split_seed": SPLIT_SEED,
        "patient_cap": args.patient_cap,
        "negative_to_positive_ratio": args.negative_ratio,
        "pre_quality_positive_targets": targets,
        "post_quality_positive_targets": POST_QUALITY_POSITIVE_TARGETS,
        "selected_patients": int(len(selection.patient_selection)),
        "selected_studies": int(
            selected_rows["study_key"].astype(str).nunique()
        ),
        "selected_views": int(len(selected_rows)),
    }
    (output_root / "cohort_meta.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    if args.skip_dicom_download:
        print("[Balanced Cohort] Skipping DICOM reuse/download.")
        return 0

    dicom_root = output_root / "dicom_train"
    if args.overwrite_dicoms:
        reuse_status = pd.DataFrame()
        needs_download = selected_rows
    else:
        print(
            f"[Balanced Cohort] Reusing matching DICOMs from "
            f"{args.reuse_dicom_root}..."
        )
        reuse_status = reuse_existing_dicoms(
            selected_rows,
            args.reuse_dicom_root,
            dicom_root,
        )
        reuse_status.to_csv(
            output_root / "dicom_reuse_status.csv",
            index=False,
        )
        reused_paths = set(
            reuse_status.loc[
                reuse_status["status"].isin(_REUSED_STATUSES),
                "dicom_path",
            ].astype(str)
        )
        needs_download = selected_rows[
            ~selected_rows["dicom_path"].astype(str).isin(reused_paths)
        ]

    print(
        f"[Balanced Cohort] DICOMs needing download={len(needs_download)}"
    )
    download_status = download_eligible_dicoms(
        client,
        needs_download,
        dicom_root,
        overwrite=args.overwrite_dicoms,
        resume=False,
    )
    kept_reuse_status = (
        reuse_status[
            reuse_status["status"].isin(_REUSED_STATUSES)
        ].copy()
        if not reuse_status.empty
        else pd.DataFrame()
    )
    final_status = pd.concat(
        [kept_reuse_status, download_status],
        ignore_index=True,
    )
    final_status.to_csv(
        output_root / "dicom_download_status.csv",
        index=False,
    )
    summary = summarize_download_status(final_status)
    print(f"[Balanced Cohort] DICOM summary: {summary}")
    return 1 if summary.get("failed", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
