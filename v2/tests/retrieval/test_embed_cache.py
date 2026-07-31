"""Tests for cached RAD-DINO study embeddings."""

from __future__ import annotations

import numpy as np

from medagentx.retrieval.embed_cache import (
    load_embeddings_cache,
    save_embeddings_cache,
)


def test_save_and_load_embeddings_cache(tmp_path) -> None:
    cache_path = tmp_path / "study_embeddings.npz"
    payload = {
        "embeddings": np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32),
        "study_keys": ["patient1/study1", "patient2/study1"],
        "patient_ids": ["patient1", "patient2"],
    }
    save_embeddings_cache(
        cache_path,
        payload,
        build_config={"checkpoint": "ckpt.pt"},
    )

    loaded = load_embeddings_cache(cache_path)
    assert loaded is not None
    assert loaded["study_keys"] == payload["study_keys"]
    assert loaded["patient_ids"] == payload["patient_ids"]
    np.testing.assert_allclose(loaded["embeddings"], payload["embeddings"])
