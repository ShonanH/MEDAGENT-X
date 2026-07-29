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


@dataclass(frozen=True)
class LabelMetrics:
   """Per-label binary metrics with coverage."""

   label: str
   tp: int
   fp: int
   fn: int
   tn: int
   miss_uncertain: int
   unresolved: int
   total: int
   scored: int
   precision: float | None
   recall: float | None
   f1: float | None
   coverage: float


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

   tp = fp = fn = tn = miss_uncertain = unresolved = 0

   for match in matches:
      if not isinstance(match, LabelMatch):
         raise ValueError(f"All items must be LabelMatch, got {match!r}")

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
   coverage = scored / total if total else 0.0

   return LabelMetrics(
      label=label,
      tp=tp,
      fp=fp,
      fn=fn,
      tn=tn,
      miss_uncertain=miss_uncertain,
      unresolved=unresolved,
      total=total,
      scored=scored,
      precision=precision,
      recall=recall,
      f1=f1,
      coverage=coverage,
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