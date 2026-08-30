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

| Ground Truth | Prediction     |        Outcome |     Binary Scored |
| ------------ | -------------- | -------------: | ----------------: |
| present      | present        |             TP |               yes |
| present      | absent         |             FN |               yes |
| present      | uncertain      | miss_uncertain | yes, hurts recall |
| absent       | present        |             FP |               yes |
| absent       | absent         |             TN |               yes |
| absent       | uncertain      |     unresolved |                no |
| uncertain    | any prediction |     unresolved |                no |
| unmentioned  | any prediction |     unresolved |                no |

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

| Scope           | Macro F1 | Macro Precision | Macro Recall | Micro F1 | Micro Precision | Micro Recall | Coverage |
| --------------- | -------: | --------------: | -----------: | -------: | --------------: | -----------: | -------: |
| Full test set   |   0.6971 |          0.9108 |       0.5695 |   0.7042 |          0.9076 |       0.5753 |   0.1494 |
| Gray-zone slice |   0.6310 |          0.8748 |       0.5090 |   0.6417 |          0.8405 |       0.5189 |   0.1849 |

### Interpretation

The vision-only model is precision-heavy. When it predicts a label as present, it is usually correct, but recall is materially lower. The model misses a meaningful number of positive findings.

Headline result:

```text
Macro F1:        0.6971
Macro precision: 0.9108
Macro recall:    0.5695
```

## Experiment 2: Fusion Without Retrieval

Folder:

