from __future__ import annotations

import pytest

from medagentx.evaluation.ground_truth import GroundTruthRecord
from medagentx.evaluation.judge import run_judge
from medagentx.evaluation.ranking import compute_ranking_metrics
from medagentx.labels.statuses import LabelStatus


def _records(label: str, statuses: list[LabelStatus]) -> list[GroundTruthRecord]:
    return [
        GroundTruthRecord(
            study_key=f"study-{index}",
            label=label,
            ground_truth_status=status,
        )
        for index, status in enumerate(statuses)
    ]


def _scores(label: str, values: list[float]) -> dict[tuple[str, str], float]:
    return {
        (f"study-{index}", label): value for index, value in enumerate(values)
    }


@pytest.mark.parametrize(
    ("scores", "expected_auroc"),
    [
        ([0.9, 0.8, 0.2, 0.1], 1.0),
        ([0.2, 0.1, 0.9, 0.8], 0.0),
        ([0.5, 0.5, 0.5, 0.5], 0.5),
    ],
)
def test_ranking_metrics_known_orderings(
    scores: list[float], expected_auroc: float
) -> None:
    label = "Edema"
    records = _records(
        label,
        [
            LabelStatus.PRESENT,
            LabelStatus.PRESENT,
            LabelStatus.ABSENT,
            LabelStatus.ABSENT,
        ],
    )

    result = compute_ranking_metrics(
        ground_truth_records=records,
        predicted_scores=_scores(label, scores),
        labels=[label],
    )

    assert result.macro_auroc == pytest.approx(expected_auroc)
    assert result.per_label_metrics[0].auroc == pytest.approx(expected_auroc)


def test_ranking_metrics_exclude_uncertain_and_unmentioned() -> None:
    label = "Atelectasis"
    statuses = [
        LabelStatus.PRESENT,
        LabelStatus.ABSENT,
        LabelStatus.UNCERTAIN,
        LabelStatus.UNMENTIONED,
    ]

    result = compute_ranking_metrics(
        ground_truth_records=_records(label, statuses),
        predicted_scores=_scores(label, [0.9, 0.1, 1.0, 0.0]),
        labels=[label],
        require_two_classes_per_label=True,
    )

    metrics = result.per_label_metrics[0]
    assert metrics.total == 4
    assert metrics.evaluated == 2
    assert metrics.positive == 1
    assert metrics.negative == 1
    assert metrics.excluded_uncertain == 1
    assert metrics.excluded_unmentioned == 1
    assert metrics.auroc == pytest.approx(1.0)
    assert [cell.included for cell in result.cells] == [True, True, False, False]


def test_ranking_metrics_macro_average_requested_labels() -> None:
    records = _records(
        "Edema", [LabelStatus.PRESENT, LabelStatus.ABSENT]
    ) + _records(
        "Cardiomegaly", [LabelStatus.PRESENT, LabelStatus.ABSENT]
    )
    scores = {
        **_scores("Edema", [0.9, 0.1]),
        **_scores("Cardiomegaly", [0.1, 0.9]),
    }

    result = compute_ranking_metrics(
        ground_truth_records=records,
        predicted_scores=scores,
        labels=["Edema", "Cardiomegaly"],
        require_two_classes_per_label=True,
    )

    assert result.macro_auroc == pytest.approx(0.5)
    assert result.requested_label_count == 2
    assert result.scored_label_count == 2


def test_ranking_metrics_strict_mode_requires_both_classes() -> None:
    label = "Consolidation"
    records = _records(label, [LabelStatus.PRESENT, LabelStatus.PRESENT])

    with pytest.raises(ValueError, match="requires both positive and negative"):
        compute_ranking_metrics(
            ground_truth_records=records,
            predicted_scores=_scores(label, [0.9, 0.8]),
            labels=[label],
            require_two_classes_per_label=True,
        )


def test_judge_status_metrics_are_unchanged_when_ranking_is_enabled() -> None:
    label = "Pleural Effusion"
    records = _records(label, [LabelStatus.PRESENT, LabelStatus.ABSENT])
    statuses = {
        ("study-0", label): LabelStatus.PRESENT,
        ("study-1", label): LabelStatus.ABSENT,
    }

    status_only = run_judge(
        ground_truth_records=records,
        predicted_statuses=statuses,
    )
    with_ranking = run_judge(
        ground_truth_records=records,
        predicted_statuses=statuses,
        predicted_scores=_scores(label, [0.8, 0.2]),
        ranking_labels=[label],
        require_two_classes_per_ranking_label=True,
    )

    assert with_ranking.aggregate_metrics == status_only.aggregate_metrics
    assert with_ranking.per_label_metrics == status_only.per_label_metrics
    assert status_only.ranking_result is None
    assert with_ranking.ranking_result is not None
    assert with_ranking.ranking_result.macro_auroc == pytest.approx(1.0)
