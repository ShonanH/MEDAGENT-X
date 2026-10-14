"""DICOM loading and study-level datasets for RAD-DINO fine-tuning."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd
from PIL import Image, ImageEnhance

from medagentx.data.dicoms import local_dicom_path
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label


@dataclass(frozen=True)
class StudyTrainingRecord:
    """One study's quality-passed views and masked disease targets."""

    study_key: str
    deid_patient_id: str
    split: str
    dicom_paths: tuple[str, ...]
    targets: tuple[float, ...]
    masks: tuple[float, ...]


@dataclass(frozen=True)
class StudyInferenceRecord:
    """One study's quality-passed views without ground-truth requirements."""

    study_key: str
    deid_patient_id: str
    split: str
    dicom_paths: tuple[str, ...]


def _require_columns(
    frame: pd.DataFrame,
    columns: Sequence[str],
    frame_name: str,
) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(
            f"{frame_name} missing required columns {missing}. "
            f"Available: {list(frame.columns)}"
        )


def build_study_training_records(
    view_splits: pd.DataFrame,
    study_labels: pd.DataFrame,
    *,
    split: str,
    label_names: Sequence[str] = DISEASE_LABELS,
    target_prefix: str = "training_target",
    mask_prefix: str = "training_mask",
    path_column: str = "dicom_path",
) -> list[StudyTrainingRecord]:
    """Join split views to study-level masked targets for any image source."""
    _require_columns(
        view_splits,
        ("study_key", "deid_patient_id", path_column, "split"),
        "view_splits",
    )
    label_names = tuple(label_names)
    if not label_names:
        raise ValueError("label_names must be non-empty")
    target_columns = [
        f"{target_prefix}_{snake_label(label)}" for label in label_names
    ]
    mask_columns = [f"{mask_prefix}_{snake_label(label)}" for label in label_names]
    _require_columns(
        study_labels,
        ("study_key", *target_columns, *mask_columns),
        "study_labels",
    )

    label_rows = study_labels.copy()
    label_rows["study_key"] = label_rows["study_key"].astype(str).str.strip()
    if label_rows["study_key"].duplicated().any():
        duplicates = label_rows.loc[
            label_rows["study_key"].duplicated(keep=False), "study_key"
        ].unique()
        raise ValueError(
            f"study_labels contains duplicate study_key values: {duplicates[:10]}"
        )
    label_lookup = label_rows.set_index("study_key")

    selected = view_splits[
        view_splits["split"].astype(str).str.strip() == split
    ].copy()
    if selected.empty:
        raise ValueError(f"No views found for split={split!r}")

    records: list[StudyTrainingRecord] = []
    for study_key, rows in selected.groupby("study_key", sort=False):
        key = str(study_key).strip()
        if key not in label_lookup.index:
            raise ValueError(f"Missing study labels for study_key={key!r}")
        label_row = label_lookup.loc[key]

        masks = tuple(
            float(value)
            for value in pd.to_numeric(
                label_row[mask_columns], errors="coerce"
            ).fillna(0.0)
        )
        raw_targets = pd.to_numeric(
            label_row[target_columns], errors="coerce"
        ).fillna(0.0)
        targets = tuple(float(value) for value in raw_targets)
        if any(mask not in (0.0, 1.0) for mask in masks):
            raise ValueError(f"Invalid training mask for study_key={key!r}")
        if any(
            mask == 1.0 and target not in (0.0, 1.0)
            for target, mask in zip(targets, masks)
        ):
            raise ValueError(
                f"Supervised targets must be 0 or 1 for study_key={key!r}"
            )

        paths = tuple(
            dict.fromkeys(rows[path_column].astype(str).str.strip().tolist())
        )
        if not paths or any(not path for path in paths):
            raise ValueError(f"Study {key!r} has no usable DICOM paths")

        patient_ids = rows["deid_patient_id"].astype(str).str.strip().unique()
        if len(patient_ids) != 1:
            raise ValueError(
                f"Study {key!r} maps to multiple patient IDs: {patient_ids}"
            )
        records.append(
            StudyTrainingRecord(
                study_key=key,
                deid_patient_id=str(patient_ids[0]),
                split=split,
                dicom_paths=paths,
                targets=targets,
                masks=masks,
            )
        )
    return records


