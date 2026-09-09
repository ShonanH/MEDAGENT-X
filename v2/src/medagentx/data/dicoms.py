"""Download eligible DICOM files via Redivis REST rawFiles."""

from __future__ import annotations

import os
import shutil
import sys
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

import pandas as pd

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.data.redivis_client import RedivisClient, RedivisDownloadResult


REQUIRED_ELIGIBLE_COLUMNS = (
    "file_id",
    "dicom_path",
    "study_key",
    "deid_patient_id",
)

DEFAULT_DOWNLOAD_WORKERS = 1
DEFAULT_PROGRESS_EVERY = 250
DEFAULT_PENDING_DOWNLOAD_FACTOR = 2


def _require_columns(df: pd.DataFrame, columns: tuple[str, ...]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(
            f"eligible_rows missing required columns {missing}. "
            f"Available: {list(df.columns)}"
        )


def local_dicom_path(output_root: str | Path, dicom_path: str) -> Path:
    """Map a cleaned relative dicom_path to a local filesystem path."""
    root = Path(output_root)
    cleaned = str(dicom_path).strip().lstrip("/")
    if not cleaned:
        raise ValueError("dicom_path must be non-empty")
    if ".." in Path(cleaned).parts:
        raise ValueError(f"Unsafe dicom_path: {dicom_path!r}")
    return root / cleaned


def _download_one_row(
    client: RedivisClient,
    row: dict[str, Any],
    output_root: Path,
    *,
    overwrite: bool,
    resume: bool,
) -> dict[str, Any]:
    """Download one eligible view and return its status record."""
    file_id = str(row["file_id"]).strip()
    dicom_path = str(row["dicom_path"]).strip()
    study_key = str(row["study_key"]).strip()
    patient_id = str(row["deid_patient_id"]).strip()

    if not file_id or file_id.lower() == "nan":
        return {
            "deid_patient_id": patient_id,
            "study_key": study_key,
            "dicom_path": dicom_path,
            "file_id": file_id,
            "local_path": "",
            "status": "failed",
            "bytes_written": 0,
            "error": "missing file_id",
        }

    try:
        local_path = local_dicom_path(output_root, dicom_path)
        result: RedivisDownloadResult = client.download_raw_file(
            file_id=file_id,
            output_path=local_path,
            overwrite=overwrite,
            resume=resume,
        )
        return {
            "deid_patient_id": patient_id,
            "study_key": study_key,
            "dicom_path": dicom_path,
            "file_id": file_id,
            "local_path": result.output_path,
            "status": result.status,
            "bytes_written": result.bytes_written,
            "error": result.error,
        }
    except Exception as exc:  # noqa: BLE001 - capture per-row failure
        return {
            "deid_patient_id": patient_id,
            "study_key": study_key,
            "dicom_path": dicom_path,
            "file_id": file_id,
            "local_path": "",
            "status": "failed",
            "bytes_written": 0,
            "error": str(exc),
        }


def _print_download_progress(
    completed: int,
    total: int,
    *,
    started: float,
    bytes_written: int,
) -> None:
    elapsed = max(time.perf_counter() - started, 1e-6)
    rate = completed / elapsed
    remaining = (total - completed) / rate if rate > 0 else 0.0
    print(
        f"[dicoms] {completed}/{total} files "
        f"({bytes_written / 1e9:.2f} GB, {rate:.1f} files/s, "
        f"eta {remaining / 60:.1f} min)",
        flush=True,
    )


def download_eligible_dicoms(
    client: RedivisClient,
    eligible_rows: pd.DataFrame,
    output_root: str | Path,
    *,
    overwrite: bool = False,
    resume: bool = True,
    max_workers: int = DEFAULT_DOWNLOAD_WORKERS,
    progress_every: int = DEFAULT_PROGRESS_EVERY,
) -> pd.DataFrame:
    """Download all eligible DICOM rows and return a status table.

    Locked behavior:
      - Uses REST-only RedivisClient.download_raw_file
      - Requires Stage A eligible rows (file_id + cleaned dicom_path)
      - Writes files under output_root / dicom_path
      - Does not invent paths or use the Redivis SDK

    Downloads may run concurrently, but the returned status table always
    follows the input row order so artifacts stay reproducible.
    """
    if not isinstance(client, RedivisClient):
        raise ValueError("client must be a RedivisClient")
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    if progress_every < 0:
        raise ValueError("progress_every must be >= 0")
    _require_columns(eligible_rows, REQUIRED_ELIGIBLE_COLUMNS)

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    rows = eligible_rows.to_dict(orient="records")
    total = len(rows)
    results: list[dict[str, Any] | None] = [None] * total
    started = time.perf_counter()
    completed = 0
    bytes_written = 0

    def record(index: int, status: dict[str, Any]) -> None:
        nonlocal completed, bytes_written
        results[index] = status
        completed += 1
        bytes_written += int(status.get("bytes_written") or 0)
        if progress_every and (
            completed % progress_every == 0 or completed == total
        ):
            _print_download_progress(
                completed,
                total,
                started=started,
                bytes_written=bytes_written,
            )

    if max_workers == 1:
        for index, row in enumerate(rows):
            record(
                index,
                _download_one_row(
                    client,
                    row,
                    output_root,
                    overwrite=overwrite,
                    resume=resume,
                ),
            )
    else:
        # Keep only a small bounded window of futures alive. Enqueuing the full
        # CheXpert train set at once consumes substantial memory before any
        # image has finished downloading.
        pending_limit = max_workers * DEFAULT_PENDING_DOWNLOAD_FACTOR
        next_index = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            pending: dict[Future[dict[str, Any]], int] = {}

            def submit_next() -> bool:
                nonlocal next_index
                if next_index >= total:
                    return False
                index = next_index
                next_index += 1
                pending[
                    pool.submit(
                        _download_one_row,
                        client,
                        rows[index],
                        output_root,
                        overwrite=overwrite,
                        resume=resume,
                    )
                ] = index
                return True

            while len(pending) < pending_limit and submit_next():
                pass

            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    index = pending.pop(future)
                    record(index, future.result())
                    submit_next()

    return pd.DataFrame([status for status in results if status is not None])


def reuse_existing_dicoms(
    eligible_rows: pd.DataFrame,
    source_root: str | Path,
    output_root: str | Path,
) -> pd.DataFrame:
    """Hardlink matching DICOMs from an earlier cohort, copying as fallback."""
    _require_columns(eligible_rows, REQUIRED_ELIGIBLE_COLUMNS)
    source_root = Path(source_root)
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    status_rows: list[dict[str, Any]] = []
    for _, row in eligible_rows.iterrows():
        patient_id = str(row["deid_patient_id"]).strip()
        study_key = str(row["study_key"]).strip()
        dicom_path = str(row["dicom_path"]).strip()
        file_id = str(row["file_id"]).strip()
        destination = local_dicom_path(output_root, dicom_path)
        source = local_dicom_path(source_root, dicom_path)
        status = "not_found"
        error = ""
        bytes_written = 0

        try:
            if destination.is_file() and destination.stat().st_size > 0:
                status = "already_exists"
                bytes_written = destination.stat().st_size
            elif source.is_file() and source.stat().st_size > 0:
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    destination.unlink()
                try:
                    os.link(source, destination)
                    status = "reused_hardlink"
                except OSError:
                    shutil.copy2(source, destination)
                    status = "reused_copy"
                bytes_written = destination.stat().st_size
        except Exception as exc:  # noqa: BLE001 - capture per-row reuse failure
            status = "failed"
            error = str(exc)

        status_rows.append(
            {
                "deid_patient_id": patient_id,
                "study_key": study_key,
                "dicom_path": dicom_path,
                "file_id": file_id,
                "local_path": str(destination),
                "status": status,
                "bytes_written": bytes_written,
                "error": error,
            }
        )

    return pd.DataFrame(status_rows)


def summarize_download_status(status_df: pd.DataFrame) -> dict[str, int]:
    """Count download outcomes for a quick Stage A summary."""
    if status_df.empty:
        return {"total": 0}

    counts = status_df["status"].astype(str).value_counts().to_dict()
    counts["total"] = int(len(status_df))
    return {str(k): int(v) for k, v in counts.items()}
