"""Bridge vision study outputs into label-fusion inputs."""

from __future__ import annotations

from medagentx.reasoning.fuse import VisionLabelPrediction
from medagentx.vision.inference_output import VisionStudyOutput


def fusion_vision_inputs(
    study_output: VisionStudyOutput,
) -> dict[str, VisionLabelPrediction]:
    """Convert one vision study output into fuse_study_labels() inputs."""
    return {
        label_output.label: VisionLabelPrediction(
            label=label_output.label,
            probability=label_output.probability,
            threshold=label_output.threshold,
            status=label_output.status,
        )
        for label_output in study_output.labels
    }
