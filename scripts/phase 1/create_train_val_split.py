import json
from pathlib import Path
from sklearn.model_selection import train_test_split

project_root = Path(__file__).resolve().parents[1]

label_path = project_root / "data" / "raw" / "ldctiqac2023" / "train.json"
output_dir = project_root / "data" / "processed" / "ldctiqac2023" / "splits"

output_dir.mkdir(parents=True, exist_ok=True)

with open(label_path, "r") as f:
   labels = json.load(f)
   filenames = sorted(labels.keys())

train_files, val_files = train_test_split(filenames, test_size=0.2, random_state=42, shuffle=True)

train_labels = {filename: labels[filename] for filename in train_files}
val_labels = {filename: labels[filename] for filename in val_files}

with open(output_dir / "train.json", "w") as f:
   json.dump(train_labels, f, indent=2)

with open(output_dir / "val.json", "w") as f:
   json.dump(val_labels, f, indent=2)

print("Total labels: ", len(labels))
print("Train labels: ", len(train_labels))
print("Validation labels: ", len(val_labels))

