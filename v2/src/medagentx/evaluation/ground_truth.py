"""Frozen report-derived ground-truth helpers for Judge evaluation."""
from __future__ import annotations
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))
from medagentx.evaluation.constants import GROUND_TRUTH_POLICY_VERSION
from medagentx.labels.constants import ALL_CHEXPERT_LABELS, DISEASE_LABELS
from medagentx.labels.statuses import LabelStatus


@dataclass(frozen=True)
class GroundTruthRecord:
   """One study-label ground-truth row for offline evaluation."""

   study_key: str
   label: str
   ground_truth_status: LabelStatus
   ground_truth_source: str = "chexpert_weak_label"
   ground_truth_policy_version: str = GROUND_TRUTH_POLICY_VERSION


def is_binary_scoreable(status: LabelStatus) -> bool:
   """Return True only for definite present/absent ground truth. """

   if not isinstance(status, LabelStatus):
      raise ValueError(f"Status must be a LabelStatus, got {status!r}")
   return status in (LabelStatus.PRESENT, LabelStatus.ABSENT)

def build_ground_truth_records(
   *,
   study_key: str,
   statuses: Mapping[str, LabelStatus],
   include_non_disease: bool = False,
) -> list[GroundTruthRecord]:
   """Build frozen GT rows from already-canonical statuses.

   Locked rules:
      - present / absent remain scoreable
      - uncertain / unmentioned are preserved but not binary-scoreable
      - default evaluation focuses on the 12 disease labels
   """

   if not isinstance(study_key, str) or not study_key.strip():
      raise ValueError("study_key must be a non-empty string")
   
   labels = ALL_CHEXPERT_LABELS if include_non_disease else DISEASE_LABELS
   expected = set(labels)
   actual = set(statuses)
   missing = sorted(expected - actual)
   unexpected = sorted(actual - expected)

   if missing or unexpected:
      raise ValueError(
         "statuses must contain exactly the requested CheXpert labels;"
         f"missing={missing}, unexpected={unexpected}"
      )
   
   records: list[GroundTruthRecord] = []

   for label in labels:
      status = statuses[label]
      if not isinstance(status, LabelStatus):
         raise ValueError(
            f"statuses[{label!r}] must be a LabelStatus, got {status!r}"
         )

      records.append(
         GroundTruthRecord(
            study_key=study_key,
            label=label,
            ground_truth_status=status,
         )
      )

   return records



def ground_truth_record_to_row(record: GroundTruthRecord) -> dict[str, Any]:
   """Flatten one GroundTruthRecord into a table row."""
   return {
      "study_key": record.study_key,
      "label": record.label,
      "ground_truth_status": record.ground_truth_status.value,
      "ground_truth_source": record.ground_truth_source,
      "ground_truth_policy_version": record.ground_truth_policy_version,
      "binary_scoreable": is_binary_scoreable(record.ground_truth_status),
   }


