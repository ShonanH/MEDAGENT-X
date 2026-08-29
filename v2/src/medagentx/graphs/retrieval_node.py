"""LangGraph node wrapper for retrieval."""

from __future__ import annotations

from typing import Any

from medagentx.graphs.state import MedAgentXInferenceState, require_state_keys
from medagentx.reasoning.constants import FUSION_RETRIEVAL_TOP_K
from medagentx.reasoning.retrieve import retrieve_similar_reports

def make_retrieval_node(
      collection: Any,
      *,
      top_k: int = FUSION_RETRIEVAL_TOP_K,
):
   """Create a retrieval node bound to an opened retrieval collection"""

   def retrieval_node(state: MedAgentXInferenceState) -> MedAgentXInferenceState:
      """Retrieve visually similar report cases for one vision output"""

      require_state_keys(
         state,
         ("vision_output",),
         node_name="retrieval_node"
      )

      retrieved_cases = retrieve_similar_reports(
         collection,
         state["vision_output"],
         top_k=top_k
      )

      return {"retrieved_cases": retrieved_cases}
   return retrieval_node