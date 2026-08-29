"""Auditable schemas for canonical, training, and conflict label fields."""

from __future__ import annotations
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))
from medagentx.labels.constants import CHEXPERT_TRAINING_POLICY_VERSION
from medagentx.labels.statuses import LabelStatus

def snake_label(label: str) -> str:
   """ Convert a CheXpert label name into snake case slug"""
   return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")

@dataclass(frozen=True)
class LabelRecord:
   """One observation after parsing and training-policy application.

   Locked fields:
      - raw value: source CheXpert value
      - status: present / absent / uncertain / unmentioned
      - training_target: 1.0 / 0.0 / None
      - training_mask: 1 train / 0 Ignore
      -conflict: multi-view disagreement for this label
   """

   label: str
   raw_value: Any
   status: LabelStatus
   training_target: float | None
   training_mask: int
   conflict: bool = False

   def __post_init__(self) -> None:
      if self.training_mask not in (0,1):
         raise ValueError(f"Training mask must be 0 or 1, got {self.training_mask!r}")
      if self.training_mask == 1 and self.training_target not in (0.0, 1.0):
         raise ValueError(
            f"Training mask  = 1 requires training target in {0.0, 1.0},"
            f"got {self.training_target!r}"
         )
      if self.training_mask == 0 and self.training_target is not None:
         raise ValueError(
            "training mask = 0 requires training target = None"
            f"got {self.training_target!r}"
         )
@dataclass(frozen=True)
class StudyLabelBundle:
   """Study-level table row with identity keys and policy version"""

   study_key: str
   dicom_path: str
   deid_patient_id: str
   labels: dict[str, LabelRecord]
   policy_version: str = CHEXPERT_TRAINING_POLICY_VERSION
   no_finding_contradiction: bool = False

def label_column_names(label: str) -> dict[str, str]:
   """Return the locked wide table column names for one labe."""
   slug = snake_label(label)

   return {
      "raw": f"raw_{slug}",
      "status": f"status_{slug}",
      "training_target": f"training_target_{slug}",
      "training_mask": f"training_mask_{slug}",
      "conflict": f"conflict_{slug}",
   }

def label_record_to_columns(record: LabelRecord) -> dict[str,Any]:
   """Flatten one LabelRecord into locked wide table columns"""
   cols = label_column_names(record.label)

   return{
      cols["raw"]: record.raw_value,
      cols["status"]: record.status.value,
      cols["training_target"]: record.training_target,
      cols["training_mask"]: record.training_mask,
      cols["conflict"]: record.conflict,
   }

def study_bundle_to_row(bundle: StudyLabelBundle) -> dict[str, Any]:
   """ Flatten a StudyLabelBundle into one auditable table row"""

   row: dict[str, Any] = {
      "study_key": bundle.study_key,
      "dicom_path": bundle.dicom_path,
      "deid_patient_id": bundle.deid_patient_id,
      "policy_version": bundle.policy_version,
      "no_finding_contradiction": bundle.no_finding_contradiction,
   }
   for record in bundle.labels.values():
      row.update(label_record_to_columns(record))
   return row