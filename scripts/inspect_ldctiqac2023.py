from torch.utils.data import DataLoader
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "data"
sys.path.insert(0, str(SRC_DIR))

from medagentx.data.ldctiqac2023 import LDCTIQAC2023Dataset


dataset_root = PROJECT_ROOT / "data" / "raw" / "ldctiqac2023"
dataset = LDCTIQAC2023Dataset(root_dir=dataset_root)

print(len(dataset))

sample = dataset[0]

print(sample["filename"])
print(sample["image"].shape)
print(sample["raw_score"])
print(sample["quality_score"])
print(sample["clinical_level"])

loader = DataLoader(dataset, batch_size=8, shuffle=True)

batch = next(iter(loader))

print(batch["filename"])
print(batch["raw_score"])
print(batch["quality_score"])
print(batch["clinical_level"])

