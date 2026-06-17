from langgraph.graph import END, START, StateGraph
from src.medagentx.agents.state import MedAgentXState


def artifact_review_node(state: MedAgentXState) -> dict:
   features = state["artifact_features"]
   artifact_flags = []

   noise_proxy = features["noise_proxy"]
   contrast_proxy = features["contrast_proxy"]
   sharpness_proxy = features["sharpness_proxy"]
   edge_density = features["edge_density"]
   
   if noise_proxy >= 0.035:
      artifact_flags.append("high_noise_proxy")
   elif noise_proxy >= 0.025:
      artifact_flags.append("moderate_noise_proxy")

   if contrast_proxy < 0.50:
      artifact_flags.append("low_contrast_proxy")
   
   if sharpness_proxy < 0.003:
      artifact_flags.append("low_sharpness_proxy")

   if edge_density < 0.025:
      artifact_flags.append("low_edge_density")
   
   if len(artifact_flags) == 0:
      artifact_severity = "low"
      summary = "No significant artifact concerns were detected."
   elif len(artifact_flags) <= 2:
      artifact_severity = "moderate"
      summary = "Moderate artifact concerns were detected. Consider further review."
   else:
      artifact_severity = "high"
      summary = "Multiple artifact concerns were detected. Consider further review."
   
   return {
      "artifact_assessment":{
         "artifact_severity": artifact_severity,
         "artifact_flags": artifact_flags,
         "summary": summary,
      }
   }

def clinical_quality_node(state: MedAgentXState) -> dict:
   predicted_level = state["model_outputs"]["predicted_clinical_level"]
   label = state["clinical_quality"]["label"]

   if predicted_level >= 4:
      usability_category = "acceptable"
      summary = f"Predicted clinical quality is {label}, so the image is acceptable for diagnostic workflow."
   elif predicted_level == 3:
      usability_category = "usable_with_caution"
      summary = f"Predicted clinical quality is {label}, so the image is usable with caution. Consider further review."
   elif predicted_level == 2:
      usability_category = "limited"
      summary = f"Predicted clinical quality is {label}, so the image is limited. Consider repeat or alternative imaging."
   else:
      usability_category = "non_usable"
      summary = f"Predicted clinical quality is {label}, so the image is non-diagnostic. Consider reject or repeat unless no alternative exists."
   
   return {
      "clinical_quality_assessment":{
         "usability_category": usability_category,
         "summary": summary,
      }
   }

def routing_node(state: MedAgentXState) -> dict:
   routing = state["routing"]
   artifact_assessment = state["artifact_assessment"]
   model_outputs = state["model_outputs"]

   rationale = []
   
   rationale.append(
      f"Predicted clinical level is {model_outputs['predicted_clinical_level']}"
   )

   rationale.append(
      f"Model uncertainty is {model_outputs['uncertainty']}"
   )
   
   rationale.append(
      f"Artifact severity is {artifact_assessment['artifact_severity']}"
   )

   if routing["requires_human_review"]:
      rationale.append(
         "Routing decision requires human review."
      )
   else:
      rationale.append(
         "Routing decision does not require human review."
      )
   
   return {
      "routing_assessment":{
         "final_gate": routing["diagnosis_gate"],
         "rationale": rationale,
         "requires_human_review": routing["requires_human_review"],
      }
   }


def build_medagentx_graph():
   graph_builder = StateGraph(MedAgentXState)

   graph_builder.add_node("artifact_review", artifact_review_node)
   graph_builder.add_node("clinical_quality_review", clinical_quality_node)
   graph_builder.add_node("routing_review", routing_node)

   graph_builder.add_edge(START, "artifact_review")
   graph_builder.add_edge("artifact_review", "clinical_quality_review")
   graph_builder.add_edge("clinical_quality_review", "routing_review")
   graph_builder.add_edge("routing_review", END)

   return graph_builder.compile()
      
