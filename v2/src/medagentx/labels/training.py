"""U-mask targets and No Finding rules for model training."""
from __future__ import annotations
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping
_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))
from medagentx.labels.constants import (
    ALL_CHEXPERT_LABELS,
    DISEASE_LABELS,
)
from medagentx.labels.schema import LabelRecord
from medagentx.labels.statuses import LabelStatus
_NO_FINDING = "No Finding"
_SUPPORT_DEVICES = "Support Devices"


def _validate_complete_label_set(values: Mapping[str, Any], field_name: str,) -> None:
   """Require exactly the canonical 14 CheXpert labels."""
   expected = set(ALL_CHEXPERT_LABELS)
   actual = set(values)

   missing = sorted(expected - actual)
   unexpected = sorted(actual - expected)

   if missing or unexpected:
      raise ValueError(
         f"{field_name} must contain exactly the 14 CheXpert Labels; "
         f"missing={missing}, unexpected={unexpected}"
      )


def training_target_for_status(label:str, status: LabelStatus) -> tuple[float | None, int]:
   """Return the training target and mask for one canonical status. """

   if label not in ALL_CHEXPERT_LABELS:
      raise ValueError(f"Unknown label: {label!r}")

   if not isinstance(status, LabelStatus):
      raise ValueError(f"status must be a LabelStatus, got {status!r}")
   
   if label == _SUPPORT_DEVICES:
      return None, 0
   
   if status is LabelStatus.PRESENT:
      return 1.0, 1
   if status is LabelStatus.ABSENT:
      return 0.0, 1
   if status in (LabelStatus.UNCERTAIN, LabelStatus.UNMENTIONED):
      return None, 0

   raise ValueError(f"Unsupported LabelStatus: {status!r}")

def build_label_record(label: str, raw_value: Any, status:LabelStatus, conflict: bool = False) -> LabelRecord:
   """Build one validated LabelRecord using the U-mask policy"""

   if not isinstance(conflict, bool):
      raise ValueError(f"conflict must be bool, got {conflict!r}")
   
   training_target, training_mask = training_target_for_status(label=label, status=status)

   return LabelRecord(
      label=label,
      status=status,
      raw_value=raw_value,
      training_mask=training_mask,
      training_target=training_target,
      conflict=conflict
   )

def apply_no_finding_training_rule(records: Mapping[str, LabelRecord ]) -> tuple[dict[str, LabelRecord], bool]:
   """Apply the locked No Finding policy here

   Rules:
      - Preserve every canonical source status
      - If No Finding is present, train unmentioned diseases as absent
      - Never overwrite explicitly present or uncertain diseases.
      - Flag No Finding present alongside any present diseases.
   """

   _validate_complete_label_set(records, "records")

   for label, record in records.items():
      if record.label != label:
         raise ValueError(
            f"Record key {label!r} does not match "
            f"record.label {record.label!r}"
         )

   updated = dict(records)
   no_finding = updated[_NO_FINDING]

   contradiction = (
      no_finding.status is LabelStatus.PRESENT and any(
         updated[label].status is LabelStatus.PRESENT
         for label in DISEASE_LABELS
      )
   )

   if no_finding.status is LabelStatus.PRESENT:
      for label in DISEASE_LABELS:
         record = updated[label]

         if record.status is LabelStatus.UNMENTIONED:
            updated[label] = replace(
               record,
               training_target=0.0,
               training_mask=1,
            )
   return updated, contradiction

def build_training_records(
   raw_values: Mapping[str, Any], 
   statuses: Mapping[str, LabelStatus], 
   conflicts: Mapping[str, bool] | None = None) -> tuple[dict[str, LabelRecord], bool]:
   """Build add 14 records and apply the No Finding policy."""
   _validate_complete_label_set(raw_values, "raw_values")
   _validate_complete_label_set(statuses, "statuses")

   conflicts = conflicts or {}

   unexpected_conflicts = sorted(
      set(conflicts) - set(ALL_CHEXPERT_LABELS)
   )

   if unexpected_conflicts:
      raise ValueError(f"Conflicts contain unknown labels, {unexpected_conflicts}")

   records: dict[str, LabelRecord] = {}

   for label in ALL_CHEXPERT_LABELS:
      records[label] = build_label_record(
         label=label,
         raw_value=raw_values[label],
         status=statuses[label],
         conflict=conflicts.get(label, False)
      )
   
   return apply_no_finding_training_rule(records)