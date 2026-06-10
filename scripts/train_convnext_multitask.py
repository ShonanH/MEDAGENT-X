import sys
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.models.convnext_multitask import ConvNeXtMultiTask
from data.ldctiqac2023 import LDCTIQAC2023Dataset
from data.transforms import ConvNeXtDataPreprocess


def train_one_epoch(model, train_loader, mse_loss_fn, ce_loss_fn, optimizer, device):
    model.train()

    running_loss = 0.0
    running_score_loss = 0.0
    running_clinical_loss = 0.0
    running_uncertainty_loss = 0.0
    total_samples = 0

    for batch in train_loader:
        images = batch["image"].to(device)
        quality_targets = batch["quality_score"].to(device)
        clinical_targets = (batch["clinical_level"] - 1).to(device)

        outputs = model(images)

        uncertainty_target = torch.abs(
            outputs["quality_score"].detach() - quality_targets
        )

        score_loss = mse_loss_fn(outputs["quality_score"], quality_targets)
        clinical_loss = ce_loss_fn(outputs["clinical_logits"], clinical_targets)
        uncertainty_loss = mse_loss_fn(outputs["uncertainty"], uncertainty_target)

        loss = score_loss + 0.5 * clinical_loss + 0.1 * uncertainty_loss

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        batch_size = images.size(0)

        running_loss += loss.item() * batch_size
        running_score_loss += score_loss.item() * batch_size
        running_clinical_loss += clinical_loss.item() * batch_size
        running_uncertainty_loss += uncertainty_loss.item() * batch_size
        total_samples += batch_size

    return {
        "loss": running_loss / total_samples,
        "score_loss": running_score_loss / total_samples,
        "clinical_loss": running_clinical_loss / total_samples,
        "uncertainty_loss": running_uncertainty_loss / total_samples,
    }


def validate(model, val_loader, mse_loss_fn, ce_loss_fn, device):
    model.eval()

    running_loss = 0.0
    running_score_loss = 0.0
    running_clinical_loss = 0.0
    running_uncertainty_loss = 0.0
    running_absolute_error = 0.0
    correct_clinical = 0
    total_samples = 0

    with torch.no_grad():
        for batch in val_loader:
            images = batch["image"].to(device)
            quality_targets = batch["quality_score"].to(device)
            clinical_targets = (batch["clinical_level"] - 1).to(device)

            outputs = model(images)

            uncertainty_target = torch.abs(outputs["quality_score"] - quality_targets)

            score_loss = mse_loss_fn(outputs["quality_score"], quality_targets)
            clinical_loss = ce_loss_fn(outputs["clinical_logits"], clinical_targets)
            uncertainty_loss = mse_loss_fn(outputs["uncertainty"], uncertainty_target)

            loss = score_loss + 0.5 * clinical_loss + 0.1 * uncertainty_loss

            absolute_error = torch.abs(outputs["quality_score"] - quality_targets)

            predicted_clinical_classes = torch.argmax(
                outputs["clinical_logits"],
                dim=1,
            )

            correct_clinical += (
                predicted_clinical_classes == clinical_targets
            ).sum().item()

            batch_size = images.size(0)

            running_loss += loss.item() * batch_size
            running_score_loss += score_loss.item() * batch_size
            running_clinical_loss += clinical_loss.item() * batch_size
            running_uncertainty_loss += uncertainty_loss.item() * batch_size
            running_absolute_error += absolute_error.sum().item()
            total_samples += batch_size

    return {
        "loss": running_loss / total_samples,
        "score_loss": running_score_loss / total_samples,
        "clinical_loss": running_clinical_loss / total_samples,
        "uncertainty_loss": running_uncertainty_loss / total_samples,
        "mae": running_absolute_error / total_samples,
        "clinical_accuracy": correct_clinical / total_samples,
    }


def main():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available. This script is intended for GPU training.")

    device = torch.device("cuda")

    image_dir = PROJECT_ROOT / "data" / "raw" / "ldctiqac2023" / "images"

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

    train_loader = DataLoader(
        train_dataset,
        batch_size=8,
        shuffle=True,
        num_workers=2,
        pin_memory=True,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=8,
        shuffle=False,
        num_workers=2,
        pin_memory=True,
    )

    model = ConvNeXtMultiTask(pretrained=True).to(device)

    mse_loss_fn = nn.MSELoss()
    ce_loss_fn = nn.CrossEntropyLoss()

    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)

    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=0.5,
        patience=2,
    )

    num_epochs = 10
    best_val_loss = float("inf")
    best_val_mae = float("inf")
    best_clinical_accuracy = 0.0

    for epoch in range(num_epochs):
        train_metrics = train_one_epoch(
            model=model,
            train_loader=train_loader,
            mse_loss_fn=mse_loss_fn,
            ce_loss_fn=ce_loss_fn,
            optimizer=optimizer,
            device=device,
        )

        val_metrics = validate(
            model=model,
            val_loader=val_loader,
            mse_loss_fn=mse_loss_fn,
            ce_loss_fn=ce_loss_fn,
            device=device,
        )

        scheduler.step(val_metrics["loss"])

        current_lr = optimizer.param_groups[0]["lr"]

        print(f"Epoch {epoch + 1}/{num_epochs}")
        print(f"Train loss:              {train_metrics['loss']:.4f}")
        print(f"Train score loss:        {train_metrics['score_loss']:.4f}")
        print(f"Train clinical loss:     {train_metrics['clinical_loss']:.4f}")
        print(f"Train uncertainty loss:  {train_metrics['uncertainty_loss']:.4f}")
        print(f"Val loss:                {val_metrics['loss']:.4f}")
        print(f"Val score loss:          {val_metrics['score_loss']:.4f}")
        print(f"Val clinical loss:       {val_metrics['clinical_loss']:.4f}")
        print(f"Val uncertainty loss:    {val_metrics['uncertainty_loss']:.4f}")
        print(f"Val MAE:                 {val_metrics['mae']:.4f}")
        print(f"Val clinical accuracy:   {val_metrics['clinical_accuracy']:.4f}")
        print(f"Learning rate:           {current_lr:.6f}")

        if val_metrics["loss"] < best_val_loss:
            best_val_loss = val_metrics["loss"]

            checkpoint_path = checkpoint_dir / "convnext_multitask_best.pt"

            torch.save(
                {
                    "epoch": epoch + 1,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "best_val_loss": best_val_loss,
                    "val_metrics": val_metrics,
                },
                checkpoint_path,
            )

            print(f"Saved best checkpoint to: {checkpoint_path}")

        if val_metrics["mae"] < best_val_mae:
            best_val_mae = val_metrics["mae"]

            checkpoint_path = checkpoint_dir / "convnext_multitask_best_mae.pt"

            torch.save(
                {
                    "epoch": epoch + 1,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "best_val_mae": best_val_mae,
                    "val_metrics": val_metrics,
                },
                checkpoint_path,
            )

            print(f"Saved best MAE checkpoint to: {checkpoint_path}")

        if val_metrics["clinical_accuracy"] > best_clinical_accuracy:
            best_clinical_accuracy = val_metrics["clinical_accuracy"]

            checkpoint_path = checkpoint_dir / "convnext_multitask_best_clinical_accuracy.pt"

            torch.save(
                {
                    "epoch": epoch + 1,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "best_clinical_accuracy": best_clinical_accuracy,
                    "val_metrics": val_metrics,
                },
                checkpoint_path,
            )

            print(f"Saved best clinical accuracy checkpoint to: {checkpoint_path}")

        print("-" * 50)


if __name__ == "__main__":
    main()