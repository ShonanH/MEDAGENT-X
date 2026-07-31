"""Study-level vision outputs used by retrieval query and label fusion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label
from medagentx.labels.statuses import LabelStatus
from medagentx.vision.constants import VISION_BACKEND_ID


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
) -> list[VisionStudyOutput]:
    """Convert a collect_inference_predictions payload into study outputs."""
    probabilities = np.asarray(predictions["probabilities"], dtype=np.float32)
    embeddings = np.asarray(predictions["study_embeddings"], dtype=np.float32)
    study_keys = list(predictions["study_keys"])

    if len(probabilities) != len(study_keys):
        raise ValueError("probabilities and study_keys length mismatch")
    if len(embeddings) != len(study_keys):
        raise ValueError("study_embeddings and study_keys length mismatch")

    outputs: list[VisionStudyOutput] = []
    for index, study_key in enumerate(study_keys):
        label_outputs = tuple(
            VisionLabelOutput.from_probability(
                label,
                float(probabilities[index, label_index]),
                float(thresholds[label]),
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
