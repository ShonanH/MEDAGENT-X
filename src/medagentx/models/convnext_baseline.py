import torch
import torch.nn as nn
from torchvision.models import convnext_tiny, ConvNeXt_Tiny_Weights

class ConvNeXtQualityRegressor(nn.Module):
   def __init__(self, pretrained=True):
      super().__init__()

      if pretrained:
         weights = ConvNeXt_Tiny_Weights.IMAGENET1K_V1
      else:
         weights = None

      self.backbone = convnext_tiny(weights=weights)

      in_features = self.backbone.classifier[2].in_features

      self.backbone.classifier[2] = nn.Linear(in_features, 1)

   def forward(self, images):
      scores = self.backbone(images)
      scores = scores.squeeze(1)

      return scores
      