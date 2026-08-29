"""Strict conversion of raw CheXpert values into canonical statuses."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_V2_SRC = Path(__file__).resolve().parents[2]
if str(_V2_SRC) not in sys.path:
    sys.path.insert(0, str(_V2_SRC))

from medagentx.labels.statuses import LabelStatus


def parse_chexpert_raw_value(value: Any) -> LabelStatus:
    """Map a raw CheXpert value to a canonical LabelStatus.

    Accepted:
      - present: 1, 1.0, "1"
      - absent: 0, 0.0, "0"
      - uncertain: -1, -1.0, "-1"
      - unmentioned: None, blank, NaN

    Raises:
      ValueError: for any other value.
    """
    if value is None:
        return LabelStatus.UNMENTIONED

    # Real NaN (float/numpy/pandas): NaN != NaN
    try:
        if value != value:
            return LabelStatus.UNMENTIONED
    except Exception:
        pass

    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return LabelStatus.UNMENTIONED
        if stripped == "1":
            return LabelStatus.PRESENT
        if stripped == "0":
            return LabelStatus.ABSENT
        if stripped == "-1":
            return LabelStatus.UNCERTAIN
        raise ValueError(f"Invalid CheXpert raw value: {value!r}")

    if isinstance(value, bool):
        raise ValueError(f"Invalid CheXpert raw value: {value!r}")

    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid CheXpert raw value: {value!r}") from exc

    if numeric != numeric:  # float NaN
        return LabelStatus.UNMENTIONED

    if numeric == 1.0:
        return LabelStatus.PRESENT
    if numeric == 0.0:
        return LabelStatus.ABSENT
    if numeric == -1.0:
        return LabelStatus.UNCERTAIN

    raise ValueError(f"Invalid CheXpert raw value: {value!r}")