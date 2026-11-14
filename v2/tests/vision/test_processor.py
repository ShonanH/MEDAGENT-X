"""Tests for reconstructing the saved RAD-DINO image processor."""

from __future__ import annotations

import json
import sys
import types

import pytest

from medagentx.vision.processor import load_training_image_processor


def test_loads_bit_processor_from_training_run_config(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkpoint_path = tmp_path / "best_checkpoint.pt"
    checkpoint_path.touch()
    processor_config = {
        "image_processor_type": "BitImageProcessor",
        "image_mean": [0.5, 0.5, 0.5],
        "image_std": [0.25, 0.25, 0.25],
    }
    (tmp_path / "run_config.json").write_text(
        json.dumps(
            {
                "image_processor": {
                    "model_name": "microsoft/rad-dino",
                    "config": processor_config,
                }
            }
        )
    )

    class FakeBitImageProcessor:
        @classmethod
        def from_dict(cls, values):
            return {"processor": cls.__name__, "config": values}

    fake_transformers = types.ModuleType("transformers")
    fake_transformers.BitImageProcessor = FakeBitImageProcessor
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    processor = load_training_image_processor(
        checkpoint_path,
        {"model_name": "microsoft/rad-dino"},
    )

    assert processor == {
        "processor": "FakeBitImageProcessor",
        "config": processor_config,
    }


def test_rejects_processor_checkpoint_model_mismatch(tmp_path) -> None:
    checkpoint_path = tmp_path / "best_checkpoint.pt"
    checkpoint_path.touch()
    (tmp_path / "run_config.json").write_text(
        json.dumps(
            {
                "image_processor": {
                    "model_name": "different/model",
                    "config": {"image_processor_type": "BitImageProcessor"},
                }
            }
        )
    )

    with pytest.raises(ValueError, match="does not match checkpoint"):
        load_training_image_processor(
            checkpoint_path,
            {"model_name": "microsoft/rad-dino"},
        )
