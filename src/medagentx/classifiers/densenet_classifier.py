from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pydicom
import skimage.io
import torch
import torchxrayvision as xrv
import torchvision


DEFAULT_QUALITY_EVIDENCE_CSV = Path("outputs/chexpert_plus/quality_evidence_manifest.csv")
DEFAULT_QUALITY_GATE_CSV = Path("outputs/chexpert_plus/quality_gate_decisions.csv")
DEFAULT_OUTPUT_CSV = Path("outputs/chexpert_plus/image_classifier_predictions.csv")

DEFAULT_MODEL_WEIGHTS = "densenet121-res224-all"
DEFAULT_PRESENT_THRESHOLD = 0.50
DEFAULT_ABSENT_THRESHOLD = 0.20


CHEXPERT_LABEL_MAP = {
    "Atelectasis": "Atelectasis",
    "Cardiomegaly": "Cardiomegaly",
    "Consolidation": "Consolidation",
    "Edema": "Edema",
    "Effusion": "Pleural Effusion",
    "Pneumonia": "Pneumonia",
    "Pneumothorax": "Pneumothorax",
    "Fracture": "Fracture",
    "Lung Lesion": "Lung Lesion",
    "Lung Opacity": "Lung Opacity",
    "Enlarged Cardiomediastinum": "Enlarged Cardiomediastinum",
    "Pleural_Thickening": "Pleural Other",
}


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().lower().replace("\\", "/")


def snake_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def choose_device(requested_device: str = "") -> torch.device:
    if requested_device:
        return torch.device(requested_device)

    if torch.cuda.is_available():
        return torch.device("cuda")

    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")

    return torch.device("cpu")


def load_quality_gate_row(
    study_key: str,
    dicom_path: str,
    quality_gate_csv: Path,
) -> dict[str, Any]:
    if not quality_gate_csv.exists():
        return {}

    df = pd.read_csv(quality_gate_csv, dtype=str)

    matched = df[
        df["study_key"].map(normalize_text).eq(normalize_text(study_key))
        & df["dicom_path"].map(normalize_text).eq(normalize_text(dicom_path))
    ]

    if matched.empty:
        return {}

    return matched.iloc[0].to_dict()


def find_image_path(
    study_key: str,
    dicom_path: str,
    quality_evidence_csv: Path,
) -> Path:
    if not quality_evidence_csv.exists():
        raise FileNotFoundError(f"Missing quality evidence CSV: {quality_evidence_csv}")

    df = pd.read_csv(quality_evidence_csv, dtype=str)

    matched = df[
        df["study_key"].map(normalize_text).eq(normalize_text(study_key))
        & df["dicom_path"].map(normalize_text).eq(normalize_text(dicom_path))
    ]

    if matched.empty:
        raise RuntimeError(f"Case not found in quality evidence manifest: {study_key} / {dicom_path}")

    row = matched.iloc[0]

    candidates = [
        row.get("local_dicom_path", ""),
        row.get("validation_preview_path", ""),
        dicom_path,
        str(Path("data/raw/chexpert_plus/dicom_train") / dicom_path),
    ]

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)

    raise FileNotFoundError(
        "Could not find local image/DICOM file. Checked: "
        + json.dumps(candidates, indent=2)
    )


def dicom_to_uint8(path: Path) -> np.ndarray:
    ds = pydicom.dcmread(path)
    image = ds.pixel_array.astype(np.float32)

    slope = float(getattr(ds, "RescaleSlope", 1.0))
    intercept = float(getattr(ds, "RescaleIntercept", 0.0))
    image = image * slope + intercept

    if getattr(ds, "PhotometricInterpretation", "").upper() == "MONOCHROME1":
        image = image.max() - image

    low, high = np.percentile(image, [0.5, 99.5])
    image = np.clip(image, low, high)

    if high > low:
        image = (image - low) / (high - low)
    else:
        image = np.zeros_like(image)

    return (image * 255.0).astype(np.uint8)


def load_xray_for_torchxrayvision(path: Path) -> torch.Tensor:
    suffix = path.suffix.lower()

    if suffix == ".dcm":
        image = dicom_to_uint8(path)
    else:
        image = skimage.io.imread(str(path))

    if image.ndim == 3:
        image = image.mean(axis=2)

    image = xrv.datasets.normalize(image, 255)
    image = image[None, ...]

    transform = torchvision.transforms.Compose(
        [
            xrv.datasets.XRayCenterCrop(),
            xrv.datasets.XRayResizer(224),
        ]
    )

    image = transform(image)
    return torch.from_numpy(image).float()


def load_classifier(weights: str, device: torch.device):
    model = xrv.models.DenseNet(weights=weights)
    model = model.to(device)
    model.eval()
    return model


def classify_image_with_model(
    model,
    image_path: Path,
    device: torch.device,
) -> tuple[dict[str, float], list[str]]:
    image = load_xray_for_torchxrayvision(image_path).to(device)
    with torch.no_grad():
        outputs = model(image[None, ...])
    probabilities = outputs[0].detach().cpu().numpy().astype(float)
    raw_predictions = {
        pathology: float(probability)
        for pathology, probability in zip(model.pathologies, probabilities)
    }
    return raw_predictions, list(model.pathologies)


def probability_status(
    probability: float | None,
    present_threshold: float = DEFAULT_PRESENT_THRESHOLD,
    absent_threshold: float = DEFAULT_ABSENT_THRESHOLD,
) -> str:
    if probability is None:
        return "unavailable"

    if probability >= present_threshold:
        return "present"

    if probability <= absent_threshold:
        return "absent"

    return "uncertain"


def map_to_chexpert_predictions(raw_predictions: dict[str, float]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}

    for raw_label, chexpert_label in CHEXPERT_LABEL_MAP.items():
        probability = raw_predictions.get(raw_label)

        mapped[chexpert_label] = {
            "source_label": raw_label,
            "probability": probability,
            "status": probability_status(probability),
        }

    mapped["Support Devices"] = {
        "source_label": "",
        "probability": None,
        "status": "unavailable",
    }

    mapped["No Finding"] = {
        "source_label": "",
        "probability": None,
        "status": "not_computed",
    }

    return mapped


def build_output_row(
    study_key: str,
    dicom_path: str,
    image_path: Path,
    weights: str,
    device: torch.device,
    raw_predictions: dict[str, float],
    model_pathologies: list[str],
) -> dict[str, Any]:
    mapped_predictions = map_to_chexpert_predictions(raw_predictions)

    row: dict[str, Any] = {
        "study_key": study_key,
        "dicom_path": dicom_path,
        "image_path": str(image_path),
        "classifier_model": "torchxrayvision.DenseNet",
        "classifier_weights": weights,
        "classifier_device": str(device),
        "present_threshold": DEFAULT_PRESENT_THRESHOLD,
        "absent_threshold": DEFAULT_ABSENT_THRESHOLD,
        "model_pathologies_json": json.dumps(model_pathologies),
    }

    for label, info in mapped_predictions.items():
        label_key = snake_label(label)
        probability = info["probability"]

        row[f"classifier_prob_{label_key}"] = "" if probability is None else probability
        row[f"classifier_status_{label_key}"] = info["status"]
        row[f"classifier_source_label_{label_key}"] = info["source_label"]

    present_labels = [
        label for label, info in mapped_predictions.items()
        if info["status"] == "present"
    ]

    row["classifier_present_labels_json"] = json.dumps(present_labels)
    row["classifier_raw_predictions_json"] = json.dumps(raw_predictions, sort_keys=True)
    row["route_next"] = "retrieval_agent"

    return row
