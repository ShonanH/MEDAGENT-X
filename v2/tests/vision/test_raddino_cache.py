"""Tests for the lossless, seekable RAD-DINO DICOM cache."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pydicom = pytest.importorskip("pydicom")
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from medagentx.vision.cache import (
    COMPLETE_MARKER_NAME,
    CachedImageLoader,
    RadDinoImageCache,
    build_raddino_cache,
    finalize_interrupted_raddino_cache,
    validate_cache_pixels,
)
from medagentx.vision.data import StudyDataset, StudyTrainingRecord, dicom_to_pil_rgb


PROCESSOR = {"model_name": "test/rad-dino", "config": {"size": 518}}


def _write_dicom(
    path: Path,
    pixels: np.ndarray,
    *,
    photometric: str = "MONOCHROME2",
    slope: float = 1.0,
    intercept: float = 0.0,
) -> None:
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
    dataset.PhotometricInterpretation = photometric
    dataset.BitsAllocated = pixels.dtype.itemsize * 8
    dataset.BitsStored = pixels.dtype.itemsize * 8
    dataset.HighBit = dataset.BitsStored - 1
    dataset.PixelRepresentation = 0
    dataset.RescaleSlope = slope
    dataset.RescaleIntercept = intercept
    dataset.PixelData = pixels.tobytes()
    dataset.save_as(path)


def _source_inventory(tmp_path: Path) -> tuple[Path, Path, Path]:
    cohort = tmp_path / "cohort"
    dicom_root = cohort / "dicom_train"
    rows: list[dict[str, str]] = []
    samples = [
        ("train", "study-train", "train.dcm", "MONOCHROME2", 1.0, 0.0),
        ("val", "study-val", "val.dcm", "MONOCHROME1", 2.0, -20.0),
        ("test", "study-test", "test.dcm", "MONOCHROME2", 1.0, 0.0),
    ]
    for index, (split, study, filename, photometric, slope, intercept) in enumerate(samples):
        relative = f"patient-{index}/{study}/{filename}"
        _write_dicom(
            dicom_root / relative,
            np.array([[0, 20, 100], [300, 800, 1000]], dtype=np.uint16),
            photometric=photometric,
            slope=slope,
            intercept=intercept,
        )
        rows.append(
            {
                "dicom_path": relative,
                "split": split,
                "study_key": study,
                "deid_patient_id": f"patient-{index}",
            }
        )
    views = cohort / "splits" / "view_splits.csv"
    views.parent.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(views, index=False)
    return cohort, dicom_root, views


def test_cache_matches_raw_pixels_and_validates_training_inputs(tmp_path: Path) -> None:
    cohort, dicom_root, views = _source_inventory(tmp_path)
    cache_root = build_raddino_cache(
        cohort_root=cohort,
        dicom_root=dicom_root,
        output_root=tmp_path / "caches",
        cache_version="raddino-cache-test-v1",
        view_splits_csv=views,
        image_processor_config=PROCESSOR,
        shard_size_bytes=1024,
    )

    cache = RadDinoImageCache(cache_root)
    assert (cache_root / COMPLETE_MARKER_NAME).is_file()
    assert cache.manifest["cached_view_count"] == 3
    assert cache.manifest["failure_count"] == 0
    assert cache.manifest["edge_coverage"]["monochrome1"] == 1
    assert cache.manifest["edge_coverage"]["non_default_rescale"] == 1

    paths = [entry["dicom_path"] for entry in cache._index.values()]
    validate_cache_pixels(cache_root, dicom_root=dicom_root, paths=paths)
    cache.validate_training_inputs(
        cohort_root=cohort,
        dicom_root=dicom_root,
        view_splits_csv=views,
        required_paths=paths,
        image_processor_config=PROCESSOR,
    )
    loader = CachedImageLoader(dicom_root=dicom_root, cache_root=cache_root)
    raw = np.asarray(dicom_to_pil_rgb(dicom_root / paths[0]), dtype=np.uint8)
    cached = np.asarray(loader(dicom_root / paths[0]), dtype=np.uint8)
    assert np.array_equal(raw, cached)

    with pytest.raises(FileExistsError, match="completed immutable"):
        build_raddino_cache(
            cohort_root=cohort,
            dicom_root=dicom_root,
            output_root=tmp_path / "caches",
            cache_version="raddino-cache-test-v1",
            view_splits_csv=views,
            image_processor_config=PROCESSOR,
        )


def test_raw_and_cached_study_datasets_keep_training_contract(tmp_path: Path) -> None:
    cohort, dicom_root, views = _source_inventory(tmp_path)
    cache_root = build_raddino_cache(
        cohort_root=cohort,
        dicom_root=dicom_root,
        output_root=tmp_path / "caches",
        cache_version="raddino-cache-contract-v1",
        view_splits_csv=views,
        image_processor_config=PROCESSOR,
    )
    record = StudyTrainingRecord(
        study_key="study-train",
        deid_patient_id="patient-0",
        split="train",
        dicom_paths=("patient-0/study-train/train.dcm",),
        targets=(1.0,),
        masks=(1.0,),
    )
    raw = StudyDataset([record], dicom_root=dicom_root)[0]
    cached = StudyDataset(
        [record],
        dicom_root=dicom_root,
        image_loader=CachedImageLoader(
            dicom_root=dicom_root,
            cache_root=cache_root,
        ),
    )[0]
    for key in ("study_key", "deid_patient_id", "dicom_paths", "targets", "masks"):
        assert cached[key] == raw[key]
    assert len(cached["images"]) == len(raw["images"]) == 1
    assert np.array_equal(
        np.asarray(cached["images"][0]), np.asarray(raw["images"][0])
    )


def test_failure_report_never_creates_success_marker(tmp_path: Path) -> None:
    cohort, dicom_root, views = _source_inventory(tmp_path)
    frame = pd.read_csv(views)
    frame.loc[len(frame)] = {
        "dicom_path": "missing/study/missing.dcm",
        "split": "train",
        "study_key": "missing-study",
        "deid_patient_id": "missing-patient",
    }
    frame.to_csv(views, index=False)

    with pytest.raises(RuntimeError, match="invalid DICOM"):
        build_raddino_cache(
            cohort_root=cohort,
            dicom_root=dicom_root,
            output_root=tmp_path / "caches",
            cache_version="raddino-cache-failure-v1",
            view_splits_csv=views,
            image_processor_config=PROCESSOR,
        )
    root = tmp_path / "caches" / "raddino-cache-failure-v1"
    assert not (root / COMPLETE_MARKER_NAME).exists()
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    failures = [json.loads(line) for line in (root / "failures.jsonl").read_text().splitlines()]
    assert len(failures) == 1
    with pytest.raises(Exception, match="not complete"):
        RadDinoImageCache(root)


def test_finalize_interrupted_cache_validates_sample_then_writes_marker(
    tmp_path: Path,
) -> None:
    cohort, dicom_root, views = _source_inventory(tmp_path)
    cache_root = build_raddino_cache(
        cohort_root=cohort,
        dicom_root=dicom_root,
        output_root=tmp_path / "caches",
        cache_version="raddino-cache-finalize-v1",
        view_splits_csv=views,
        image_processor_config=PROCESSOR,
    )
    marker = cache_root / COMPLETE_MARKER_NAME
    marker.unlink()
    manifest_path = cache_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("pixel_validation", None)
    manifest["status"] = "validating"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    finalized_root = finalize_interrupted_raddino_cache(
        cache_root=cache_root,
        dicom_root=dicom_root,
        validation_views_per_split=1,
    )

    assert finalized_root == cache_root
    finalized = json.loads(manifest_path.read_text())
    assert finalized["status"] == "complete"
    assert finalized["pixel_validation"]["status"] == "exact_match"
    assert finalized["pixel_validation"]["view_count"] == 3
    assert marker.is_file()
    RadDinoImageCache(cache_root)
