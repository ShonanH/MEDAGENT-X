"""Fetch Stage A metadata, label-gated cohort rows, and DICOMs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.data.cohort import (
    apply_label_gated_cohort,
    load_findings_for_cohort,
    summarize_label_gated_cohort,
    write_label_gated_cohort_artifacts,
)
from medagentx.data.dicoms import (
    download_eligible_dicoms,
    summarize_download_status,
)
from medagentx.data.findings import ensure_findings_fixed_json
from medagentx.data.redivis_client import RedivisClient
from medagentx.data.rows import (
    DEFAULT_INDEX_PAGE_SIZE,
    DEFAULT_METADATA_PAGE_SIZE,
    DEFAULT_REPORT_BATCH_SIZE,
    fetch_eligible_dicom_rows,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the Stage A command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Fetch train metadata, apply label-gated cohort rules, download "
            "findings_fixed.json, and download only labeled DICOMs."
        )
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("v2/artifacts/cohort"),
        help="Root for eligible rows, DICOMs, labels, and status artifacts.",
    )
    parser.add_argument("--max-patients", type=int, default=None)
    parser.add_argument("--max-studies", type=int, default=None)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional view-row ceiling applied after label gating (whole studies only).",
    )
    parser.add_argument(
        "--metadata-limit",
        type=int,
        default=None,
        help="Optional SQL metadata row limit for development only.",
    )
    parser.add_argument(
        "--index-limit",
        type=int,
        default=None,
        help="Optional SQL DICOM-index row limit for development only.",
    )
    parser.add_argument(
        "--metadata-page-size",
        type=int,
        default=DEFAULT_METADATA_PAGE_SIZE,
        help="Rows per metadata SQL page (Redivis caps responses at 100MB).",
    )
    parser.add_argument(
        "--index-page-size",
        type=int,
        default=DEFAULT_INDEX_PAGE_SIZE,
        help="Rows per DICOM-index SQL page.",
    )
    parser.add_argument(
        "--report-batch-size",
        type=int,
        default=DEFAULT_REPORT_BATCH_SIZE,
        help="Cohort paths per report-text query batch.",
    )
    parser.add_argument(
        "--skip-reports",
        action="store_true",
        help="Skip fetching report text for the eligible cohort.",
    )
    parser.add_argument("--overwrite-dicoms", action="store_true")
    parser.add_argument("--overwrite-findings", action="store_true")
    parser.add_argument(
        "--skip-dicom-download",
        action="store_true",
        help="Fetch label-gated cohort rows without downloading DICOM files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run Stage A retrieval and persist auditable output tables."""
    args = build_parser().parse_args(argv)
    output_root: Path = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)

    client = RedivisClient.from_env()

    print("[Stage A] Fetching downloadable train metadata rows...")
    prefilter = fetch_eligible_dicom_rows(
        client,
        metadata_limit=args.metadata_limit,
        index_limit=args.index_limit,
        max_patients=args.max_patients,
        max_studies=args.max_studies,
        max_rows=None,
        metadata_page_size=args.metadata_page_size,
        index_page_size=args.index_page_size,
        include_reports=not args.skip_reports,
        report_batch_size=args.report_batch_size,
    )
    prefilter_csv = output_root / "eligible_dicom_rows_prefilter.csv"
    prefilter.to_csv(prefilter_csv, index=False)
    print(
        f"[Stage A] Wrote {len(prefilter)} prefilter rows -> {prefilter_csv}"
    )

    findings_path = ensure_findings_fixed_json(
        client,
        output_root / "chexpert_labels" / "findings_fixed.json",
        overwrite=args.overwrite_findings,
    )
    print(f"[Stage A] Label asset ready -> {findings_path}")

    print("[Stage A] Applying label-gated cohort rules...")
    findings_index = load_findings_for_cohort(findings_path, prefilter)
    kept, dropped = apply_label_gated_cohort(
        prefilter,
        findings_index,
        max_rows=args.max_rows,
    )
    artifacts = write_label_gated_cohort_artifacts(
        output_root,
        eligible_rows=prefilter,
        kept_rows=kept,
        dropped_rows=dropped,
    )
    summary = summarize_label_gated_cohort(prefilter, kept, dropped)
    print(f"[Stage A] Label-gated cohort summary: {summary}")
    print(f"[Stage A] Wrote eligible rows -> {artifacts['eligible_csv']}")
    print(f"[Stage A] Wrote dropped studies -> {artifacts['dropped_csv']}")

    if kept.empty:
        print("[Stage A] No label-gated rows remain after filtering.")
        return 1

    if args.skip_dicom_download:
        print("[Stage A] Skipping DICOM download.")
        return 0

    dicom_root = output_root / "dicom_train"
    print(f"[Stage A] Downloading DICOMs -> {dicom_root}")
    status = download_eligible_dicoms(
        client,
        kept,
        dicom_root,
        overwrite=args.overwrite_dicoms,
        resume=True,
    )
    status_csv = output_root / "dicom_download_status.csv"
    status.to_csv(status_csv, index=False)

    download_summary = summarize_download_status(status)
    print(f"[Stage A] Download summary: {download_summary}")
    print(f"[Stage A] Wrote status -> {status_csv}")

    if download_summary.get("failed", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
