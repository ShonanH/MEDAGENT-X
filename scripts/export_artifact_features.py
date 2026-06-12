import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.features.artifact_features import compute_artifact_features

prediction_path = (
   PROJECT_ROOT / "experiments" / "predictions" / "convnext_multitask_val_predictions.csv"
)

image_dir = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "ldctiqac2023"
    / "images"
)

output_path = (
    PROJECT_ROOT
    / "experiments"
    / "predictions"
    / "convnext_multitask_val_agent_inputs.csv"
)

def load_image(image_path):
   image = Image.open(image_path)
   image = np.array(image, dtype=np.float32)
   return image

def main():
   predictions = pd.read_csv(prediction_path)

   rows = []

   for _, prediction_row in predictions.iterrows():
      filename = prediction_row["filename"]
      image_path = image_dir / filename

      if not image_path.exists():
         raise FileNotFoundError(f"Missing image: {image_path}")

      image = load_image(image_path)
      artifact_features = compute_artifact_features(image)

      combined_row = prediction_row.to_dict()
      combined_row.update(artifact_features)

      rows.append(combined_row)
   
   combined_df = pd.DataFrame(rows)
   combined_df.to_csv(output_path, index=False)
   print(f"Saved combined agent input CSV to: {output_path}")
   print(f"Rows written: {len(combined_df)}")
   print(f"Columns written: {len(combined_df.columns)}")



if __name__ == "__main__":
    main()