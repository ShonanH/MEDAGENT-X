"""Build the offline train-study retrieval index for MEDAGENT-X v2."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import torch

from medagentx.data.balanced_constants import DEFAULT_BALANCED_COHORT_ROOT
from medagentx.retrieval.constants import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_EMBED_BATCH_SIZE,
    DEFAULT_EMBED_NUM_WORKERS,
    DEFAULT_MAX_DOCUMENT_CHARS,
    DEFAULT_RETRIEVAL_SUBDIR,
    EMBEDDING_BACKEND_ID,
    INDEX_BUILD_SPLIT,
)
from medagentx.retrieval.documents import (
    build_study_report_table,
    truncate_document,
)
from medagentx.retrieval.embed import extract_study_embeddings
from medagentx.retrieval.index import (
    build_index_records,
    write_chroma_index,
    write_index_manifest,
)
from medagentx.vision.data import build_study_inference_records


def build_parser() -> argparse.ArgumentParser:
    """Build the retrieval index command-line parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Build a Chroma retrieval index from fine-tuned RAD-DINO "
            "study embeddings and report text on the train split."
        )
    )
    parser.add_argument(
        "--cohort-root",
        type=Path,
        default=Path(DEFAULT_BALANCED_COHORT_ROOT),
    )
    parser.add_argument(
        "--views-csv",
        type=Path,
        default=None,
        help="Defaults to cohort-root/splits/view_splits.csv",
    )
    parser.add_argument(
        "--reports-csv",
        type=Path,
        default=None,
        help="Defaults to cohort-root/eligible_dicom_rows.csv",
    )
    parser.add_argument(
        "--dicom-root",
        type=Path,
        default=None,
        help="Defaults to cohort-root/dicom_train",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help=(
            "Defaults to cohort-root/vision/raddino_finetuned_v1/"
            "best_checkpoint.pt"
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=f"Defaults to cohort-root/{DEFAULT_RETRIEVAL_SUBDIR}",
    )
    parser.add_argument(
        "--collection-name",
        default=DEFAULT_COLLECTION_NAME,
    )
    parser.add_argument(
        "--split",
        default=INDEX_BUILD_SPLIT,
        choices=("train",),
        help="Locked default: train-only index corpus.",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_EMBED_BATCH_SIZE)
    parser.add_argument(
        "--num-workers", type=int, default=DEFAULT_EMBED_NUM_WORKERS
    )
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
    )
    parser.add_argument("--no-mixed-precision", action="store_true")
    parser.add_argument(
        "--max-document-chars",
        type=int,
        default=DEFAULT_MAX_DOCUMENT_CHARS,
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete and recreate the Chroma collection if it exists.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Embed train studies and write the persistent Chroma retrieval index."""
    args = build_parser().parse_args(argv)
    if args.batch_size <= 0:
        raise ValueError("batch-size must be > 0")
    if args.num_workers < 0:
        raise ValueError("num-workers must be >= 0")
    if args.max_document_chars <= 0:
        raise ValueError("max-document-chars must be > 0")

    cohort_root: Path = args.cohort_root
    views_csv = args.views_csv or (cohort_root / "splits" / "view_splits.csv")
    reports_csv = args.reports_csv or (
        cohort_root / "eligible_dicom_rows.csv"
    )
    dicom_root = args.dicom_root or (cohort_root / "dicom_train")
    checkpoint_path = args.checkpoint or (
        cohort_root
        / "vision"
        / "raddino_finetuned_v1"
        / "best_checkpoint.pt"
    )
    output_root = args.output_root or (
        cohort_root / DEFAULT_RETRIEVAL_SUBDIR
    )
    vector_db_dir = output_root / "chroma"

    for path in (views_csv, reports_csv, checkpoint_path):
        if not path.exists():
            raise FileNotFoundError(f"Required retrieval artifact missing: {path}")
    if not dicom_root.exists():
        raise FileNotFoundError(f"DICOM root missing: {dicom_root}")

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")

    views = pd.read_csv(views_csv, dtype=str)
    reports = pd.read_csv(reports_csv, dtype=str)
    train_views = views[views["split"].astype(str).str.strip() == args.split].copy()
    if train_views.empty:
        raise ValueError(f"No views found for split={args.split!r}")

    report_table = build_study_report_table(reports)
    train_study_keys = set(train_views["study_key"].astype(str).str.strip())
    report_table = report_table[
        report_table["study_key"].astype(str).str.strip().isin(train_study_keys)
    ].copy()
    if report_table.empty:
        raise ValueError(
            "No train study report rows found after joining views and reports"
        )
    if len(report_table) != len(train_study_keys):
        missing = sorted(train_study_keys - set(report_table["study_key"]))
        raise ValueError(
            "Report table is missing train studies required for indexing: "
            f"{missing[:5]}"
        )

    documents = {
        row.study_key: truncate_document(
            row.retrieval_document,
            max_chars=args.max_document_chars,
        )
        for row in report_table.itertuples(index=False)
    }

    records = build_study_inference_records(train_views, split=args.split)
    print(
        f"[Retrieval] embedding train studies={len(records)} "
        f"device={device} batch_size={args.batch_size}"
    )
    embedding_payload = extract_study_embeddings(
        records,
        checkpoint_path=checkpoint_path,
        dicom_root=dicom_root,
        device=device,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        mixed_precision=not args.no_mixed_precision,
    )
    if len(embedding_payload["study_keys"]) != len(records):
        raise RuntimeError("Embedding extraction returned an unexpected study count")

    indexed = build_index_records(
        embeddings=embedding_payload["embeddings"],
        study_keys=embedding_payload["study_keys"],
        patient_ids=embedding_payload["patient_ids"],
        documents=documents,
    )
    collection = write_chroma_index(
        vector_db_dir,
        indexed,
        collection_name=args.collection_name,
        rebuild=args.rebuild,
    )
    manifest_path = write_index_manifest(
        output_root / "index_manifest.csv",
        records=indexed,
        build_config={
            "cohort_root": str(cohort_root),
            "views_csv": str(views_csv),
            "reports_csv": str(reports_csv),
            "dicom_root": str(dicom_root),
            "checkpoint": str(checkpoint_path),
            "vector_db_dir": str(vector_db_dir),
            "collection_name": args.collection_name,
            "split": args.split,
            "device": str(device),
            "batch_size": args.batch_size,
            "num_workers": args.num_workers,
            "max_document_chars": args.max_document_chars,
            "embedding_backend_id": embedding_payload["checkpoint"].get(
                "vision_backend_id",
                EMBEDDING_BACKEND_ID,
            ),
            "model_name": embedding_payload["checkpoint"].get("model_name"),
        },
    )
    print(
        f"[Retrieval] Wrote {len(indexed)} studies -> {vector_db_dir} "
        f"(collection={args.collection_name}, count={collection.count()})"
    )
    print(f"[Retrieval] Manifest -> {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
