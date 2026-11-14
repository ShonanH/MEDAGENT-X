"""Tests for auditable weak-label evaluation strata."""

from __future__ import annotations

import pandas as pd

from medagentx.evaluation.fusion_eval import (
    study_labels_to_ground_truth_strata,
)
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label
from medagentx.labels.statuses import LabelStatus


def _study_row(study_key: str) -> dict[str, object]:
    row: dict[str, object] = {"study_key": study_key}
    for label in DISEASE_LABELS:
        slug = snake_label(label)
        row[f"status_{slug}"] = "unmentioned"
        row[f"training_mask_{slug}"] = 0
        row[f"training_target_{slug}"] = None
    return row


def test_ground_truth_strata_preserve_explicit_and_derived_provenance() -> None:
    row = _study_row("patient1/study1")
    row["status_atelectasis"] = "present"
    row["training_mask_atelectasis"] = 1
    row["training_target_atelectasis"] = 1.0
    row["status_cardiomegaly"] = "absent"
    row["training_mask_cardiomegaly"] = 1
    row["training_target_cardiomegaly"] = 0.0
    row["training_mask_consolidation"] = 1
    row["training_target_consolidation"] = 0.0
    row["status_edema"] = "uncertain"

    strata = study_labels_to_ground_truth_strata(pd.DataFrame([row]))

    explicit = {record.label: record for record in strata.explicit}
    combined = {record.label: record for record in strata.combined}
    assert explicit["Atelectasis"].ground_truth_status is LabelStatus.PRESENT
    assert explicit["Cardiomegaly"].ground_truth_status is LabelStatus.ABSENT
    assert explicit["Consolidation"].ground_truth_status is LabelStatus.UNMENTIONED
    assert combined["Consolidation"].ground_truth_status is LabelStatus.ABSENT
    assert combined["Edema"].ground_truth_status is LabelStatus.UNCERTAIN
    assert len(strata.no_finding_derived) == 1
    assert strata.no_finding_derived[0].label == "Consolidation"

    provenance = strata.provenance.set_index("label")
    assert provenance.loc["Atelectasis", "target_provenance"] == "explicit_present"
    assert provenance.loc["Cardiomegaly", "target_provenance"] == "explicit_absent"
    assert (
        provenance.loc["Consolidation", "target_provenance"]
        == "no_finding_derived_negative"
    )
    assert bool(provenance.loc["Consolidation", "combined_scoreable"])
    assert not bool(provenance.loc["Edema", "combined_scoreable"])


def test_ground_truth_strata_respect_requested_study_order() -> None:
    rows = [_study_row("second"), _study_row("first")]

    strata = study_labels_to_ground_truth_strata(
        pd.DataFrame(rows),
        study_keys=["first", "second"],
    )

    assert strata.explicit[0].study_key == "first"
    assert strata.explicit[len(DISEASE_LABELS)].study_key == "second"
