from torch.utils.data import DataLoader
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.models.convnext_multitask import ConvNeXtMultiTask
from data.ldctiqac2023 import LDCTIQAC2023Dataset
from data.transforms import ConvNeXtDataPreprocess

image_dir = PROJECT_ROOT / "data" / "raw" / "ldctiqac2023" / "images"

train_label_path = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "ldctiqac2023"
    / "splits"
    / "train.json"
)

transform = ConvNeXtDataPreprocess(image_size=224)
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

model = ConvNeXtMultiTask(pretrained=True)


batch = next(iter(training_loader))

images = batch["image"]
quality_targets = batch["quality_score"]
clinical_targets = batch["clinical_level"] - 1

outputs = model(images)

print("Images:", images.shape)
print("Quality targets:", quality_targets.shape)
print("Clinical targets:", clinical_targets.shape)

print("Quality predictions:", outputs["quality_score"].shape)
print("Clinical logits:", outputs["clinical_logits"].shape)
print("Uncertainty:", outputs["uncertainty"].shape)

print("Sample quality predictions:", outputs["quality_score"])
print("Sample clinical logits:", outputs["clinical_logits"])
print("Sample uncertainty:", outputs["uncertainty"])