import sys
from pathlib import Path

import numpy as np
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.features.artifact_features import compute_artifact_features

image_path = (
   PROJECT_ROOT / "data" / "raw" / "ldctiqac2023" / "images" / "0000.tif"
)

image = Image.open(image_path)
image = np.array(image, dtype=np.float32)

features = compute_artifact_features(image)

print("Image: ", image_path.name)
print("Shape: ", image.shape)

for key, value in features.items():
   print(f"{key}: {value: .6f}")