def build_study_inference_records(
    view_rows: pd.DataFrame,
    *,
    split: str | None = None,
) -> list[StudyInferenceRecord]:
    """Group quality-passed view rows into studies for image-only inference."""
    _require_columns(
        view_rows,
        ("study_key", "deid_patient_id", "dicom_path"),
        "view_rows",
    )
    selected = view_rows.copy()
    if split is not None:
        _require_columns(selected, ("split",), "view_rows")
        selected = selected[
            selected["split"].astype(str).str.strip() == split
        ].copy()
    if selected.empty:
        raise ValueError(f"No inference views found for split={split!r}")

    records: list[StudyInferenceRecord] = []
    for study_key, rows in selected.groupby("study_key", sort=False):
        key = str(study_key).strip()
        patient_ids = rows["deid_patient_id"].astype(str).str.strip().unique()
        if len(patient_ids) != 1:
            raise ValueError(
                f"Study {key!r} maps to multiple patient IDs: {patient_ids}"
            )
        paths = tuple(
            dict.fromkeys(rows["dicom_path"].astype(str).str.strip().tolist())
        )
        if not paths or any(not path for path in paths):
            raise ValueError(f"Study {key!r} has no usable DICOM paths")
        record_split = (
            str(rows.iloc[0]["split"]).strip()
            if "split" in rows.columns
            else (split or "")
        )
        records.append(
            StudyInferenceRecord(
                study_key=key,
                deid_patient_id=str(patient_ids[0]),
                split=record_split,
                dicom_paths=paths,
            )
        )
    return records


def dicom_to_pil_rgb(path: str | Path) -> Image.Image:
    """Load one grayscale DICOM as an intensity-normalized RGB image."""
    import pydicom

    dataset = pydicom.dcmread(path)
    pixels = np.asarray(dataset.pixel_array, dtype=np.float32)
    if pixels.ndim != 2 or pixels.size == 0:
        raise ValueError(
            f"Expected non-empty 2D DICOM pixels, got shape={pixels.shape}"
        )
    if not np.isfinite(pixels).all():
        raise ValueError("DICOM contains NaN or infinite pixels")

    slope = float(getattr(dataset, "RescaleSlope", 1.0))
    intercept = float(getattr(dataset, "RescaleIntercept", 0.0))
    pixels = pixels * slope + intercept

    if str(getattr(dataset, "PhotometricInterpretation", "")).upper() == (
        "MONOCHROME1"
    ):
        pixels = float(pixels.max()) + float(pixels.min()) - pixels

    low, high = np.percentile(pixels, [0.5, 99.5])
    if high <= low:
        normalized = np.zeros_like(pixels, dtype=np.float32)
    else:
        normalized = np.clip((pixels - low) / (high - low), 0.0, 1.0)
    uint8 = np.rint(normalized * 255.0).astype(np.uint8)
    return Image.fromarray(uint8, mode="L").convert("RGB")


def raster_to_pil_rgb(path: str | Path) -> Image.Image:
    """Load a standard raster image as a detached RGB PIL image."""
    with Image.open(path) as image:
        return image.convert("RGB").copy()


class LightCxrAugment:
    """Light geometry/intensity augmentation for disease classification."""

    def __init__(
        self,
        *,
        horizontal_flip_probability: float = 0.5,
        max_rotation_degrees: float = 5.0,
        brightness_jitter: float = 0.10,
        contrast_jitter: float = 0.10,
    ) -> None:
        self.horizontal_flip_probability = horizontal_flip_probability
        self.max_rotation_degrees = max_rotation_degrees
        self.brightness_jitter = brightness_jitter
        self.contrast_jitter = contrast_jitter

    def __call__(self, image: Image.Image) -> Image.Image:
        output = image
        if random.random() < self.horizontal_flip_probability:
            output = output.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

        angle = random.uniform(
            -self.max_rotation_degrees,
            self.max_rotation_degrees,
        )
        output = output.rotate(angle, resample=Image.Resampling.BILINEAR)

        brightness = random.uniform(
            1.0 - self.brightness_jitter,
            1.0 + self.brightness_jitter,
        )
        contrast = random.uniform(
            1.0 - self.contrast_jitter,
            1.0 + self.contrast_jitter,
        )
        output = ImageEnhance.Brightness(output).enhance(brightness)
        return ImageEnhance.Contrast(output).enhance(contrast)


