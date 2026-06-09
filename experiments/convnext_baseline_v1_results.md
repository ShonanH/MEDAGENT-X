# ConvNeXt-Tiny Baseline v1 Results

## Dataset

- Dataset: LDCTIQAC2023 training set
- Train split: 800 images
- Validation split: 200 images
- Score target: MEDAGENT-X quality score, 1-5 scale

## Model

- Backbone: ConvNeXt-Tiny
- Pretraining: ImageNet pretrained
- Input: 3 x 224 x 224
- Output: single quality score
- Loss: MSELoss
- Optimizer: AdamW
- Learning rate: 1e-4
- Scheduler: ReduceLROnPlateau
- Epochs: 10

## Best Validation Metrics

- MAE: 0.1689
- RMSE: 0.2106
- PLCC: 0.9799
- SRCC: 0.9810

## Notes

- This is a validation result from a split of the official training data.
- Official test set evaluation has not been run yet.
- This model is a score-regression baseline only.
- It does not yet predict clinical level, artifacts, uncertainty, or recommendations.
