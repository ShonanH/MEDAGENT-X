"""LangGraph node wrapper for label fusion"""

from __future__ import annotations

from medagentx.graphs.state import MedAgentXInferenceState, require_state_keys
from medagentx.reasoning.constants import GRAY_ZONE_MARGIN
from medagentx.reasoning.fuse import fuse_study_labels
from medagentx.reasoning.vision_adapter import fusion_vision_inputs

def fusion_node(
      state: MedAgentXInferenceState,
      *,
      margin: float = GRAY_ZONE_MARGIN
) -> MedAgentXInferenceState:
   """Fuse vision predictions with retrieved report evidence"""

   require_state_keys(
      state,
      ("vision_output", "retrieved_cases"),
      node_name="fusion_node"
   )

   vision_output = state["vision_output"]
   fusion_result = fuse_study_labels(
      fusion_vision_inputs(vision_output),
      state["retrieved_cases"],
      study_key=vision_output.study_key,
      margin=margin
   )

   return {"fusion_result": fusion_result}