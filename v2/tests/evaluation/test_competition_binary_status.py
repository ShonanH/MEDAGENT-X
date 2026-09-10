from __future__ import annotations

from medagentx.evaluation.chexpert_competition import (
    competition_binary_status_map,
)
from medagentx.labels.statuses import LabelStatus


def test_competition_binary_status_maps_uncertain_to_absent() -> None:
    statuses = {
        ("patient1/study1", "Atelectasis"): LabelStatus.UNCERTAIN,
        ("patient1/study1", "Cardiomegaly"): LabelStatus.PRESENT,
        ("patient1/study1", "Pneumonia"): LabelStatus.PRESENT,
    }

    binary, audit = competition_binary_status_map(statuses)

    assert binary[("patient1/study1", "Atelectasis")] is LabelStatus.ABSENT
    assert binary[("patient1/study1", "Cardiomegaly")] is LabelStatus.PRESENT
    assert ("patient1/study1", "Pneumonia") not in binary
    atelectasis = audit[audit["label"] == "Atelectasis"].iloc[0]
    assert atelectasis["raw_status"] == "uncertain"
    assert atelectasis["binary_status"] == "absent"
    assert atelectasis["was_mapped"] == "true"
