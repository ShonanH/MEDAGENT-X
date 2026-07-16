from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "chexpert_plus" / "fusion_classifier"

DEFAULT_REDIVIS_CSV = PROJECT_ROOT / "outputs" / "chexpert_plus" / "redivis_chexpert_plus_filtered_rows.csv"
DEFAULT_CONVNEXT_MANIFEST = PROJECT_ROOT / "outputs" / "chexpert_plus" / "convnext_feature_manifest.csv"
DEFAULT_RADDINO_MANIFEST = PROJECT_ROOT / "outputs" / "chexpert_plus" / "raddino_feature_manifest.csv"
DEFAULT_DENSENET_PREDICTIONS = PROJECT_ROOT / "outputs" / "chexpert_plus" / "image_classifier_predictions.csv"

DEFAULT_REPORT_LABEL_TABLE = DEFAULT_OUTPUT_DIR / "report_label_training_table.csv"
DEFAULT_SPLIT_METADATA = DEFAULT_OUTPUT_DIR / "patient_split_metadata.csv"
DEFAULT_MODEL_PATH = DEFAULT_OUTPUT_DIR / "fusion_model.pt"
DEFAULT_THRESHOLDS_PATH = DEFAULT_OUTPUT_DIR / "fusion_thresholds.json"
DEFAULT_TRAINING_METRICS = DEFAULT_OUTPUT_DIR / "fusion_training_metrics.csv"
DEFAULT_TEST_PREDICTIONS = DEFAULT_OUTPUT_DIR / "fusion_test_predictions.csv"
DEFAULT_FUSION_PREDICTIONS = DEFAULT_OUTPUT_DIR / "fusion_predictions.csv"
DEFAULT_ENSEMBLE_PREDICTIONS = DEFAULT_OUTPUT_DIR / "ensemble_classifier_predictions.csv"

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

# present=1, absent=0, uncertain/unmentioned=NaN (masked in loss)
LABEL_VALUE_PRESENT = 1.0
LABEL_VALUE_ABSENT = 0.0

SPLIT_SEED = 42
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15


def snake_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")