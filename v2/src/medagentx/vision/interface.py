"""Backend-neutral contract used by the future Vision Agent."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

import pandas as pd

from medagentx.vision.data import StudyInferenceRecord


class VisionBackend(Protocol):
    """A pluggable image-only study prediction backend."""

    @property
    def backend_id(self) -> str:
        """Return a versioned backend identifier."""

    def predict_studies(
        self,
        records: Sequence[StudyInferenceRecord],
        *,
        dicom_root: str | Path,
        batch_size: int,
        num_workers: int,
    ) -> pd.DataFrame:
        """Return one permanent-contract prediction row per study."""
