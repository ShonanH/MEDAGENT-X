"""Build and audit the competition-aligned CheXpert Plus manifest.

This module intentionally stops at data products. It does not train a model,
choose a checkpoint, or alter any existing cohort artifacts.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from PIL import Image

from medagentx.data.catalog import (
    COMPETITION_METADATA_COLUMNS,
    build_competition_metadata_sql,
    build_png_train_index_sql,
)
from medagentx.data.constants import (
    REDIVIS_CHEXPERT_LABELS_INDEX_TABLE_ID,
    REDIVIS_DATASET_ID,
    REDIVIS_METADATA_TABLE_ID,
    REDIVIS_PNG_TRAIN_INDEX_TABLE_ID,
)
from medagentx.data.findings import ensure_findings_fixed_json
from medagentx.data.redivis_client import RedivisClient
from medagentx.evaluation.chexpert_competition import competition_study_key
from medagentx.labels.constants import (
    ALL_CHEXPERT_LABELS,
    CHEXPERT_COMPETITION_LABELS,
)
from medagentx.labels.parse import parse_chexpert_raw_value
from medagentx.labels.statuses import LabelStatus


DEFAULT_OUTPUT_ROOT = Path("v2/artifacts/chexpert_competition_v1")
DEFAULT_FINDINGS_PATH = DEFAULT_OUTPUT_ROOT / "source" / "findings_fixed.json"
TRAIN_SPLIT = "train"
VALID_SPLIT = "valid"
SUPPORTED_SOURCE_SPLITS = frozenset({TRAIN_SPLIT, VALID_SPLIT})
EXPECTED_VALID_VIEWS = 234
EXPECTED_VALID_STUDIES = 200
EXPECTED_EXPERT_TEST_STUDIES = 500

_IMAGE_PATH_RE = re.compile(
    r"^(patient\d+)/(study\d+)/(view\d+_(?:frontal|lateral))\.(jpg|png)$",
    re.IGNORECASE,
)
_STATUS_PRIORITY = {
    LabelStatus.PRESENT: 3,
    LabelStatus.UNCERTAIN: 2,
    LabelStatus.ABSENT: 1,
    LabelStatus.UNMENTIONED: 0,
}
_POLICY_MODES = {
    "ignore_uncertain": "chexpert_ignore_uncertain_v1",
    "u_zero": "chexpert_u_zero_v1",
    "u_one": "chexpert_u_one_v1",
}


class CompetitionManifestError(ValueError):
    """Raised when the competition manifest contract is violated."""


def normalize_image_path(
    value: Any,
    *,
    field_name: str,
    expected_split: str | None = None,
    require_split: bool = False,
) -> tuple[str | None, str]:
    """Return source split and canonical relative PNG path."""
    if value is None:
        raise CompetitionManifestError(f"{field_name} must not be null")

    text = str(value).strip().replace("\\", "/").lstrip("./")
    if not text or text.lower() == "nan":
        raise CompetitionManifestError(f"{field_name} must not be blank")

    parts = text.split("/")
    source_split: str | None = None
    if len(parts) == 4 and parts[0].lower() in SUPPORTED_SOURCE_SPLITS:
        source_split = parts[0].lower()
        relative = "/".join(parts[1:])
    elif len(parts) == 3:
        relative = text
    else:
        raise CompetitionManifestError(
            f"Unsupported {field_name} path shape: {value!r}"
        )

    if require_split and source_split is None:
        raise CompetitionManifestError(
            f"{field_name} must include a source split: {value!r}"
        )
    if expected_split is not None and source_split != expected_split:
        raise CompetitionManifestError(
            f"{field_name} split mismatch: expected={expected_split!r}, "
            f"observed={source_split!r}, value={value!r}"
        )

    match = _IMAGE_PATH_RE.fullmatch(relative)
    if match is None:
        raise CompetitionManifestError(
            f"Unsupported {field_name} image path: {value!r}"
        )

    patient, study, view, _extension = match.groups()
    canonical = f"{patient.lower()}/{study.lower()}/{view.lower()}.png"
    return source_split, canonical


def study_key_from_image_path(canonical_path: str) -> str:
    """Return the verified path-derived patient/study key."""
    parts = canonical_path.split("/")
    if len(parts) != 3:
        raise CompetitionManifestError(
            f"Canonical image path has an invalid shape: {canonical_path!r}"
        )
    return f"{parts[0]}/{parts[1]}"


def _require_columns(
    frame: pd.DataFrame,
    required: tuple[str, ...] | list[str],
    frame_name: str,
) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise CompetitionManifestError(
            f"{frame_name} missing required columns {missing}; "
            f"available={list(frame.columns)}"
        )


def _fetch_paged(
    client: RedivisClient,
    builder: Callable[..., str],
    *,
    page_size: int,
    label: str,
) -> pd.DataFrame:
    if page_size <= 0:
        raise ValueError("page_size must be > 0")

    frames: list[pd.DataFrame] = []
    offset = 0
    while True:
        page = client.run_sql_query(
            builder(limit=page_size, offset=offset),
            max_results=page_size,
        )
        if page.empty:
            break
        frames.append(page)
        offset += len(page)
        print(f"[{label}] fetched {offset} rows")
        if len(page) < page_size:
            break

    if not frames:
        raise CompetitionManifestError(f"{label} returned no rows")
    return pd.concat(frames, ignore_index=True)


def fetch_competition_metadata(
    client: RedivisClient,
    *,
    page_size: int = 50_000,
) -> pd.DataFrame:
    """Fetch train and released-valid metadata identity rows."""
    frame = _fetch_paged(
        client,
        lambda **kwargs: build_competition_metadata_sql(
            columns=COMPETITION_METADATA_COLUMNS,
            **kwargs,
        ),
        page_size=page_size,
        label="metadata",
    )
    _require_columns(frame, COMPETITION_METADATA_COLUMNS, "metadata")
    return frame


def fetch_png_train_index(
    client: RedivisClient,
    *,
    page_size: int = 100_000,
) -> pd.DataFrame:
    """Fetch the complete PNG_train file index."""
    frame = _fetch_paged(
        client,
        build_png_train_index_sql,
        page_size=page_size,
        label="png_train",
    )
    _require_columns(
        frame,
        ("file_id", "file_name", "size", "md5_hash"),
        "png_train",
    )
    return frame


def _parse_findings_jsonl(path: str | Path) -> dict[str, Any]:
    """Parse every findings JSONL row with strict schema/value validation."""
    records: dict[tuple[str, str], dict[str, Any]] = {}
    raw_counts: dict[str, Counter[str]] = {
        split: Counter() for split in SUPPORTED_SOURCE_SPLITS
    }
    split_rows: Counter[str] = Counter()
    schema_counts: Counter[tuple[str, ...]] = Counter()
    malformed: list[dict[str, Any]] = []
    duplicate_paths: list[dict[str, Any]] = []
    invalid_values: list[dict[str, Any]] = []
    path_examples: dict[str, list[str]] = defaultdict(list)

    expected_keys = {"path_to_image", *ALL_CHEXPERT_LABELS}
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                malformed.append(
                    {"line": line_number, "reason": f"invalid_json: {exc}"}
                )
                continue
            if not isinstance(record, dict):
                malformed.append(
                    {"line": line_number, "reason": "record_is_not_object"}
                )
                continue

            schema_counts[tuple(sorted(record))] += 1
            actual_keys = set(record)
            if actual_keys != expected_keys:
                malformed.append(
                    {
                        "line": line_number,
                        "reason": "label_schema_mismatch",
                        "missing": sorted(expected_keys - actual_keys),
                        "unexpected": sorted(actual_keys - expected_keys),
                    }
                )
                continue

            raw_path = record["path_to_image"]
            try:
                source_split, canonical = normalize_image_path(
                    raw_path,
                    field_name="path_to_image",
                    require_split=True,
                )
            except CompetitionManifestError as exc:
                malformed.append(
                    {"line": line_number, "reason": str(exc), "path": raw_path}
                )
                continue

            assert source_split is not None
            split_rows[source_split] += 1
            if len(path_examples[source_split]) < 5:
                path_examples[source_split].append(str(raw_path))

            key = (source_split, canonical)
            if key in records:
                duplicate_paths.append(
                    {
                        "line": line_number,
                        "split": source_split,
                        "canonical_path": canonical,
                    }
                )
                continue

            values = {label: record[label] for label in ALL_CHEXPERT_LABELS}
            for label, value in values.items():
                try:
                    parse_chexpert_raw_value(value)
                except ValueError as exc:
                    invalid_values.append(
                        {
                            "line": line_number,
                            "split": source_split,
                            "canonical_path": canonical,
                            "label": label,
                            "value": repr(value),
                            "reason": str(exc),
                        }
                    )
                    continue
                if value is None:
                    token = "null"
                elif isinstance(value, str):
                    token = value.strip()
                else:
                    token = str(int(float(value)))
                raw_counts[source_split][f"{label}:{token}"] += 1

            records[key] = {
                "path_to_image": str(raw_path),
                "canonical_path": canonical,
                "source_split": source_split,
                "values": values,
            }

    if malformed or duplicate_paths or invalid_values:
        raise CompetitionManifestError(
            "findings_fixed.json failed strict validation: "
            f"malformed={len(malformed)}, "
            f"duplicate_paths={len(duplicate_paths)}, "
            f"invalid_values={len(invalid_values)}"
        )

    return {
        "records": records,
        "split_rows": dict(split_rows),
        "raw_counts": {
            split: dict(counts) for split, counts in raw_counts.items()
        },
        "schema_counts": {
            "|".join(keys): count for keys, count in schema_counts.items()
        },
        "path_examples": dict(path_examples),
    }


def _build_png_lookup(
    png_frame: pd.DataFrame,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Build a strict canonical PNG lookup and content-duplicate audit."""
    lookup: dict[str, dict[str, Any]] = {}
    duplicate_paths: list[str] = []
    for row in png_frame.to_dict(orient="records"):
        for field in ("file_id", "file_name", "size", "md5_hash"):
            value = row.get(field)
            if value is None or pd.isna(value) or not str(value).strip():
                raise CompetitionManifestError(
                    f"PNG_train has a missing {field}: {row!r}"
                )
        _, canonical = normalize_image_path(
            row["file_name"],
            field_name="file_name",
        )
        if canonical in lookup:
            duplicate_paths.append(canonical)
        lookup[canonical] = row

    if duplicate_paths:
        raise CompetitionManifestError(
            "PNG_train contains duplicate canonical filenames: "
            f"{duplicate_paths[:10]}"
        )

    by_hash: dict[str, list[str]] = defaultdict(list)
    for row in png_frame.to_dict(orient="records"):
        by_hash[str(row["md5_hash"])].append(str(row["file_name"]))
    duplicate_hashes = {
        digest: sorted(names)
        for digest, names in by_hash.items()
        if len(names) > 1
    }
    return lookup, {
        "duplicate_md5_hash_count": len(duplicate_hashes),
        "duplicate_md5_hashes": duplicate_hashes,
    }