```text
v2/experiments/exp02_fusion_no_retrieval/
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

| Quantity                             |  Count |
| ------------------------------------ | -----: |
| Total label cells                    | 10,872 |
| Strong-zone cells kept as vision     |  9,060 |
| Gray-zone cells changed to uncertain |  1,812 |
| Retrieval positive mentions          |      0 |
| Retrieval negative mentions          |      0 |

Final fused status counts:

| Fused Status | Count |
| ------------ | ----: |
| absent       | 7,199 |
| present      | 1,861 |
| uncertain    | 1,812 |

### Results

| Scope           | Run                 | Macro F1 | Macro Precision | Macro Recall | Micro F1 | Micro Precision | Micro Recall | Coverage |
| --------------- | ------------------- | -------: | --------------: | -----------: | -------: | --------------: | -----------: | -------: |
| Full test set   | Vision baseline     |   0.6971 |          0.9108 |       0.5695 |   0.7042 |          0.9076 |       0.5753 |   0.1494 |
| Full test set   | Fusion no retrieval |   0.6126 |          0.9241 |       0.4619 |   0.6240 |          0.9239 |       0.4711 |   0.1428 |
| Gray-zone slice | Vision baseline     |   0.6310 |          0.8748 |       0.5090 |   0.6417 |          0.8405 |       0.5189 |   0.1849 |
| Gray-zone slice | Fusion no retrieval |     null |            null |       0.0000 |     null |            null |       0.0000 |   0.1457 |

### Per-Label Gray-Zone Changes

| Label                      | Gray-Zone Cells | Changed Cells | Net TP Change | Net FP Change | Net FN Change |
| -------------------------- | --------------: | ------------: | ------------: | ------------: | ------------: |
| Atelectasis                |             124 |           124 |           -10 |             0 |            10 |
| Cardiomegaly               |             126 |           126 |           -15 |            -4 |            15 |
| Consolidation              |             157 |           157 |           -14 |            -4 |            14 |
| Edema                      |             142 |           142 |            -8 |             0 |             8 |
| Enlarged Cardiomediastinum |             145 |           145 |            -4 |            -1 |             4 |
| Fracture                   |             174 |           174 |            -9 |            -1 |             9 |
| Lung Lesion                |             136 |           136 |            -5 |             0 |             5 |
| Lung Opacity               |             165 |           165 |           -26 |             0 |            26 |
| Pleural Effusion           |             129 |           129 |           -22 |            -3 |            22 |
| Pleural Other              |             135 |           135 |            -8 |             0 |             8 |
| Pneumonia                  |             220 |           220 |            -9 |             0 |             9 |
| Pneumothorax               |             159 |           159 |            -7 |           -13 |             7 |

### Interpretation

Marking all gray-zone labels as `uncertain` made the model more conservative:

- Macro precision increased from 0.9108 to 0.9241.
- Macro recall decreased from 0.5695 to 0.4619.
- Macro F1 decreased from 0.6971 to 0.6126.
- Coverage decreased from 0.1494 to 0.1428.

The precision improvement comes from avoiding some false positives. The recall and F1 drop happens because the Judge counts `GT present + predicted uncertain` as `miss_uncertain`, which hurts recall.

This experiment shows that gray-zone abstention without retrieval is too conservative under the current Judge scoring policy. It may still be useful as a clinical uncertainty signal, but it is worse than vision-only on binary F1.

## Experiment 4: Fusion With Retrieval

Folder:

```text
v2/experiments/exp04_fusion_with_retrieval/
```

Policy:

```text
deterministic_gray_zone_fusion_v2
```

Description:

```text
Run RAD-DINO vision inference.
Retrieve top-10 similar train studies using the RAD-DINO image embedding.
Apply deterministic gray-zone label fusion using retrieved report mentions.
Evaluate vision-only and fused labels with Judge.
```

This experiment does not use an LLM.

### Change Summary

| Quantity                    |  Count |
| --------------------------- | -----: |
| Total label cells           | 10,872 |
| Gray-zone cells             |  1,812 |
| Changed cells               |    390 |
| Promotions                  |    374 |
| Demotions                   |     16 |
| Retrieval positive mentions | 33,965 |
| Retrieval negative mentions |  3,849 |

Final fused status counts:

| Fused Status | Count |
| ------------ | ----: |
| absent       | 7,881 |
| present      | 2,975 |
| uncertain    |    16 |

### Results

| Scope           | Run                   | Macro F1 | Macro Precision | Macro Recall | Micro F1 | Micro Precision | Micro Recall | Coverage |
| --------------- | --------------------- | -------: | --------------: | -----------: | -------: | --------------: | -----------: | -------: |
| Full test set   | Vision baseline       |   0.6971 |          0.9108 |       0.5695 |   0.7042 |          0.9076 |       0.5753 |   0.1494 |
| Full test set   | Fusion with retrieval |   0.7246 |          0.9117 |       0.6051 |   0.7383 |          0.9136 |       0.6195 |   0.1491 |
| Gray-zone slice | Vision baseline       |   0.6310 |          0.8748 |       0.5090 |   0.6417 |          0.8405 |       0.5189 |   0.1849 |
| Gray-zone slice | Fusion with retrieval |   0.7613 |          0.8773 |       0.6950 |   0.8041 |          0.8824 |       0.7386 |   0.1832 |

### Deltas Versus Vision Baseline

| Scope           | Macro F1 Delta | Macro Precision Delta | Macro Recall Delta | Micro F1 Delta | Micro Precision Delta | Micro Recall Delta |
| --------------- | -------------: | --------------------: | -----------------: | -------------: | --------------------: | -----------------: |
| Full test set   |        +0.0275 |               +0.0009 |            +0.0356 |        +0.0341 |               +0.0060 |            +0.0441 |
| Gray-zone slice |        +0.1303 |               +0.0025 |            +0.1860 |        +0.1624 |               +0.0419 |            +0.2197 |

### Per-Label Fusion Changes

| Label                      | Gray-Zone Cells | Changed Cells | Promotions | Demotions | Net TP Change | Net FP Change | Net FN Change |
| -------------------------- | --------------: | ------------: | ---------: | --------: | ------------: | ------------: | ------------: |
| Atelectasis                |             124 |            55 |         55 |         0 |             7 |             0 |            -7 |
| Cardiomegaly               |             126 |            25 |         25 |         0 |             4 |             1 |            -4 |
| Consolidation              |             157 |            51 |         47 |         4 |             3 |             0 |            -3 |
| Edema                      |             142 |            62 |         62 |         0 |            10 |             0 |           -10 |
| Enlarged Cardiomediastinum |             145 |             0 |          0 |         0 |             0 |             0 |             0 |
| Fracture                   |             174 |            26 |         26 |         0 |             2 |             1 |            -2 |
| Lung Lesion                |             136 |            18 |         18 |         0 |             4 |             0 |            -4 |
| Lung Opacity               |             165 |            63 |         63 |         0 |            13 |             0 |           -13 |
| Pleural Effusion           |             129 |            45 |         45 |         0 |            16 |             1 |           -16 |
| Pleural Other              |             135 |            11 |         10 |         1 |             0 |             0 |             0 |
| Pneumonia                  |             220 |            18 |         18 |         0 |             0 |             0 |             0 |
| Pneumothorax               |             159 |            16 |          5 |        11 |            -1 |            -3 |             1 |

### Interpretation

Retrieval-backed fusion improves the vision baseline on both full-test and gray-zone metrics. The gain is concentrated in the gray-zone slice, which is exactly where the fusion policy is allowed to intervene.

The full-test macro F1 improved from 0.6971 to 0.7246. Macro recall improved from 0.5695 to 0.6051 while macro precision stayed nearly unchanged.

The strongest useful changes came from retrieval-supported promotions. Pleural Effusion, Lung Opacity, Edema, and Atelectasis gained true positives with little or no false-positive cost.

Pneumothorax is the main caution case: fusion reduced false positives, but also lost one true positive and slightly reduced recall/F1 for that label.

## Experiment 6: Deterministic Fusion and Evidence Verification

Folder:

```text
v2/experiments/exp06_deterministic_fusion_evidence_verification/
```

Policies:

```text
fusion_policy_version: deterministic_gray_zone_fusion_v2
verification_policy_version: evidence_verification_policy_v1
```

Description:

```text
Run RAD-DINO vision inference.
Retrieve top-10 similar train studies.
Apply deterministic gray-zone label fusion.
Run deterministic evidence verification over the fused labels.
```

This experiment does not use an LLM.

### Fusion Consistency Check

Experiment 6 reruns the same deterministic fusion stage as Experiment 4. The generated `fusion_label_predictions.csv` was compared against Experiment 4 on the core columns:

```text
study_key
label
vision_status
fused_status
in_gray_zone
positive_count
negative_count
```

Result:

```text
Experiment 4 fusion rows: 10,872
Experiment 6 fusion rows: 10,872
Core fusion mismatches: 0
Fusion changed cells: 390
```

Therefore, Experiment 6 has the same label-level Judge performance as Experiment 4:

| Scope           | Run                                 | Macro F1 | Macro Precision | Macro Recall | Micro F1 | Micro Precision | Micro Recall |
| --------------- | ----------------------------------- | -------: | --------------: | -----------: | -------: | --------------: | -----------: |
| Full test set   | Deterministic fusion with retrieval |   0.7246 |          0.9117 |       0.6051 |   0.7383 |          0.9136 |       0.6195 |
| Gray-zone slice | Deterministic fusion with retrieval |   0.7613 |          0.8773 |       0.6950 |   0.8041 |          0.8824 |       0.7386 |

### Evidence Verification Summary

| Quantity                            | Count |
| ----------------------------------- | ----: |
| Studies                             |   906 |
| Studies with no predicted labels    |   396 |
| Studies with predicted labels       |   510 |
| Positive/uncertain predicted labels | 2,991 |
| Mean predicted labels per study     |  3.30 |
| Max predicted labels per study      |    12 |
| Label evidence detail rows          | 2,991 |
| Fusion-changed label details        |   390 |
| Unchanged label details             | 2,601 |

### Study-Level Evidence Scores

| Overall Evidence Score | Studies |
| ---------------------: | ------: |
|                      1 |     396 |
|                      2 |      15 |
|                      3 |      69 |
|                      4 |     421 |
|                      5 |       5 |

Most studies either had no positive/uncertain predicted labels and received score 1, or had reasonably well-supported predicted labels and received score 4.

### Label-Level Evidence Scores

| Label Evidence Score | Label Details |
| -------------------: | ------------: |
|                    1 |            16 |
|                    2 |           191 |
|                    3 |           745 |
|                    4 |         1,257 |
|                    5 |           782 |

### Retrieval Support Across Predicted Labels

| Retrieval Support | Label Details |
| ----------------- | ------------: |
| strong            |         1,307 |
| moderate          |           900 |
| weak              |           232 |
| none              |           522 |
| mixed             |            14 |
| contradictory     |            16 |

### Vision Support Across Predicted Labels

| Vision Support | Label Details |
| -------------- | ------------: |
| strong         |         1,861 |
| moderate       |           740 |
| weak           |           390 |

The 390 weak-vision labels correspond to the fusion-changed gray-zone labels.

### Contradiction Levels

| Contradiction Level | Label Details |
| ------------------- | ------------: |
| none                |         2,961 |
| weak                |            14 |
| strong              |            16 |

### Evidence Snippets

| Snippet Category                    | Count |
| ----------------------------------- | ----: |
| Studies with supporting snippets    |   503 |
| Studies with contradicting snippets |   281 |
| Supporting snippets total           | 3,467 |
| Contradicting snippets total        |   729 |

### Predicted Labels by Disease

| Label                      | Predicted Label Details |
| -------------------------- | ----------------------: |
| Lung Opacity               |                     384 |
| Pneumonia                  |                     316 |
| Consolidation              |                     299 |
| Pleural Effusion           |                     299 |
| Edema                      |                     279 |
| Atelectasis                |                     248 |
| Fracture                   |                     218 |
| Lung Lesion                |                     214 |
| Enlarged Cardiomediastinum |                     201 |
| Cardiomegaly               |                     197 |
| Pleural Other              |                     180 |
| Pneumothorax               |                     156 |

### Interpretation

Experiment 6 is the full deterministic agentic baseline. It keeps Experiment 4's retrieval-backed fusion behavior unchanged, then adds structured evidence verification.

The evidence verifier provides:

- Overall study-level evidence scores.
- Per-label evidence scores.
- Vision support levels.
- Retrieval support levels.
- Contradiction levels.
- Supporting and contradicting report snippets.
- Human-readable evidence narratives.

Because the evidence verification stage does not modify fused labels, it does not change Judge F1, precision, or recall. Its value is interpretability, auditability, and a baseline for the later LLM evidence-verification experiment.

## Current Takeaways

1. RAD-DINO alone is the current F1 baseline: macro F1 0.6971.
2. No-retrieval gray-zone uncertainty fusion improves precision slightly but substantially lowers recall.
3. Retrieval-backed deterministic fusion is a clear improvement over vision-only: macro F1 0.7246.
4. Deterministic evidence verification does not change labels, but adds study-level and label-level evidence scoring plus retrieved evidence snippets.
5. The next experiment should add LLM capability to both Label Fusion and Evidence Verification, then compare against this deterministic full-agent baseline.
