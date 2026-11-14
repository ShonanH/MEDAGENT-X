"""Recreate the image processor used by a saved RAD-DINO training run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_training_image_processor(
    checkpoint_path: str | Path,
    checkpoint: dict[str, Any],
) -> Any:
    """Load the exact processor configuration recorded beside a checkpoint."""
    resolved_checkpoint = Path(checkpoint_path)
    run_config_path = resolved_checkpoint.parent / "run_config.json"
    if run_config_path.exists():
        run_config = json.loads(run_config_path.read_text())
        saved_processor = run_config.get("image_processor")
        if not isinstance(saved_processor, dict):
            raise ValueError(
                f"Training run config has no image_processor object: "
                f"{run_config_path}"
            )
        saved_model_name = saved_processor.get("model_name")
        checkpoint_model_name = checkpoint.get("model_name")
        if saved_model_name != checkpoint_model_name:
            raise ValueError(
                "Training image processor model does not match checkpoint: "
                f"processor={saved_model_name!r} "
                f"checkpoint={checkpoint_model_name!r}"
            )
        processor_config = saved_processor.get("config")
        if not isinstance(processor_config, dict):
            raise ValueError(
                f"Training image processor config is invalid: {run_config_path}"
            )
        processor_type = processor_config.get("image_processor_type")
        if processor_type != "BitImageProcessor":
            raise ValueError(
                "Unsupported saved image processor type "
                f"{processor_type!r} in {run_config_path}"
            )
        from transformers import BitImageProcessor

        print(
            "[Vision] loading image processor from training run config "
            f"{run_config_path}"
        )
        return BitImageProcessor.from_dict(processor_config)

    from transformers import AutoImageProcessor

    print(
        "[Vision] training run config not found; loading image processor "
        f"from model hub for {checkpoint['model_name']}"
    )
    return AutoImageProcessor.from_pretrained(checkpoint["model_name"])
