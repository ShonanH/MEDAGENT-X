from typing import Any, Mapping

from src.medagentx.agents.state import MedAgentXState

CLINICAL_LABELS = {
   1: "Non-diagnostic",
   2: "Limited",
   3: "Adequate with caution",
   4: "Good",
   5: "Excellent",
}

CLINICAL_RECOMMENDATIONS = {
   1: "Reject or repeat unless no alternative exists.",
   2: "Restricted diagnostic value; consider repeat or alternative imaging.",
   3: "Use with caution; subtle findings may be limited.",
   4: "Accept for routine diagnostic use.",
   5: "Accept for diagnostic interpretation.",
}

def get_case_id(filename: str) -> str:
   return filename.rsplit(".", 1)[0]

def get_routing_decision(predicted_clinical_level: int, uncertainty: float) -> dict:
   if predicted_clinical_level <= 1:
      return {
         "diagnosis_gate": "reject_or_repeat",
         "requires_human_review": True,
      }
   
   if predicted_clinical_level == 2:
      return {
         "diagnosis_gate": "human_review",
         "requires_human_review": True,
      }
   
   if predicted_clinical_level == 3:
      return {
         "diagnosis_gate": "proceed_with_caution",
         "requires_human_review": True,
      }
   
   if uncertainty >= 0.5:
      return {
         "diagnosis_gate": "proceed_with_caution",
         "requires_human_review": True,
      }
   
   return {
      "diagnosis_gate": "proceed",
      "requires_human_review": False,
   }

def build_case_state_from_row(row: Mapping[str, Any]) -> MedAgentXState:
   filename = str(row["filename"])
   predicted_clinical_level = int(row["predicted_clinical_level"])
   uncertainty = float(row["uncertainty"])

   return {
      "case_metadata": {
         "case_id": get_case_id(filename),
         "dataset": "LDCTIQAC2023",
         "modality": "CT",
         "image_file": filename,
      },
      "ground_truth": {
         "quality_score": float(row["true_quality_score"]),
         "clinical_level": int(row["true_clinical_level"]),
      },
      "model_outputs": {
         "predicted_quality_score": float(row["predicted_quality_score"]),
         "predicted_clinical_level": predicted_clinical_level,
         "uncertainty": uncertainty,
      },
      "artifact_features": {
         "intensity_min": float(row["intensity_min"]),
         "intensity_max": float(row["intensity_max"]),
         "intensity_mean": float(row["intensity_mean"]),
         "intensity_std": float(row["intensity_std"]),
         "contrast_proxy": float(row["contrast_proxy"]),
         "noise_proxy": float(row["noise_proxy"]),
         "blur_proxy": float(row["blur_proxy"]),
         "sharpness_proxy": float(row["sharpness_proxy"]),
         "edge_density": float(row["edge_density"]),
         "entropy": float(row["entropy"]),
      },
      "clinical_quality": {
         "label": CLINICAL_LABELS[predicted_clinical_level],
         "recommendation": CLINICAL_RECOMMENDATIONS[predicted_clinical_level],
      },
      "routing": get_routing_decision(predicted_clinical_level=predicted_clinical_level, uncertainty=uncertainty),
   }