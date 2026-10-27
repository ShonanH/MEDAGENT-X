"""Safely finalize an intact RAD-DINO cache after interrupted validation."""

from __future__ import annotations

import argparse
from pathlib import Path

from medagentx.vision.cache import finalize_interrupted_raddino_cache


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Exact-pixel validate and finalize a fully written RAD-DINO cache "
            "whose previous validation was interrupted."
        )
    )
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--dicom-root", type=Path, required=True)
    parser.add_argument(
        "--validation-views-per-split",
        type=int,
        default=100,
        help="Deterministic exact-pixel validation views from each split.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.validation_views_per_split <= 0:
        raise ValueError("validation-views-per-split must be > 0")
    cache_root = finalize_interrupted_raddino_cache(
        cache_root=args.cache_root,
        dicom_root=args.dicom_root,
        validation_views_per_split=args.validation_views_per_split,
    )
    print(f"[RAD-DINO cache] finalized root={cache_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
