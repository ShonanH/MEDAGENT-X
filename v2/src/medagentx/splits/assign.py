"""Deterministic patient-level split assignment."""

from __future__ import annotations

import hashlib

from medagentx.splits.constants import (
    SPLIT_SEED,
    TEST_RATIO,
    TEST_SPLIT,
    TRAIN_RATIO,
    TRAIN_SPLIT,
    VAL_RATIO,
    VAL_SPLIT,
)


def assign_patient_split(patient_id: str, *, seed: int = SPLIT_SEED) -> str:
    """Assign one patient to train/val/test via a stable hash bucket.

    Locked policy:
      - split unit = deid_patient_id
      - ratios = 0.70 / 0.15 / 0.15
      - deterministic MD5(seed:patient_id)
      - no agent_eval holdout
    """
    if not isinstance(patient_id, str) or not patient_id.strip():
        raise ValueError("patient_id must be a non-empty string")
    if seed < 0:
        raise ValueError("seed must be >= 0")
    if abs((TRAIN_RATIO + VAL_RATIO + TEST_RATIO) - 1.0) > 1e-9:
        raise ValueError("TRAIN_RATIO + VAL_RATIO + TEST_RATIO must equal 1.0")

    cleaned = patient_id.strip()
    digest = hashlib.md5(f"{seed}:{cleaned}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF

    if bucket < TRAIN_RATIO:
        return TRAIN_SPLIT
    if bucket < TRAIN_RATIO + VAL_RATIO:
        return VAL_SPLIT
    return TEST_SPLIT
