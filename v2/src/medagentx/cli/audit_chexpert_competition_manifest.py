"""CLI for the competition-aligned CheXpert Plus manifest audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from medagentx.data.competition_manifest import (
    DEFAULT_OUTPUT_ROOT,
    build_competition_manifest,
)
from medagentx.data.redivis_client import RedivisClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit Redivis PNG_train, metadata, and findings_fixed.json; "
            "write a fresh competition manifest."
        )
    )
    parser.add_argument(
        "--png-root",
        type=Path,
        required=True,
        help="Local directory containing patient/study/view PNG files.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=(
            "Fresh artifact root "
            "(default: v2/artifacts/chexpert_competition_v1)."
        ),
    )
    parser.add_argument(
        "--findings-json",
        type=Path,
        default=None,
        help=(
            "Existing findings_fixed.json. If omitted, the Redivis client "
            "downloads it below the output root."
        ),
    )
    parser.add_argument(
        "--expert-test-groundtruth",
        type=Path,
        default=Path("v2/data/groundtruth.csv"),
        help="Released 500-study expert test groundtruth CSV.",
    )
    parser.add_argument(
        "--uncertainty-policy",
        choices=("ignore_uncertain", "u_zero", "u_one"),
        default="ignore_uncertain",
        help="Explicit policy for study target/mask columns.",
    )
    parser.add_argument(
        "--metadata-page-size",
        type=int,
        default=50_000,
    )
    parser.add_argument(
        "--png-page-size",
        type=int,
        default=100_000,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = RedivisClient.from_env()
    outputs = build_competition_manifest(
        client,
        image_root=args.png_root,
        output_root=args.output_root,
        findings_json=args.findings_json,
        expert_test_groundtruth=args.expert_test_groundtruth,
        uncertainty_policy=args.uncertainty_policy,
        metadata_page_size=args.metadata_page_size,
        png_page_size=args.png_page_size,
    )
    for name, path in outputs.items():
        print(f"[CompetitionManifest] {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

