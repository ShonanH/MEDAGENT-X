"""GPU-resident study batches for throughput-sensitive RAD-DINO training."""

from __future__ import annotations

import math
from typing import Any, Iterator, Sequence

import torch
from torch.nn import functional as F

from medagentx.vision.data import StudyTrainingRecord


class GpuResidentStudyLoader:
    """Create complete study batches from a preloaded uint8 GPU image tensor.

    No per-view reads, PIL conversion, processor invocation, or CPU-to-GPU
    image copy occurs after startup.  Targets and study metadata are tiny and
    are also constructed directly on the target device.
    """

    def __init__(
        self,
        records: Sequence[StudyTrainingRecord],
        *,
        path_to_index: dict[str, int],
        cached_pixels: torch.Tensor,
        batch_size: int,
        train: bool,
        image_mean: Sequence[float],
        image_std: Sequence[float],
    ) -> None:
        if not records or batch_size <= 0:
            raise ValueError("records must be non-empty and batch_size must be > 0")
        if cached_pixels.dtype != torch.uint8:
            raise ValueError("cached_pixels must be a uint8 tensor")
        if (
            cached_pixels.ndim != 4
            or tuple(cached_pixels.shape[1:]) != (1, 518, 518)
        ):
            raise ValueError("cached_pixels must have shape [views, 1, 518, 518]")
        self.records = list(records)
        self.batch_size = batch_size
        self.train = train
        self.cached_pixels = cached_pixels
        self.device = cached_pixels.device
        self._record_view_indices = [
            tuple(path_to_index[path] for path in record.dicom_paths)
            for record in self.records
        ]
        self.mean = torch.tensor(image_mean, device=self.device).view(1, 3, 1, 1)
        self.std = torch.tensor(image_std, device=self.device).view(1, 3, 1, 1)
        if tuple(self.mean.shape) != (1, 3, 1, 1) or torch.any(self.std <= 0):
            raise ValueError(
                "RAD-DINO image statistics must contain three positive values"
            )

    def __len__(self) -> int:
        return math.ceil(len(self.records) / self.batch_size)

    def _augment(self, images: torch.Tensor) -> torch.Tensor:
        """Apply the existing light CXR augmentation distribution on the GPU."""
        count = len(images)
        if count == 0:
            return images
        flipped = torch.rand(count, device=self.device) < 0.5
        if torch.any(flipped):
            images[flipped] = torch.flip(images[flipped], dims=(3,))

        angles = (torch.rand(count, device=self.device) * 10.0 - 5.0) * (
            math.pi / 180.0
        )
        theta = torch.zeros((count, 2, 3), device=self.device, dtype=images.dtype)
        theta[:, 0, 0] = torch.cos(angles)
        theta[:, 0, 1] = -torch.sin(angles)
        theta[:, 1, 0] = torch.sin(angles)
        theta[:, 1, 1] = torch.cos(angles)
        grid = F.affine_grid(theta, images.shape, align_corners=False)
        images = F.grid_sample(
            images,
            grid,
            mode="bilinear",
            padding_mode="zeros",
            align_corners=False,
        )
        brightness = torch.empty(
            (count, 1, 1, 1), device=self.device
        ).uniform_(0.9, 1.1)
        contrast = torch.empty(
            (count, 1, 1, 1), device=self.device
        ).uniform_(0.9, 1.1)
        images = images * brightness
        means = images.mean(dim=(2, 3), keepdim=True)
        return ((images - means) * contrast + means).clamp_(0.0, 1.0)

    def _make_batch(self, record_indices: Sequence[int]) -> dict[str, Any]:
        view_indices: list[int] = []
        study_indices: list[int] = []
        records = [self.records[index] for index in record_indices]
        for study_index, record_index in enumerate(record_indices):
            views = self._record_view_indices[record_index]
            view_indices.extend(views)
            study_indices.extend([study_index] * len(views))
        image_indices = torch.tensor(
            view_indices, device=self.device, dtype=torch.long
        )
        pixels = self.cached_pixels.index_select(0, image_indices).float().div_(255.0)
        if self.train:
            pixels = self._augment(pixels)
        pixels = pixels.expand(-1, 3, -1, -1)
        pixel_values = (pixels - self.mean) / self.std
        return {
            "pixel_values": pixel_values,
            "study_indices": torch.tensor(
                study_indices, device=self.device, dtype=torch.long
            ),
            "num_studies": len(records),
            "study_keys": [record.study_key for record in records],
            "patient_ids": [record.deid_patient_id for record in records],
            "splits": [record.split for record in records],
            "dicom_paths": [record.dicom_paths for record in records],
            "view_counts": [len(record.dicom_paths) for record in records],
            "targets": torch.tensor(
                [record.targets for record in records],
                device=self.device,
                dtype=torch.float32,
            ),
            "masks": torch.tensor(
                [record.masks for record in records],
                device=self.device,
                dtype=torch.float32,
            ),
        }

    def __iter__(self) -> Iterator[dict[str, Any]]:
        if self.train:
            order = torch.randperm(len(self.records)).tolist()
        else:
            order = list(range(len(self.records)))
        for start in range(0, len(order), self.batch_size):
            yield self._make_batch(order[start : start + self.batch_size])
