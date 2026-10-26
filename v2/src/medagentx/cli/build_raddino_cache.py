"""Build and validate a lossless, versioned RAD-DINO DICOM cache."""

from __future__ import annotations

import argparse
from pathlib import Path

from transformers import AutoImageProcessor

from medagentx.vision.cache import (
    DEFAULT_CACHE_VERSION,
    RadDinoImageCache,
    build_raddino_cache,
)
from medagentx.vision.constants import DEFAULT_MODEL_NAME


def _processor_config(model_name: str) -> dict:
    """Load the exact processor configuration used to bind a cache."""
    processor = AutoImageProcessor.from_pretrained(model_name)
    return {"model_name": model_name, "config": processor.to_dict()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an immutable, validated RAD-DINO DICOM cache."
    )
    parser.add_argument("--cohort-root", type=Path, required=True)
    parser.add_argument("--dicom-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cache-version", default=DEFAULT_CACHE_VERSION)
    parser.add_argument("--view-splits-csv", type=Path, default=None)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=None,
        help="Validation-only cap, applied independently to each split.",
    )
    parser.add_argument(
        "--shard-size-mib",
        type=int,
        default=512,
        help="Target uncompressed tar-shard size in MiB.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace only an incomplete cache at this exact output path.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop processing after recording the first invalid DICOM.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.num_workers < 0:
        raise ValueError("num-workers must be >= 0")
    if args.sample_limit is not None and args.sample_limit <= 0:
        raise ValueError("sample-limit must be > 0")
    if args.shard_size_mib <= 0:
        raise ValueError("shard-size-mib must be > 0")

    views_csv = args.view_splits_csv or (
        args.cohort_root / "splits" / "view_splits.csv"
    )
    cache_root = build_raddino_cache(
        cohort_root=args.cohort_root,
        dicom_root=args.dicom_root,
        output_root=args.output_root,
        cache_version=args.cache_version,
        view_splits_csv=views_csv,
        num_workers=args.num_workers,
        sample_limit=args.sample_limit,
        shard_size_bytes=args.shard_size_mib * 1024 * 1024,
        overwrite=args.overwrite,
        fail_fast=args.fail_fast,
        image_processor_config=_processor_config(args.model_name),
    )
    cache = RadDinoImageCache(cache_root)
    print(
        f"[RAD-DINO cache] complete root={cache_root} "
        f"validated_pixels={cache.manifest['pixel_validation']['view_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
