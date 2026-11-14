"""Study-level vision outputs used by retrieval query and label fusion."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label
from medagentx.labels.statuses import LabelStatus
from medagentx.vision.constants import VISION_BACKEND_ID

VISION_OUTPUT_CACHE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class VisionLabelOutput:
    """One disease prediction from a vision forward pass."""

    label: str
    probability: float
    threshold: float
    status: LabelStatus

    @classmethod
    def from_probability(
        cls,
        label: str,
        probability: float,
        threshold: float,
    ) -> "VisionLabelOutput":
        status = (
            LabelStatus.PRESENT
            if float(probability) >= float(threshold)
            else LabelStatus.ABSENT
        )
        return cls(
            label=label,
            probability=float(probability),
            threshold=float(threshold),
            status=status,
        )


@dataclass(frozen=True)
class VisionStudyOutput:
    """One study's vision probabilities plus the retrieval query embedding."""

    study_key: str
    deid_patient_id: str
    split: str
    view_count: int
    dicom_paths: tuple[str, ...]
    vision_backend_id: str
    study_embedding: tuple[float, ...]
    labels: tuple[VisionLabelOutput, ...]

    def label_map(self) -> dict[str, VisionLabelOutput]:
        return {item.label: item for item in self.labels}

    def query_embedding(self) -> tuple[float, ...]:
        """Return the study embedding used for image-similarity retrieval."""
        return self.study_embedding


def build_study_outputs(
    predictions: Mapping[str, Any],
    thresholds: Mapping[str, float],
    *,
    vision_backend_id: str = VISION_BACKEND_ID,
    threshold_overrides: Mapping[str, float] | None = None,
) -> list[VisionStudyOutput]:
    """Convert a collect_inference_predictions payload into study outputs."""
    probabilities = np.asarray(predictions["probabilities"], dtype=np.float32)
    embeddings = np.asarray(predictions["study_embeddings"], dtype=np.float32)
    study_keys = list(predictions["study_keys"])
    active_thresholds = dict(thresholds)
    if threshold_overrides is not None:
        unexpected = sorted(set(threshold_overrides) - set(DISEASE_LABELS))
        if unexpected:
            raise ValueError(f"Unexpected threshold override labels: {unexpected}")
        active_thresholds.update(
            {label: float(value) for label, value in threshold_overrides.items()}
        )

    if len(probabilities) != len(study_keys):
        raise ValueError("probabilities and study_keys length mismatch")
    if len(embeddings) != len(study_keys):
        raise ValueError("study_embeddings and study_keys length mismatch")
    missing_thresholds = sorted(set(DISEASE_LABELS) - set(active_thresholds))
    if missing_thresholds:
        raise ValueError(f"Missing thresholds for labels: {missing_thresholds}")

    outputs: list[VisionStudyOutput] = []
    for index, study_key in enumerate(study_keys):
        label_outputs = tuple(
            VisionLabelOutput.from_probability(
                label,
                float(probabilities[index, label_index]),
                float(active_thresholds[label]),
            )
            for label_index, label in enumerate(DISEASE_LABELS)
        )
        outputs.append(
            VisionStudyOutput(
                study_key=study_key,
                deid_patient_id=str(predictions["patient_ids"][index]),
                split=str(predictions["splits"][index]),
                view_count=int(predictions["view_counts"][index]),
                dicom_paths=tuple(predictions["dicom_paths"][index]),
                vision_backend_id=vision_backend_id,
                study_embedding=tuple(float(value) for value in embeddings[index]),
                labels=label_outputs,
            )
        )
    return outputs


def study_outputs_to_prediction_frame(outputs: list[VisionStudyOutput]):
    """Flatten study outputs into the permanent vision prediction CSV contract."""
    import pandas as pd

    rows: list[dict[str, Any]] = []
    for output in outputs:
        row: dict[str, Any] = {
            "study_key": output.study_key,
            "deid_patient_id": output.deid_patient_id,
            "split": output.split,
            "view_count": output.view_count,
            "dicom_paths": "|".join(output.dicom_paths),
            "vision_backend_id": output.vision_backend_id,
        }
        for label_output in output.labels:
            slug = snake_label(label_output.label)
            row[f"probability_{slug}"] = label_output.probability
            row[f"threshold_{slug}"] = label_output.threshold
            row[f"status_{slug}"] = label_output.status.value
        rows.append(row)
    return pd.DataFrame(rows)


def _vision_cache_meta_path(path: str | Path) -> Path:
    resolved = Path(path)
    return resolved.with_suffix(resolved.suffix + ".meta.json")


