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
    DEFAULT_EMBEDDINGS_CACHE_NAME,
    DEFAULT_MAX_DOCUMENT_CHARS,
    DEFAULT_PROGRESS_EVERY_BATCHES,
    DEFAULT_RETRIEVAL_SUBDIR,
    EMBEDDING_BACKEND_ID,
    INDEX_BUILD_SPLIT,
)
from medagentx.retrieval.documents import (
    build_study_report_table,
    truncate_document,
)
from medagentx.retrieval.embed import extract_study_embeddings
from medagentx.retrieval.embed_cache import (
    load_embeddings_cache,
    save_embeddings_cache,
)
from medagentx.retrieval.index import (
    build_index_records,
    write_chroma_index,
    write_index_manifest,
)
from medagentx.vision.cache import sha256_file
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
        "--embeddings-cache",
        type=Path,
        default=None,
        help=(
            "Defaults to output-root/study_embeddings.npz. Saved after embed; "
            "reused with --reuse-embeddings."
        ),
    )
    parser.add_argument(
        "--model-ready-cache-root",
        type=Path,
        default=None,
        help=(
            "Optional validated fixed-shape image cache to preload on CUDA "
            "instead of decoding DICOMs during embedding."
        ),
    )
    parser.add_argument(
        "--gpu-cache-preload-chunk-size",
        type=int,
        default=64,
        help="Views copied to the GPU per model-ready-cache preload chunk.",
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
        "--progress-every",
        type=int,
        default=DEFAULT_PROGRESS_EVERY_BATCHES,
        help="Log embedding progress every N batches.",
    )
    parser.add_argument(
        "--max-studies",
        type=int,
        default=None,
        help="Optional smoke-test limit on the number of train studies.",
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
        "--reuse-embeddings",
        action="store_true",
        help="Skip DICOM embedding when a compatible cache file already exists.",
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
    if args.progress_every <= 0:
        raise ValueError("progress-every must be > 0")
    if args.gpu_cache_preload_chunk_size <= 0:
        raise ValueError("gpu-cache-preload-chunk-size must be > 0")
    if args.max_studies is not None and args.max_studies <= 0:
        raise ValueError("max-studies must be > 0")

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
    embeddings_cache = args.embeddings_cache or (
        output_root / DEFAULT_EMBEDDINGS_CACHE_NAME
    )

    for path in (views_csv, reports_csv, checkpoint_path):
        if not path.exists():
            raise FileNotFoundError(f"Required retrieval artifact missing: {path}")
    if not dicom_root.exists():
        raise FileNotFoundError(f"DICOM root missing: {dicom_root}")
    if (
        args.model_ready_cache_root is not None
        and not args.model_ready_cache_root.is_dir()
    ):
        raise FileNotFoundError(
            f"Model-ready cache missing: {args.model_ready_cache_root}"
        )

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")
    if args.model_ready_cache_root is not None and device.type != "cuda":
        raise ValueError("--model-ready-cache-root requires --device cuda")

    print(f"[Retrieval] loading views from {views_csv}")
    views = pd.read_csv(views_csv, dtype=str)
    print(f"[Retrieval] loading reports from {reports_csv}")
    reports = pd.read_csv(reports_csv, dtype=str)
    train_views = views[views["split"].astype(str).str.strip() == args.split].copy()
    if train_views.empty:
        raise ValueError(f"No views found for split={args.split!r}")

    print(
        f"[Retrieval] building study report table for split={args.split!r} "
        f"views={len(train_views)}"
    )
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
    if args.max_studies is not None:
        records = records[: args.max_studies]
        allowed = {record.study_key for record in records}
        documents = {
            study_key: document
            for study_key, document in documents.items()
            if study_key in allowed
        }
        print(f"[Retrieval] limiting to max_studies={args.max_studies}")

    checkpoint_meta: dict[str, object] = {
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "device": str(device),
        "batch_size": args.batch_size,
        "num_workers": args.num_workers,
        "split": args.split,
        "study_count": len(records),
        "model_ready_cache_root": (
            str(args.model_ready_cache_root)
            if args.model_ready_cache_root is not None
            else None
        ),
    }

    embedding_payload: dict[str, object] | None = None
    if args.reuse_embeddings:
        print(f"[Retrieval] checking embeddings cache {embeddings_cache}")
        embedding_payload = load_embeddings_cache(embeddings_cache)
        if embedding_payload is None:
            print("[Retrieval] cache miss; will embed from DICOMs")
        elif embedding_payload["study_keys"] != [
            record.study_key for record in records
        ]:
            raise ValueError(
                "Embeddings cache study identities/order do not match this run"
            )
        elif embedding_payload["meta"].get("checkpoint_sha256") != (
            checkpoint_meta["checkpoint_sha256"]
        ):
            raise ValueError(
                "Embeddings cache checkpoint SHA-256 does not match this run"
            )
        else:
            checkpoint_meta["input_cache"] = embedding_payload["meta"].get(
                "input_cache"
            )
            print(
                f"[Retrieval] reusing cached embeddings "
                f"studies={len(embedding_payload['study_keys'])}"
            )

    if embedding_payload is None:
        print(
            f"[Retrieval] embedding train studies={len(records)} "
            f"device={device} batch_size={args.batch_size} "
            f"num_workers={args.num_workers}"
        )
        embedding_payload = extract_study_embeddings(
            records,
            checkpoint_path=checkpoint_path,
            dicom_root=dicom_root,
            device=device,
            batch_size=args.batch_size,
            num_workers=args.num_workers,
            mixed_precision=not args.no_mixed_precision,
            progress_every=args.progress_every,
            model_ready_cache_root=args.model_ready_cache_root,
            cohort_root=cohort_root,
            view_splits_csv=views_csv,
            gpu_cache_preload_chunk_size=args.gpu_cache_preload_chunk_size,
        )
        checkpoint_meta["input_cache"] = embedding_payload["input_cache"]
        if len(embedding_payload["study_keys"]) != len(records):
            raise RuntimeError(
                "Embedding extraction returned an unexpected study count"
            )
        save_embeddings_cache(
            embeddings_cache,
            embedding_payload,
            build_config=checkpoint_meta,
        )
        print(f"[Retrieval] saved embeddings cache -> {embeddings_cache}")
    else:
        embedding_payload["checkpoint"] = {"vision_backend_id": EMBEDDING_BACKEND_ID}

    all_embedding_study_keys = list(embedding_payload["study_keys"])
    all_embedding_patient_ids = list(embedding_payload["patient_ids"])
    included_indices: list[int] = []
    excluded_rows: list[dict[str, str]] = []
    for index, (study_key, patient_id) in enumerate(
        zip(all_embedding_study_keys, all_embedding_patient_ids)
    ):
        if str(documents.get(study_key, "")).strip():
            included_indices.append(index)
        else:
            excluded_rows.append(
                {
                    "study_key": study_key,
                    "deid_patient_id": patient_id,
                    "reason": "empty_findings_and_impression",
                }
            )
    if not included_indices:
        raise ValueError("No report-bearing train studies remain for indexing")
    output_root.mkdir(parents=True, exist_ok=True)
    exclusions_path = output_root / "excluded_empty_report_studies.csv"
    pd.DataFrame(
        excluded_rows,
        columns=("study_key", "deid_patient_id", "reason"),
    ).to_csv(exclusions_path, index=False)
    print(
        "[Retrieval] report eligibility "
        f"eligible={len(included_indices)} excluded_empty={len(excluded_rows)}"
    )

    print("[Retrieval] assembling index records")
    indexed = build_index_records(
        embeddings=embedding_payload["embeddings"][included_indices],
        study_keys=[all_embedding_study_keys[index] for index in included_indices],
        patient_ids=[
            all_embedding_patient_ids[index] for index in included_indices
        ],
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
            "checkpoint_sha256": checkpoint_meta["checkpoint_sha256"],
            "embeddings_cache": str(embeddings_cache),
            "model_ready_cache_root": checkpoint_meta[
                "model_ready_cache_root"
            ],
            "input_cache": checkpoint_meta.get("input_cache"),
            "vector_db_dir": str(vector_db_dir),
            "collection_name": args.collection_name,
            "split": args.split,
            "device": str(device),
            "batch_size": args.batch_size,
            "num_workers": args.num_workers,
            "max_studies": args.max_studies,
            "embedding_studies": len(all_embedding_study_keys),
            "excluded_empty_report_studies": len(excluded_rows),
            "exclusions_path": str(exclusions_path),
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
