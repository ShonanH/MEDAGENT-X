"""Build the compact fixed-shape cache used by GPU-resident RAD-DINO input."""

from __future__ import annotations

import argparse
from pathlib import Path

from transformers import AutoImageProcessor

from medagentx.vision.constants import DEFAULT_MODEL_NAME
from medagentx.vision.model_ready_cache import (
    DEFAULT_MODEL_READY_CACHE_VERSION,
    ModelReadyImageCache,
    build_model_ready_cache,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a compact fixed-shape RAD-DINO model-ready cache."
    )
    parser.add_argument("--raw-cache-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--cache-version", default=DEFAULT_MODEL_READY_CACHE_VERSION
    )
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    processor = AutoImageProcessor.from_pretrained(args.model_name)
    root = build_model_ready_cache(
        raw_cache_root=args.raw_cache_root,
        output_root=args.output_root,
        cache_version=args.cache_version,
        processor=processor,
        image_processor_config={
            "model_name": args.model_name,
            "config": processor.to_dict(),
        },
        overwrite=args.overwrite,
    )
    cache = ModelReadyImageCache(root)
    print(
        f"[RAD-DINO model-ready cache] complete root={root} "
        f"views={cache.manifest['view_count']} cache_id={cache.cache_id}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