def _audit_local_pngs(
    view_frame: pd.DataFrame,
    image_root: Path,
) -> dict[str, Any]:
    """Verify existence and readability of every training PNG."""
    missing: list[str] = []
    unreadable: list[dict[str, str]] = []
    for relative in view_frame["image_path_relative"].astype(str):
        local_path = image_root / relative
        if not local_path.is_file():
            missing.append(str(local_path))
            continue
        try:
            with Image.open(local_path) as image:
                image.verify()
        except Exception as exc:
            unreadable.append({"path": str(local_path), "error": str(exc)})

    if missing or unreadable:
        raise CompetitionManifestError(
            "Local PNG audit failed: "
            f"missing={len(missing)}, unreadable={len(unreadable)}"
        )
    return {
        "checked": int(len(view_frame)),
        "missing": 0,
        "unreadable": 0,
    }


def _policy_target_mask(
    raw_value: Any,
    *,
    label: str,
    uncertainty_policy: str,
) -> tuple[float | None, int]:
    status = parse_chexpert_raw_value(raw_value)
    if status is LabelStatus.PRESENT:
        return 1.0, 1
    if status is LabelStatus.ABSENT:
        return 0.0, 1
    if status is LabelStatus.UNMENTIONED:
        return None, 0
    if uncertainty_policy == "ignore_uncertain":
        return None, 0
    if uncertainty_policy == "u_zero":
        return 0.0, 1
    if uncertainty_policy == "u_one":
        return 1.0, 1
    raise ValueError(
        f"Unsupported uncertainty policy {uncertainty_policy!r} for {label!r}"
    )


