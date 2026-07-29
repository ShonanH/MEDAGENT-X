"""Locked constants for patient-level train/val/test splits."""

from __future__ import annotations

SPLIT_POLICY_VERSION = "patient_split_policy_v1"

SPLIT_SEED = 42
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

TRAIN_SPLIT = "train"
VAL_SPLIT = "val"
TEST_SPLIT = "test"

ALL_SPLITS: tuple[str, ...] = (TRAIN_SPLIT, VAL_SPLIT, TEST_SPLIT)
