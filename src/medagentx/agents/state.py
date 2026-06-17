from typing import TypedDict, Literal
try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired

class CaseMetadata(TypedDict):
   case_id: str
   dataset: str
   modality: str
   image_file: str
   
class GroundTruth(TypedDict):
   quality_score: float
   clinical_level: int

class ModelOutputs(TypedDict):
   predicted_quality_score: float
   predicted_clinical_level: int
   uncertainty: float

class ArtifactFeatures(TypedDict):
   intensity_min: float
   intensity_max: float
   intensity_mean: float
   intensity_std: float
   contrast_proxy: float
   noise_proxy: float
   blur_proxy: float
   sharpness_proxy: float
   edge_density: float
   entropy: float

class ClinicalQuality(TypedDict):
   label: Literal["Non-diagnostic", "Limited", "Adequate with caution", "Good", "Excellent"]
   recommendation: str

class Routing(TypedDict):
   diagnosis_gate: Literal[
      "proceed", 
      "proceed_with_caution",
      "human_review",
      "reject_or_repeat",
   ]
   requires_human_review: bool

class ArtifactAssessment(TypedDict):
    artifact_severity: Literal["low", "moderate", "high"]
    artifact_flags: list[str]
    summary: str


class ClinicalAssessment(TypedDict):
    usability_category: Literal[
        "acceptable",
        "usable_with_caution",
        "limited",
        "not_usable",
    ]
    summary: str


class RoutingAssessment(TypedDict):
    final_gate: Literal[
        "proceed",
        "proceed_with_caution",
        "human_review",
        "reject_or_repeat",
    ]
    requires_human_review: bool
    rationale: list[str]
class MedAgentXState(TypedDict):
   case_metadata: CaseMetadata
   ground_truth: GroundTruth
   model_outputs: ModelOutputs
   artifact_features: ArtifactFeatures
   clinical_quality: ClinicalQuality
   routing: Routing
   artifact_assessment: NotRequired[ArtifactAssessment]
   clinical_assessment: NotRequired[ClinicalAssessment]
   routing_assessment: NotRequired[RoutingAssessment]