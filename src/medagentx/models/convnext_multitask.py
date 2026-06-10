import torch
import torch.nn as nn
from torchvision.models import convnext_tiny, ConvNeXt_Tiny_Weights

class ConvNeXtMultiTask(nn.Module):
   def __init__(self, pretrained=True):
      super().__init__()

      if pretrained:
         weights = ConvNeXt_Tiny_Weights.IMAGENET1K_V1
      else:
         weights = None

      self.backbone = convnext_tiny(weights=weights)

      in_features = self.backbone.classifier[2].in_features

      self.backbone.classifier[2] = nn.Identity()

      self.score_head = nn.Linear(in_features, 1)
      self.clinical_head = nn.Linear(in_features, 5)
      self.uncertainty_head = nn.Linear(in_features, 1)

   
   def forward(self, images):
      features = self.backbone(images)

      quality_score = self.score_head(features).squeeze(1)
      clinical_logits = self.clinical_head(features)
      uncertainty = self.uncertainty_head(features).squeeze(1)


      return {
         "quality_score": quality_score,
         "clinical_logits": clinical_logits,
         "uncertainty": uncertainty
      }