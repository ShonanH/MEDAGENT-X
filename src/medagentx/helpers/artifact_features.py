from __future__ import annotations

import numpy as np


def compute_artifact_features(image: np.ndarray) -> dict[str, float]:
    return {
        "pixel_mean": float(np.mean(image)),
        "pixel_std": float(np.std(image)),
        "pixel_min": float(np.min(image)),
        "pixel_max": float(np.max(image)),
    }
