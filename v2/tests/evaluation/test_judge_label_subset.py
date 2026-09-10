from __future__ import annotations

import pandas as pd

from medagentx.cli.summarize_judge_label_subset import summarize_label_subset


def test_summarize_label_subset_recomputes_macro_and_micro_metrics() -> None:
    metrics = pd.DataFrame(
        [
            {
                "run_name": run,
                "label": label,
                "eval_scope": "full",
                "scoreable_cells": 8,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": tp / (tp + fp),
                "recall": tp / (tp + fn),
                "f1": 2 * tp / (2 * tp + fp + fn),
            }
            for run, label, tp, fp, fn in (
                ("vision_full", "A", 3, 1, 2),
                ("vision_full", "B", 1, 1, 0),
                ("fusion_full", "A", 4, 1, 1),
                ("fusion_full", "B", 2, 0, 0),
            )
        ]
    )

    selected, summary = summarize_label_subset(
        metrics,
        labels=("A", "B"),
        run_names=("vision_full", "fusion_full"),
        study_count=10,
    )

    assert len(selected) == 4
    vision = summary[summary["run_name"] == "vision_full"].iloc[0]
    assert vision["coverage"] == 0.8
    assert vision["tp"] == 4
    assert vision["fp"] == 2
    assert vision["fn"] == 2
    assert vision["micro_precision"] == 4 / 6
    assert vision["micro_recall"] == 4 / 6
    assert vision["micro_f1"] == 4 / 6
