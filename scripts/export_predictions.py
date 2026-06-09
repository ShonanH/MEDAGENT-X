import csv
import sys
from pathlib import Path

from numpy import absolute
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from data.ldctiqac2023 import LDCTIQAC2023Dataset
from data.transforms import ConvNeXtDataPreprocess
from src.medagentx.models.convnext_baseline import ConvNeXtQualityRegressor

def quality_score_to_clinical_level(score):
    if score < 1.5:
        return 1
    if score < 2.5:
        return 2
    if score < 3.5:
        return 3
    if score < 4.5:
        return 4
    return 5

   
def main():
   if not torch.cuda.is_available():
      raise RuntimeError("CUDA is not available")
   
   device = torch.device("cuda")

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

   output_dir = PROJECT_ROOT / "experiments" / "predictions"
   output_dir.mkdir(parents=True, exist_ok=True)
   output_path = output_dir / "convnext_baseline_val_predictions.csv"


   transform = ConvNeXtDataPreprocess(image_size=224)

   val_dataset = LDCTIQAC2023Dataset(
      image_dir=image_dir,
      label_path=val_label_path,
      transform=transform
   )

   val_loader = DataLoader(
      val_dataset,
      batch_size=8,
      shuffle=False,
      num_workers=2,
      pin_memory=True,
   )

   model = ConvNeXtQualityRegressor(pretrained=False)
   model = model.to(device)

   checkpoint = torch.load(checkpoint_path, map_location=device)
   model.load_state_dict(checkpoint["model_state_dict"])
   model.eval()

   rows = []

   with torch.no_grad():
      for batch in val_loader:
         images = batch["image"].to(device)
         true_quality_scores = batch["quality_score"]
         filenames = batch["filename"]

         predictions = model(images)
         predictions = predictions.clamp(1.0, 5.0)

         predictions = predictions.cpu()

         for filename, true_score, predicted_score, true_level in zip(
            filenames,
            true_quality_scores,
            predictions,
         ):
            true_score = float(true_score.item())
            predicted_score = float(predicted_score.item())
            absolute_error = abs(predicted_score - true_score)

            true_level = quality_score_to_clinical_level(true_score)
            predicted_level = quality_score_to_clinical_level(predicted_score)

            rows.append(
               {
                  "filename": filename,
                  "true_quality_score": round(true_score, 4),
                  "predicted_quality_score": round(predicted_score, 4),
                  "absolute_error": round(absolute_error, 4),
                  "true_clinical_level": true_level,
                  "predicted_clinical_level": predicted_level,
               }
            )

   with open(output_path, "w", newline="") as f:
      fieldnames = [
         "filename",
         "true_quality_score",
         "predicted_quality_score",
         "absolute_error",
         "true_clinical_level",
         "predicted_clinical_level",
      ]

      writer = csv.DictWriter(f, fieldnames=fieldnames)
      writer.writeheader()
      writer.writerows(rows)


   print(f"Saved predictions to: {output_path}")
   print(f"Rows written: {len(rows)}")


if __name__ == "__main__":
    main()
