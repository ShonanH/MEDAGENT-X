"""Locked identifiers and defaults for deterministic label fusion."""

from __future__ import annotations

from medagentx.labels.constants import DISEASE_LABELS

FUSION_POLICY_VERSION = "deterministic_gray_zone_fusion_v2"

# Decision 1 — rules-only fusion; no LLM in this step (Report Writer is separate).
FUSION_USE_LLM = False

# Decision 2 — gray zone: fusion may override vision only when |p - tau| <= margin.
GRAY_ZONE_MARGIN = 0.15

# Decision 3 — keyword mention counts from retrieved reports (see reasoning/mentions.py).
PROMOTION_MIN_POSITIVE_COUNT = 3
PROMOTION_MAX_NEGATIVE_COUNT = 0
DEMOTION_MIN_NEGATIVE_COUNT = 1

# Decision 4 — demote gray-zone present only when negatives outweigh positives.
DEMOTION_REQUIRES_NEGATIVE_MAJORITY = True

# Decision 5 — label-specific overrides tune noisy promotion/demotion behavior.
LABEL_FUSION_RULE_OVERRIDES: dict[str, dict[str, int]] = {
    "Pleural Effusion": {
        "promotion_min_positive_count": 4,
    },
    "Consolidation": {
        "demotion_min_negative_count": 3,
    },
    "Lung Lesion": {
        "demotion_min_negative_count": 3,
    },
    "Lung Opacity": {
        "demotion_min_negative_count": 3,
    },
}

# Decision 6 — fusion applies only to every supervised disease head.
FUSION_LABELS: tuple[str, ...] = DISEASE_LABELS

# Decision 7 — fusion outputs 12 disease statuses only (no No Finding / Support Devices).
FUSION_INCLUDES_NO_FINDING = False
FUSION_INCLUDES_SUPPORT_DEVICES = False

# Retrieval input contract at inference (locked to retrieval.constants.DEFAULT_TOP_K).
FUSION_RETRIEVAL_TOP_K = 5

# Decision 9 — Judge compares vision-only vs fusion on both slices.
EVALUATE_FULL_TEST = True
EVALUATE_GRAY_ZONE_SUBSET = True

# Default artifact location under a cohort root (offline fusion eval outputs).
DEFAULT_FUSION_SUBDIR = "reasoning/fusion_eval_v1"
