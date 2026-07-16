# Batch Calibration Metrics

- Batch dir: `outputs/chexpert_plus/batch_first_100`
- Cases: 100
- Disease label rows: 1200

## Workflow disease F1
- Mean disease F1: **0.4128**
- Mean disease precision: 0.4457
- Mean disease recall: 0.6913
- Judge decisions: concordant=16, partial=45, discordant=39

## Pooled probability calibration (binary GT: present=1, absent=0)
- **Ensemble:** n=1170, RMSE=0.5231, PLCC=0.3266, SRCC=0.3500
- **DenseNet:** n=1170, RMSE=0.4606, PLCC=0.2548, SRCC=0.2719
- **Fusion:** n=1170, RMSE=0.6940, PLCC=0.2623, SRCC=0.3678

## Baselines (binary GT)
- **Always predict 0:** n=1170, RMSE=0.3422, PLCC=n/a, SRCC=n/a
- **Always predict prevalence:** n=1170, RMSE=0.3215, PLCC=n/a, SRCC=n/a

## Ordinal GT (present=1, uncertain=0.5, absent=0)
- **Ensemble:** n=1200, RMSE=0.5181, PLCC=0.3272, SRCC=0.3504

## Per-label ensemble vs binary GT

| Label | n | RMSE | PLCC | SRCC |
|---|---:|---:|---:|---:|
| Atelectasis | 90 | 0.610 | 0.333 | 0.386 |
| Cardiomegaly | 100 | 0.458 | 0.209 | 0.218 |
| Consolidation | 96 | 0.545 | 0.314 | 0.296 |
| Edema | 98 | 0.453 | 0.503 | 0.501 |
| Pleural Effusion | 92 | 0.527 | 0.452 | 0.475 |
| Pneumonia | 99 | 0.529 | n/a | n/a |
| Pneumothorax | 99 | 0.272 | 0.772 | 0.581 |
| Fracture | 100 | 0.610 | 0.031 | -0.018 |
| Lung Lesion | 98 | 0.499 | 0.036 | 0.056 |
| Lung Opacity | 98 | 0.592 | 0.250 | 0.235 |
| Enlarged Cardiomediastinum | 100 | 0.565 | 0.102 | 0.144 |
| Pleural Other | 100 | 0.536 | -0.223 | -0.223 |

## Notes
- RMSE below the always-zero / prevalence baselines indicates better probability calibration.
- Disease F1 is the primary workflow metric; correlation metrics measure probability ranking/calibration only.
