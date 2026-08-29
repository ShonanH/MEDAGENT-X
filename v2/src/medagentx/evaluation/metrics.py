"""Aggregate Judge comparison outcomes into locked evaluation metrics."""
from __future__ import annotations
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))
from medagentx.evaluation.constants import JUDGE_METRIC_VERSION
from medagentx.evaluation.matching import LabelMatch, MatchOutcome
from medagentx.labels.statuses import LabelStatus


@dataclass(frozen=True)
class LabelMetrics:
   """Per-label binary metrics with coverage."""

   label: str
   gt_present: int
   gt_absent: int
   pred_present: int
   pred_absent: int
   tp: int
   tn: int
   fp: int
   fn: int
   miss_uncertain: int
   unresolved: int
   total: int
   scored: int
   scoreable_cells: int
   precision: float | None
   recall: float | None
   f1: float | None
   specificity: float | None
   coverage: float
   coverage_rate: float


@dataclass(frozen=True)
class UncertainStatusMetrics:
   """Per-label uncertain-status diagnostics outside headline binary F1."""

   label: str
   gt_uncertain: int
   pred_uncertain: int
   uncertain_matches: int
   uncertain_match_rate: float | None
   uncertain_overcalls: int
   uncertain_undercalls: int


@dataclass(frozen=True)
class StatusConfusionCount:
   """One long-form status confusion bucket for a label."""

   label: str
   ground_truth_status: LabelStatus
   predicted_status: LabelStatus
   cell_count: int


@dataclass(frozen=True)
class AggregateMetrics:
   """Macro/micro summary across labels."""

   macro_precision: float | None
   macro_recall: float | None
   macro_f1: float | None
   micro_precision: float | None
   micro_recall: float | None
   micro_f1: float | None
   coverage: float
   judge_metric_version: str = JUDGE_METRIC_VERSION

def _safe_div(numerator: float, denominator: float) -> float | None:
   if denominator == 0:
      return None
   return numerator / denominator

def _f1(precision: float | None, recall: float | None) -> float | None:
   if precision is None or recall is None:
      return None
   return _safe_div(2.0 * precision * recall, precision + recall)

def compute_label_metrics(matches: Sequence[LabelMatch]) -> LabelMetrics:
   """ Compute locked per-label metrics from LabelMatch rows.

   Locked scoring:
      - TP/FP/FN/TN from binary-scoreable outcomes
      - miss_uncertain counts against recall (like FN)
      - unresolved is excluded from binary metrics but counted in coverage denominator
   """

   if not matches:
      raise ValueError("matches must contain at least one LabelMatch")

   labels = {match.label for match in matches}
   if len(labels) != 1:
      raise ValueError(f"compute_label_metrics requires one label, got {sorted(labels)}")
   label = next(iter(labels))

   gt_present = gt_absent = pred_present = pred_absent = 0
   tp = fp = fn = tn = miss_uncertain = unresolved = 0

   for match in matches:
      if not isinstance(match, LabelMatch):
         raise ValueError(f"All items must be LabelMatch, got {match!r}")

      if match.ground_truth_status is LabelStatus.PRESENT:
         gt_present += 1
      elif match.ground_truth_status is LabelStatus.ABSENT:
         gt_absent += 1

      if match.predicted_status is LabelStatus.PRESENT:
         pred_present += 1
      elif match.predicted_status is LabelStatus.ABSENT:
         pred_absent += 1

      if match.outcome is MatchOutcome.TP:
         tp += 1
      elif match.outcome is MatchOutcome.FP:
         fp += 1
      elif match.outcome is MatchOutcome.FN:
         fn += 1
      elif match.outcome is MatchOutcome.TN:
         tn += 1
      elif match.outcome is MatchOutcome.MISS_UNCERTAIN:
         miss_uncertain += 1
      elif match.outcome is MatchOutcome.UNRESOLVED:
         unresolved += 1
      else:
         raise ValueError(f"Unsupported MatchOutcome: {match.outcome!r}")

   total = len(matches)
   scored = tp + fp + fn + tn + miss_uncertain

   precision = _safe_div(tp, tp + fp)
   recall = _safe_div(tp, tp + fn + miss_uncertain)
   f1 = _f1(precision, recall)
   specificity = _safe_div(tn, tn + fp)
   coverage = scored / total if total else 0.0

   return LabelMetrics(
      label=label,
      gt_present=gt_present,
      gt_absent=gt_absent,
      pred_present=pred_present,
      pred_absent=pred_absent,
      tp=tp,
      tn=tn,
      fp=fp,
      fn=fn,
      miss_uncertain=miss_uncertain,
      unresolved=unresolved,
      total=total,
      scored=scored,
      scoreable_cells=scored,
      precision=precision,
      recall=recall,
      f1=f1,
      specificity=specificity,
      coverage=coverage,
      coverage_rate=coverage,
   )

