from random import shuffle
import sys
from pathlib import Path

from numpy import absolute
from scripts.inspect_ldctiqac2023 import PROJECT_ROOT, training_loader, validation_dataset
from scripts.test_convnext_forward import predictions
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from data.ldctiqac2023 import LDCTIQAC2023Dataset
from data.transforms import ConvNeXtDataPreprocess
from src.medagentx.models.convnext_baseline import ConvNeXtQualityRegressor

def train_one_epoch(model, train_loader, loss_fn, optimizer, device):
   model.train()

   total_loss = 0.0
   total_samples = 0

   for batch in train_loader:
      images = batch["image"].to(device)
      targets = batch["quality_score"].to(device)

      predictions = model(images)

      loss = loss_fn(predictions, targets)

      optimizer.zero_grad()
      loss.backward()
      optimizer.step()

      batch_size = images.size(0)
      total_loss += loss.item() * batch_size
      total_samples += batch_size
   
   return total_loss / total_samples

def validate(model, validation_loader, loss_fn, device):
   model.eval()

   total_loss = 0.0
   total_absolute_error = 0.0
   total_samples = 0

   with torch.no_grad():
      for batch in validation_loader:
            images = batch["image"].to(device)
            targets = batch["quality_score"].to(device)

            predictions = model(images)
            loss = loss_fn(predictions, targets)

            absolute_error = torch.abs(predictions - targets)

            batch_size = images.size(0)
            total_loss += loss.item() * batch_size

            total_absolute_error += absolute_error.sum().item()
            total_samples += batch_size
   
   validation_loss = total_loss / total_samples
   validation_mae = total_absolute_error / total_samples

   return validation_loss, validation_mae

def main():
   if not torch.cuda.is_available():
      raise RuntimeError("CUDA IS NOT AVAILABLE")
   
   device = torch.device("cuda")

   image_dir = PROJECT_ROOT / "data" / "raw" / "ldctiqac2023" / "image"

   train_label_path = (
      PROJECT_ROOT
      / "data"
      / "processed"
      / "ldctiqac2023"
      / "splits"
      / "train.json"
   )

   val_label_path = (
      PROJECT_ROOT
      / "data"
      / "processed"
      / "ldctiqac2023"
      / "splits"
      / "val.json"
   )

   checkpoint_dir = PROJECT_ROOT / "experiments" / "checkpoints"
   checkpoint_dir.mkdir(parents=True, exist_ok=True)

   transform = ConvNeXtDataPreprocess(image_size=224)

   train_dataset = LDCTIQAC2023Dataset(
      image_dir=image_dir,
      label_path=train_label_path,
      transform=transform,
   )

   val_dataset = LDCTIQAC2023Dataset(
      image_dir=image_dir,
      label_path=val_label_path,
      transform=transform,
   )

   training_loader = DataLoader(
      train_dataset,
      batch_size=8,
      shuffle=True,
      num_workers=2,
      pin_memory=True,
   )

   validation_loader = DataLoader(
      val_dataset,
      batch_size=8,
      shuffle=False,
      num_workers=2,
      pin_memory=True,
   )

   model = ConvNeXtQualityRegressor(pretrained=True)
   model = model.to(device)

   loss_fn = nn.MSELoss()
   optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)

   num_epochs = 5
   best_validation_loss = float('inf')

   for epoch in range(num_epochs):
      train_loss = train_one_epoch(
         model = model,
         train_loader=training_loader,
         loss_fn=loss_fn,
         optimizer=optimizer,
         device=device
      )

      val_loss, val_mae = validate(
         model = model,
         validation_loader=validation_loader,
         loss_fn=loss_fn,
         device=device
      )

      print(f"Epoch {epoch + 1}/{num_epochs}")
      print(f"Train loss: {train_loss:.4f}")
      print(f"Val loss:   {val_loss:.4f}")
      print(f"Val MAE:    {val_mae:.4f}")

      if val_loss < best_validation_loss:
         best_validation_loss = val_loss

         checkpoint_path = checkpoint_dir / "convnext_baseline_best.pt"

         torch.save(
            {
               "epoch": epoch + 1,
               "model_state_dict": model.state_dict(),
               "optimizer_state_dict": optimizer.state_dict(),
               "best_validation_loss": best_validation_loss,
            },
            checkpoint_path,
         )

         print(f"Saved best checkpoint to: {checkpoint_path}")

      print("-" * 50)


if __name__ == "__main__":
    main()