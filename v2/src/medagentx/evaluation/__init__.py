"""Offline evaluation package for frozen GT matching and Judge metrics."""

from __future__ import annotations

import sys
from pathlib import Path

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.evaluation.constants import (
    GROUND_TRUTH_POLICY_VERSION,
    JUDGE_METRIC_VERSION,
    RANKING_METRIC_VERSION,
)
from medagentx.evaluation.ground_truth import (
    GroundTruthRecord,
    build_ground_truth_records,
    ground_truth_record_to_row,
    is_binary_scoreable,
)
from medagentx.evaluation.judge import JudgeResult, run_judge
from medagentx.evaluation.matching import LabelMatch, MatchOutcome, compare_statuses
from medagentx.evaluation.metrics import (
    AggregateMetrics,
    LabelMetrics,
    compute_aggregate_metrics,
    compute_label_metrics,
)
from medagentx.evaluation.ranking import (
    LabelRankingMetrics,
    RankingCell,
    RankingResult,
    compute_ranking_metrics,
)

__all__ = [
    "AggregateMetrics",
    "GROUND_TRUTH_POLICY_VERSION",
    "GroundTruthRecord",
    "JUDGE_METRIC_VERSION",
    "JudgeResult",
    "LabelMatch",
    "LabelMetrics",
    "LabelRankingMetrics",
    "MatchOutcome",
    "RankingCell",
    "RankingResult",
    "RANKING_METRIC_VERSION",
    "build_ground_truth_records",
    "compare_statuses",
    "compute_aggregate_metrics",
    "compute_label_metrics",
    "compute_ranking_metrics",
    "ground_truth_record_to_row",
    "is_binary_scoreable",
    "run_judge",
]