def compute_uncertain_status_metrics(
   matches: Sequence[LabelMatch],
) -> UncertainStatusMetrics:
   """Compute per-label diagnostics for GT/predicted uncertain statuses."""

   if not matches:
      raise ValueError("matches must contain at least one LabelMatch")

   labels = {match.label for match in matches}
   if len(labels) != 1:
      raise ValueError(
         f"compute_uncertain_status_metrics requires one label, got {sorted(labels)}"
      )
   label = next(iter(labels))

   gt_uncertain = pred_uncertain = uncertain_matches = 0
   uncertain_overcalls = uncertain_undercalls = 0

   for match in matches:
      if not isinstance(match, LabelMatch):
         raise ValueError(f"All items must be LabelMatch, got {match!r}")

      gt_is_uncertain = match.ground_truth_status is LabelStatus.UNCERTAIN
      pred_is_uncertain = match.predicted_status is LabelStatus.UNCERTAIN

      if gt_is_uncertain:
         gt_uncertain += 1
      if pred_is_uncertain:
         pred_uncertain += 1
      if gt_is_uncertain and pred_is_uncertain:
         uncertain_matches += 1
      elif (
         pred_is_uncertain
         and match.ground_truth_status in (LabelStatus.PRESENT, LabelStatus.ABSENT)
      ):
         uncertain_overcalls += 1
      elif gt_is_uncertain and not pred_is_uncertain:
         uncertain_undercalls += 1

   uncertain_match_rate = _safe_div(uncertain_matches, gt_uncertain)

   return UncertainStatusMetrics(
      label=label,
      gt_uncertain=gt_uncertain,
      pred_uncertain=pred_uncertain,
      uncertain_matches=uncertain_matches,
      uncertain_match_rate=uncertain_match_rate,
      uncertain_overcalls=uncertain_overcalls,
      uncertain_undercalls=uncertain_undercalls,
   )

def compute_status_confusion_counts(
   matches: Sequence[LabelMatch],
) -> tuple[StatusConfusionCount, ...]:
   """Compute long-form GT-status by predicted-status counts."""

   if not matches:
      raise ValueError("matches must contain at least one LabelMatch")

   labels = {match.label for match in matches}
   if len(labels) != 1:
      raise ValueError(
         f"compute_status_confusion_counts requires one label, got {sorted(labels)}"
      )
   label = next(iter(labels))

   counts: dict[tuple[LabelStatus, LabelStatus], int] = {}
   for match in matches:
      if not isinstance(match, LabelMatch):
         raise ValueError(f"All items must be LabelMatch, got {match!r}")
      key = (match.ground_truth_status, match.predicted_status)
      counts[key] = counts.get(key, 0) + 1

   return tuple(
      StatusConfusionCount(
         label=label,
         ground_truth_status=ground_truth_status,
         predicted_status=predicted_status,
         cell_count=cell_count,
      )
      for (ground_truth_status, predicted_status), cell_count in sorted(
         counts.items(), key=lambda item: (item[0][0].value, item[0][1].value)
      )
   )

def compute_aggregate_metrics(label_metrics: Sequence[LabelMetrics]) -> AggregateMetrics:
   """Compute macro and micro metrics across per-label results """
   if not label_metrics:
      raise ValueError("label_metrics must contain at least one LabelMetrics")
   
   for item in label_metrics:
      if not isinstance(item, LabelMetrics):
         raise ValueError(f"All items must be LabelMetrics, got {item!r}")

   precisions = [m.precision for m in label_metrics if m.precision is not None]
   recalls = [m.recall for m in label_metrics if m.recall is not None]
   f1s = [m.f1 for m in label_metrics if m.f1 is not None]

   macro_precision = (
      sum(precisions) / len(precisions) if precisions else None
   )

   macro_recall = sum(recalls) / len(recalls) if recalls else None
   macro_f1 = sum(f1s) / len(f1s) if f1s else None


   tp = sum(m.tp for m in label_metrics)
   fp = sum(m.fp for m in label_metrics)
   fn = sum(m.fn for m in label_metrics)

   miss_uncertain = sum(m.miss_uncertain for m in label_metrics)
   scored = sum(m.scored for m in label_metrics)
   total = sum(m.total for m in label_metrics)

   micro_precision = _safe_div(tp, tp + fp)
   micro_recall = _safe_div(tp, tp + fn + miss_uncertain)
   micro_f1 = _f1(micro_precision, micro_recall)
   coverage = scored / total if total else 0.0

   return AggregateMetrics(
      macro_precision=macro_precision,
      macro_recall=macro_recall,
      macro_f1=macro_f1,
      micro_precision=micro_precision,
      micro_recall=micro_recall,
      micro_f1=micro_f1,
      coverage=coverage
   )
