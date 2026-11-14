"""CLI contracts for held-out-test handling during RAD-DINO training."""

import inspect

import pytest
import torch

pytest.importorskip("PIL")
pytest.importorskip("transformers")

from medagentx.cli.train_raddino import build_parser, main  # noqa: E402
from medagentx.cli.evaluate_raddino_checkpoint import (  # noqa: E402
    build_parser as build_evaluation_parser,
)
from medagentx.vision.trainer import set_reproducible_seed  # noqa: E402


def test_skip_test_is_opt_in_and_records_the_intent() -> None:
    parser = build_parser()

    assert parser.parse_args([]).skip_test is False
    assert parser.parse_args(["--skip-test"]).skip_test is True


def test_model_initialization_is_seeded_before_construction() -> None:
    set_reproducible_seed(42)
    first = torch.nn.Linear(4, 3)
    set_reproducible_seed(42)
    second = torch.nn.Linear(4, 3)

    assert torch.equal(first.weight, second.weight)
    assert torch.equal(first.bias, second.bias)

    source = inspect.getsource(main)
    assert source.index("set_reproducible_seed(args.seed)") < source.index(
        "RadDinoStudyClassifier.from_pretrained"
    )


def test_held_out_evaluation_requires_explicit_checkpoint_and_output() -> None:
    parser = build_evaluation_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])

    args = parser.parse_args(
        [
            "--checkpoint",
            "/runs/best_checkpoint.pt",
            "--output-root",
            "/runs/test-evaluation",
            "--model-ready-cache-root",
            "/data/model-ready-cache",
        ]
    )
    assert args.max_test_studies is None
