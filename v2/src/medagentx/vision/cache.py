"""Versioned, lossless DICOM preprocessing cache for RAD-DINO.

The cache deliberately stores the output immediately before augmentation:
one normalized uint8 grayscale image per source DICOM.  Assets are ``.npy``
members in uncompressed tar shards.  A JSON index records the member byte
range, so readers can seek directly to an asset without unpacking a shard.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tarfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
from PIL import Image

from medagentx.vision.data import dicom_dataset_to_uint8, dicom_to_pil_rgb


CACHE_SCHEMA_VERSION = 1
DEFAULT_CACHE_VERSION = "raddino-cache-v1"
DEFAULT_SHARD_SIZE_BYTES = 512 * 1024 * 1024
COMPLETE_MARKER_NAME = "COMPLETE.json"
MANIFEST_NAME = "manifest.json"
INDEX_NAME = "index.jsonl"
FAILURES_NAME = "failures.jsonl"


class CacheValidationError(ValueError):
    """Raised when a cache is absent, incomplete, or incompatible."""


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def sha256_file(path: str | Path) -> str:
    """Return a streaming SHA-256 digest for one file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_file_checksums(view_splits_csv: str | Path) -> dict[str, str]:
    """Hash every split artifact beside the training view inventory."""
    views_path = Path(view_splits_csv).resolve()
    split_root = views_path.parent
    files = sorted(path for path in split_root.rglob("*") if path.is_file())
    if views_path not in files:
        files.append(views_path)
    return {str(path): sha256_file(path) for path in sorted(set(files))}


def _read_file_with_sha256(path: Path) -> tuple[bytes, str]:
    """Read a DICOM once, returning its bytes and content digest."""
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
            chunks.append(chunk)
    return b"".join(chunks), digest.hexdigest()


def _normalize_relative_path(value: str) -> str:
    path = Path(str(value).strip())
    if not str(path) or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"DICOM path must be a safe relative path: {value!r}")
    return path.as_posix()


