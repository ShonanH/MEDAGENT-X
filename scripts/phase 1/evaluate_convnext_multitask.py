import csv
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error
from torch.utils.data import DataLoader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.medagentx.models.convnext_multitask import ConvNeXtMultiTask
from data.ldctiqac2023 import LDCTIQAC2023Dataset
from data.transforms import ConvNeXtDataPreprocess


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


def plot_confusion_matrix(confusion_matrix, output_path):
    level_labels = [
        "1\nNon-diagnostic",
        "2\nLimited",
        "3\nAdequate",
        "4\nGood",
        "5\nExcellent",
    ]

    fig, ax = plt.subplots(figsize=(8, 7))

    image = ax.imshow(confusion_matrix.values, cmap="Blues")

    ax.set_title("ConvNeXt Multi-Task Clinical Level Confusion Matrix")
    ax.set_xlabel("Predicted Clinical Level")
    ax.set_ylabel("True Clinical Level")

    ax.set_xticks(range(len(level_labels)))
    ax.set_yticks(range(len(level_labels)))

    ax.set_xticklabels(level_labels)
    ax.set_yticklabels(level_labels)

    plt.setp(
        ax.get_xticklabels(),
        rotation=30,
        ha="right",
        rotation_mode="anchor",
    )

    max_value = confusion_matrix.values.max()

    for row_idx in range(confusion_matrix.shape[0]):
        for col_idx in range(confusion_matrix.shape[1]):
            value = confusion_matrix.values[row_idx, col_idx]
            text_color = "white" if value > max_value / 2 else "black"

            ax.text(
                col_idx,
                row_idx,
                str(value),
                ha="center",
                va="center",
                color=text_color,
                fontsize=11,
                fontweight="bold",
            )

    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def main():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available. This script is intended for GPU evaluation.")

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
        / "convnext_multitask_best_loss.pt"
        # / "convnext_multitask_best_mae.pt"
        # / "convnext_multitask_best_clinical_accuracy.pt"
    )

    prediction_dir = PROJECT_ROOT / "experiments" / "predictions"
    figure_dir = PROJECT_ROOT / "experiments" / "figures"

    prediction_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    prediction_path = prediction_dir / "convnext_multitask_val_predictions.csv"
    confusion_matrix_path = prediction_dir / "convnext_multitask_confusion_matrix.csv"
    confusion_matrix_figure_path = figure_dir / "convnext_multitask_confusion_matrix.png"

    transform = ConvNeXtDataPreprocess(image_size=224)

    val_dataset = LDCTIQAC2023Dataset(
        image_dir=image_dir,
        label_path=val_label_path,
        transform=transform,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=8,
        shuffle=False,
        num_workers=2,
        pin_memory=True,
    )

    model = ConvNeXtMultiTask(pretrained=False).to(device)

    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    rows = []

    true_quality_scores_all = []
    predicted_quality_scores_all = []

    correct_clinical = 0
    total_samples = 0

    with torch.no_grad():
        for batch in val_loader:
            images = batch["image"].to(device)
            filenames = batch["filename"]

            true_quality_scores = batch["quality_score"]
            true_clinical_levels = batch["clinical_level"]

            outputs = model(images)

            predicted_quality_scores = outputs["quality_score"].clamp(1.0, 5.0).cpu()

            predicted_classes = torch.argmax(
                outputs["clinical_logits"],
                dim=1,
            ).cpu()

            predicted_clinical_levels = predicted_classes + 1

            uncertainty_scores = outputs["uncertainty"].cpu()

            for (
                filename,
                true_score,
                predicted_score,
                true_level,
                predicted_level,
                uncertainty_score,
            ) in zip(
                filenames,
                true_quality_scores,
                predicted_quality_scores,
                true_clinical_levels,
                predicted_clinical_levels,
                uncertainty_scores,
            ):
                true_score = float(true_score.item())
                predicted_score = float(predicted_score.item())
                true_level = int(true_level.item())
                predicted_level = int(predicted_level.item())
                uncertainty_score = float(uncertainty_score.item())

                absolute_error = abs(predicted_score - true_score)

                true_quality_scores_all.append(true_score)
                predicted_quality_scores_all.append(predicted_score)

                if predicted_level == true_level:
                    correct_clinical += 1

                total_samples += 1

                rows.append(
                    {
                        "filename": filename,
                        "true_quality_score": round(true_score, 4),
                        "predicted_quality_score": round(predicted_score, 4),
                        "absolute_error": round(absolute_error, 4),
                        "true_clinical_level": true_level,
                        "predicted_clinical_level": predicted_level,
                        "uncertainty": round(uncertainty_score, 4),
                    }
                )

    true_quality_scores_all = np.array(true_quality_scores_all)
    predicted_quality_scores_all = np.array(predicted_quality_scores_all)

    mae = mean_absolute_error(true_quality_scores_all, predicted_quality_scores_all)
    rmse = mean_squared_error(true_quality_scores_all, predicted_quality_scores_all) ** 0.5
    plcc = pearsonr(true_quality_scores_all, predicted_quality_scores_all).statistic
    srcc = spearmanr(true_quality_scores_all, predicted_quality_scores_all).statistic
    clinical_accuracy = correct_clinical / total_samples

    with open(prediction_path, "w", newline="") as f:
        fieldnames = [
            "filename",
            "true_quality_score",
            "predicted_quality_score",
            "absolute_error",
            "true_clinical_level",
            "predicted_clinical_level",
            "uncertainty",
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    predictions_df = pd.DataFrame(rows)

    levels = [1, 2, 3, 4, 5]

    confusion_matrix = pd.crosstab(
        predictions_df["true_clinical_level"],
        predictions_df["predicted_clinical_level"],
        rownames=["True Level"],
        colnames=["Predicted Level"],
    )

    confusion_matrix = confusion_matrix.reindex(
        index=levels,
        columns=levels,
        fill_value=0,
    )

    confusion_matrix.to_csv(confusion_matrix_path)
    plot_confusion_matrix(confusion_matrix, confusion_matrix_figure_path)

    print("ConvNeXt Multi-Task Validation Metrics")
    print(f"MAE:               {mae:.4f}")
    print(f"RMSE:              {rmse:.4f}")
    print(f"PLCC:              {plcc:.4f}")
    print(f"SRCC:              {srcc:.4f}")
    print(f"Clinical accuracy: {clinical_accuracy:.4f}")
    print(f"Saved predictions to: {prediction_path}")
    print(f"Saved confusion matrix to: {confusion_matrix_path}")
    print(f"Saved confusion matrix figure to: {confusion_matrix_figure_path}")


if __name__ == "__main__":
    main()