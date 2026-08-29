"""Locate and download findings_fixed.json from the labels file index."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.data.catalog import build_findings_fixed_lookup_sql
from medagentx.data.constants import FINDINGS_FIXED_JSON_NAME
from medagentx.data.redivis_client import RedivisClient

_FILE_NAME_COLUMNS = ("file_name", "name", "filename", "path", "file_path")


def resolve_findings_fixed_file_id(
    client: RedivisClient,
    *,
    index_df: pd.DataFrame | None = None,
) -> str:
    """Return the unique Redivis file_id for findings_fixed.json."""
    if not isinstance(client, RedivisClient):
        raise ValueError("client must be a RedivisClient")

    if index_df is None:
        index_df = client.run_sql_query(
            build_findings_fixed_lookup_sql(),
            max_results=100,
        )

    if "file_id" not in index_df.columns:
        raise ValueError(
            "labels file index must contain file_id. "
            f"Available: {list(index_df.columns)}"
        )

    available_name_columns = [
        column for column in _FILE_NAME_COLUMNS if column in index_df.columns
    ]
    if not available_name_columns:
        raise ValueError(
            "labels file index has no recognized filename column. "
            f"Available: {list(index_df.columns)}"
        )

    target = FINDINGS_FIXED_JSON_NAME.lower()
    matched_indices: set[object] = set()

    for column in available_name_columns:
        values = index_df[column].fillna("").astype(str)
        basenames = values.map(lambda value: Path(value).name.lower())
        matched_indices.update(index_df.index[basenames == target].tolist())

    if not matched_indices:
        available = sorted(
            {
                str(value)
                for column in available_name_columns
                for value in index_df[column].dropna().tolist()
            }
        )
        raise RuntimeError(
            f"Could not find {FINDINGS_FIXED_JSON_NAME}. "
            f"Available files: {available}"
        )

    file_ids = {
        str(index_df.loc[index, "file_id"]).strip()
        for index in matched_indices
        if str(index_df.loc[index, "file_id"]).strip().lower()
        not in {"", "nan", "none"}
    }
    if len(file_ids) != 1:
        raise RuntimeError(
            f"Expected one file_id for {FINDINGS_FIXED_JSON_NAME}, "
            f"found {sorted(file_ids)}"
        )

    return next(iter(file_ids))


def ensure_findings_fixed_json(
    client: RedivisClient,
    output_path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Download findings_fixed.json if needed and return its local path."""
    if not isinstance(client, RedivisClient):
        raise ValueError("client must be a RedivisClient")

    output = Path(output_path)
    if output.exists() and output.stat().st_size > 0 and not overwrite:
        return output

    file_id = resolve_findings_fixed_file_id(client)
    result = client.download_raw_file(
        file_id=file_id,
        output_path=output,
        overwrite=overwrite,
        resume=True,
    )
    if result.status == "failed":
        raise RuntimeError(
            f"Failed to download {FINDINGS_FIXED_JSON_NAME}: {result.error}"
        )
    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError(
            f"Downloaded {FINDINGS_FIXED_JSON_NAME} is missing or empty"
        )
    return output