def _build_study_labels(
    train_views: pd.DataFrame,
    label_records: dict[tuple[str, str], dict[str, Any]],
    *,
    uncertainty_policy: str,
) -> pd.DataFrame:
    """Aggregate per-view labels into one policy-tagged row per study."""
    if uncertainty_policy not in _POLICY_MODES:
        raise ValueError(
            f"uncertainty_policy must be one of {sorted(_POLICY_MODES)}"
        )

    rows: list[dict[str, Any]] = []
    for study_key, study_rows in train_views.groupby("study_key", sort=True):
        first = study_rows.iloc[0]
        out: dict[str, Any] = {
            "study_key": study_key,
            "patient_id": first["patient_id"],
            "deid_patient_id": first["deid_patient_id"],
            "view_count": int(len(study_rows)),
            "label_policy_version": _POLICY_MODES[uncertainty_policy],
        }

        for label in CHEXPERT_COMPETITION_LABELS:
            view_values: list[Any] = []
            view_statuses: list[LabelStatus] = []
            for path in study_rows["canonical_image_path"]:
                record = label_records.get((TRAIN_SPLIT, path))
                if record is None:
                    raise CompetitionManifestError(
                        f"Missing training label record for {path!r}"
                    )
                value = record["values"][label]
                view_values.append(value)
                view_statuses.append(parse_chexpert_raw_value(value))

            selected_index = max(
                range(len(view_statuses)),
                key=lambda index: _STATUS_PRIORITY[view_statuses[index]],
            )
            raw_value = view_values[selected_index]
            slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
            target, mask = _policy_target_mask(
                raw_value,
                label=label,
                uncertainty_policy=uncertainty_policy,
            )
            out[f"raw_{slug}"] = raw_value
            out[f"target_{slug}"] = target
            out[f"mask_{slug}"] = mask
            out[f"conflict_{slug}"] = int(len(set(view_statuses)) > 1)

        rows.append(out)

    result = pd.DataFrame(rows)
    if result.empty:
        raise CompetitionManifestError("No study labels were produced")
    if result["study_key"].duplicated().any():
        raise CompetitionManifestError("Duplicate study keys in study_labels")
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _test_patient_keys(test_groundtruth: Path) -> tuple[set[str], int]:
    if not test_groundtruth.is_file():
        raise FileNotFoundError(
            f"Expert test groundtruth not found: {test_groundtruth}"
        )
    groundtruth = pd.read_csv(test_groundtruth, dtype=str)
    _require_columns(groundtruth, ("Study",), "expert_test_groundtruth")
    keys = {
        competition_study_key(value, field_name="Study")
        for value in groundtruth["Study"]
    }
    if len(keys) != len(groundtruth):
        raise CompetitionManifestError(
            "Expert test groundtruth contains duplicate study keys"
        )
    if len(keys) != EXPECTED_EXPERT_TEST_STUDIES:
        raise CompetitionManifestError(
            "Expert test groundtruth study count mismatch: "
            f"expected={EXPECTED_EXPERT_TEST_STUDIES}, observed={len(keys)}"
        )
    return {key.split("/", maxsplit=1)[0] for key in keys}, len(keys)


