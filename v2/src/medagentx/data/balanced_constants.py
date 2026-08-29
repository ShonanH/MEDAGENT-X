"""Locked policy constants for the label-enriched cohort."""

from __future__ import annotations

from medagentx.splits.constants import TEST_SPLIT, TRAIN_SPLIT, VAL_SPLIT

BALANCED_COHORT_POLICY_VERSION = "label_enriched_cohort_policy_v2"
BALANCED_EVAL_MODE = "label_sufficient_eval"

# Patients contribute a bounded, label-aware subset of their studies. Every
# selected study still lands in that patient's single deterministic split, so
# patient-level leakage protection is unchanged; we simply stop downloading
# redundant repeat studies from the same patient.
MAX_STUDIES_PER_PATIENT = 4

DEFAULT_BALANCED_COHORT_ROOT = "v2/artifacts/cohort_balanced_v1"
DEFAULT_REUSE_DICOM_ROOT = "v2/artifacts/cohort/dicom_train"

# Selection happens before pixel-quality filtering. These buffered targets are
# intentionally higher than the final targets to absorb failed DICOM views.
PRE_QUALITY_POSITIVE_TARGETS: dict[str, int] = {
    TRAIN_SPLIT: 250,
    VAL_SPLIT: 63,
    TEST_SPLIT: 63,
}

POST_QUALITY_POSITIVE_TARGETS: dict[str, int] = {
    TRAIN_SPLIT: 200,
    VAL_SPLIT: 50,
    TEST_SPLIT: 50,
}

NEGATIVE_TO_POSITIVE_RATIO = 2
SOFT_PATIENT_CAP = 5000
