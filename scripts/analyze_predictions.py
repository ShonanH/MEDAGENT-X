from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from pandas.core.config_init import plotting_backend_doc


PROJECT_ROOT = Path(__file__).resolve().parents[1]

prediction_path = (
    PROJECT_ROOT
    / "experiments"
    / "predictions"
    / "convnext_baseline_val_predictions.csv"
)

output_dir = PROJECT_ROOT / "experiments" / "predictions"
figure_dir = PROJECT_ROOT / "experiments" / "figures"

output_dir.mkdir(parents=True, exist_ok=True)
figure_dir.mkdir(parents=True, exist_ok=True)

def main():
   predictions = pd.read_csv(prediction_path)

   print("Rows Loaded: ", len(predictions))
   print(prediction_path)

   worst_20_predictions = predictions.sort_values(
      by="absolute_error",
      ascending=False,
   ).head(20)

   worst_20_predictions_path = output_dir / "worst_20_predictions.csv"
   worst_20_predictions.to_csv(worst_20_predictions_path, index=False)

   print(f"Saved worst predictions to: {worst_20_predictions_path}")

   error_summary = (
      predictions.groupby("true_clinical_level").agg(
         count=('filename', "count"),
         mean_absolute_error=("absolute_error", "mean"),
         max_absolute_error=("absolute_error", "max"),
         min_absolute_error=("absolute_error", "min"),
      ).reset_index()
   )

   error_summary_path = output_dir / "clinical_level_error_summary.csv"
   error_summary.to_csv(error_summary_path, index=False)

   print(f"Saved error summary to: {error_summary_path}")

   levels = [1,2,3,4,5]
   
   confusion_matrix = pd.crosstab(
      predictions["true_clinical_level"],
      predictions["predicted_clinical_level"],
      rownames=["True Level"],
      colnames=["Predicted Levels"],
   )

   confusion_matrix = confusion_matrix.reindex(
      index = levels,
      columns=levels,
      fill_value=0,
   )

   confusion_matrix_path = output_dir / "clinical_level_confusion_matrix.csv"
   confusion_matrix.to_csv(confusion_matrix_path)

   print(f"Saved confusion matrix to: {confusion_matrix_path}")

   def plot_confusion_matrix(confusion_matrix, output_path):
      level_labels = [
         "1\nNon-diagnostic",
         "2\nLimited",
         "3\nAdequate",
         "4\nGood",
         "5\nExcellent",
      ]

      fig, ax = plt.subplots(figsize=(8,7))

      image = ax.imshow(confusion_matrix.values, cmap="Blues")

      ax.set_title("ConvNeXt Baseline Results Confusion Matrix")
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
               fontweight="bold"
            )

      fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

      fig.tight_layout()
      fig.savefig(output_path, dpi=300)
      plt.close(fig)

      print(f"Saved confusion matrix figure to: {output_path}")

   
if __name__ == "__main__":
   main()
   