class StudyDataset:
    """Dataset that returns all source images for one study."""

    def __init__(
        self,
        records: Sequence[StudyTrainingRecord],
        *,
        dicom_root: str | Path | None = None,
        image_root: str | Path | None = None,
        image_loader: Callable[[str | Path], Image.Image] = dicom_to_pil_rgb,
    ) -> None:
        if not records:
            raise ValueError("records must be non-empty")
        self.records = list(records)
        if dicom_root is not None and image_root is not None:
            raise ValueError("Pass only one of dicom_root or image_root")
        root = image_root if image_root is not None else dicom_root
        if root is None:
            raise ValueError("An image_root or dicom_root is required")
        self.image_root = Path(root)
        self.image_loader = image_loader

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]
        images = [
            self.image_loader(
                local_dicom_path(self.image_root, dicom_path)
            )
            for dicom_path in record.dicom_paths
        ]
        return {
            "study_key": record.study_key,
            "deid_patient_id": record.deid_patient_id,
            "dicom_paths": record.dicom_paths,
            "images": images,
            "targets": record.targets,
            "masks": record.masks,
        }


class InferenceStudyDataset:
    """Image-only study dataset for the Vision Agent/backend."""

    def __init__(
        self,
        records: Sequence[StudyInferenceRecord],
        *,
        dicom_root: str | Path | None = None,
        image_root: str | Path | None = None,
        image_loader: Callable[[str | Path], Image.Image] = dicom_to_pil_rgb,
    ) -> None:
        if not records:
            raise ValueError("records must be non-empty")
        self.records = list(records)
        if dicom_root is not None and image_root is not None:
            raise ValueError("Pass only one of dicom_root or image_root")
        root = image_root if image_root is not None else dicom_root
        if root is None:
            raise ValueError("An image_root or dicom_root is required")
        self.image_root = Path(root)
        self.image_loader = image_loader

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]
        images = [
            self.image_loader(
                local_dicom_path(self.image_root, dicom_path)
            )
            for dicom_path in record.dicom_paths
        ]
        return {
            "study_key": record.study_key,
            "deid_patient_id": record.deid_patient_id,
            "split": record.split,
            "dicom_paths": record.dicom_paths,
            "images": images,
        }


class StudyBatchCollator:
    """Flatten study views for RAD-DINO and retain study membership indices."""

    def __init__(
        self,
        processor: Any,
        *,
        augment: Callable[[Image.Image], Image.Image] | None = None,
    ) -> None:
        self.processor = processor
        self.augment = augment

    def __call__(self, items: Sequence[dict[str, Any]]) -> dict[str, Any]:
        import torch

        images: list[Image.Image] = []
        study_indices: list[int] = []
        view_counts: list[int] = []
        dicom_paths: list[tuple[str, ...]] = []

        for study_index, item in enumerate(items):
            study_images = item["images"]
            view_counts.append(len(study_images))
            dicom_paths.append(tuple(item["dicom_paths"]))
            for image in study_images:
                images.append(self.augment(image) if self.augment else image)
                study_indices.append(study_index)

        processed = self.processor(images=images, return_tensors="pt")
        output = {
            "pixel_values": processed["pixel_values"],
            "study_indices": torch.tensor(study_indices, dtype=torch.long),
            "num_studies": len(items),
            "study_keys": [item["study_key"] for item in items],
            "patient_ids": [item["deid_patient_id"] for item in items],
            "splits": [str(item.get("split", "")) for item in items],
            "dicom_paths": dicom_paths,
            "view_counts": view_counts,
        }
        if all("targets" in item and "masks" in item for item in items):
            output["targets"] = torch.tensor(
                [item["targets"] for item in items], dtype=torch.float32
            )
            output["masks"] = torch.tensor(
                [item["masks"] for item in items], dtype=torch.float32
            )
        return output
