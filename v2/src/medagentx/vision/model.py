"""Study-level RAD-DINO classifier with partial backbone fine-tuning."""

from __future__ import annotations

from typing import Any, Iterable, Sequence

import torch
from torch import nn

from medagentx.labels.constants import DISEASE_LABELS
from medagentx.vision.constants import (
    DEFAULT_MODEL_NAME,
    TRAINABLE_LAST_BLOCKS,
)


def _transformer_blocks(backbone: nn.Module) -> Sequence[nn.Module]:
    """Resolve the transformer block list for Hugging Face DINO variants."""
    candidates = (
        ("encoder", "layer"),
        ("encoder", "layers"),
        ("blocks",),
        ("layer",),
    )
    for path in candidates:
        value: Any = backbone
        for part in path:
            value = getattr(value, part, None)
            if value is None:
                break
        if isinstance(value, (nn.ModuleList, list, tuple)):
            return value
    raise RuntimeError(
        "Could not locate RAD-DINO transformer blocks. "
        "Expected encoder.layer, encoder.layers, blocks, or layer."
    )


def configure_partial_fine_tuning(
    backbone: nn.Module,
    *,
    trainable_last_blocks: int = TRAINABLE_LAST_BLOCKS,
) -> dict[str, int]:
    """Freeze RAD-DINO except for the locked final transformer blocks."""
    if trainable_last_blocks <= 0:
        raise ValueError("trainable_last_blocks must be > 0")

    for parameter in backbone.parameters():
        parameter.requires_grad = False

    blocks = _transformer_blocks(backbone)
    if trainable_last_blocks > len(blocks):
        raise ValueError(
            f"Requested {trainable_last_blocks} trainable blocks, "
            f"but backbone has {len(blocks)}"
        )
    for block in blocks[-trainable_last_blocks:]:
        for parameter in block.parameters():
            parameter.requires_grad = True

    total = sum(parameter.numel() for parameter in backbone.parameters())
    trainable = sum(
        parameter.numel()
        for parameter in backbone.parameters()
        if parameter.requires_grad
    )
    return {
        "total_backbone_parameters": int(total),
        "trainable_backbone_parameters": int(trainable),
        "total_transformer_blocks": len(blocks),
        "trainable_transformer_blocks": trainable_last_blocks,
    }


class RadDinoStudyClassifier(nn.Module):
    """Encode every view, pool by study, and predict configured labels."""

    def __init__(
        self,
        backbone: nn.Module,
        *,
        hidden_size: int,
        num_labels: int | None = None,
        label_names: Sequence[str] | None = None,
        dropout: float = 0.1,
        trainable_last_blocks: int = TRAINABLE_LAST_BLOCKS,
        pooling_mode: str = "mean",
    ) -> None:
        super().__init__()
        if hidden_size <= 0:
            raise ValueError("hidden_size must be > 0")
        labels = tuple(label_names or DISEASE_LABELS)
        if not labels:
            raise ValueError("label_names must be non-empty")
        resolved_num_labels = len(labels) if num_labels is None else num_labels
        if resolved_num_labels != len(labels):
            raise ValueError(
                f"num_labels={resolved_num_labels} does not match "
                f"label_names={len(labels)}"
            )

        self.backbone = backbone
        self.hidden_size = hidden_size
        self.num_labels = resolved_num_labels
        self.label_names = labels
        self.trainable_last_blocks = trainable_last_blocks
        self.pooling_mode = pooling_mode.strip().lower()
        if self.pooling_mode not in {"mean", "mean_max", "max"}:
            raise ValueError("pooling_mode must be 'mean', 'mean_max', or 'max'")
        self.freeze_summary = configure_partial_fine_tuning(
            self.backbone,
            trainable_last_blocks=trainable_last_blocks,
        )
        classifier_input_size = (
            hidden_size * 2 if self.pooling_mode == "mean_max" else hidden_size
        )
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(classifier_input_size, resolved_num_labels),
        )

    @classmethod
    def from_pretrained(
        cls,
        model_name: str = DEFAULT_MODEL_NAME,
        **kwargs: Any,
    ) -> "RadDinoStudyClassifier":
        from transformers import AutoModel

        backbone = AutoModel.from_pretrained(model_name)
        hidden_size = int(getattr(backbone.config, "hidden_size"))
        return cls(backbone, hidden_size=hidden_size, **kwargs)

    def trainable_backbone_parameters(self) -> Iterable[nn.Parameter]:
        return (
            parameter
            for parameter in self.backbone.parameters()
            if parameter.requires_grad
        )

    def forward(
        self,
        pixel_values: torch.Tensor,
        study_indices: torch.Tensor,
        num_studies: int,
    ) -> dict[str, torch.Tensor]:
        if pixel_values.ndim != 4:
            raise ValueError(
                "pixel_values must have shape [views, channels, height, width]"
            )
        if study_indices.ndim != 1 or len(study_indices) != len(pixel_values):
            raise ValueError(
                "study_indices must contain one index for every input view"
            )
        if num_studies <= 0:
            raise ValueError("num_studies must be > 0")

        outputs = self.backbone(pixel_values=pixel_values)
        if not hasattr(outputs, "last_hidden_state"):
            raise RuntimeError("RAD-DINO output has no last_hidden_state")
        view_embeddings = outputs.last_hidden_state[:, 0, :]
        if view_embeddings.shape[-1] != self.hidden_size:
            raise RuntimeError(
                f"Expected hidden size {self.hidden_size}, "
                f"got {view_embeddings.shape[-1]}"
            )

        mean_embeddings = torch.zeros(
            (num_studies, self.hidden_size),
            dtype=view_embeddings.dtype,
            device=view_embeddings.device,
        )
        mean_embeddings.index_add_(0, study_indices, view_embeddings)
        counts = torch.zeros(
            num_studies,
            dtype=view_embeddings.dtype,
            device=view_embeddings.device,
        )
        counts.index_add_(
            0,
            study_indices,
            torch.ones_like(study_indices, dtype=view_embeddings.dtype),
        )
        if torch.any(counts == 0):
            raise ValueError("Every study must contribute at least one view")
        mean_embeddings = mean_embeddings / counts.unsqueeze(1)

        if self.pooling_mode in {"mean_max", "max"}:
            max_embeddings = []
            for study_index in range(num_studies):
                max_embeddings.append(
                    view_embeddings[study_indices == study_index].max(dim=0).values
                )
            max_embeddings = torch.stack(max_embeddings, dim=0)
            study_embeddings = (
                torch.cat([mean_embeddings, max_embeddings], dim=1)
                if self.pooling_mode == "mean_max"
                else max_embeddings
            )
        else:
            study_embeddings = mean_embeddings

        if self.pooling_mode == "max":
            # The competition baseline takes the maximum view probability.
            # Since sigmoid is monotonic, max logits is equivalent and keeps
            # the operation numerically stable.
            view_logits = self.classifier(view_embeddings)
            study_logits = []
            for study_index in range(num_studies):
                study_logits.append(
                    view_logits[study_indices == study_index].max(dim=0).values
                )
            logits = torch.stack(study_logits, dim=0)
        else:
            logits = self.classifier(study_embeddings)
        return {
            "logits": logits,
            "study_embeddings": study_embeddings,
            "view_embeddings": view_embeddings,
        }
