"""Persist and reload offline RAD-DINO study embeddings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from medagentx.retrieval.constants import (
    EMBEDDING_BACKEND_ID,
    RETRIEVAL_POLICY_VERSION,
)


def embeddings_cache_meta_path(cache_path: str | Path) -> Path:
    """Return the JSON sidecar path for one embeddings cache file."""
    path = Path(cache_path)
    return path.with_suffix(path.suffix + ".meta.json")


def save_embeddings_cache(
    cache_path: str | Path,
    payload: dict[str, Any],
    *,
    build_config: dict[str, Any],
) -> Path:
    """Write study embeddings and a small metadata sidecar."""
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        embeddings=np.asarray(payload["embeddings"], dtype=np.float32),
        study_keys=np.asarray(payload["study_keys"], dtype=str),
        patient_ids=np.asarray(payload["patient_ids"], dtype=str),
    )
    meta = {
        "retrieval_policy_version": RETRIEVAL_POLICY_VERSION,
        "embedding_backend_id": EMBEDDING_BACKEND_ID,
        "study_count": int(len(payload["study_keys"])),
        "embedding_dim": int(np.asarray(payload["embeddings"]).shape[1]),
        **build_config,
    }
    embeddings_cache_meta_path(path).write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n"
    )
    return path


def load_embeddings_cache(cache_path: str | Path) -> dict[str, Any] | None:
    """Load a cached embedding payload if the file exists."""
    path = Path(cache_path)
    if not path.exists():
        return None

    with np.load(path, allow_pickle=False) as archive:
        embeddings = archive["embeddings"]
        study_keys = [str(value) for value in archive["study_keys"].tolist()]
        patient_ids = [str(value) for value in archive["patient_ids"].tolist()]

    return {
        "embeddings": embeddings,
        "study_keys": study_keys,
        "patient_ids": patient_ids,
    }