def save_vision_study_outputs(
    path: str | Path,
    outputs: list[VisionStudyOutput],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    """Persist prediction probabilities and retrieval embeddings losslessly."""
    if not outputs:
        raise ValueError("outputs must not be empty")
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)

    embeddings = np.asarray(
        [output.study_embedding for output in outputs], dtype=np.float32
    )
    probabilities = np.asarray(
        [
            [label_output.probability for label_output in output.labels]
            for output in outputs
        ],
        dtype=np.float32,
    )
    thresholds = np.asarray(
        [
            [label_output.threshold for label_output in output.labels]
            for output in outputs
        ],
        dtype=np.float32,
    )
    expected_label_order = tuple(DISEASE_LABELS)
    for output in outputs:
        if tuple(item.label for item in output.labels) != expected_label_order:
            raise ValueError(
                f"Unexpected label order in vision output {output.study_key!r}"
            )

    np.savez_compressed(
        resolved,
        study_keys=np.asarray([output.study_key for output in outputs]),
        patient_ids=np.asarray([output.deid_patient_id for output in outputs]),
        splits=np.asarray([output.split for output in outputs]),
        view_counts=np.asarray([output.view_count for output in outputs], dtype=np.int32),
        dicom_paths_json=np.asarray(
            [json.dumps(output.dicom_paths) for output in outputs]
        ),
        vision_backend_ids=np.asarray(
            [output.vision_backend_id for output in outputs]
        ),
        embeddings=embeddings,
        probabilities=probabilities,
        thresholds=thresholds,
    )
    cache_metadata = {
        "schema_version": VISION_OUTPUT_CACHE_SCHEMA_VERSION,
        "study_count": len(outputs),
        "embedding_dimension": int(embeddings.shape[1]),
        "label_order": list(DISEASE_LABELS),
        **dict(metadata or {}),
    }
    _vision_cache_meta_path(resolved).write_text(
        json.dumps(cache_metadata, indent=2, sort_keys=True) + "\n"
    )


def load_vision_study_outputs(
    path: str | Path,
) -> tuple[list[VisionStudyOutput], dict[str, Any]]:
    """Load a cache created by :func:`save_vision_study_outputs`."""
    resolved = Path(path)
    meta_path = _vision_cache_meta_path(resolved)
    if not resolved.is_file() or not meta_path.is_file():
        raise FileNotFoundError(
            f"Vision output cache or metadata is missing: {resolved}"
        )
    metadata = json.loads(meta_path.read_text())
    if metadata.get("schema_version") != VISION_OUTPUT_CACHE_SCHEMA_VERSION:
        raise ValueError("Unsupported vision output cache schema")
    if metadata.get("label_order") != list(DISEASE_LABELS):
        raise ValueError("Vision output cache label order is incompatible")

    with np.load(resolved, allow_pickle=False) as payload:
        arrays = {name: payload[name] for name in payload.files}
    required = {
        "study_keys",
        "patient_ids",
        "splits",
        "view_counts",
        "dicom_paths_json",
        "vision_backend_ids",
        "embeddings",
        "probabilities",
        "thresholds",
    }
    missing = sorted(required - set(arrays))
    if missing:
        raise ValueError(f"Vision output cache is missing arrays: {missing}")

    study_count = len(arrays["study_keys"])
    if metadata.get("study_count") != study_count:
        raise ValueError("Vision output cache study count does not match metadata")
    if arrays["embeddings"].shape[0] != study_count:
        raise ValueError("Vision output embedding count mismatch")
    expected_matrix_shape = (study_count, len(DISEASE_LABELS))
    if arrays["probabilities"].shape != expected_matrix_shape:
        raise ValueError("Vision output probability shape mismatch")
    if arrays["thresholds"].shape != expected_matrix_shape:
        raise ValueError("Vision output threshold shape mismatch")

    outputs: list[VisionStudyOutput] = []
    for index in range(study_count):
        labels = tuple(
            VisionLabelOutput.from_probability(
                label,
                float(arrays["probabilities"][index, label_index]),
                float(arrays["thresholds"][index, label_index]),
            )
            for label_index, label in enumerate(DISEASE_LABELS)
        )
        outputs.append(
            VisionStudyOutput(
                study_key=str(arrays["study_keys"][index]),
                deid_patient_id=str(arrays["patient_ids"][index]),
                split=str(arrays["splits"][index]),
                view_count=int(arrays["view_counts"][index]),
                dicom_paths=tuple(
                    str(value)
                    for value in json.loads(str(arrays["dicom_paths_json"][index]))
                ),
                vision_backend_id=str(arrays["vision_backend_ids"][index]),
                study_embedding=tuple(
                    float(value) for value in arrays["embeddings"][index]
                ),
                labels=labels,
            )
        )
    return outputs, metadata
