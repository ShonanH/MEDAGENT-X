"""Compact, fixed-shape cache used to keep RAD-DINO input batches on a GPU.

The lossless DICOM cache remains the immutable source of truth.  This cache is
derived from it once, after the deterministic resize/center-crop portion of
the RAD-DINO image processor.  It stores one 518x518 uint8 grayscale tensor
per view in a contiguous ``.npy`` file.  Keeping one channel is intentional:
the three RGB channels are identical for radiographs and are expanded on the
GPU immediately before normalization.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch

from medagentx.vision.cache import (
    COMPLETE_MARKER_NAME,
    CacheValidationError,
    RadDinoImageCache,
    _normalize_relative_path,
    sha256_file,
    split_file_checksums,
)


MODEL_READY_CACHE_SCHEMA_VERSION = 1
DEFAULT_MODEL_READY_CACHE_VERSION = "raddino-model-ready-v1"
MODEL_READY_MANIFEST_NAME = "manifest.json"
MODEL_READY_INDEX_NAME = "index.jsonl"
MODEL_READY_PIXELS_NAME = "pixels.npy"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _geometry_uint8(
    grayscale: np.ndarray,
    *,
    processor: Any,
) -> np.ndarray:
    """Apply only the processor's deterministic geometry and retain uint8.

    The source image is already a deterministic uint8 radiograph.  Expanding
    it to RGB before passing it to the processor exactly follows the existing
    raw/cache path.  Rescaling and normalization are deliberately deferred to
    the GPU loader.
    """
    from medagentx.vision.cache import grayscale_to_pil_rgb

    output = processor(
        images=[grayscale_to_pil_rgb(grayscale)],
        return_tensors="pt",
        do_rescale=False,
        do_normalize=False,
    )["pixel_values"]
    array = output.detach().cpu().numpy()
    if array.shape[0] != 1 or array.shape[1] != 3:
        raise CacheValidationError(
            "RAD-DINO processor must return one three-channel image"
        )
    if array.dtype != np.uint8:
        if np.issubdtype(array.dtype, np.floating) and np.all(
            (array >= 0) & (array <= 255)
        ):
            array = np.rint(array).astype(np.uint8)
        else:
            raise CacheValidationError(
                "Model-ready processor output must contain uint8-range pixels"
            )
    image = array[0]
    if not np.array_equal(image[0], image[1]) or not np.array_equal(
        image[0], image[2]
    ):
        raise CacheValidationError(
            "Radiograph RGB channels must remain identical after geometry"
        )
    if image.ndim != 3 or image.shape[1:] != (518, 518):
        raise CacheValidationError(
            "Model-ready images must have shape [3, 518, 518], got "
            f"{tuple(image.shape)}"
        )
    return np.ascontiguousarray(image[0])


def build_model_ready_cache(
    *,
    raw_cache_root: str | Path,
    output_root: str | Path,
    cache_version: str,
    processor: Any,
    image_processor_config: dict[str, Any],
    overwrite: bool = False,
) -> Path:
    """Build an immutable compact cache from a completed lossless cache."""
    raw_cache = RadDinoImageCache(raw_cache_root)
    root = Path(output_root) / cache_version
    if root.exists():
        if not overwrite:
            raise FileExistsError(
                f"Model-ready cache path already exists: {root}. "
                "Use a new version or --overwrite for an incomplete cache."
            )
        marker = root / COMPLETE_MARKER_NAME
        if marker.exists():
            raise FileExistsError("Refusing to overwrite a completed immutable cache")
        import shutil

        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=False)

    # Preserve raw-cache index order.  It is the order in which the tar shards
    # were written, so this turns the one-time source read into an effectively
    # sequential read rather than 17,908 cross-shard seeks on the RBD volume.
    ordered_paths = list(raw_cache._index)
    if not ordered_paths:
        raise CacheValidationError("Lossless cache contains no images")

    pixels_path = root / MODEL_READY_PIXELS_NAME
    temporary_pixels_path = root / f"{MODEL_READY_PIXELS_NAME}.partial"
    index_path = root / MODEL_READY_INDEX_NAME
    manifest_path = root / MODEL_READY_MANIFEST_NAME
    first = _geometry_uint8(
        raw_cache.load_grayscale(ordered_paths[0]), processor=processor
    )
    shape = (len(ordered_paths), *first.shape)
    pixels = np.lib.format.open_memmap(
        temporary_pixels_path,
        mode="w+",
        dtype=np.uint8,
        shape=shape,
    )
    with index_path.open("w", encoding="utf-8") as index_file:
        for index, dicom_path in enumerate(ordered_paths):
            image = first if index == 0 else _geometry_uint8(
                raw_cache.load_grayscale(dicom_path), processor=processor
            )
            pixels[index] = image
            index_file.write(
                json.dumps(
                    {"dicom_path": dicom_path, "index": index}, sort_keys=True
                )
                + "\n"
            )
            if (index + 1) % 100 == 0 or index + 1 == len(ordered_paths):
                print(
                    "[RAD-DINO model-ready cache] "
                    f"processed {index + 1}/{len(ordered_paths)}",
                    flush=True,
                )
    del pixels
    os.replace(temporary_pixels_path, pixels_path)

    manifest = {
        "schema_version": MODEL_READY_CACHE_SCHEMA_VERSION,
        "cache_version": cache_version,
        "status": "complete",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_lossless_cache_manifest_sha256": sha256_file(
            Path(raw_cache_root) / "manifest.json"
        ),
        "source": raw_cache.manifest["source"],
        "image_processor": image_processor_config,
        "pixel_format": {
            "dtype": "uint8",
            "channels": 1,
            "height": int(shape[1]),
            "width": int(shape[2]),
            "geometry": "rad_dino_processor_resize_center_crop",
            "rgb_expansion": "GPU grayscale-to-RGB expansion",
            "normalization": "GPU image_processor mean/std",
        },
        "view_count": len(ordered_paths),
        "files": {
            "pixels": MODEL_READY_PIXELS_NAME,
            "index": MODEL_READY_INDEX_NAME,
        },
    }
    _write_json(manifest_path, manifest)
    _write_json(
        root / COMPLETE_MARKER_NAME,
        {
            "manifest": MODEL_READY_MANIFEST_NAME,
            "manifest_sha256": sha256_file(manifest_path),
            "status": "complete",
        },
    )
    return root


class ModelReadyImageCache:
    """Validated reader for a compact, fixed-shape RAD-DINO input cache."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.manifest = self._validate()
        self._path_to_index = self._load_index()

    def _validate(self) -> dict[str, Any]:
        manifest_path = self.root / MODEL_READY_MANIFEST_NAME
        marker_path = self.root / COMPLETE_MARKER_NAME
        if not manifest_path.is_file() or not marker_path.is_file():
            raise CacheValidationError("Model-ready cache is incomplete")
        manifest = json.loads(manifest_path.read_text())
        marker = json.loads(marker_path.read_text())
        if manifest.get("schema_version") != MODEL_READY_CACHE_SCHEMA_VERSION:
            raise CacheValidationError("Unsupported model-ready cache schema")
        if (
            manifest.get("status") != "complete"
            or marker.get("status") != "complete"
        ):
            raise CacheValidationError("Model-ready cache was not completed")
        if marker.get("manifest_sha256") != sha256_file(manifest_path):
            raise CacheValidationError("Model-ready cache manifest digest mismatch")
        pixel_format = manifest.get("pixel_format", {})
        if (pixel_format.get("dtype"), pixel_format.get("channels")) != (
            "uint8",
            1,
        ):
            raise CacheValidationError("Unsupported model-ready pixel format")
        if (pixel_format.get("height"), pixel_format.get("width")) != (518, 518):
            raise CacheValidationError("Unsupported model-ready image shape")
        return manifest

    def _load_index(self) -> dict[str, int]:
        path = self.root / self.manifest["files"]["index"]
        entries: dict[str, int] = {}
        with path.open(encoding="utf-8") as source:
            for line in source:
                item = json.loads(line)
                key = _normalize_relative_path(item["dicom_path"])
                index = item["index"]
                if key in entries or not isinstance(index, int) or index < 0:
                    raise CacheValidationError("Invalid model-ready cache index")
                entries[key] = index
        if len(entries) != self.manifest.get("view_count"):
            raise CacheValidationError(
                "Model-ready index count does not match manifest"
            )
        if set(entries.values()) != set(range(len(entries))):
            raise CacheValidationError("Model-ready cache indices are not contiguous")
        return entries

    @property
    def cache_id(self) -> str:
        return sha256_file(self.root / MODEL_READY_MANIFEST_NAME)

    @property
    def path_to_index(self) -> dict[str, int]:
        return dict(self._path_to_index)

    def validate_training_inputs(
        self,
        *,
        cohort_root: str | Path,
        dicom_root: str | Path,
        view_splits_csv: str | Path,
        required_paths: Iterable[str],
        image_processor_config: dict[str, Any],
    ) -> None:
        source = self.manifest["source"]
        if source.get("split_files_sha256", {}) != split_file_checksums(
            view_splits_csv
        ):
            raise CacheValidationError(
                "Model-ready cache split checksums do not match"
            )
        if str(Path(cohort_root).resolve()) != source.get("cohort_root"):
            raise CacheValidationError("Model-ready cache cohort root does not match")
        if str(Path(dicom_root).resolve()) != source.get("dicom_root"):
            raise CacheValidationError("Model-ready cache DICOM root does not match")
        if self.manifest.get("image_processor") != image_processor_config:
            raise CacheValidationError(
                "Model-ready cache image processor does not match"
            )
        missing = sorted(
            {
                _normalize_relative_path(path)
                for path in required_paths
                if _normalize_relative_path(path) not in self._path_to_index
            }
        )
        if missing:
            raise CacheValidationError(
                f"Model-ready cache lacks {len(missing)} paths; first: {missing[:3]}"
            )

    def preload_to_device(
        self,
        device: torch.device,
        *,
        chunk_size: int = 64,
    ) -> torch.Tensor:
        """Read the compact cache once and retain all views as GPU uint8 data."""
        if device.type != "cuda":
            raise ValueError("Model-ready GPU preload requires a CUDA device")
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        path = self.root / self.manifest["files"]["pixels"]
        cpu_pixels = np.load(path, mmap_mode="r", allow_pickle=False)
        expected = (self.manifest["view_count"], 518, 518)
        if cpu_pixels.dtype != np.uint8 or tuple(cpu_pixels.shape) != expected:
            raise CacheValidationError(
                "Model-ready pixels file does not match manifest"
            )
        output = torch.empty(
            (len(cpu_pixels), 1, 518, 518), dtype=torch.uint8, device=device
        )
        for start in range(0, len(cpu_pixels), chunk_size):
            end = min(start + chunk_size, len(cpu_pixels))
            chunk = torch.from_numpy(np.array(cpu_pixels[start:end], copy=True))
            output[start:end, 0].copy_(chunk.to(device, non_blocking=False))
            if end % 512 == 0 or end == len(cpu_pixels):
                print(
                    "[RAD-DINO model-ready cache] "
                    f"GPU preload {end}/{len(cpu_pixels)}",
                    flush=True,
                )
        return output
