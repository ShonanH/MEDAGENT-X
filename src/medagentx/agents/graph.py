from langgraph.graph import END, START, StateGraph
import os
from textwrap import dedent
from langchain.chat_models import init_chat_model
from src.medagentx.agents.state import MedAgentXState
import json


def get_report_llm():
   model_name = os.environ.get("MEDAGENTX_LLM_MODEL")

   if model_name is None:
      raise RuntimeError("MEDAGENTX_LLM_MODEL environment variable is not set")
   
   return init_chat_model(model_name, temperature=0.0)

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
      usability_category = "not_usable"
      summary = f"Predicted clinical quality is {label}, so the image is non-diagnostic. Consider reject or repeat unless no alternative exists."
   
   return {
      "clinical_assessment":{
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

def report_agent_node(state: MedAgentXState) -> dict:
   llm = get_report_llm()

   model_outputs = state["model_outputs"]
   clinical_quality = state["clinical_quality"]
   routing_assessment = state["routing_assessment"]
   artifact_assessment = state["artifact_assessment"]
   clinical_assessment = state["clinical_assessment"]

   prompt = f"""
You are the MEDAGENT-X image quality report agent. You are an expert in medical imaging quality assessment.

Goal:
Generate the narrative parts of a CT image quality report before diagnosis.

Rules:
- Use only the provided state information.
- Do not change raw model outputs.
- Do not make diagnosis claims.
- Do not mention disease, pathology, or anatomical findings.
- Do not invent artifact information.
- Focus only on image quality, uncertainty, artifact evidence, and routing.
- Return valid JSON only.
- Do not wrap the output in Markdown.
- Do not wrap the output in a code block.

Return exactly this JSON structure:
{{
  "explanation": "Write 10-12 concise sentences explaining the image quality assessment.",
  "limitations": [
    "case-specific limitation 1",
    "case-specific limitation 2",
    "case-specific limitation 3"
  ],
  "conclusion": "Write a 1-2 sentence conclusion about image-quality gate routing."
}}

State information:

1. Raw model outputs:
- predicted_quality_score: {model_outputs['predicted_quality_score']}
- predicted_clinical_level: {model_outputs['predicted_clinical_level']}
- uncertainty: {model_outputs['uncertainty']}

2. Clinical quality:
- label: {clinical_quality['label']}
- recommendation: {clinical_quality['recommendation']}

3. Clinical assessment:
- usability_category: {clinical_assessment['usability_category']}
- summary: {clinical_assessment['summary']}

4. Routing assessment:
- final_gate: {routing_assessment['final_gate']}
- rationale: {routing_assessment['rationale']}
- requires_human_review: {routing_assessment['requires_human_review']}

5. Artifact assessment:
- severity: {artifact_assessment['artifact_severity']}
- flags: {artifact_assessment['artifact_flags']}
- summary: {artifact_assessment['summary']}
"""

   response = llm.invoke(prompt)
   report_text = response.content.strip()

   if report_text.startswith("```json"):
      report_text = report_text.removeprefix("```json").removesuffix("```").strip()
   elif report_text.startswith("```"):
      report_text = report_text.removeprefix("```").removesuffix("```").strip()

   report_parts = json.loads(report_text)

   explanation = report_parts["explanation"]
   limitations = report_parts["limitations"]
   conclusion = report_parts["conclusion"]

   confidence = round(
      max(0.0, min(1.0, 1.0 - float(model_outputs["uncertainty"]))),
      4,
   )

   limitations_markdown = "\n".join(f"- {limitation}" for limitation in limitations)

   markdown_content = dedent(f"""
# MEDAGENT-X Image Quality Report

## Case
- Case ID: {state["case_metadata"]["case_id"]}
- Dataset: {state["case_metadata"]["dataset"]}
- Modality: {state["case_metadata"]["modality"]}
- Image file: {state["case_metadata"]["image_file"]}

## Model Outputs
- Predicted quality score: {model_outputs["predicted_quality_score"]:.4f}
- Predicted clinical level: {model_outputs["predicted_clinical_level"]}
- Uncertainty: {model_outputs["uncertainty"]:.4f}

## Clinical Quality
- Label: {clinical_quality["label"]}
- Recommendation: {clinical_quality["recommendation"]}

## Artifact Assessment
- Severity: {artifact_assessment["artifact_severity"]}
- Flags: {", ".join(artifact_assessment["artifact_flags"]) if artifact_assessment["artifact_flags"] else "None"}
- Summary: {artifact_assessment["summary"]}

## Routing
- Diagnosis gate: {routing_assessment["final_gate"]}
- Requires human review: {routing_assessment["requires_human_review"]}

## Explanation
{explanation}

## Limitations
{limitations_markdown}

## Conclusion
{conclusion}
""").strip()

   return {
      "final_report": {
         "quality_score": float(model_outputs["predicted_quality_score"]),
         "clinical_usability_level": int(model_outputs["predicted_clinical_level"]),
         "clinical_usability_label": clinical_quality["label"],
         "recommendation": clinical_quality["recommendation"],
         "confidence": confidence,
         "requires_human_review": routing_assessment["requires_human_review"],
         "diagnosis_gate": routing_assessment["final_gate"],
         "explanation": explanation,
         "limitations": limitations,
         "conclusion": conclusion,
      },
      "markdown_report": {
         "content": markdown_content,
      },
   }



def build_medagentx_graph():
   graph_builder = StateGraph(MedAgentXState)

   graph_builder.add_node("artifact_review", artifact_review_node)
   graph_builder.add_node("clinical_quality_review", clinical_quality_node)
   graph_builder.add_node("routing_review", routing_node)
   graph_builder.add_node("report_agent", report_agent_node)

   graph_builder.add_edge(START, "artifact_review")
   graph_builder.add_edge("artifact_review", "clinical_quality_review")
   graph_builder.add_edge("clinical_quality_review", "routing_review")
   graph_builder.add_edge("routing_review", "report_agent")
   graph_builder.add_edge("report_agent", END)

   return graph_builder.compile()
      