def build_competition_manifest(
    client: RedivisClient,
    *,
    image_root: str | Path,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    findings_json: str | Path | None = None,
    expert_test_groundtruth: str | Path = "v2/data/groundtruth.csv",
    uncertainty_policy: str = "ignore_uncertain",
    metadata_page_size: int = 50_000,
    png_page_size: int = 100_000,
) -> dict[str, Path]:
    """Fetch, validate, and write the competition manifest artifacts."""
    if not isinstance(client, RedivisClient):
        raise ValueError("client must be a RedivisClient")

    image_root = Path(image_root)
    root = Path(output_root)
    manifests = root / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)

    metadata = fetch_competition_metadata(client, page_size=metadata_page_size)
    png = fetch_png_train_index(client, page_size=png_page_size)

    findings_path = (
        Path(findings_json)
        if findings_json
        else root / "source" / "findings_fixed.json"
    )
    if not findings_path.is_file():
        ensure_findings_fixed_json(client, findings_path)
    findings = _parse_findings_jsonl(findings_path)
    png_lookup, duplicate_audit = _build_png_lookup(png)

    metadata_records: list[dict[str, Any]] = []
    seen_metadata_keys: set[tuple[str, str]] = set()
    excluded_rows: list[dict[str, Any]] = []
    source_split_counts: Counter[str] = Counter()

    for raw in metadata.to_dict(orient="records"):
        split = str(raw["split"]).strip().lower()
        if split not in SUPPORTED_SOURCE_SPLITS:
            raise CompetitionManifestError(
                f"Unsupported metadata split: {split!r}"
            )
        for field in ("path_to_image", "deid_patient_id", "frontal_lateral"):
            value = raw.get(field)
            if value is None or pd.isna(value) or not str(value).strip():
                raise CompetitionManifestError(
                    f"Metadata has a missing {field}: {raw!r}"
                )

        # AP/PA is a frontal-view projection attribute. CheXpert metadata
        # correctly leaves it null for lateral views, so only require it when
        # the image is marked as frontal (or has an unknown view type).
        view_type = str(raw["frontal_lateral"]).strip().lower()
        ap_pa = raw.get("ap_pa")
        if view_type != "lateral" and (
            ap_pa is None or pd.isna(ap_pa) or not str(ap_pa).strip()
        ):
            raise CompetitionManifestError(
                f"Metadata has a missing ap_pa for non-lateral view: {raw!r}"
            )

        _, canonical = normalize_image_path(
            raw["path_to_image"],
            field_name="path_to_image",
            expected_split=split,
            require_split=True,
        )
        key = (split, canonical)
        if key in seen_metadata_keys:
            raise CompetitionManifestError(
                f"Duplicate metadata image key: {split}/{canonical}"
            )
        seen_metadata_keys.add(key)

        patient_id, study_id, view_name = canonical.split("/")
        study_key = f"{patient_id}/{study_id}"
        metadata_patient = str(raw["deid_patient_id"]).strip().lower()
        if metadata_patient != patient_id:
            raise CompetitionManifestError(
                f"Path patient does not match deid_patient_id for {canonical!r}: "
                f"{patient_id!r} != {metadata_patient!r}"
            )

        source_split_counts[split] += 1
        if split != TRAIN_SPLIT:
            excluded_rows.append(
                {
                    "split": split,
                    "study_key": study_key,
                    "patient_id": patient_id,
                    "canonical_image_path": canonical,
                    "source_path": raw["path_to_image"],
                    "reason": "released_validation_split_not_training_source",
                }
            )
            continue

        png_row = png_lookup.get(canonical)
        if png_row is None:
            raise CompetitionManifestError(
                f"Training metadata image missing from PNG_train: {canonical!r}"
            )

        metadata_records.append(
            {
                "patient_id": patient_id,
                "study_id": study_id,
                "study_key": study_key,
                "image_id": str(png_row["file_id"]),
                "image_path_relative": canonical,
                "image_path": str(image_root / canonical),
                "view": view_name.rsplit("_", maxsplit=1)[-1],
                "split": TRAIN_SPLIT,
                "source_split": split,
                "path_to_image": str(raw["path_to_image"]),
                "deid_patient_id": str(raw["deid_patient_id"]),
                "frontal_lateral": raw["frontal_lateral"],
                "ap_pa": raw["ap_pa"],
                "patient_report_date_order": raw["patient_report_date_order"],
                "section_accession_number": raw["section_accession_number"],
                "md5_hash": str(png_row["md5_hash"]),
            }
        )

    train_views = pd.DataFrame(metadata_records)
    if train_views.empty:
        raise CompetitionManifestError("No training view rows were produced")
    if train_views["canonical_image_path"].duplicated().any():
        raise CompetitionManifestError("Duplicate canonical training image paths")
    if train_views["image_id"].duplicated().any():
        raise CompetitionManifestError("Duplicate PNG file_ids in training manifest")

    train_metadata_paths = set(train_views["canonical_image_path"])
    png_paths = set(png_lookup)
    if train_metadata_paths != png_paths:
        raise CompetitionManifestError(
            "PNG_train and train metadata sets differ: "
            f"metadata_missing={len(train_metadata_paths - png_paths)}, "
            f"png_missing={len(png_paths - train_metadata_paths)}"
        )

    metadata_paths_by_split: dict[str, set[str]] = defaultdict(set)
    for raw in metadata.to_dict(orient="records"):
        split = str(raw["split"]).strip().lower()
        _, canonical = normalize_image_path(
            raw["path_to_image"],
            field_name="path_to_image",
            expected_split=split,
            require_split=True,
        )
        metadata_paths_by_split[split].add(canonical)

    label_paths_by_split: dict[str, set[str]] = defaultdict(set)
    for split, canonical in findings["records"]:
        label_paths_by_split[split].add(canonical)
    for split in SUPPORTED_SOURCE_SPLITS:
        if metadata_paths_by_split[split] != label_paths_by_split[split]:
            raise CompetitionManifestError(
                f"Metadata/label path sets differ for {split}: "
                f"metadata_missing={len(metadata_paths_by_split[split] - label_paths_by_split[split])}, "
                f"labels_missing={len(label_paths_by_split[split] - metadata_paths_by_split[split])}"
            )

    valid_studies = {
        study_key_from_image_path(path)
        for path in metadata_paths_by_split[VALID_SPLIT]
    }
    if len(metadata_paths_by_split[VALID_SPLIT]) != EXPECTED_VALID_VIEWS:
        raise CompetitionManifestError(
            "Released validation view count mismatch: "
            f"expected={EXPECTED_VALID_VIEWS}, "
            f"observed={len(metadata_paths_by_split[VALID_SPLIT])}"
        )
    if len(valid_studies) != EXPECTED_VALID_STUDIES:
        raise CompetitionManifestError(
            "Released validation study count mismatch: "
            f"expected={EXPECTED_VALID_STUDIES}, observed={len(valid_studies)}"
        )

    local_image_audit = _audit_local_pngs(train_views, image_root)
    study_labels = _build_study_labels(
        train_views,
        findings["records"],
        uncertainty_policy=uncertainty_policy,
    )

    train_patients = set(train_views["patient_id"])
    valid_patients = {
        study_key.split("/", maxsplit=1)[0] for study_key in valid_studies
    }
    test_patients, test_studies = _test_patient_keys(
        Path(expert_test_groundtruth)
    )
    if train_patients & valid_patients:
        raise CompetitionManifestError("Train/validation patient overlap detected")
    if train_patients & test_patients:
        raise CompetitionManifestError("Train/test patient overlap detected")
    if valid_patients & test_patients:
        raise CompetitionManifestError("Validation/test patient overlap detected")

    all_views = train_views.copy()
    train_views_out = train_views.copy()

    label_distribution_rows: list[dict[str, Any]] = []
    for split, counts in findings["raw_counts"].items():
        for label_value, count in counts.items():
            label, raw_value = label_value.split(":", maxsplit=1)
            label_distribution_rows.append(
                {
                    "scope": f"view_{split}",
                    "label": label,
                    "raw_value": raw_value,
                    "count": count,
                }
            )
    for label in CHEXPERT_COMPETITION_LABELS:
        slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
        counts = Counter(
            "missing" if mask == 0 else str(int(target))
            for target, mask in zip(
                study_labels[f"target_{slug}"],
                study_labels[f"mask_{slug}"],
            )
        )
        for value, count in counts.items():
            label_distribution_rows.append(
                {
                    "scope": "study_train_policy_applied",
                    "label": label,
                    "raw_value": value,
                    "count": int(count),
                }
            )

    outputs = {
        "all_views": manifests / "all_views.csv",
        "train_views": manifests / "train_views.csv",
        "study_labels": manifests / "study_labels.csv",
        "manifest_audit": manifests / "manifest_audit.json",
        "label_distribution": manifests / "label_distribution.csv",
        "excluded_rows": manifests / "excluded_rows.csv",
    }
    all_views.to_csv(outputs["all_views"], index=False)
    train_views_out.to_csv(outputs["train_views"], index=False)
    study_labels.to_csv(outputs["study_labels"], index=False)
    pd.DataFrame(label_distribution_rows).to_csv(
        outputs["label_distribution"], index=False
    )
    pd.DataFrame(excluded_rows).to_csv(outputs["excluded_rows"], index=False)

    valid_study_count = len(valid_studies)
    audit: dict[str, Any] = {
        "schema_version": "chexpert_competition_manifest_v1",
        "source_refs": {
            "dataset": REDIVIS_DATASET_ID,
            "metadata_table": REDIVIS_METADATA_TABLE_ID,
            "png_train_table": REDIVIS_PNG_TRAIN_INDEX_TABLE_ID,
            "labels_table": REDIVIS_CHEXPERT_LABELS_INDEX_TABLE_ID,
            "findings_file": str(findings_path),
        },
        "source_file_sha256": {
            "findings_fixed.json": _sha256(findings_path),
        },
        "label_order": list(CHEXPERT_COMPETITION_LABELS),
        "all_label_schema": list(ALL_CHEXPERT_LABELS),
        "uncertainty_policy": {
            "name": uncertainty_policy,
            "version": _POLICY_MODES[uncertainty_policy],
            "missing_values": "masked",
        },
        "study_key": {
            "definition": "patientXXXX/studyN from canonical image path",
            "path_study_count": int(train_views["study_key"].nunique()),
        },
        "source_split_counts": dict(source_split_counts),
        "source_split_patients": {
            TRAIN_SPLIT: len(train_patients),
            VALID_SPLIT: len(valid_patients),
        },
        "source_split_studies": {
            TRAIN_SPLIT: int(train_views["study_key"].nunique()),
            VALID_SPLIT: valid_study_count,
        },
        "label_rows": findings["split_rows"],
        "label_schema": findings["schema_counts"],
        "raw_label_value_counts": findings["raw_counts"],
        "join_checks": {
            "train_metadata_png_missing": 0,
            "train_png_metadata_missing": 0,
            "train_metadata_label_missing": 0,
            "valid_metadata_label_missing": 0,
        },
        "leakage_checks": {
            "train_valid_patient_overlap": 0,
            "train_test_patient_overlap": 0,
            "valid_test_patient_overlap": 0,
            "expert_test_studies": test_studies,
        },
        "local_image_audit": local_image_audit,
        "content_duplicate_audit": duplicate_audit,
        "excluded_row_counts": dict(
            Counter(row["reason"] for row in excluded_rows)
        ),
        "dev_split_status": "pending_separate_patient_level_split_step",
    }

    outputs["manifest_audit"].write_text(
        json.dumps(audit, indent=2, sort_keys=True, default=str) + "\\n",
        encoding="utf-8",
    )
    audit["artifact_sha256"] = {
        name: _sha256(path)
        for name, path in outputs.items()
        if name != "manifest_audit"
    }
    outputs["manifest_audit"].write_text(
        json.dumps(audit, indent=2, sort_keys=True, default=str) + "\\n",
        encoding="utf-8",
    )
    return outputs
