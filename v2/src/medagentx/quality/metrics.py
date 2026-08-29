"""DICOM-only technical quality metrics computed per image view."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ViewQualityMetrics:
    """Technical metrics for one DICOM view."""

    readable: bool
    finite_pixels: bool
    rows: int | None
    columns: int | None
    intensity_mean: float | None
    intensity_std: float | None
    contrast_proxy: float | None
    entropy: float | None
    sharpness_proxy: float | None
    noise_proxy: float | None
    error: str = ""


def _normalized_pixels(pixel_array: np.ndarray) -> np.ndarray:
    """Normalize finite pixels to [0, 1] using the full finite range."""
    pixels = np.asarray(pixel_array, dtype=np.float32)
    if pixels.ndim != 2 or pixels.size == 0:
        raise ValueError(
            f"pixel_array must be a non-empty 2D image, got shape={pixels.shape}"
        )
    if not np.isfinite(pixels).all():
        raise ValueError("pixel_array contains NaN or infinite values")

    low = float(np.min(pixels))
    high = float(np.max(pixels))
    if high <= low:
        return np.zeros_like(pixels, dtype=np.float32)
    return (pixels - low) / (high - low)


def _entropy(pixels: np.ndarray, bins: int = 256) -> float:
    counts, _ = np.histogram(pixels, bins=bins, range=(0.0, 1.0))
    probabilities = counts[counts > 0].astype(np.float64)
    probabilities /= probabilities.sum()
    return float(-np.sum(probabilities * np.log2(probabilities)))


def _laplacian_variance(pixels: np.ndarray) -> float:
    if min(pixels.shape) < 3:
        return 0.0
    center = pixels[1:-1, 1:-1]
    laplacian = (
        -4.0 * center
        + pixels[:-2, 1:-1]
        + pixels[2:, 1:-1]
        + pixels[1:-1, :-2]
        + pixels[1:-1, 2:]
    )
    return float(np.var(laplacian))


def _noise_proxy(pixels: np.ndarray) -> float:
    """Estimate high-frequency noise from diagonal second differences."""
    if min(pixels.shape) < 3:
        return 0.0
    residual = (
        pixels[:-2, :-2]
        - pixels[:-2, 2:]
        - pixels[2:, :-2]
        + pixels[2:, 2:]
    )
    return float(np.median(np.abs(residual)) / 0.6745)


def compute_pixel_quality_metrics(pixel_array: np.ndarray) -> ViewQualityMetrics:
    """Compute the locked DICOM-only metric set from one pixel array."""
    raw = np.asarray(pixel_array)
    rows = int(raw.shape[-2]) if raw.ndim >= 2 else None
    columns = int(raw.shape[-1]) if raw.ndim >= 2 else None
    finite_pixels = bool(raw.size > 0 and np.isfinite(raw).all())

    try:
        pixels = _normalized_pixels(raw)
    except Exception as exc:  # noqa: BLE001 - returned as auditable evidence
        return ViewQualityMetrics(
            readable=True,
            finite_pixels=finite_pixels,
            rows=rows,
            columns=columns,
            intensity_mean=None,
            intensity_std=None,
            contrast_proxy=None,
            entropy=None,
            sharpness_proxy=None,
            noise_proxy=None,
            error=str(exc),
        )

    p05, p95 = np.percentile(pixels, [5.0, 95.0])
    return ViewQualityMetrics(
        readable=True,
        finite_pixels=True,
        rows=int(pixels.shape[0]),
        columns=int(pixels.shape[1]),
        intensity_mean=float(np.mean(pixels)),
        intensity_std=float(np.std(pixels)),
        contrast_proxy=float(p95 - p05),
        entropy=_entropy(pixels),
        sharpness_proxy=_laplacian_variance(pixels),
        noise_proxy=_noise_proxy(pixels),
    )


def read_dicom_quality_metrics(path: str | Path) -> ViewQualityMetrics:
    """Read one DICOM and compute technical quality metrics."""
    dicom_path = Path(path)
    try:
        import pydicom

        dataset = pydicom.dcmread(dicom_path)
        pixels = np.asarray(dataset.pixel_array, dtype=np.float32)

        slope = float(getattr(dataset, "RescaleSlope", 1.0))
        intercept = float(getattr(dataset, "RescaleIntercept", 0.0))
        pixels = pixels * slope + intercept

        if str(getattr(dataset, "PhotometricInterpretation", "")).upper() == (
            "MONOCHROME1"
        ):
            finite = pixels[np.isfinite(pixels)]
            if finite.size:
                pixels = float(finite.max()) + float(finite.min()) - pixels

        return compute_pixel_quality_metrics(pixels)
    except Exception as exc:  # noqa: BLE001 - one bad view must not stop cohort
        return ViewQualityMetrics(
            readable=False,
            finite_pixels=False,
            rows=None,
            columns=None,
            intensity_mean=None,
            intensity_std=None,
            contrast_proxy=None,
            entropy=None,
            sharpness_proxy=None,
            noise_proxy=None,
            error=str(exc),
        )
