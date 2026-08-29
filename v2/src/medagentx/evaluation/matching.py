"""Compare predicted statuses against frozen ground-truth statuses."""
from __future__ import annotations
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))
from medagentx.labels.statuses import LabelStatus

class MatchOutcome(str, Enum):
   """Locked Judge comparison outcomes."""

   TP = "tp"
   FP = "fp"
   FN = "fn"
   TN = "tn"
   UNRESOLVED = "unresolved"
   MISS_UNCERTAIN = "miss_uncertain"


@dataclass(frozen=True)
class LabelMatch:
   """One study-label comparison result."""

   study_key: str
   label: str
   ground_truth_status: LabelStatus
   predicted_status: LabelStatus
   outcome: MatchOutcome
   binary_scoreable: bool


def compare_statuses(*, study_key: str, label:str, ground_truth_status: LabelStatus, predicted_status: LabelStatus) -> LabelMatch:
   """Apply the locked Judge comparison rules.
   Rules:
      - GT present + prediction present -> TP
      - GT present + prediction absent -> FN
      - GT present + prediction uncertain -> miss_uncertain (counts against recall)
      - GT absent + prediction present -> FP
      - GT absent + prediction absent -> TN
      - GT absent + prediction uncertain -> unresolved (excluded from binary metrics)
   """

   if not isinstance(study_key, str) or not study_key.strip():
      raise ValueError("study_key must be a non-empty string")
   if not isinstance(label, str) or not label.strip():
      raise ValueError("label must be a non-empty string")
   if not isinstance(ground_truth_status, LabelStatus):
      raise ValueError(
         f"GT status must be LabelStatus, got {ground_truth_status!r}"
      )
   if not isinstance(predicted_status, LabelStatus):
      raise ValueError(f"predicted status must be LabelStatus, got {predicted_status!r}")

   if ground_truth_status in (LabelStatus.UNCERTAIN, LabelStatus.UNMENTIONED):
      outcome = MatchOutcome.UNRESOLVED
      binary_scoreable = False
   elif ground_truth_status is LabelStatus.PRESENT:
      if predicted_status is LabelStatus.PRESENT:
         outcome = MatchOutcome.TP
         binary_scoreable = True
      elif predicted_status is LabelStatus.ABSENT:
         outcome = MatchOutcome.FN
         binary_scoreable = True
      elif predicted_status is LabelStatus.UNCERTAIN:
         outcome = MatchOutcome.MISS_UNCERTAIN
         binary_scoreable = True
      else:
         outcome = MatchOutcome.FN
         binary_scoreable = True
   elif ground_truth_status is LabelStatus.ABSENT:
      if predicted_status is LabelStatus.PRESENT:
         outcome = MatchOutcome.FP
         binary_scoreable = True
      elif predicted_status is LabelStatus.ABSENT:
         outcome = MatchOutcome.TN
         binary_scoreable = True
      else:
         outcome = MatchOutcome.UNRESOLVED
         binary_scoreable = False
   else:
      raise ValueError(f"Unsupported GT status: {ground_truth_status!r}")

   return LabelMatch(
      study_key=study_key,
      label=label,
      ground_truth_status=ground_truth_status,
      predicted_status=predicted_status,
      outcome=outcome,
      binary_scoreable=binary_scoreable
   )