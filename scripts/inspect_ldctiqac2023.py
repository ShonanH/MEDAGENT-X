from random import shuffle
from torch.utils.data import DataLoader
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from ldctiqac2023 import LDCTIQAC2023Dataset
from transforms import ConvNeXtDataPreprocess


image_dir = PROJECT_ROOT / "data" / "raw" / "ldctiqac2023" / "image"

training_dataset_label_path = PROJECT_ROOT / "data" / "processed" / "ldctiqac2023" / "splits" / "train_split.json"
validation_dataset_label_path = PROJECT_ROOT / "data" / "processed" / "ldctiqac2023" / "splits" / "val_split.json"

transform = ConvNeXtDataPreprocess(image_size=224)


training_dataset = LDCTIQAC2023Dataset(image_dir=image_dir, label_path=training_dataset_label_path, transform=transform)
validation_dataset = LDCTIQAC2023Dataset(image_dir=image_dir, label_path=validation_dataset_label_path, transform=transform)


# print(len(dataset))
# sample = dataset[0]
# print("Filename:",  sample["filename"])
# print(sample["image"].shape)
# print(sample["raw_score"])
# print(sample["quality_score"])
# print(sample["clinical_level"])

training_loader = DataLoader(training_dataset, batch_size=8, shuffle=True)
validation_loader = DataLoader(validation_dataset, batch_size=8, shuffle=False)


train_batch = next(iter(training_loader))
val_batch = next(iter(validation_loader))

print("Train batch image shape:", train_batch["image"].shape)
print("Train filenames:", train_batch["filename"])
print("Train raw scores:", train_batch["raw_score"])
print("Train quality scores:", train_batch["quality_score"])
print("Train clinical levels:", train_batch["clinical_level"])

print("Validation batch image shape:", val_batch["image"].shape)
print("Validation filenames:", val_batch["filename"])
print("Validation raw scores:", val_batch["raw_score"])
print("Validation quality scores:", val_batch["quality_score"])
print("Validation clinical levels:", val_batch["clinical_level"])


