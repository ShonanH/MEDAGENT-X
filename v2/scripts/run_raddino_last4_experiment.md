# RAD-DINO Last-4-Blocks Experiment

Run these commands from the repository root.

```bash
export PYTHONPATH="v2/src${PYTHONPATH:+:${PYTHONPATH}}"
```

## 1. Train Vision Model

```bash
python -m medagentx.cli.train_raddino \
  --cohort-root v2/artifacts/cohort_balanced_v1 \
  --output-root v2/artifacts/cohort_balanced_v1/vision/raddino_finetuned_v1_last4_blocks \
  --loss-name bce \
  --pooling-mode mean_max \
  --selection-metric macro_f1 \
  --trainable-last-blocks 4
```

## 2. Generate Validation Vision Predictions

```bash
python -m medagentx.cli.predict_raddino \
  --cohort-root v2/artifacts/cohort_balanced_v1 \
  --checkpoint v2/artifacts/cohort_balanced_v1/vision/raddino_finetuned_v1_last4_blocks/best_checkpoint.pt \
  --split val \
  --output-csv v2/artifacts/cohort_balanced_v1/reasoning/fusion_eval_v1/last4_blocks/val/vision_study_predictions.csv
```

## 3. Tune Thresholds On Validation

```bash
python -m medagentx.cli.tune_vision_thresholds \
  --cohort-root v2/artifacts/cohort_balanced_v1 \
  --split val \
  --vision-predictions-csv v2/artifacts/cohort_balanced_v1/reasoning/fusion_eval_v1/last4_blocks/val/vision_study_predictions.csv \
  --output-dir v2/artifacts/cohort_balanced_v1/reasoning/fusion_eval_v1/last4_blocks/val/threshold_tuning
```

## 4. Build Matching Retrieval Index

```bash
python -m medagentx.cli.build_retrieval_index \
  --cohort-root v2/artifacts/cohort_balanced_v1 \
  --checkpoint v2/artifacts/cohort_balanced_v1/vision/raddino_finetuned_v1_last4_blocks/best_checkpoint.pt \
  --output-root v2/artifacts/cohort_balanced_v1/retrieval/raddino_train_v1_last4_blocks \
  --rebuild
```

## 5. Run Test Fusion Evaluation

```bash
python -m medagentx.cli.run_fusion_eval \
  --cohort-root v2/artifacts/cohort_balanced_v1 \
  --checkpoint v2/artifacts/cohort_balanced_v1/vision/raddino_finetuned_v1_last4_blocks/best_checkpoint.pt \
  --threshold-policy-json v2/artifacts/cohort_balanced_v1/reasoning/fusion_eval_v1/last4_blocks/val/threshold_tuning/threshold_policy_v2.json \
  --vector-db-dir v2/artifacts/cohort_balanced_v1/retrieval/raddino_train_v1_last4_blocks/chroma \
  --split test \
  --output-dir v2/artifacts/cohort_balanced_v1/reasoning/fusion_eval_v1/last4_blocks/test
```
