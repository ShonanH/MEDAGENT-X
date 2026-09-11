"""Download the complete CheXpert Plus PNG_train table locally."""

from __future__ import annotations

import argparse
from pathlib import Path

from medagentx.data.competition_manifest import DEFAULT_OUTPUT_ROOT
from medagentx.data.png_download import (
    DEFAULT_PNG_DOWNLOAD_WORKERS,
    DEFAULT_PNG_PROGRESS_EVERY,
    download_png_train,
)
from medagentx.data.redivis_client import RedivisClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download every image in the verified Redivis PNG_train file "
            "index, preserving patient/study/view paths."
        )
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT / "PNG_train",
        help=(
            "Local PNG root (default: "
            "v2/artifacts/chexpert_competition_v1/PNG_train)."
        ),
    )
    parser.add_argument(
        "--status-path",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT / "png_download_status.csv",
        help="CSV path for per-file download status.",
    )
    parser.add_argument("--page-size", type=int, default=100_000)
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_PNG_DOWNLOAD_WORKERS,
        help="Concurrent raw-file downloads (default: 8).",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=DEFAULT_PNG_PROGRESS_EVERY,
        help="Print progress every N files; 0 disables progress output.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing files instead of preserving matching files.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not resume a partial existing file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = RedivisClient.from_env()
    status = download_png_train(
        client,
        args.output_root,
        page_size=args.page_size,
        max_workers=args.workers,
        progress_every=args.progress_every,
        overwrite=args.overwrite,
        resume=not args.no_resume,
        status_path=args.status_path,
    )
    counts = status["status"].value_counts().to_dict()
    print(f"[png_train] completed={len(status)} status={counts}")
    failed = int((status["status"] == "failed").sum())
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
