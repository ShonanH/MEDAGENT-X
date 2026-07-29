"""Fine-tuned RAD-DINO implementation of the VisionBackend contract."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd
import torch
from torch.utils.data import DataLoader
from transformers import AutoImageProcessor

from medagentx.vision.constants import VISION_BACKEND_ID
from medagentx.vision.data import (
    InferenceStudyDataset,
    StudyBatchCollator,
    StudyInferenceRecord,
)
from medagentx.vision.trainer import (
    collect_inference_predictions,
    inference_prediction_table,
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

    def predict_studies(
        self,
        records: Sequence[StudyInferenceRecord],
        *,
        dicom_root: str | Path,
        batch_size: int,
        num_workers: int,
    ) -> pd.DataFrame:
        dataset = InferenceStudyDataset(records, dicom_root=dicom_root)
        loader = DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            pin_memory=self.device.type == "cuda",
            persistent_workers=num_workers > 0,
            collate_fn=StudyBatchCollator(self.processor),
        )
        predictions = collect_inference_predictions(
            self.model,
            loader,
            device=self.device,
            mixed_precision=self.mixed_precision,
        )
        return inference_prediction_table(predictions, self.thresholds)
