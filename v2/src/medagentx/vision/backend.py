"""Fine-tuned RAD-DINO implementation of the VisionBackend contract."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd
import torch
from torch.utils.data import DataLoader

from medagentx.vision.constants import VISION_BACKEND_ID
from medagentx.vision.data import (
    InferenceStudyDataset,
    StudyBatchCollator,
    StudyInferenceRecord,
)
from medagentx.vision.gpu_data import GpuResidentStudyLoader
from medagentx.vision.inference_output import (
    VisionStudyOutput,
    build_study_outputs,
    study_outputs_to_prediction_frame,
)
from medagentx.vision.processor import load_training_image_processor
from medagentx.vision.model_ready_cache import ModelReadyImageCache
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
        model_name: str,
        device: torch.device,
        mixed_precision: bool = True,
    ) -> None:
        self.model = model
        self.processor = processor
        self.thresholds = dict(thresholds)
        self.model_name = str(model_name)
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
        processor = load_training_image_processor(
            checkpoint_path,
            checkpoint,
        )
        return cls(
            model=model,
            processor=processor,
            thresholds=checkpoint["thresholds"],
            model_name=str(checkpoint["model_name"]),
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
    ) -> DataLoader:
        dataset = InferenceStudyDataset(records, dicom_root=dicom_root)
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
    ) -> dict[str, object]:
        loader = self._build_loader(
            records,
            dicom_root=dicom_root,
            batch_size=batch_size,
            num_workers=num_workers,
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
    ) -> list[VisionStudyOutput]:
        """Run one DICOM pass and return probabilities plus study embeddings."""
        predictions = self._collect_predictions(
            records,
            dicom_root=dicom_root,
            batch_size=batch_size,
            num_workers=num_workers,
        )
        return build_study_outputs(
            predictions,
            self.thresholds,
            vision_backend_id=self.backend_id,
            threshold_overrides=threshold_overrides,
        )

    def predict_study_outputs_from_model_ready_cache(
        self,
        records: Sequence[StudyInferenceRecord],
        *,
        cache_root: str | Path,
        cohort_root: str | Path,
        dicom_root: str | Path,
        view_splits_csv: str | Path,
        batch_size: int,
        preload_chunk_size: int = 64,
        threshold_overrides: Mapping[str, float] | None = None,
    ) -> list[VisionStudyOutput]:
        """Run inference from the validated GPU-resident uint8 image cache."""
        if self.device.type != "cuda":
            raise ValueError("The model-ready image cache requires a CUDA device")
        if preload_chunk_size <= 0:
            raise ValueError("preload_chunk_size must be > 0")

        image_processor_config = {
            "model_name": self.model_name,
            "config": self.processor.to_dict(),
        }
        image_cache = ModelReadyImageCache(cache_root)
        image_cache.validate_training_inputs(
            cohort_root=cohort_root,
            dicom_root=dicom_root,
            view_splits_csv=view_splits_csv,
            required_paths=(
                path for record in records for path in record.dicom_paths
            ),
            image_processor_config=image_processor_config,
        )
        cached_pixels = image_cache.preload_to_device(
            self.device,
            chunk_size=preload_chunk_size,
        )
        loader = GpuResidentStudyLoader(
            records,
            path_to_index=image_cache.path_to_index,
            cached_pixels=cached_pixels,
            batch_size=batch_size,
            train=False,
            image_mean=image_processor_config["config"]["image_mean"],
            image_std=image_processor_config["config"]["image_std"],
        )
        print(
            "[Vision] model-ready cache preloaded to GPU "
            f"views={len(cached_pixels)} resident_gib="
            f"{cached_pixels.numel() / (1024**3):.2f}",
            flush=True,
        )
        predictions = collect_inference_predictions(
            self.model,
            loader,
            device=self.device,
            mixed_precision=self.mixed_precision,
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
    ) -> pd.DataFrame:
        """Return the permanent vision prediction table without embeddings."""
        outputs = self.predict_study_outputs(
            records,
            dicom_root=dicom_root,
            batch_size=batch_size,
            num_workers=num_workers,
            threshold_overrides=threshold_overrides,
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
    ) -> tuple[pd.DataFrame, list[VisionStudyOutput]]:
        """Return both the CSV contract and embedding-bearing study outputs."""
        predictions = self._collect_predictions(
            records,
            dicom_root=dicom_root,
            batch_size=batch_size,
            num_workers=num_workers,
        )
        outputs = build_study_outputs(
            predictions,
            self.thresholds,
            vision_backend_id=self.backend_id,
            threshold_overrides=threshold_overrides,
        )
        return study_outputs_to_prediction_frame(outputs), outputs
