from __future__ import annotations

import re

from medagentx.paths import (
    CHEXPERT_OUTPUT_DIR,
    FUSION_OUTPUT_DIR,
    RAW_DATA_DIR,
)

DEFAULT_OUTPUT_DIR = FUSION_OUTPUT_DIR

DEFAULT_REDIVIS_CSV = CHEXPERT_OUTPUT_DIR / "redivis_chexpert_plus_filtered_rows.csv"
DEFAULT_CONVNEXT_MANIFEST = CHEXPERT_OUTPUT_DIR / "convnext_feature_manifest.csv"
DEFAULT_RADDINO_MANIFEST = CHEXPERT_OUTPUT_DIR / "raddino_feature_manifest.csv"
DEFAULT_DENSENET_PREDICTIONS = CHEXPERT_OUTPUT_DIR / "image_classifier_predictions.csv"
DEFAULT_CHEXPERT_LABELS_CSV = CHEXPERT_OUTPUT_DIR / "chexpert_labels.csv"
DEFAULT_CHEXPERT_FINDINGS_JSON = (
    RAW_DATA_DIR / "chexpert_plus" / "chexpert_labels" / "findings_fixed.json"
)

DEFAULT_REPORT_LABEL_TABLE = DEFAULT_OUTPUT_DIR / "report_label_training_table.csv"
DEFAULT_SPLIT_METADATA = DEFAULT_OUTPUT_DIR / "patient_split_metadata.csv"
DEFAULT_AGENT_EVAL_MANIFEST = DEFAULT_OUTPUT_DIR / "agent_eval_patient_manifest.csv"
DEFAULT_QUALITY_GATE_CSV = CHEXPERT_OUTPUT_DIR / "quality_gate_decisions.csv"
DEFAULT_QUALITY_GATE_ELIGIBLE_COHORT = CHEXPERT_OUTPUT_DIR / "quality_gate_eligible_cohort.csv"
DEFAULT_MODEL_PATH = DEFAULT_OUTPUT_DIR / "fusion_model.pt"
DEFAULT_THRESHOLDS_PATH = DEFAULT_OUTPUT_DIR / "fusion_thresholds.json"
DEFAULT_TRAINING_METRICS = DEFAULT_OUTPUT_DIR / "fusion_training_metrics.csv"
DEFAULT_TEST_PREDICTIONS = DEFAULT_OUTPUT_DIR / "fusion_test_predictions.csv"
DEFAULT_FUSION_PREDICTIONS = DEFAULT_OUTPUT_DIR / "fusion_predictions.csv"
DEFAULT_ENSEMBLE_PREDICTIONS = DEFAULT_OUTPUT_DIR / "ensemble_classifier_predictions.csv"
DEFAULT_ENSEMBLE_THRESHOLDS = DEFAULT_OUTPUT_DIR / "ensemble_thresholds.json"

FUSION_MODEL_VERSION = "fusion_mlp_v1"

DISEASE_LABELS = [
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
    "Pneumonia",
    "Pneumothorax",
    "Fracture",
    "Lung Lesion",
    "Lung Opacity",
    "Enlarged Cardiomediastinum",
    "Pleural Other",
]

NON_DISEASE_LABELS = ["Support Devices", "No Finding"]

ALL_CHEXPERT_LABELS = DISEASE_LABELS + NON_DISEASE_LABELS

# present=1, absent=0, uncertain/unmentioned=NaN (masked in loss)
LABEL_VALUE_PRESENT = 1.0
LABEL_VALUE_ABSENT = 0.0

SPLIT_SEED = 42
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

# Held-out patients for script 17 agent+judge evaluation (never used in fusion train/val).
AGENT_EVAL_PATIENT_COUNT = 100
AGENT_EVAL_MIN_CASES = 100
AGENT_EVAL_SPLIT = "agent_eval"
QUALITY_GATE_PASS_DECISIONS = ("pass", "review_with_technical_warning")
QUALITY_GATE_ROUTE_RETRIEVAL = "retrieval_agent"
FUSION_TRAIN_SPLIT = "train"
FUSION_VAL_SPLIT = "validation"
FUSION_TEST_SPLIT = "test"


def derive_no_finding_status(disease_statuses: dict[str, str]) -> str:
    if any(status == "present" for status in disease_statuses.values()):
        return "absent"
    if any(status == "uncertain" for status in disease_statuses.values()):
        return "uncertain"
    return "present"


def snake_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
