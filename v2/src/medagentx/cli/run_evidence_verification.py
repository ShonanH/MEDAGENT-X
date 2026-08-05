"""Run the Evidence Verification Agent over live fusion outputs."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import pandas as pd

from medagentx.agents.evidence_verification import verify_study_evidence
from medagentx.contracts.evidence_verification import (
    EVIDENCE_VERIFICATION_COLUMNS,
    study_verification_to_json_dict,
    study_verifications_to_csv_rows,
)
from medagentx.data.balanced_constants import DEFAULT_BALANCED_COHORT_ROOT
from medagentx.reasoning.constants import (
    FUSION_POLICY_VERSION,
    FUSION_RETRIEVAL_TOP_K,
    GRAY_ZONE_MARGIN,
)
from medagentx.reasoning.fuse import fuse_study_labels
from medagentx.reasoning.vision_adapter import fusion_vision_inputs
from medagentx.vision.constants import DEFAULT_BATCH_SIZE, DEFAULT_NUM_WORKERS


DEFAULT_VERIFICATION_SUBDIR = "reasoning/evidence_verification_v1"
DEFAULT_COLLECTION_NAME = "medagentx_train_studies_v1"


def _default_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def build_parser() -> argparse.ArgumentParser:
    """Build the Evidence Verification command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Run vision, retrieval, fusion, and the Evidence Verification Agent "
            "for one split."
        )
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path(DEFAULT_BALANCED_COHORT_ROOT),
    )
    parser.add_argument("--views-csv", type=Path, default=None)
    parser.add_argument("--dicom-root", type=Path, default=None)
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument(
        "--threshold-policy-json",
        type=Path,
        default=None,
        help=(
            "Optional threshold_policy_v2.json. When provided, selected_thresholds "
            "override checkpoint thresholds during vision prediction."
        ),
    )
    parser.add_argument(
        "--vector-db-dir",
        type=Path,
        default=None,
        help="Defaults to cohort-root/retrieval/raddino_train_v1/chroma",
    )
    parser.add_argument(
        "--collection-name",
        default=DEFAULT_COLLECTION_NAME,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Defaults to cohort-root/{DEFAULT_VERIFICATION_SUBDIR}/<split>",
    )
    parser.add_argument(
        "--split",
        choices=("val", "test"),
        default="test",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--num-workers", type=int, default=DEFAULT_NUM_WORKERS)
    parser.add_argument(
        "--device",
        default=_default_device(),
    )
    parser.add_argument("--no-mixed-precision", action="store_true")
    parser.add_argument(
        "--gray-zone-margin",
        type=float,
        default=GRAY_ZONE_MARGIN,
    )
    parser.add_argument(
        "--max-studies",
        type=int,
        default=None,
        help="Optional smoke-test limit on the number of studies.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Log verification progress every N studies.",
    )
    parser.add_argument(
        "--write-intermediate-predictions",
        action="store_true",
        help="Also write vision_study_predictions.csv and fusion_label_predictions.csv.",
    )
    return parser


def _load_threshold_overrides(
    threshold_policy_json: Path | None,
) -> tuple[dict[str, float] | None, str | None]:
    if threshold_policy_json is None:
        return None, None
    if not threshold_policy_json.exists():
        raise FileNotFoundError(f"Threshold policy JSON missing: {threshold_policy_json}")
    threshold_policy = json.loads(threshold_policy_json.read_text())
    selected_thresholds = threshold_policy.get("selected_thresholds")
    if not isinstance(selected_thresholds, dict):
        raise ValueError("Threshold policy JSON must contain selected_thresholds object")
    return (
        {str(label): float(value) for label, value in selected_thresholds.items()},
        threshold_policy.get("threshold_policy_version"),
    )


def _verification_summary_payload(
    *,
    split: str,
    study_count: int,
    label_count: int,
    elapsed_seconds: float,
    threshold_policy_version: str | None,
    threshold_policy_json: Path | None,
    gray_zone_margin: float,
    status_counts: Counter[str],
    score_counts: Counter[int],
) -> dict[str, object]:
    return {
        "split": split,
        "fusion_policy_version": FUSION_POLICY_VERSION,
        "threshold_policy_version": threshold_policy_version,
        "threshold_policy_json": (
            str(threshold_policy_json) if threshold_policy_json is not None else None
        ),
        "verification_policy_version": "evidence_verification_policy_v1",
        "gray_zone_margin": gray_zone_margin,
        "retrieved_top_k": FUSION_RETRIEVAL_TOP_K,
        "study_count": study_count,
        "label_count": label_count,
        "elapsed_seconds": elapsed_seconds,
        "verification_status_counts": dict(sorted(status_counts.items())),
        "evidence_score_counts": {
            str(score): count for score, count in sorted(score_counts.items())
        },
    }


def main(argv: list[str] | None = None) -> int:
    """Run the live verification pipeline and write CSV/JSON outputs."""
    import torch

    from medagentx.reasoning.retrieve import (
        default_retrieval_chroma_dir,
        open_retrieval_collection,
        retrieve_similar_reports,
    )
    from medagentx.vision.backend import FineTunedRadDinoBackend
    from medagentx.vision.data import build_study_inference_records
    from medagentx.vision.inference_output import study_outputs_to_prediction_frame

    args = build_parser().parse_args(argv)
    if args.batch_size <= 0:
        raise ValueError("batch-size must be > 0")
    if args.num_workers < 0:
        raise ValueError("num-workers must be >= 0")
    if args.gray_zone_margin < 0:
        raise ValueError("gray-zone-margin must be >= 0")
    if args.progress_every <= 0:
        raise ValueError("progress-every must be > 0")
    if args.max_studies is not None and args.max_studies <= 0:
        raise ValueError("max-studies must be > 0")

    cohort_root: Path = args.cohort_root
    views_csv = args.views_csv or (cohort_root / "splits" / "view_splits.csv")
    dicom_root = args.dicom_root or (cohort_root / "dicom_train")
    checkpoint_path = args.checkpoint or (
        cohort_root
        / "vision"
        / "raddino_finetuned_v1"
        / "best_checkpoint.pt"
    )
    vector_db_dir = args.vector_db_dir or default_retrieval_chroma_dir(cohort_root)
    output_dir = args.output_dir or (
        cohort_root / DEFAULT_VERIFICATION_SUBDIR / args.split
    )

    for path in (views_csv, checkpoint_path, vector_db_dir):
        if not path.exists():
            raise FileNotFoundError(f"Required verification artifact missing: {path}")
    if not dicom_root.exists():
        raise FileNotFoundError(f"DICOM root missing: {dicom_root}")

    threshold_overrides, threshold_policy_version = _load_threshold_overrides(
        args.threshold_policy_json
    )
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")

    print(
        f"[EvidenceVerification] split={args.split} "
        f"fusion_policy={FUSION_POLICY_VERSION} device={device} "
        f"gray_margin={args.gray_zone_margin}"
    )
    if args.threshold_policy_json is not None:
        print(
            "[EvidenceVerification] using threshold policy "
            f"{threshold_policy_version or 'unknown'} -> "
            f"{args.threshold_policy_json}"
        )

    print(f"[EvidenceVerification] loading views from {views_csv}")
    views = pd.read_csv(views_csv, dtype=str)
    records = build_study_inference_records(views, split=args.split)
    if args.max_studies is not None:
        records = records[: args.max_studies]
    if not records:
        raise ValueError(f"No studies found for split={args.split!r}")

    print(f"[EvidenceVerification] loading checkpoint {checkpoint_path}")
    backend = FineTunedRadDinoBackend.from_checkpoint(
        checkpoint_path,
        device=device,
        mixed_precision=not args.no_mixed_precision,
    )

    start = time.perf_counter()
    print(
        f"[EvidenceVerification] running vision on {len(records)} studies "
        f"(batch_size={args.batch_size}, num_workers={args.num_workers})"
    )
    study_outputs = backend.predict_study_outputs(
        records,
        dicom_root=dicom_root,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        threshold_overrides=threshold_overrides,
    )

    print(f"[EvidenceVerification] opening retrieval collection at {vector_db_dir}")
    collection = open_retrieval_collection(
        vector_db_dir,
        collection_name=args.collection_name,
    )

    verification_results = []
    fusion_results = []
    total_studies = len(study_outputs)
    for index, study_output in enumerate(study_outputs, start=1):
        retrieved = retrieve_similar_reports(collection, study_output)
        fusion_result = fuse_study_labels(
            fusion_vision_inputs(study_output),
            retrieved,
            study_key=study_output.study_key,
            margin=args.gray_zone_margin,
        )
        fusion_results.append(fusion_result)
        verification_results.append(
            verify_study_evidence(
                vision_output=study_output,
                fusion_result=fusion_result,
                retrieved_cases=retrieved,
                margin=args.gray_zone_margin,
            )
        )
        if index == 1 or index % args.progress_every == 0 or index == total_studies:
            elapsed = time.perf_counter() - start
            print(
                f"[EvidenceVerification] verified {index}/{total_studies} studies "
                f"elapsed={elapsed:.1f}s"
            )

    elapsed = time.perf_counter() - start
    csv_rows = study_verifications_to_csv_rows(verification_results)
    json_payload = [
        study_verification_to_json_dict(result)
        for result in verification_results
    ]
    status_counts: Counter[str] = Counter(
        row["verification_status"] for row in csv_rows
    )
    score_counts: Counter[int] = Counter(int(row["evidence_score"]) for row in csv_rows)
    summary_payload = _verification_summary_payload(
        split=args.split,
        study_count=len(verification_results),
        label_count=len(csv_rows),
        elapsed_seconds=elapsed,
        threshold_policy_version=threshold_policy_version,
        threshold_policy_json=args.threshold_policy_json,
        gray_zone_margin=args.gray_zone_margin,
        status_counts=status_counts,
        score_counts=score_counts,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    verification_csv = output_dir / "evidence_verification.csv"
    verification_json = output_dir / "evidence_verification.json"
    summary_json = output_dir / "evidence_verification_summary.json"
    pd.DataFrame(csv_rows, columns=EVIDENCE_VERIFICATION_COLUMNS).to_csv(
        verification_csv,
        index=False,
    )
    verification_json.write_text(
        json.dumps(json_payload, indent=2, sort_keys=True) + "\n"
    )
    summary_json.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n"
    )

    if args.write_intermediate_predictions:
        from medagentx.evaluation.fusion_eval import fusion_results_to_frame

        vision_csv = output_dir / "vision_study_predictions.csv"
        fusion_csv = output_dir / "fusion_label_predictions.csv"
        study_outputs_to_prediction_frame(study_outputs).to_csv(vision_csv, index=False)
        fusion_results_to_frame(fusion_results).to_csv(fusion_csv, index=False)
        print(f"[EvidenceVerification] wrote vision predictions -> {vision_csv}")
        print(f"[EvidenceVerification] wrote fusion predictions -> {fusion_csv}")

    print(f"[EvidenceVerification] wrote verification CSV -> {verification_csv}")
    print(f"[EvidenceVerification] wrote verification JSON -> {verification_json}")
    print(f"[EvidenceVerification] wrote summary -> {summary_json}")
    print(
        "[EvidenceVerification] status counts: "
        + ", ".join(
            f"{status}={count}" for status, count in sorted(status_counts.items())
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
