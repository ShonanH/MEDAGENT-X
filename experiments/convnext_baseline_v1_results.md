# ConvNeXt-Tiny Baseline v1 Results

## Objective

- Establish a first supervised image quality assessment baseline for MEDAGENT-X.
- Predict CT image quality score from LDCTIQAC2023 validation images.
- Use this baseline as the comparison point before building the multi-task and agentic versions.

## Dataset

- Dataset: LDCTIQAC2023 training dataset
- Total labeled images: 1000
- Training split: 800 images
- Validation split: 200 images
- Image format: `.tif`
- Image size before preprocessing: `512 x 512`
- Raw dataset score range: `0.0` to `4.0`
- MEDAGENT-X score range: `1.0` to `5.0`

## Label Mapping

- MEDAGENT-X quality score:

```text
quality_score = raw_score + 1.0
```

- Clinical level mapping from quality score:

| Quality Score Range | Clinical Level | Label                 |
| ------------------: | -------------: | --------------------- |
|         1.0 to <1.5 |              1 | Non-diagnostic        |
|         1.5 to <2.5 |              2 | Limited               |
|         2.5 to <3.5 |              3 | Adequate with caution |
|         3.5 to <4.5 |              4 | Good                  |
|          4.5 to 5.0 |              5 | Excellent             |

## Model

- Backbone: ConvNeXt-Tiny
- Pretraining: ImageNet pretrained
- Task: score regression
- Input shape after preprocessing: `3 x 224 x 224`
- Output: one continuous quality score
- Output scale: `1.0` to `5.0` after clamping during evaluation/export

## Preprocessing

- Load grayscale `.tif` CT image.
- Convert image to tensor.
- Repeat grayscale channel into 3 channels for ConvNeXt compatibility.
- Resize image to `224 x 224`.
- Normalize using ImageNet mean and standard deviation.

## Training Setup

- Loss function: `MSELoss`
- Optimizer: `AdamW`
- Initial learning rate: `1e-4`
- Scheduler: `ReduceLROnPlateau`
- Scheduler factor: `0.5`
- Scheduler patience: `2`
- Batch size: `8`
- Epochs: `10`
- Device: CUDA GPU
- Best checkpoint saved by validation loss.

## Training Log Summary

| Epoch | Train Loss | Validation Loss | Validation MAE | Learning Rate |
| ----: | ---------: | --------------: | -------------: | ------------: |
|     1 |     0.4750 |          0.0929 |         0.2418 |      0.000100 |
|     2 |     0.0873 |          0.2450 |         0.4353 |      0.000100 |
|     3 |     0.0892 |          0.0930 |         0.2527 |      0.000100 |
|     4 |     0.0560 |          0.0533 |         0.1849 |      0.000100 |
|     5 |     0.0574 |          0.0473 |         0.1693 |      0.000100 |
|     6 |     0.0355 |          0.0448 |         0.1699 |      0.000100 |
|     7 |     0.0363 |          0.0488 |         0.1757 |      0.000100 |
|     8 |     0.0301 |          0.0464 |         0.1702 |      0.000100 |
|     9 |     0.0255 |          0.0449 |         0.1649 |      0.000050 |
|    10 |     0.0168 |          0.0509 |         0.1802 |      0.000050 |

## Best Validation Metrics

| Metric |  Value |
| ------ | -----: |
| MAE    | 0.1689 |
| RMSE   | 0.2106 |
| PLCC   | 0.9799 |
| SRCC   | 0.9810 |

## Clinical-Level Confusion Matrix

- Rows are true clinical levels.
- Columns are predicted clinical levels.
- Diagonal values are correct clinical-level predictions.
- Above-diagonal values are overestimation errors.
- Below-diagonal values are underestimation errors.

| True \ Predicted |   1 |   2 |   3 |   4 |   5 |
| ---------------: | --: | --: | --: | --: | --: |
|                1 |   9 |   1 |   0 |   0 |   0 |
|                2 |   0 |  38 |   3 |   0 |   0 |
|                3 |   0 |   4 |  54 |   6 |   0 |
|                4 |   0 |   0 |   2 |  54 |   3 |
|                5 |   0 |   0 |   0 |   5 |  21 |

## Error By True Clinical Level

| True Clinical Level | Count | Mean Absolute Error | Max Absolute Error |
| ------------------: | ----: | ------------------: | -----------------: |
|                   1 |    10 |              0.1899 |             0.3640 |
|                   2 |    41 |              0.1870 |             0.5606 |
|                   3 |    64 |              0.1849 |             0.5330 |
|                   4 |    59 |              0.1342 |             0.4161 |
|                   5 |    26 |              0.1719 |             0.5304 |

## Interpretation

- The baseline performs strongly on the validation split.
- The average validation error is about `0.17` points on the `1-5` quality scale.
- PLCC and SRCC are both high, suggesting the model captures both score magnitude and ranking well.
- Most clinical-level predictions are on the diagonal of the confusion matrix.
- The most important safety errors are overestimations, because MEDAGENT-X is intended to act as a safety gate before diagnosis.

## Known Limitations

- This is validation performance from a split of the official training dataset.
- Official test-set evaluation has not been run yet.
- This model predicts only the quality score.
- It does not yet predict artifact labels, uncertainty, or full clinical recommendations.
- The clinical-level output is derived from the predicted score, not trained directly as a classification task.
- ImageNet normalization was used because the backbone is ImageNet pretrained; CT-specific normalization should be tested later.

## Saved Artifacts

- Best checkpoint:

```text
experiments/checkpoints/convnext_baseline_best.pt
```

- Prediction export:

```text
experiments/predictions/convnext_baseline_val_predictions.csv
```

- Error analysis:

```text
experiments/predictions/worst_20_predictions.csv
experiments/predictions/clinical_level_error_summary.csv
experiments/predictions/clinical_level_confusion_matrix.csv
```

- Figure:

```text
experiments/figures/clinical_level_confusion_matrix.png
```

## Next Step

- Move to Phase 6: multi-task model.
- Add explicit clinical usability classification.
- Add uncertainty estimation.
- Keep artifact prediction as a later step unless weak labels or expert annotations are created.
