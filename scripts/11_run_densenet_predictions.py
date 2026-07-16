#!/usr/bin/env python3
"""Batch TorchXRayVision DenseNet predictions for Workflow B."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.classifiers.densenet_classifier import (
    DEFAULT_OUTPUT_CSV,
    DEFAULT_QUALITY_EVIDENCE_CSV,
    DEFAULT_QUALITY_GATE_CSV,
    build_output_row,
    choose_device,
    find_image_path,
    classify_image_with_model,
    load_classifier,
)
from src.medagentx.fusion.paths import clean_dicom_path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quality-gate-csv", type=Path, default=DEFAULT_QUALITY_GATE_CSV)
    parser.add_argument("--quality-evidence-csv", type=Path, default=DEFAULT_QUALITY_EVIDENCE_CSV)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--model-weights", default="densenet121-res224-all")
    parser.add_argument("--device", default="")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def load_eligible_cases(gate_csv: Path, limit: int | None) -> pd.DataFrame:
    df = pd.read_csv(gate_csv, dtype=str)
    df["dicom_path"] = df["dicom_path"].map(clean_dicom_path)

    eligible = df[
        df["quality_gate_decision"].isin(["pass", "review_with_technical_warning"])
        & ~df["route_next"].eq("stop_unreliable")
    ].copy()

    if limit:
        eligible = eligible.head(limit)

    return eligible.reset_index(drop=True)


def main():
    args = parse_args()
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    cases = load_eligible_cases(args.quality_gate_csv, args.limit)
    device = choose_device(args.device)
    model = load_classifier(args.model_weights, device)

    existing_keys: set[tuple[str, str]] = set()
    if args.skip_existing and args.output_csv.exists():
        prev = pd.read_csv(args.output_csv, dtype=str)
        existing_keys = {
            (r["study_key"], clean_dicom_path(r["dicom_path"]))
            for _, r in prev.iterrows()
        }

    rows = []
    if args.skip_existing and args.output_csv.exists():
        rows = pd.read_csv(args.output_csv, dtype=str).to_dict(orient="records")

    for _, case in tqdm(cases.iterrows(), total=len(cases), desc="DenseNet"):
        study_key = case["study_key"]
        dicom_path = clean_dicom_path(case["dicom_path"])
        key = (study_key, dicom_path)

        if key in existing_keys:
            continue

        image_path = find_image_path(
            study_key=study_key,
            dicom_path=dicom_path,
            quality_evidence_csv=args.quality_evidence_csv,
        )

        raw_predictions, model_pathologies = classify_image_with_model(
            model=model,
            image_path=image_path,
            device=device,
        )

        rows.append(
            build_output_row(
                study_key=study_key,
                dicom_path=dicom_path,
                image_path=image_path,
                weights=args.model_weights,
                device=device,
                raw_predictions=raw_predictions,
                model_pathologies=model_pathologies,
            )
        )

    pd.DataFrame(rows).to_csv(args.output_csv, index=False)
    print(f"Wrote {len(rows)} rows to {args.output_csv}")


if __name__ == "__main__":
    main()