"""Build the immutable patient-level development split for CheXpert competition data."""

from __future__ import annotations

import argparse
from pathlib import Path

from medagentx.splits.competition import (
    COMPETITION_SPLIT_POLICY_VERSION,
    DEFAULT_COMPETITION_SPLIT_SEED,
    DEFAULT_DEV_FRACTION,
    build_competition_split_artifacts,
)


DEFAULT_MANIFEST_ROOT = Path("v2/artifacts/chexpert_competition_v1/manifests")
DEFAULT_SPLIT_ROOT = Path("v2/artifacts/chexpert_competition_v1/splits")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build an immutable patient-level 95/5 train/dev split from the "
            "competition manifest."
        )
    )
    parser.add_argument("--manifest-root", type=Path, default=DEFAULT_MANIFEST_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_SPLIT_ROOT)
    parser.add_argument(
        "--expert-test-groundtruth",
        type=Path,
        default=Path("v2/data/groundtruth.csv"),
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_COMPETITION_SPLIT_SEED)
    parser.add_argument("--dev-fraction", type=float, default=DEFAULT_DEV_FRACTION)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly replace existing split artifacts.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest_root: Path = args.manifest_root
    paths = build_competition_split_artifacts(
        train_views_path=manifest_root / "train_views.csv",
        study_labels_path=manifest_root / "study_labels.csv",
        excluded_rows_path=manifest_root / "excluded_rows.csv",
        expert_test_groundtruth=args.expert_test_groundtruth,
        output_root=args.output_root,
        seed=args.seed,
        dev_fraction=args.dev_fraction,
        overwrite=args.overwrite,
    )
    print(f"[CompetitionSplit] policy={COMPETITION_SPLIT_POLICY_VERSION}")
    for name, path in paths.items():
        print(f"[CompetitionSplit] {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
