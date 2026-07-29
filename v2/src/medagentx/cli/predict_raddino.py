"""Run the fine-tuned RAD-DINO vision backend on quality-passed studies."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import torch

from medagentx.vision.constants import DEFAULT_BATCH_SIZE, DEFAULT_NUM_WORKERS
from medagentx.vision.backend import FineTunedRadDinoBackend
from medagentx.vision.data import build_study_inference_records


def build_parser() -> argparse.ArgumentParser:
    """Build the fine-tuned RAD-DINO inference parser."""
    parser = argparse.ArgumentParser(
        description="Predict 12 study-level diseases from quality-passed DICOMs."
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path("v2/artifacts/cohort"),
    )
    parser.add_argument("--views-csv", type=Path, default=None)
    parser.add_argument("--dicom-root", type=Path, default=None)
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument(
        "--split",
        choices=("train", "val", "test", "all"),
        default="test",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--num-workers", type=int, default=DEFAULT_NUM_WORKERS
    )
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
    )
    parser.add_argument("--no-mixed-precision", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Load one checkpoint and emit the permanent vision prediction table."""
    args = build_parser().parse_args(argv)
    cohort_root: Path = args.cohort_root
    views_csv = args.views_csv or (
        cohort_root / "splits" / "view_splits.csv"
    )
    dicom_root = args.dicom_root or (cohort_root / "dicom_train")
    checkpoint_path = args.checkpoint or (
        cohort_root
        / "vision"
        / "raddino_finetuned_v1"
        / "best_checkpoint.pt"
    )
    output_csv = args.output_csv or (
        cohort_root
        / "vision"
        / "raddino_finetuned_v1"
        / f"{args.split}_study_predictions.csv"
    )
    for path in (views_csv, checkpoint_path):
        if not path.exists():
            raise FileNotFoundError(f"Required inference artifact missing: {path}")
    if not dicom_root.exists():
        raise FileNotFoundError(f"DICOM root missing: {dicom_root}")

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")
    backend = FineTunedRadDinoBackend.from_checkpoint(
        checkpoint_path,
        device=device,
        mixed_precision=not args.no_mixed_precision,
    )

    views = pd.read_csv(views_csv, dtype=str)
    records = build_study_inference_records(
        views,
        split=None if args.split == "all" else args.split,
    )
    table = backend.predict_studies(
        records,
        dicom_root=dicom_root,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
    )
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output_csv, index=False)
    print(f"[Vision] Wrote {len(table)} study predictions -> {output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
