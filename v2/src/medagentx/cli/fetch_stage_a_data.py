"""Fetch Stage A metadata, DICOMs, and findings_fixed.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.data.dicoms import (
    download_eligible_dicoms,
    summarize_download_status,
)
from medagentx.data.findings import ensure_findings_fixed_json
from medagentx.data.redivis_client import RedivisClient
from medagentx.data.rows import fetch_eligible_dicom_rows


def build_parser() -> argparse.ArgumentParser:
    """Build the Stage A command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Fetch eligible CheXpert Plus train rows, DICOMs, and "
            "findings_fixed.json."
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
    parser.add_argument("--max-rows", type=int, default=None)
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
    parser.add_argument("--overwrite-dicoms", action="store_true")
    parser.add_argument("--overwrite-findings", action="store_true")
    parser.add_argument(
        "--skip-dicom-download",
        action="store_true",
        help="Fetch eligible rows and findings_fixed.json without DICOM files.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run Stage A retrieval and persist auditable output tables."""
    args = build_parser().parse_args(argv)
    output_root: Path = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)

    client = RedivisClient.from_env()

    print("[Stage A] Fetching eligible train DICOM rows...")
    eligible = fetch_eligible_dicom_rows(
        client,
        metadata_limit=args.metadata_limit,
        index_limit=args.index_limit,
        max_patients=args.max_patients,
        max_studies=args.max_studies,
        max_rows=args.max_rows,
    )
    eligible_csv = output_root / "eligible_dicom_rows.csv"
    eligible.to_csv(eligible_csv, index=False)
    print(f"[Stage A] Wrote {len(eligible)} eligible rows -> {eligible_csv}")

    findings_path = ensure_findings_fixed_json(
        client,
        output_root / "chexpert_labels" / "findings_fixed.json",
        overwrite=args.overwrite_findings,
    )
    print(f"[Stage A] Label asset ready -> {findings_path}")

    if args.skip_dicom_download:
        print("[Stage A] Skipping DICOM download.")
        return 0

    dicom_root = output_root / "dicom_train"
    print(f"[Stage A] Downloading DICOMs -> {dicom_root}")
    status = download_eligible_dicoms(
        client,
        eligible,
        dicom_root,
        overwrite=args.overwrite_dicoms,
        resume=True,
    )
    status_csv = output_root / "dicom_download_status.csv"
    status.to_csv(status_csv, index=False)

    summary = summarize_download_status(status)
    print(f"[Stage A] Download summary: {summary}")
    print(f"[Stage A] Wrote status -> {status_csv}")

    if summary.get("failed", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
