"""Download the complete CheXpert Plus PNG_train file-index table."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PurePosixPath
from typing import Any

import pandas as pd

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.data.competition_manifest import normalize_image_path
from medagentx.data.competition_manifest import fetch_png_train_index
from medagentx.data.redivis_client import RedivisClient


DEFAULT_PNG_DOWNLOAD_WORKERS = 8
DEFAULT_PNG_PROGRESS_EVERY = 250
REQUIRED_PNG_INDEX_COLUMNS = ("file_id", "file_name", "size", "md5_hash")


def _require_columns(frame: pd.DataFrame) -> None:
    missing = [
        column for column in REQUIRED_PNG_INDEX_COLUMNS if column not in frame
    ]
    if missing:
        raise ValueError(
            f"PNG_train index missing required columns {missing}; "
            f"available={list(frame.columns)}"
        )


def _canonical_download_path(file_name: Any) -> str:
    """Normalize a Redivis file name to the local patient/study/view path."""
    text = str(file_name).strip().replace("\\", "/")
    if not text or text.lower() == "nan":
        raise ValueError("PNG_train file_name must be non-empty")
    if PurePosixPath(text).is_absolute() or ".." in PurePosixPath(text).parts:
        raise ValueError(f"Unsafe PNG_train file_name: {file_name!r}")
    _split, canonical = normalize_image_path(
        text,
        field_name="PNG_train.file_name",
    )
    return canonical


def _expected_size(value: Any) -> int:
    try:
        size = int(float(str(value).strip()))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid PNG_train file size: {value!r}") from exc
    if size <= 0:
        raise ValueError(f"PNG_train file size must be positive: {value!r}")
    return size


def _prepare_index(index: pd.DataFrame) -> pd.DataFrame:
    """Validate and add deterministic canonical local paths."""
    _require_columns(index)
    rows = index.copy()
    rows["file_id"] = rows["file_id"].astype(str).str.strip()
    rows["file_name"] = rows["file_name"].astype(str).str.strip()
    if rows["file_id"].eq("").any() or rows["file_id"].str.lower().eq(
        "nan"
    ).any():
        raise ValueError("PNG_train index contains a missing file_id")
    if rows["file_name"].eq("").any() or rows["file_name"].str.lower().eq(
        "nan"
    ).any():
        raise ValueError("PNG_train index contains a missing file_name")
    if rows["file_id"].duplicated().any():
        raise ValueError("PNG_train index contains duplicate file_id values")

    rows["relative_path"] = rows["file_name"].map(_canonical_download_path)
    duplicate_paths = rows.loc[rows["relative_path"].duplicated(), "relative_path"]
    if not duplicate_paths.empty:
        examples = duplicate_paths.head(5).tolist()
        raise ValueError(
            "PNG_train index contains duplicate local paths: "
            f"{examples!r}"
        )
    rows["expected_size"] = rows["size"].map(_expected_size)
    return rows.reset_index(drop=True)


def _download_one(
    client: RedivisClient,
    row: dict[str, Any],
    output_root: Path,
    *,
    overwrite: bool,
    resume: bool,
) -> dict[str, Any]:
    relative_path = str(row["relative_path"])
    destination = output_root / relative_path
    expected_size = int(row["expected_size"])
    status = "downloaded"
    error = ""

    try:
        if destination.is_file() and not overwrite:
            existing_size = destination.stat().st_size
            if existing_size == expected_size:
                return {
                    "file_id": row["file_id"],
                    "file_name": row["file_name"],
                    "relative_path": relative_path,
                    "local_path": str(destination),
                    "expected_size": expected_size,
                    "bytes_written": existing_size,
                    "status": "already_exists",
                    "error": "",
                }
            if not resume:
                return {
                    "file_id": row["file_id"],
                    "file_name": row["file_name"],
                    "relative_path": relative_path,
                    "local_path": str(destination),
                    "expected_size": expected_size,
                    "bytes_written": existing_size,
                    "status": "failed",
                    "error": (
                        "existing file has the wrong size; remove "
                        "--no-resume or rerun with --overwrite"
                    ),
                }

        result = client.download_raw_file(
            file_id=str(row["file_id"]),
            output_path=destination,
            overwrite=overwrite,
            resume=resume,
        )
        bytes_written = int(result.bytes_written)
        if result.status == "failed":
            status = "failed"
            error = result.error
        elif bytes_written != expected_size:
            status = "failed"
            error = (
                f"downloaded {bytes_written} bytes, expected {expected_size}"
            )
        else:
            status = result.status
        return {
            "file_id": row["file_id"],
            "file_name": row["file_name"],
            "relative_path": relative_path,
            "local_path": str(destination),
            "expected_size": expected_size,
            "bytes_written": bytes_written,
            "status": status,
            "error": error,
        }
    except Exception as exc:  # noqa: BLE001 - retain per-file failure details
        return {
            "file_id": row["file_id"],
            "file_name": row["file_name"],
            "relative_path": relative_path,
            "local_path": str(destination),
            "expected_size": expected_size,
            "bytes_written": (
                destination.stat().st_size if destination.exists() else 0
            ),
            "status": "failed",
            "error": str(exc),
        }


def download_png_train(
    client: RedivisClient,
    output_root: str | Path,
    *,
    page_size: int = 100_000,
    max_workers: int = DEFAULT_PNG_DOWNLOAD_WORKERS,
    progress_every: int = DEFAULT_PNG_PROGRESS_EVERY,
    overwrite: bool = False,
    resume: bool = True,
    status_path: str | Path | None = None,
) -> pd.DataFrame:
    """Fetch the PNG index, download every file, and return status rows."""
    if not isinstance(client, RedivisClient):
        raise ValueError("client must be a RedivisClient")
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    if progress_every < 0:
        raise ValueError("progress_every must be >= 0")

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    index = _prepare_index(fetch_png_train_index(client, page_size=page_size))
    rows = index.to_dict(orient="records")
    results: list[dict[str, Any] | None] = [None] * len(rows)
    started = time.perf_counter()
    completed = 0
    bytes_written = 0

    def record(index_number: int, result: dict[str, Any]) -> None:
        nonlocal completed, bytes_written
        results[index_number] = result
        completed += 1
        bytes_written += int(result.get("bytes_written") or 0)
        if progress_every and (
            completed % progress_every == 0 or completed == len(rows)
        ):
            elapsed = max(time.perf_counter() - started, 1e-6)
            rate = completed / elapsed
            remaining = (len(rows) - completed) / rate if rate else 0.0
            print(
                f"[png_train] {completed}/{len(rows)} files "
                f"({bytes_written / 1e9:.2f} GB, {rate:.1f} files/s, "
                f"eta {remaining / 60:.1f} min)",
                flush=True,
            )

    if max_workers == 1:
        for index_number, row in enumerate(rows):
            record(
                index_number,
                _download_one(
                    client,
                    row,
                    output_root,
                    overwrite=overwrite,
                    resume=resume,
                ),
            )
    else:
        # Keep only a small batch of futures in memory; the table contains
        # 223k files, so submitting every row at once is unnecessarily costly.
        batch_size = max_workers * 4
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for batch_start in range(0, len(rows), batch_size):
                batch = rows[batch_start : batch_start + batch_size]
                futures = {
                    pool.submit(
                        _download_one,
                        client,
                        row,
                        output_root,
                        overwrite=overwrite,
                        resume=resume,
                    ): batch_start + offset
                    for offset, row in enumerate(batch)
                }
                for future in as_completed(futures):
                    index_number = futures[future]
                    record(index_number, future.result())

    status = pd.DataFrame([row for row in results if row is not None])
    if status_path is not None:
        status_path = Path(status_path)
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status.to_csv(status_path, index=False)
    return status
