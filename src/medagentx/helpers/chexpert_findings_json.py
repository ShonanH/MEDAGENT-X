"""
Load per-image CheXpert labels from findings_fixed.json (JSONL on Redivis).

Each line is one image:
  {"path_to_image": "train/patient.../view1_frontal.jpg", "Atelectasis": 1.0, ...}
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from medagentx.fusion.chexpert_labels import normalize_path_to_image
from medagentx.fusion.constants import ALL_CHEXPERT_LABELS
from medagentx.helpers.redivis_query_client import run_redivis_export
from medagentx.helpers.redivis_rest_client import RedivisRestClient

FINDINGS_FIXED_FILENAME = "findings_fixed.json"


def resolve_findings_fixed_file_id(file_index_df: pd.DataFrame | None = None) -> str:
    if file_index_df is None:
        file_index_df = run_redivis_export("chexpert_labels_file_index", max_results=100)

    if "file_name" not in file_index_df.columns:
        raise RuntimeError("CheXpert labels file index is missing file_name.")

    matches = file_index_df[
        file_index_df["file_name"].astype(str).str.lower() == FINDINGS_FIXED_FILENAME
    ]
    if matches.empty:
        available = ", ".join(file_index_df["file_name"].astype(str).tolist())
        raise RuntimeError(
            f"Could not find {FINDINGS_FIXED_FILENAME} in CheXpert labels file index. "
            f"Available files: {available}"
        )

    file_id = str(matches.iloc[0]["file_id"]).strip()
    if not file_id:
        raise RuntimeError(f"File index row for {FINDINGS_FIXED_FILENAME} has no file_id.")
    return file_id


def download_findings_fixed_json(
    output_path: Path,
    *,
    file_id: str | None = None,
    overwrite: bool = False,
) -> Path:
    output_path = Path(output_path)
    if output_path.exists() and not overwrite:
        return output_path

    resolved_file_id = file_id or resolve_findings_fixed_file_id()
    client = RedivisRestClient.from_env()
    result = client.download_raw_file(
        file_id=resolved_file_id,
        output_path=output_path,
        overwrite=overwrite,
    )
    if result.status == "failed":
        raise RuntimeError(
            f"Failed to download {FINDINGS_FIXED_FILENAME} ({resolved_file_id}): {result.error}"
        )
    return output_path


def parse_findings_jsonl_record(line: str) -> dict | None:
    stripped = line.strip()
    if not stripped:
        return None
    record = json.loads(stripped)
    if not isinstance(record, dict):
        raise ValueError("findings_fixed.json lines must be JSON objects.")
    return record


def load_findings_labels_for_paths(
    json_path: Path,
    path_to_images: Iterable[str],
) -> pd.DataFrame:
    wanted = {
        normalize_path_to_image(path)
        for path in path_to_images
        if normalize_path_to_image(path)
    }
    if not wanted:
        return pd.DataFrame(columns=["path_to_image", *ALL_CHEXPERT_LABELS])

    rows: list[dict] = []
    with Path(json_path).open(encoding="utf-8") as handle:
        for line in handle:
            record = parse_findings_jsonl_record(line)
            if record is None:
                continue
            key = normalize_path_to_image(record.get("path_to_image"))
            if key in wanted:
                rows.append(record)

    if not rows:
        return pd.DataFrame(columns=["path_to_image", *ALL_CHEXPERT_LABELS])

    labels_df = pd.DataFrame(rows)
    keep_columns = ["path_to_image"] + [
        label for label in ALL_CHEXPERT_LABELS if label in labels_df.columns
    ]
    return labels_df[keep_columns].drop_duplicates(subset=["path_to_image"], keep="last")


def ensure_findings_fixed_json(
    json_path: Path,
    *,
    download: bool = True,
    overwrite: bool = False,
    file_id: str | None = None,
) -> Path:
    json_path = Path(json_path)
    if json_path.exists() and not overwrite:
        return json_path
    if not download:
        raise FileNotFoundError(
            f"CheXpert findings JSON not found at {json_path}. "
            "Pass --download-findings or provide --findings-json."
        )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    return download_findings_fixed_json(json_path, file_id=file_id, overwrite=overwrite)
