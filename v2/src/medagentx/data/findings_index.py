"""Load and query findings_fixed.json for per-image CheXpert labels."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.data.paths import path_to_image_join_key
from medagentx.labels.constants import ALL_CHEXPERT_LABELS
from medagentx.labels.parse import parse_chexpert_raw_value


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    try:
        return bool(value != value)
    except Exception:
        return False


def _canonical_raw_value(value: Any) -> Any:
    """Normalize raw values for duplicate-record comparison."""
    if _is_missing(value):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped in {"1", "0", "-1"}:
            return stripped
        return stripped
    if isinstance(value, bool):
        return value
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return value
    if numeric != numeric:
        return None
    if numeric in (0.0, 1.0, -1.0):
        return int(numeric) if numeric.is_integer() else numeric
    return value


@dataclass(frozen=True)
class FindingsRecord:
    """One findings_fixed.json image record."""

    path_to_image: str
    values: dict[str, Any]
    missing_label_keys: int


@dataclass(frozen=True)
class FindingsIndex:
    """In-memory index of findings_fixed.json keyed by path_to_image."""

    records: dict[str, FindingsRecord]
    conflicting_paths: frozenset[str]

    def get(self, path_to_image: str) -> FindingsRecord | None:
        key = path_to_image_join_key(path_to_image)
        if not key:
            return None
        if key in self.conflicting_paths:
            return None
        return self.records.get(key)

    def has_conflict(self, path_to_image: str) -> bool:
        key = path_to_image_join_key(path_to_image)
        return bool(key) and key in self.conflicting_paths

    def build_view_raw_map(self, path_to_image: str) -> dict[str, Any] | None:
        """Return all 14 labels, using None for omitted keys (CheXpert blank)."""
        record = self.get(path_to_image)
        if record is None:
            return None
        return {
            label: record.values.get(label)
            for label in ALL_CHEXPERT_LABELS
        }

    def validate_view_raw_map(self, raw_map: dict[str, Any]) -> str | None:
        """Return an error message when any present value is invalid."""
        try:
            for label in ALL_CHEXPERT_LABELS:
                parse_chexpert_raw_value(raw_map[label])
        except ValueError as exc:
            return str(exc)
        return None

    @classmethod
    def from_jsonl(cls, json_path: str | Path) -> "FindingsIndex":
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"findings_fixed.json not found: {path}")

        grouped: dict[str, list[dict[str, Any]]] = {}
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                record = json.loads(stripped)
                if not isinstance(record, dict):
                    raise ValueError(
                        f"{path}: line {line_number} must be a JSON object"
                    )
                key = path_to_image_join_key(record.get("path_to_image"))
                if not key:
                    continue
                grouped.setdefault(key, []).append(record)

        records: dict[str, FindingsRecord] = {}
        conflicting_paths: set[str] = set()

        for key, items in grouped.items():
            if len(items) > 1 and not _records_equivalent(items):
                conflicting_paths.add(key)
                continue

            source = items[-1]
            values = {
                label: source[label]
                for label in ALL_CHEXPERT_LABELS
                if label in source
            }
            missing_label_keys = sum(
                1 for label in ALL_CHEXPERT_LABELS if label not in source
            )
            records[key] = FindingsRecord(
                path_to_image=key,
                values=values,
                missing_label_keys=missing_label_keys,
            )

        return cls(
            records=records,
            conflicting_paths=frozenset(conflicting_paths),
        )

    @classmethod
    def subset_for_paths(
        cls,
        json_path: str | Path,
        path_to_images: Iterable[str],
    ) -> "FindingsIndex":
        """Load only the requested image paths from a large JSONL file."""
        wanted = {
            path_to_image_join_key(path)
            for path in path_to_images
            if path_to_image_join_key(path)
        }
        if not wanted:
            return cls(records={}, conflicting_paths=frozenset())

        grouped: dict[str, list[dict[str, Any]]] = {}
        path = Path(json_path)
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                record = json.loads(stripped)
                if not isinstance(record, dict):
                    raise ValueError(
                        f"{path}: line {line_number} must be a JSON object"
                    )
                key = path_to_image_join_key(record.get("path_to_image"))
                if key not in wanted:
                    continue
                grouped.setdefault(key, []).append(record)

        records: dict[str, FindingsRecord] = {}
        conflicting_paths: set[str] = set()
        for key, items in grouped.items():
            if len(items) > 1 and not _records_equivalent(items):
                conflicting_paths.add(key)
                continue
            source = items[-1]
            values = {
                label: source[label]
                for label in ALL_CHEXPERT_LABELS
                if label in source
            }
            missing_label_keys = sum(
                1 for label in ALL_CHEXPERT_LABELS if label not in source
            )
            records[key] = FindingsRecord(
                path_to_image=key,
                values=values,
                missing_label_keys=missing_label_keys,
            )

        return cls(
            records=records,
            conflicting_paths=frozenset(conflicting_paths),
        )


def _records_equivalent(records: list[dict[str, Any]]) -> bool:
    """Return True when duplicate JSONL rows carry identical label values."""
    canonical_rows = []
    for record in records:
        canonical_rows.append(
            {
                label: _canonical_raw_value(record.get(label))
                for label in ALL_CHEXPERT_LABELS
            }
        )

    first = canonical_rows[0]
    return all(row == first for row in canonical_rows[1:])


def summarize_findings_index(index: FindingsIndex) -> dict[str, int]:
    """Return quick counts for CLI summaries."""
    missing_key_rows = sum(
        1 for record in index.records.values() if record.missing_label_keys > 0
    )
    return {
        "indexed_images": len(index.records),
        "conflicting_images": len(index.conflicting_paths),
        "images_with_missing_label_keys": missing_key_rows,
    }
