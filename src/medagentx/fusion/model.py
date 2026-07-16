from __future__ import annotations

import torch
import torch.nn as nn


class FusionMLP(nn.Module):
    """
    Multi-label fusion classifier with optional DenseNet probability stacking,
    residual trunk, and per-label output heads.
    """

    def __init__(
        self,
        input_dim: int,
        num_labels: int,
        hidden_dim: int = 512,
        dropout: float = 0.3,
        densenet_dim: int = 0,
        per_label_heads: bool = True,
    ):
        super().__init__()
        self.embedding_dim = int(input_dim)
        self.num_labels = int(num_labels)
        self.densenet_dim = int(densenet_dim)
        self.per_label_heads = bool(per_label_heads)
        total_in = self.embedding_dim + self.densenet_dim

        self.input_norm = nn.LayerNorm(total_in)
        self.trunk = nn.Sequential(
            nn.Linear(total_in, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )
        self.residual = (
            nn.Linear(total_in, hidden_dim)
            if total_in != hidden_dim
            else nn.Identity()
        )

        if self.per_label_heads:
            self.heads = nn.ModuleList([nn.Linear(hidden_dim, 1) for _ in range(num_labels)])
            self.head = None
        else:
            self.heads = None
            self.head = nn.Linear(hidden_dim, num_labels)

    def forward(
        self,
        x: torch.Tensor,
        densenet_probs: torch.Tensor | None = None,
    ) -> torch.Tensor:
        if self.densenet_dim > 0:
            if densenet_probs is None:
                raise ValueError("densenet_probs required when densenet_dim > 0")
            x = torch.cat([x, densenet_probs], dim=-1)

        normalized = self.input_norm(x)
        hidden = self.trunk(normalized) + self.residual(normalized)

        if self.per_label_heads:
            return torch.cat([head(hidden) for head in self.heads], dim=-1)
        return self.head(hidden)


class TemperatureScaler(nn.Module):
    def __init__(self, init_temperature: float = 1.0):
        super().__init__()
        self.temperature = nn.Parameter(torch.tensor([init_temperature], dtype=torch.float32))

    def forward(self, logits: torch.Tensor) -> torch.Tensor:
        return logits / self.temperature.clamp_min(1e-3)
