import sys
from pathlib import Path

import numpy as np
import torch
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from data.ldctiqac2023 import LDCTIQAC2023Dataset
from data.transforms import ConvNeXtDataPreprocess
from src.medagentx.models.convnext_baseline import ConvNeXtQualityRegressor

image_dir = PROJECT_ROOT / "data" / "raw" / "ldctiqac2023" / "images"

val_label_path = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "ldctiqac2023"
    / "splits"
    / "val.json"
)

checkpoint_path = (
    PROJECT_ROOT
    / "experiments"
    / "checkpoints"
    / "convnext_baseline_best.pt"
)

transform = ConvNeXtDataPreprocess(image_size=224)

val_dataset = LDCTIQAC2023Dataset(
    image_dir=image_dir,
    label_path=val_label_path,
    transform=transform,
)

val_loader = DataLoader(
    val_dataset,
    batch_size=8,
    shuffle=False,
    num_workers=2,
    pin_memory=True,
)

device = torch.device("cuda")
model = ConvNeXtQualityRegressor(pretrained=False)
model = model.to(device)

checkpoint = torch.load(checkpoint_path, map_location=device)
model.load_state_dict(checkpoint["model_state_dict"])

model.eval()

all_predictions = []
all_targets = []

with torch.no_grad():
   for batch in val_loader:
      images = batch["image"].to(device)
      targets = batch["quality_score"].to(device)

      predictions = model(images)

      all_predictions.extend(predictions.cpu().numpy())
      all_targets.extend(targets.cpu().numpy())

all_predictions = np.array(all_predictions)
all_targets = np.array(all_targets)

clamped_predictions = np.clip(all_predictions, 1.0, 5.0)

mae = mean_absolute_error(all_targets, clamped_predictions)
rmse = mean_squared_error(all_targets, clamped_predictions) ** 0.5
plcc = pearsonr(all_targets, clamped_predictions).statistic
srcc = spearmanr(all_targets, clamped_predictions).statistic

print("Validation metrics")
print(f"MAE:  {mae:.4f}")
print(f"RMSE: {rmse:.4f}")
print(f"PLCC: {plcc:.4f}")
print(f"SRCC: {srcc:.4f}")