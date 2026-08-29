# MEDAGENT-X v2 Experiment Results So Far

Generated from the current artifacts in `v2/experiments/`.

## Evaluation Setup

- Study count: 906 test studies
- Disease labels: 12 CheXpert disease labels
- Total study-label cells: 10,872
- Gray-zone margin: 0.15
- Gray-zone cells: 1,812
- Ground truth source: `v2/artifactsLocal/val_last4_blocks_0818/val/study_label_table.csv`
- Judge metric policy: `judge_metric_policy_v1`

## Judge Policy Summary

The Judge evaluates predictions against frozen CheXpert-derived study labels.

| Ground Truth | Prediction | Outcome | Binary Scored |
|---|---|---:|---:|
| present | present | TP | yes |
| present | absent | FN | yes |
| present | uncertain | miss_uncertain | yes, hurts recall |
| absent | present | FP | yes |
| absent | absent | TN | yes |
| absent | uncertain | unresolved | no |
| uncertain | any prediction | unresolved | no |
| unmentioned | any prediction | unresolved | no |

Metric formulas:

```text
precision = TP / (TP + FP)
recall    = TP / (TP + FN + miss_uncertain)
F1        = 2 * precision * recall / (precision + recall)
coverage  = scored cells / total cells
```

This means `uncertain` is not a free abstention. It helps avoid false positives for ground-truth absent cells, but it is penalized as `miss_uncertain` for ground-truth present cells.

## Experiment 1: RAD-DINO Vision Only

Folder:

```text
v2/experiments/exp01_vision_only/
```

Description:

```text
RAD-DINO vision backbone only.
No retrieval.
No label fusion.
No evidence verification.
```

### Results

| Scope | Macro F1 | Macro Precision | Macro Recall | Micro F1 | Micro Precision | Micro Recall | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full test set | 0.6971 | 0.9108 | 0.5695 | 0.7042 | 0.9076 | 0.5753 | 0.1494 |
| Gray-zone slice | 0.6310 | 0.8748 | 0.5090 | 0.6417 | 0.8405 | 0.5189 | 0.1849 |

### Interpretation

The vision-only model is precision-heavy. When it predicts a label as present, it is usually correct, but recall is materially lower. The model misses a meaningful number of positive findings.

Headline result:

```text
Macro F1:        0.6971
Macro precision: 0.9108
Macro recall:    0.5695
```

## Experiment 3: Fusion Without Retrieval

Folder:

```text
v2/experiments/exp03_fusion_no_retrieval/
```

Current policy:

```text
gray_zone_uncertainty_no_retrieval_v1
```

Description:

```text
Use RAD-DINO predictions as input.
Do not retrieve similar cases.
If a label is outside the gray zone, keep the RAD-DINO status.
If a label is inside the gray zone, set fused_status = uncertain.
```

This is a no-retrieval uncertainty/abstention experiment, not the production retrieval-fusion policy.

### Change Summary

| Quantity | Count |
|---|---:|
| Total label cells | 10,872 |
| Strong-zone cells kept as vision | 9,060 |
| Gray-zone cells changed to uncertain | 1,812 |
| Retrieval positive mentions | 0 |
| Retrieval negative mentions | 0 |

Final fused status counts:

| Fused Status | Count |
|---|---:|
| absent | 7,199 |
| present | 1,861 |
| uncertain | 1,812 |

### Results

| Scope | Run | Macro F1 | Macro Precision | Macro Recall | Micro F1 | Micro Precision | Micro Recall | Coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Full test set | Vision baseline | 0.6971 | 0.9108 | 0.5695 | 0.7042 | 0.9076 | 0.5753 | 0.1494 |
| Full test set | Fusion no retrieval | 0.6126 | 0.9241 | 0.4619 | 0.6240 | 0.9239 | 0.4711 | 0.1428 |
| Gray-zone slice | Vision baseline | 0.6310 | 0.8748 | 0.5090 | 0.6417 | 0.8405 | 0.5189 | 0.1849 |
| Gray-zone slice | Fusion no retrieval | null | null | 0.0000 | null | null | 0.0000 | 0.1457 |

### Per-Label Gray-Zone Changes

| Label | Gray-Zone Cells | Changed Cells | Net TP Change | Net FP Change | Net FN Change |
|---|---:|---:|---:|---:|---:|
| Atelectasis | 124 | 124 | -10 | 0 | 10 |
| Cardiomegaly | 126 | 126 | -15 | -4 | 15 |
| Consolidation | 157 | 157 | -14 | -4 | 14 |
| Edema | 142 | 142 | -8 | 0 | 8 |
| Enlarged Cardiomediastinum | 145 | 145 | -4 | -1 | 4 |
| Fracture | 174 | 174 | -9 | -1 | 9 |
| Lung Lesion | 136 | 136 | -5 | 0 | 5 |
| Lung Opacity | 165 | 165 | -26 | 0 | 26 |
| Pleural Effusion | 129 | 129 | -22 | -3 | 22 |
| Pleural Other | 135 | 135 | -8 | 0 | 8 |
| Pneumonia | 220 | 220 | -9 | 0 | 9 |
| Pneumothorax | 159 | 159 | -7 | -13 | 7 |

### Interpretation

Marking all gray-zone labels as `uncertain` made the model more conservative:

- Macro precision increased from 0.9108 to 0.9241.
- Macro recall decreased from 0.5695 to 0.4619.
- Macro F1 decreased from 0.6971 to 0.6126.
- Coverage decreased from 0.1494 to 0.1428.

The precision improvement comes from avoiding some false positives. The recall and F1 drop happens because the Judge counts `GT present + predicted uncertain` as `miss_uncertain`, which hurts recall.

This experiment shows that gray-zone abstention without retrieval is too conservative under the current Judge scoring policy. It may still be useful as a clinical uncertainty signal, but it is worse than vision-only on binary F1.

## Current Takeaways

1. RAD-DINO alone is the current F1 baseline: macro F1 0.6971.
2. No-retrieval gray-zone uncertainty fusion improves precision slightly but substantially lowers recall.
3. The main opportunity is still Experiment 4: retrieval-backed fusion, where gray-zone decisions can be changed using report evidence instead of blanket uncertainty.