def _inventory_hash(entries: Iterable[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(_canonical_json(entry))
        digest.update(b"\n")
    return digest.hexdigest()


@dataclass(frozen=True)
class CacheSourceView:
    """A source DICOM selected from the locked split inventory."""

    dicom_path: str
    split: str
    study_key: str
    deid_patient_id: str

    def identity(self) -> dict[str, str]:
        return {
            "dicom_path": self.dicom_path,
            "split": self.split,
            "study_key": self.study_key,
            "deid_patient_id": self.deid_patient_id,
        }


@dataclass(frozen=True)
class PreparedCacheImage:
    """One decoded source image, ready for ordered shard writing."""

    view: CacheSourceView
    source_sha256: str
    grayscale: np.ndarray
    photometric: str
    slope: float
    intercept: float
    bits_allocated: int


def _prepare_cache_image(
    view: CacheSourceView, *, dicom_root: Path
) -> PreparedCacheImage:
    """Read, hash, decode, and deterministically preprocess one DICOM once."""
    import pydicom

    source_path = (dicom_root / view.dicom_path).resolve()
    if dicom_root not in source_path.parents:
        raise ValueError("DICOM path escapes dicom root")
    source_bytes, source_sha256 = _read_file_with_sha256(source_path)
    dataset = pydicom.dcmread(io.BytesIO(source_bytes))
    return PreparedCacheImage(
        view=view,
        source_sha256=source_sha256,
        grayscale=dicom_dataset_to_uint8(dataset),
        photometric=str(getattr(dataset, "PhotometricInterpretation", "")).upper(),
        slope=float(getattr(dataset, "RescaleSlope", 1.0)),
        intercept=float(getattr(dataset, "RescaleIntercept", 0.0)),
        bits_allocated=int(getattr(dataset, "BitsAllocated", 0) or 0),
    )


def load_source_views(view_splits_csv: str | Path) -> list[CacheSourceView]:
    """Load one unique, deterministically ordered source view inventory."""
    frame = pd.read_csv(view_splits_csv, dtype=str)
    required = ("dicom_path", "split", "study_key", "deid_patient_id")
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(
            f"view splits file missing required columns {missing}: "
            f"{view_splits_csv}"
        )
    rows: dict[str, CacheSourceView] = {}
    for row in frame.loc[:, required].fillna("").to_dict("records"):
        dicom_path = _normalize_relative_path(row["dicom_path"])
        view = CacheSourceView(
            dicom_path=dicom_path,
            split=str(row["split"]).strip(),
            study_key=str(row["study_key"]).strip(),
            deid_patient_id=str(row["deid_patient_id"]).strip(),
        )
        if not view.split or not view.study_key or not view.deid_patient_id:
            raise ValueError(f"Incomplete source-view metadata for {dicom_path}")
        existing = rows.get(dicom_path)
        if existing is not None and existing != view:
            raise ValueError(
                "DICOM path occurs with incompatible study/split metadata: "
                f"{dicom_path}"
            )
        rows[dicom_path] = view
    if not rows:
        raise ValueError("view splits inventory contains no DICOM paths")
    return sorted(
        rows.values(),
        key=lambda item: (
            item.split,
            item.study_key,
            item.dicom_path,
        ),
    )


def _npy_payload(image: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    np.save(buffer, image, allow_pickle=False)
    return buffer.getvalue()


def _load_npy_payload(payload: bytes) -> np.ndarray:
    image = np.load(io.BytesIO(payload), allow_pickle=False)
    if image.dtype != np.uint8 or image.ndim != 2 or image.size == 0:
        raise CacheValidationError(
            "Cached image must be a non-empty 2D uint8 grayscale array"
        )
    return image


def grayscale_to_pil_rgb(image: np.ndarray) -> Image.Image:
    """Expand cached grayscale pixels to the current RGB loader contract."""
    if image.dtype != np.uint8 or image.ndim != 2:
        raise CacheValidationError("Expected a 2D uint8 grayscale cache image")
    return Image.fromarray(image, mode="L").convert("RGB")


class SeekableTarShardWriter:
    """Write simple uncompressed tar members and return their byte ranges."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._raw = path.open("wb")
        self._tar = tarfile.open(fileobj=self._raw, mode="w", format=tarfile.USTAR_FORMAT)

    def add(self, member_name: str, payload: bytes) -> tuple[int, int]:
        offset = self._raw.tell()
        info = tarfile.TarInfo(member_name)
        info.size = len(payload)
        info.mtime = 0
        info.mode = 0o644
        self._tar.addfile(info, io.BytesIO(payload))
        return offset + tarfile.BLOCKSIZE, len(payload)

    def close(self) -> None:
        self._tar.close()
        self._raw.close()


def _cache_path(output_root: Path, cache_version: str) -> Path:
    version = cache_version.strip()
    if not version or Path(version).name != version or version in {".", ".."}:
        raise ValueError("cache-version must be one safe directory name")
    return output_root / version


def _prepare_output(cache_root: Path, *, overwrite: bool) -> None:
    if not cache_root.exists():
        cache_root.mkdir(parents=True)
        return
    marker = cache_root / COMPLETE_MARKER_NAME
    if marker.exists():
        raise FileExistsError(
            "Refusing to replace a completed immutable cache: "
            f"{cache_root}. Choose a new cache version."
        )
    if not overwrite:
        raise FileExistsError(
            f"Cache output already exists and is incomplete: {cache_root}. "
            "Use --overwrite to replace this incomplete cache."
        )
    shutil.rmtree(cache_root)
    cache_root.mkdir(parents=True)


def _failure_payload(view: CacheSourceView, error: Exception) -> dict[str, str]:
    return {
        **view.identity(),
        "error_type": type(error).__name__,
        "error": str(error),
    }


def _sample_views(
    views: Sequence[CacheSourceView],
    sample_limit: int | None,
    *,
    dicom_root: Path,
) -> list[CacheSourceView]:
    """Return a deterministic split-stratified preliminary validation sample.

    ``sample_limit`` is deliberately per split; callers should use at least
    100 to meet the validation protocol.  Edge-case coverage is verified as
    images are decoded and reported in the manifest.
    """
    if sample_limit is None:
        return list(views)
    if sample_limit <= 0:
        raise ValueError("sample-limit must be > 0")
    selected: list[CacheSourceView] = []
    for split in sorted({item.split for item in views}):
        split_views = [item for item in views if item.split == split]
        selected.extend(split_views[:sample_limit])
    # The normal full builder needs no metadata pre-pass.  A deliberately
    # small validation cache must additionally include the known semantic
    # edge cases, even if they are outside its first N views per split.
    import pydicom

    selected_paths = {view.dicom_path for view in selected}
    seen_bit_depths: set[int] = set()
    needs_monochrome1 = True
    needs_non_default_rescale = True
    multi_view_study = next(
        (
            study
            for study in sorted({view.study_key for view in views})
            if sum(view.study_key == study for view in views) > 1
        ),
        None,
    )
    for view in views:
        if view.dicom_path in selected_paths:
            continue
        try:
            header = pydicom.dcmread(
                dicom_root / view.dicom_path,
                stop_before_pixels=True,
                specific_tags=(
                    "PhotometricInterpretation",
                    "RescaleSlope",
                    "RescaleIntercept",
                    "BitsAllocated",
                ),
            )
        except Exception:
            # Full decoding records failures; a preliminary selector must not
            # mask or reclassify them.
            continue
        photometric = str(
            getattr(header, "PhotometricInterpretation", "")
        ).upper()
        slope = float(getattr(header, "RescaleSlope", 1.0))
        intercept = float(getattr(header, "RescaleIntercept", 0.0))
        bits = int(getattr(header, "BitsAllocated", 0) or 0)
        include = (
            (needs_monochrome1 and photometric == "MONOCHROME1")
            or (needs_non_default_rescale and (slope != 1.0 or intercept != 0.0))
            or (bits and bits not in seen_bit_depths)
            or (multi_view_study is not None and view.study_key == multi_view_study)
        )
        if include:
            selected.append(view)
            selected_paths.add(view.dicom_path)
            needs_monochrome1 = needs_monochrome1 and photometric != "MONOCHROME1"
            needs_non_default_rescale = needs_non_default_rescale and (
                slope == 1.0 and intercept == 0.0
            )
            if bits:
                seen_bit_depths.add(bits)
    return selected


def _pixel_validation_paths(
    entries: Sequence[dict[str, Any]], *, sample_cache: bool
) -> list[str]:
    """Select deterministic split and semantic coverage for exact checking."""
    if sample_cache:
        return [entry["dicom_path"] for entry in entries]
    paths_by_split: dict[str, list[str]] = {}
    for entry in entries:
        paths_by_split.setdefault(entry["split"], []).append(entry["dicom_path"])
    paths = {
        path
        for split in sorted(paths_by_split)
        for path in sorted(paths_by_split[split])[:100]
    }
    paths.update(
        entry["dicom_path"]
        for entry in entries
        if entry["photometric_interpretation"] == "MONOCHROME1"
        or entry["rescale_slope"] != 1.0
        or entry["rescale_intercept"] != 0.0
    )
    for bit_depth in sorted({entry["bits_allocated"] for entry in entries}):
        paths.add(
            next(
                entry["dicom_path"]
                for entry in entries
                if entry["bits_allocated"] == bit_depth
            )
        )
    study_counts: dict[str, int] = {}
    for entry in entries:
        study_counts[entry["study_key"]] = (
            study_counts.get(entry["study_key"], 0) + 1
        )
    paths.update(
        entry["dicom_path"]
        for entry in entries
        if study_counts[entry["study_key"]] > 1
    )
    return sorted(paths)


def _finalization_validation_paths(
    entries: Sequence[dict[str, Any]], *, views_per_split: int
) -> list[str]:
    """Select a bounded, deterministic exact-pixel validation sample.

    This is deliberately narrower than the original full-build validation
    selector.  It covers a fixed number of views from every split plus one
    representative of each preprocessing edge case and all views from one
    multi-view study.  It is used only to recover a fully written cache whose
    prior validation was interrupted before its completion marker was written.
    """
    if views_per_split <= 0:
        raise ValueError("views-per-split must be > 0")

    ordered = sorted(entries, key=lambda entry: entry["dicom_path"])
    paths_by_split: dict[str, list[str]] = {}
    for entry in ordered:
        paths_by_split.setdefault(entry["split"], []).append(
            entry["dicom_path"]
        )
    paths = {
        path
        for split in sorted(paths_by_split)
        for path in paths_by_split[split][:views_per_split]
    }

    def include_first(predicate: Any) -> None:
        match = next((entry for entry in ordered if predicate(entry)), None)
        if match is not None:
            paths.add(match["dicom_path"])

    include_first(
        lambda entry: entry["photometric_interpretation"] == "MONOCHROME1"
    )
    include_first(
        lambda entry: entry["rescale_slope"] != 1.0
        or entry["rescale_intercept"] != 0.0
    )
    for bit_depth in sorted({entry["bits_allocated"] for entry in ordered}):
        include_first(lambda entry, bits=bit_depth: entry["bits_allocated"] == bits)

    study_counts: dict[str, int] = {}
    for entry in ordered:
        study_counts[entry["study_key"]] = (
            study_counts.get(entry["study_key"], 0) + 1
        )
    multi_view_study = next(
        (
            study_key
            for study_key in sorted(study_counts)
            if study_counts[study_key] > 1
        ),
        None,
    )
    if multi_view_study is not None:
        paths.update(
            entry["dicom_path"]
            for entry in ordered
            if entry["study_key"] == multi_view_study
        )
    return sorted(paths)


def finalize_interrupted_raddino_cache(
    *,
    cache_root: str | Path,
    dicom_root: str | Path,
    validation_views_per_split: int = 100,
) -> Path:
    """Finalize an intact cache whose validation process was interrupted.

    The cache must already contain every indexed source view, have no decode
    failures, and be in ``validating`` state.  The function never rebuilds or
    changes image shards.  It writes ``COMPLETE.json`` only after exact raw
    DICOM-versus-cache pixel validation succeeds on a deterministic sample.
    """
    root = Path(cache_root).resolve()
    cache = RadDinoImageCache(root, require_complete=False)
    manifest = dict(cache.manifest)
    if (root / COMPLETE_MARKER_NAME).exists() or manifest.get("status") == "complete":
        raise FileExistsError(f"Cache is already complete: {root}")
    if manifest.get("status") != "validating":
        raise CacheValidationError(
            "Only a fully written cache in validating state can be finalized"
        )
    if manifest.get("failure_count") != 0:
        raise CacheValidationError("Cannot finalize a cache with decode failures")
    if not manifest.get("is_full_source_inventory"):
        raise CacheValidationError("Cannot finalize a sample cache for training")
    if manifest.get("cached_view_count") != manifest.get("source_view_count"):
        raise CacheValidationError(
            "Cannot finalize a cache that does not contain every source view"
        )

    paths = _finalization_validation_paths(
        list(cache._index.values()),
        views_per_split=validation_views_per_split,
    )
    manifest_path = root / MANIFEST_NAME
    try:
        validate_cache_pixels(
            root,
            dicom_root=dicom_root,
            paths=paths,
            require_complete=False,
        )
    except Exception as error:
        manifest.update(
            {
                "status": "failed",
                "pixel_validation": {
                    "status": "failed",
                    "view_count": len(paths),
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            }
        )
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        raise RuntimeError(
            "Interrupted-cache pixel validation failed; cache remains incomplete: "
            f"{error}"
        ) from error

    manifest.update(
        {
            "status": "complete",
            "pixel_validation": {
                "status": "exact_match",
                "view_count": len(paths),
                "validation_scope": "deterministic_stratified_edge_sample",
                "views_per_split": validation_views_per_split,
            },
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (root / COMPLETE_MARKER_NAME).write_text(
        json.dumps(
            {
                "manifest": MANIFEST_NAME,
                "manifest_sha256": sha256_file(manifest_path),
                "status": "complete",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return root


def build_raddino_cache(
    *,
    cohort_root: str | Path,
    dicom_root: str | Path,
    output_root: str | Path,
    cache_version: str = DEFAULT_CACHE_VERSION,
    view_splits_csv: str | Path | None = None,
    num_workers: int = 0,
    sample_limit: int | None = None,
    shard_size_bytes: int = DEFAULT_SHARD_SIZE_BYTES,
    overwrite: bool = False,
    fail_fast: bool = False,
    image_processor_config: dict[str, Any] | None = None,
) -> Path:
    """Build a strict, immutable lossless cache and return its directory.

    Decode/hash work can be parallelized while ordered shard writes remain
    single-writer and deterministic. A worker count of zero uses one worker.
    """
    if num_workers < 0:
        raise ValueError("num-workers must be >= 0")
    if shard_size_bytes <= 0:
        raise ValueError("shard-size-bytes must be > 0")

    cohort = Path(cohort_root).resolve()
    dicoms = Path(dicom_root).resolve()
    views_csv = Path(view_splits_csv or cohort / "splits" / "view_splits.csv").resolve()
    output = Path(output_root).resolve()
    if not dicoms.is_dir():
        raise FileNotFoundError(f"DICOM root missing: {dicoms}")
    if not views_csv.is_file():
        raise FileNotFoundError(f"View splits file missing: {views_csv}")

    all_views = load_source_views(views_csv)
    selected_views = _sample_views(
        all_views, sample_limit, dicom_root=dicoms
    )
    cache_root = _cache_path(output, cache_version)
    _prepare_output(cache_root, overwrite=overwrite)
    shards_dir = cache_root / "shards"
    shards_dir.mkdir()
    index_path = cache_root / INDEX_NAME
    failures_path = cache_root / FAILURES_NAME

    source_split_checksums = split_file_checksums(views_csv)
    manifest: dict[str, Any] = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "status": "building",
        "cache_version": cache_version,
        "cache_format": {
            "container": "uncompressed-tar",
            "member_format": "npy",
            "dtype": "uint8",
            "channels": 1,
            "reader_rgb_expansion": "PIL L to RGB",
            "compression": "none",
            "index": "jsonl byte-offset/size",
        },
        "preprocessing_version": "dicom_to_uint8_percentile_v1",
        "image_processor": image_processor_config or {},
        "source": {
            "cohort_root": str(cohort),
            "dicom_root": str(dicoms),
            "view_splits_csv": str(views_csv),
            "split_files_sha256": source_split_checksums,
        },
        "sample_limit_per_split": sample_limit,
        "requested_num_workers": num_workers,
        "selected_view_count": len(selected_views),
        "source_view_count": len(all_views),
        "is_full_source_inventory": len(selected_views) == len(all_views),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "failures_file": FAILURES_NAME,
    }
    (cache_root / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )

    failures: list[dict[str, str]] = []
    edge_coverage = {
        "monochrome1": 0,
        "non_default_rescale": 0,
        "bits_allocated": [],
        "multi_view_studies": 0,
    }
    study_counts: dict[str, int] = {}
    for view in selected_views:
        study_counts[view.study_key] = study_counts.get(view.study_key, 0) + 1
    edge_coverage["multi_view_studies"] = sum(
        count > 1 for count in study_counts.values()
    )

    shard_number = 0
    shard_bytes = 0
    artifact_number = 0
    index_entries: list[dict[str, Any]] = []
    writer: SeekableTarShardWriter | None = None
    try:
        with index_path.open("w", encoding="utf-8") as index_file, failures_path.open(
            "w", encoding="utf-8"
        ) as failures_file:
            prepare = partial(_prepare_cache_image, dicom_root=dicoms)
            if num_workers > 0:
                executor: ThreadPoolExecutor | None = ThreadPoolExecutor(
                    max_workers=num_workers
                )
                prepared_images = executor.map(prepare, selected_views)
            else:
                executor = None
                prepared_images = map(prepare, selected_views)
            for view in selected_views:
                try:
                    prepared = next(prepared_images)
                    grayscale = prepared.grayscale
                    payload = _npy_payload(grayscale)
                    if writer is None or (
                        shard_bytes > 0
                        and shard_bytes + len(payload) + tarfile.BLOCKSIZE
                        > shard_size_bytes
                    ):
                        if writer is not None:
                            writer.close()
                        shard_name = f"shard-{shard_number:05d}.tar"
                        writer = SeekableTarShardWriter(shards_dir / shard_name)
                        shard_number += 1
                        shard_bytes = 0
                    artifact_id = f"image-{artifact_number:09d}"
                    member_name = f"images/{artifact_id}.npy"
                    offset, size = writer.add(member_name, payload)
                    shard_bytes += len(payload) + tarfile.BLOCKSIZE
                    artifact_number += 1
                    edge_coverage["monochrome1"] += int(
                        prepared.photometric == "MONOCHROME1"
                    )
                    edge_coverage["non_default_rescale"] += int(
                        prepared.slope != 1.0 or prepared.intercept != 0.0
                    )
                    if (
                        prepared.bits_allocated
                        and prepared.bits_allocated not in edge_coverage["bits_allocated"]
                    ):
                        edge_coverage["bits_allocated"].append(
                            prepared.bits_allocated
                        )
                    entry = {
                        **view.identity(),
                        "artifact_id": artifact_id,
                        "artifact_sha256": hashlib.sha256(payload).hexdigest(),
                        "pixel_sha256": hashlib.sha256(grayscale.tobytes()).hexdigest(),
                        "source_sha256": prepared.source_sha256,
                        "shape": list(grayscale.shape),
                        "photometric_interpretation": prepared.photometric,
                        "rescale_slope": prepared.slope,
                        "rescale_intercept": prepared.intercept,
                        "bits_allocated": prepared.bits_allocated,
                        "shard": f"shards/{shard_name}",
                        "member": member_name,
                        "offset": offset,
                        "size": size,
                    }
                    index_entries.append(entry)
                    index_file.write(json.dumps(entry, sort_keys=True) + "\n")
                except Exception as error:
                    failure = _failure_payload(view, error)
                    failures.append(failure)
                    failures_file.write(json.dumps(failure, sort_keys=True) + "\n")
                    failures_file.flush()
                    if fail_fast:
                        break
                if (len(index_entries) + len(failures)) % 100 == 0:
                    print(
                        "[RAD-DINO cache] processed "
                        f"{len(index_entries) + len(failures)}/{len(selected_views)} "
                        f"cached={len(index_entries)} failures={len(failures)}"
                    )
            if executor is not None:
                executor.shutdown(wait=True)
    finally:
        if writer is not None:
            writer.close()

    edge_coverage["bits_allocated"].sort()
    manifest.update(
        {
            "processed_view_count": len(index_entries) + len(failures),
            "cached_view_count": len(index_entries),
            "failure_count": len(failures),
            "edge_coverage": edge_coverage,
            "ordered_inventory_sha256": _inventory_hash(index_entries),
            "status": "failed" if failures else "validating",
        }
    )
    manifest_path = cache_root / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    if failures:
        raise RuntimeError(
            f"Cache build failed with {len(failures)} invalid DICOM(s); "
            f"review {failures_path}"
        )

    validation_paths = _pixel_validation_paths(
        index_entries,
        sample_cache=sample_limit is not None,
    )
    try:
        validate_cache_pixels(
            cache_root,
            dicom_root=dicoms,
            paths=validation_paths,
            require_complete=False,
        )
    except Exception as error:
        manifest.update(
            {
                "status": "failed",
                "pixel_validation": {
                    "status": "failed",
                    "view_count": len(validation_paths),
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            }
        )
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        raise RuntimeError(
            "Cache pixel validation failed; cache remains incomplete: "
            f"{error}"
        ) from error
    manifest["pixel_validation"] = {
        "status": "exact_match",
        "view_count": len(validation_paths),
    }
    manifest["status"] = "complete"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    manifest_sha256 = sha256_file(manifest_path)
    (cache_root / COMPLETE_MARKER_NAME).write_text(
        json.dumps(
            {
                "manifest": MANIFEST_NAME,
                "manifest_sha256": manifest_sha256,
                "status": "complete",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return cache_root


class RadDinoImageCache:
    """Validated direct-reader for one immutable RAD-DINO image cache."""

    def __init__(self, root: str | Path, *, require_complete: bool = True) -> None:
        self.root = Path(root).resolve()
        self.manifest = self._validate(require_complete=require_complete)
        self._index = self._load_index()

    def _validate(self, *, require_complete: bool) -> dict[str, Any]:
        manifest_path = self.root / MANIFEST_NAME
        marker_path = self.root / COMPLETE_MARKER_NAME
        if not manifest_path.is_file() or (require_complete and not marker_path.is_file()):
            raise CacheValidationError(
                "Cache is not complete: manifest or successful-completion "
                f"marker missing in {self.root}"
            )
        manifest = json.loads(manifest_path.read_text())
        if require_complete and manifest.get("status") != "complete":
            raise CacheValidationError("Cache was not successfully completed")
        if not require_complete and manifest.get("status") not in {"validating", "complete"}:
            raise CacheValidationError("Cache is not ready for pixel validation")
        if marker_path.is_file():
            marker = json.loads(marker_path.read_text())
            if marker.get("status") != "complete":
                raise CacheValidationError("Cache completion marker is invalid")
            if marker.get("manifest_sha256") != sha256_file(manifest_path):
                raise CacheValidationError("Cache manifest digest does not match marker")
        if manifest.get("schema_version") != CACHE_SCHEMA_VERSION:
            raise CacheValidationError("Unsupported cache schema version")
        if manifest.get("cache_format", {}).get("compression") != "none":
            raise CacheValidationError("Cache shards must be uncompressed")
        return manifest

    def _load_index(self) -> dict[str, dict[str, Any]]:
        index_path = self.root / INDEX_NAME
        if not index_path.is_file():
            raise CacheValidationError(f"Cache index missing: {index_path}")
        entries: dict[str, dict[str, Any]] = {}
        with index_path.open(encoding="utf-8") as source:
            for line in source:
                entry = json.loads(line)
                path = _normalize_relative_path(entry.get("dicom_path", ""))
                if path in entries:
                    raise CacheValidationError(f"Duplicate cache index entry: {path}")
                shard = Path(str(entry.get("shard", "")))
                if shard.is_absolute() or ".." in shard.parts:
                    raise CacheValidationError("Invalid cache shard path")
                if not isinstance(entry.get("offset"), int) or not isinstance(
                    entry.get("size"), int
                ):
                    raise CacheValidationError("Cache index has invalid byte range")
                entries[path] = entry
        if len(entries) != self.manifest.get("cached_view_count"):
            raise CacheValidationError("Cache index count does not match manifest")
        if _inventory_hash(entries.values()) != self.manifest.get(
            "ordered_inventory_sha256"
        ):
            raise CacheValidationError("Cache index inventory digest does not match")
        return entries

    def validate_training_inputs(
        self,
        *,
        cohort_root: str | Path,
        dicom_root: str | Path,
        view_splits_csv: str | Path,
        required_paths: Iterable[str],
        image_processor_config: dict[str, Any],
    ) -> None:
        """Reject stale/sample caches before a training process starts."""
        source = self.manifest["source"]
        if not self.manifest.get("is_full_source_inventory"):
            raise CacheValidationError(
                "Sample cache cannot be used for training; build the complete "
                "source inventory first"
            )
        expected_checksums = source.get("split_files_sha256", {})
        actual_checksums = split_file_checksums(view_splits_csv)
        if expected_checksums != actual_checksums:
            raise CacheValidationError(
                "Cache split-file checksums do not match the requested training inputs"
            )
        if str(Path(cohort_root).resolve()) != source.get("cohort_root"):
            raise CacheValidationError("Cache cohort root does not match training")
        if str(Path(dicom_root).resolve()) != source.get("dicom_root"):
            raise CacheValidationError("Cache DICOM root does not match training")
        if self.manifest.get("image_processor") != image_processor_config:
            raise CacheValidationError(
                "Cache image-processor configuration does not match training"
            )
        missing = sorted(
            {
                _normalize_relative_path(path)
                for path in required_paths
                if _normalize_relative_path(path) not in self._index
            }
        )
        if missing:
            raise CacheValidationError(
                f"Cache lacks {len(missing)} requested DICOM paths; first: {missing[:3]}"
            )

    def load_grayscale(self, dicom_path: str | Path) -> np.ndarray:
        """Read one indexed image directly from its uncompressed shard."""
        path = _normalize_relative_path(str(dicom_path))
        try:
            entry = self._index[path]
        except KeyError as error:
            raise KeyError(f"DICOM path is absent from cache: {path}") from error
        shard_path = self.root / entry["shard"]
        with shard_path.open("rb") as source:
            source.seek(entry["offset"])
            payload = source.read(entry["size"])
        if len(payload) != entry["size"]:
            raise CacheValidationError(f"Truncated cache payload for {path}")
        if hashlib.sha256(payload).hexdigest() != entry["artifact_sha256"]:
            raise CacheValidationError(f"Cached artifact digest mismatch for {path}")
        image = _load_npy_payload(payload)
        if hashlib.sha256(image.tobytes()).hexdigest() != entry["pixel_sha256"]:
            raise CacheValidationError(f"Cached pixel digest mismatch for {path}")
        return image

    def load_pil_rgb(self, dicom_path: str | Path) -> Image.Image:
        return grayscale_to_pil_rgb(self.load_grayscale(dicom_path))

    @property
    def cache_id(self) -> str:
        return sha256_file(self.root / MANIFEST_NAME)


class CachedImageLoader:
    """Pickle-safe StudyDataset loader that maps local paths to cache keys."""

    def __init__(self, *, dicom_root: str | Path, cache_root: str | Path) -> None:
        self.dicom_root = Path(dicom_root).resolve()
        self.cache_root = Path(cache_root).resolve()
        self._cache: RadDinoImageCache | None = None

    def __call__(self, local_path: str | Path) -> Image.Image:
        path = Path(local_path).resolve(strict=False)
        try:
            relative = path.relative_to(self.dicom_root).as_posix()
        except ValueError as error:
            raise CacheValidationError(
                f"Dataset image path is outside cache DICOM root: {path}"
            ) from error
        if self._cache is None:
            self._cache = RadDinoImageCache(self.cache_root)
        return self._cache.load_pil_rgb(relative)


def validate_cache_pixels(
    cache_root: str | Path,
    *,
    dicom_root: str | Path,
    paths: Iterable[str],
    require_complete: bool = True,
) -> None:
    """Raise unless raw and cached pre-augmentation RGB pixels are identical."""
    cache = RadDinoImageCache(cache_root, require_complete=require_complete)
    root = Path(dicom_root)
    for relative_path in paths:
        raw = np.asarray(dicom_to_pil_rgb(root / relative_path), dtype=np.uint8)
        cached = np.asarray(cache.load_pil_rgb(relative_path), dtype=np.uint8)
        if not np.array_equal(raw, cached):
            raise CacheValidationError(
                f"Raw and cached pixels differ for {relative_path}"
            )
