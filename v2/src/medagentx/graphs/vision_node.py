# v2/src/medagentx/graphs/vision_node.py
"""LangGraph node wrapper for the vision backbone."""

from __future__ import annotations

from collections.abc import Callable

from medagentx.graphs.state import MedAgentXInferenceState, require_state_keys
from medagentx.vision.inference_output import VisionStudyOutput


VisionBackbone = Callable[[str, tuple[str, ...]], VisionStudyOutput]


def make_vision_node(
    vision_backbone: VisionBackbone,
):
    """Create a vision node bound to an existing vision backbone."""

    def vision_node(state: MedAgentXInferenceState) -> MedAgentXInferenceState:
        """Run the vision backbone and attach its structured output."""
        require_state_keys(
            state,
            ("study_key", "dicom_paths"),
            node_name="vision_node",
        )

        study_key = state["study_key"]
        dicom_paths = state["dicom_paths"]

        vision_output = vision_backbone(study_key, dicom_paths)

        if vision_output.study_key != study_key:
            raise ValueError(
                "vision_node received mismatched vision output study_key: "
                f"expected {study_key!r}, got {vision_output.study_key!r}"
            )

        return {"vision_output": vision_output}

    return vision_node