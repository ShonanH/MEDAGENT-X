"""Fine-tuned RAD-DINO implementation of the VisionBackend contract."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Mapping, Sequence

import pandas as pd
import torch
from PIL import Image
from torch.utils.data import DataLoader
from transformers import AutoImageProcessor

from medagentx.vision.constants import VISION_BACKEND_ID
from medagentx.vision.data import (
    InferenceStudyDataset,
    StudyBatchCollator,
    StudyInferenceRecord,
    dicom_to_pil_rgb,
)
from medagentx.vision.inference_output import (
    VisionStudyOutput,
    build_study_outputs,
    study_outputs_to_prediction_frame,
)
from medagentx.vision.trainer import (
    collect_inference_predictions,
    load_finetuned_checkpoint,
)


class FineTunedRadDinoBackend:
    """Checkpoint-backed RAD-DINO study classifier."""

    def __init__(
        self,
        *,
        model: object,
        processor: object,
        thresholds: dict[str, float],
        device: torch.device,
        mixed_precision: bool = True,
    ) -> None:
        self.model = model
        self.processor = processor
        self.thresholds = dict(thresholds)
        self.device = device
        self.mixed_precision = mixed_precision

    @property
    def backend_id(self) -> str:
        return VISION_BACKEND_ID

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint_path: str | Path,
        *,
        device: str | torch.device,
        mixed_precision: bool = True,
    ) -> "FineTunedRadDinoBackend":
        resolved_device = torch.device(device)
        model, checkpoint = load_finetuned_checkpoint(
            checkpoint_path,
            device=resolved_device,
        )
        processor = AutoImageProcessor.from_pretrained(
            checkpoint["model_name"]
        )
        return cls(
            model=model,
            processor=processor,
            thresholds=checkpoint["thresholds"],
            device=resolved_device,
            mixed_precision=mixed_precision,
        )

    def _build_loader(
        self,
        records: Sequence[StudyInferenceRecord],
        *,
        dicom_root: str | Path,
        batch_size: int,
        num_workers: int,
        image_loader: Callable[[str | Path], Image.Image] | None = None,
    ) -> DataLoader:
        dataset = InferenceStudyDataset(
            records,
            dicom_root=dicom_root,
            image_loader=image_loader or dicom_to_pil_rgb,
        )
        return DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            pin_memory=self.device.type == "cuda",
            persistent_workers=num_workers > 0,
            collate_fn=StudyBatchCollator(self.processor),
        )

    def _collect_predictions(
        self,
        records: Sequence[StudyInferenceRecord],
        *,
        dicom_root: str | Path,
        batch_size: int,
        num_workers: int,
        image_loader: Callable[[str | Path], Image.Image] | None = None,
    ) -> dict[str, object]:
        loader = self._build_loader(
            records,
            dicom_root=dicom_root,
            batch_size=batch_size,
            num_workers=num_workers,
            image_loader=image_loader,
        )
        return collect_inference_predictions(
            self.model,
            loader,
            device=self.device,
            mixed_precision=self.mixed_precision,
        )

    def predict_study_outputs(
        self,
        records: Sequence[StudyInferenceRecord],
        *,
        dicom_root: str | Path,
        batch_size: int,
        num_workers: int,
        threshold_overrides: Mapping[str, float] | None = None,
        image_loader: Callable[[str | Path], Image.Image] | None = None,
    ) -> list[VisionStudyOutput]:
        """Run one image pass and return probabilities plus study embeddings."""
        predictions = self._collect_predictions(
            records,
            dicom_root=dicom_root,
            batch_size=batch_size,
            num_workers=num_workers,
            image_loader=image_loader,
        )
        return build_study_outputs(
            predictions,
            self.thresholds,
            vision_backend_id=self.backend_id,
            threshold_overrides=threshold_overrides,
        )

    def predict_studies(
        self,
        records: Sequence[StudyInferenceRecord],
        *,
        dicom_root: str | Path,
        batch_size: int,
        num_workers: int,
        threshold_overrides: Mapping[str, float] | None = None,
        image_loader: Callable[[str | Path], Image.Image] | None = None,
    ) -> pd.DataFrame:
        """Return the permanent vision prediction table without embeddings."""
        outputs = self.predict_study_outputs(
            records,
            dicom_root=dicom_root,
            batch_size=batch_size,
            num_workers=num_workers,
            threshold_overrides=threshold_overrides,
            image_loader=image_loader,
        )
        return study_outputs_to_prediction_frame(outputs)

    def predict_studies_with_outputs(
        self,
        records: Sequence[StudyInferenceRecord],
        *,
        dicom_root: str | Path,
        batch_size: int,
        num_workers: int,
        threshold_overrides: Mapping[str, float] | None = None,
        image_loader: Callable[[str | Path], Image.Image] | None = None,
    ) -> tuple[pd.DataFrame, list[VisionStudyOutput]]:
        """Return both the CSV contract and embedding-bearing study outputs."""
        predictions = self._collect_predictions(
            records,
            dicom_root=dicom_root,
            batch_size=batch_size,
            num_workers=num_workers,
            image_loader=image_loader,
        )
        outputs = build_study_outputs(
            predictions,
            self.thresholds,
            vision_backend_id=self.backend_id,
            threshold_overrides=threshold_overrides,
        )
        return study_outputs_to_prediction_frame(outputs), outputs
