from random import shuffle
from torch.utils.data import DataLoader
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.models.convnext_baseline import ConvNeXtQualityRegressor
from data.ldctiqac2023 import LDCTIQAC2023Dataset
from data.transforms import ConvNeXtPreprocess


image_dir = PROJECT_ROOT / "data" / "raw" / "ldctiqac2023" / "image"

train_label_path = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "ldctiqac2023"
    / "splits"
    / "train_split.json"
)

transform = ConvNeXtPreprocess(image_size=224)

train_dataset = LDCTIQAC2023Dataset(
    image_dir=image_dir,
    label_path=train_label_path,
    transform=transform,
)

training_loader = DataLoader(
    train_dataset,
    batch_size=8,
    shuffle=True,
)
model = ConvNeXtQualityRegressor(pretrained=True)

batch = next(iter(training_loader))

images = batch["images"]
target = batch["quality_score"]

predictions = model(images)


print(images.shape)
print(target.shape)
print(predictions.shape)
print(predictions)