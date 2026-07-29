"""Version identifiers for frozen ground truth and Judge metrics."""

from __future__ import annotations

import sys
from pathlib import Path

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

GROUND_TRUTH_POLICY_VERSION = "chexpert_weak_gt_policy_v1"
JUDGE_METRIC_VERSION = "judge_metric_policy_v1"