"""Contract tests for compact GPU-resident RAD-DINO inputs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch
from PIL import Image

pydicom = pytest.importorskip("pydicom")
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from medagentx.vision.cache import build_raddino_cache
from medagentx.vision.data import StudyTrainingRecord
from medagentx.vision.gpu_data import GpuResidentStudyLoader
from medagentx.vision.model_ready_cache import (
    ModelReadyImageCache,
    build_model_ready_cache,
)


class _FixedGeometryProcessor:
    """Small offline stand-in for the RAD-DINO geometry-only processor."""

    def __call__(self, *, images, return_tensors, **kwargs):
        assert return_tensors == "pt"
        assert kwargs["do_rescale"] is False
        assert kwargs["do_normalize"] is False
        arrays = []
        for image in images:
            resized = image.resize((518, 518), Image.Resampling.BICUBIC)
            arrays.append(np.asarray(resized, dtype=np.uint8).transpose(2, 0, 1))
        return {"pixel_values": torch.from_numpy(np.stack(arrays))}


def _write_dicom(path: Path, pixels: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = generate_uid()
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dataset = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    dataset.is_little_endian = True
    dataset.is_implicit_VR = False
    dataset.SOPClassUID = meta.MediaStorageSOPClassUID
    dataset.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    dataset.Rows, dataset.Columns = pixels.shape
    dataset.SamplesPerPixel = 1
    dataset.PhotometricInterpretation = "MONOCHROME2"
    dataset.BitsAllocated = pixels.dtype.itemsize * 8
    dataset.BitsStored = dataset.BitsAllocated
    dataset.HighBit = dataset.BitsStored - 1
    dataset.PixelRepresentation = 0
    dataset.PixelData = pixels.tobytes()
    dataset.save_as(path)


def _raw_cache(tmp_path: Path) -> tuple[Path, Path, Path]:
    cohort = tmp_path / "cohort"
    dicom_root = cohort / "dicom_train"
    rows = []
    for split, name in (("train", "a"), ("val", "b"), ("test", "c")):
        relative = f"p/{name}.dcm"
        _write_dicom(
            dicom_root / relative,
            np.array([[0, 40], [100, 300]], dtype=np.uint16),
        )
        rows.append(
            {
                "dicom_path": relative,
                "split": split,
                "study_key": name,
                "deid_patient_id": "p",
            }
        )
    views = cohort / "splits" / "view_splits.csv"
    views.parent.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(views, index=False)
    raw = build_raddino_cache(
        cohort_root=cohort,
        dicom_root=dicom_root,
        output_root=tmp_path / "raw-caches",
        cache_version="raw-v1",
        view_splits_csv=views,
        image_processor_config={"model_name": "test", "config": {}},
        shard_size_bytes=1024,
    )
    return cohort, dicom_root, raw


def test_model_ready_cache_is_compact_fixed_shape_and_validated(tmp_path: Path) -> None:
    cohort, dicom_root, raw = _raw_cache(tmp_path)
    root = build_model_ready_cache(
        raw_cache_root=raw,
        output_root=tmp_path / "model-ready",
        cache_version="model-ready-v1",
        processor=_FixedGeometryProcessor(),
        image_processor_config={"model_name": "test", "config": {}},
    )
    cache = ModelReadyImageCache(root)
    assert cache.manifest["view_count"] == 3
    assert np.load(root / "pixels.npy", mmap_mode="r").shape == (3, 518, 518)
    cache.validate_training_inputs(
        cohort_root=cohort,
        dicom_root=dicom_root,
        view_splits_csv=cohort / "splits" / "view_splits.csv",
        required_paths=cache.path_to_index,
        image_processor_config={"model_name": "test", "config": {}},
    )


def test_gpu_resident_loader_preserves_study_view_mapping_without_augmentation() -> None:
    records = [
        StudyTrainingRecord(
            study_key="one",
            deid_patient_id="p1",
            split="train",
            dicom_paths=("a", "b"),
            targets=(1.0,),
            masks=(1.0,),
        ),
        StudyTrainingRecord(
            study_key="two",
            deid_patient_id="p2",
            split="train",
            dicom_paths=("c",),
            targets=(0.0,),
            masks=(1.0,),
        ),
    ]
    pixels = torch.zeros((3, 1, 518, 518), dtype=torch.uint8)
    pixels[0].fill_(10)
    pixels[1].fill_(20)
    pixels[2].fill_(30)
    loader = GpuResidentStudyLoader(
        records,
        path_to_index={"a": 0, "b": 1, "c": 2},
        cached_pixels=pixels,
        batch_size=2,
        train=False,
        image_mean=(0.0, 0.0, 0.0),
        image_std=(1.0, 1.0, 1.0),
    )
    batch = next(iter(loader))
    assert batch["num_studies"] == 2
    assert batch["study_indices"].tolist() == [0, 0, 1]
    assert batch["view_counts"] == [2, 1]
    assert batch["pixel_values"].shape == (3, 3, 518, 518)
    assert torch.allclose(batch["pixel_values"][1], torch.full((3, 518, 518), 20 / 255))
