"""Download eligible DICOM files via Redivis REST rawFiles."""

from __future__ import annotations

import sys
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


def download_eligible_dicoms(
    client: RedivisClient,
    eligible_rows: pd.DataFrame,
    output_root: str | Path,
    *,
    overwrite: bool = False,
    resume: bool = True,
) -> pd.DataFrame:
    """Download all eligible DICOM rows and return a status table.

    Locked behavior:
      - Uses REST-only RedivisClient.download_raw_file
      - Requires Stage A eligible rows (file_id + cleaned dicom_path)
      - Writes files under output_root / dicom_path
      - Does not invent paths or use the Redivis SDK
    """
    if not isinstance(client, RedivisClient):
        raise ValueError("client must be a RedivisClient")
    _require_columns(eligible_rows, REQUIRED_ELIGIBLE_COLUMNS)

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    status_rows: list[dict[str, Any]] = []

    for _, row in eligible_rows.iterrows():
        file_id = str(row["file_id"]).strip()
        dicom_path = str(row["dicom_path"]).strip()
        study_key = str(row["study_key"]).strip()
        patient_id = str(row["deid_patient_id"]).strip()

        if not file_id or file_id.lower() == "nan":
            status_rows.append(
                {
                    "deid_patient_id": patient_id,
                    "study_key": study_key,
                    "dicom_path": dicom_path,
                    "file_id": file_id,
                    "local_path": "",
                    "status": "failed",
                    "bytes_written": 0,
                    "error": "missing file_id",
                }
            )
            continue

        try:
            local_path = local_dicom_path(output_root, dicom_path)
            result: RedivisDownloadResult = client.download_raw_file(
                file_id=file_id,
                output_path=local_path,
                overwrite=overwrite,
                resume=resume,
            )
            status_rows.append(
                {
                    "deid_patient_id": patient_id,
                    "study_key": study_key,
                    "dicom_path": dicom_path,
                    "file_id": file_id,
                    "local_path": result.output_path,
                    "status": result.status,
                    "bytes_written": result.bytes_written,
                    "error": result.error,
                }
            )
        except Exception as exc:  # noqa: BLE001 - capture per-row failure
            status_rows.append(
                {
                    "deid_patient_id": patient_id,
                    "study_key": study_key,
                    "dicom_path": dicom_path,
                    "file_id": file_id,
                    "local_path": "",
                    "status": "failed",
                    "bytes_written": 0,
                    "error": str(exc),
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
