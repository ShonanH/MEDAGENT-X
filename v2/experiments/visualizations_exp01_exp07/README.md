# MEDAGENT-X Experiment 1–7 Visualization Pack

## Interpretation notes

- Full-test experiment bars use each experiment's final prediction run.
- Experiment 6 aliases Experiment 4 because its evidence verifier does not modify labels.
- Experiment 7 evidence plots describe verification quality; a Judge score is not available.
- ROC/PR curves describe continuous RAD-DINO probabilities, not hard-status fusion outputs.
- Confusion matrices follow the repository's Judge policy and therefore cover only scoreable cells.

## Artifact availability

- Experiment 3: No independent Experiment 3 Judge artifact is retained in this workspace.
- Experiment 7: Evidence artifacts exist, but no completed Judge summary is retained.
- Evidence checkpoint mixes verification policies: llm_evidence_verification_review_v1=491, evidence_verification_policy_v1=415. Aggregate evidence plots must be interpreted as descriptive, not as a clean policy comparison.
- Evidence source: `/Users/shonanhendre/Desktop/MEDAGENT-X/v2/experiments/exp07_llm_fusion_evidence_verification_graph/qwen3_14b/.ipynb_checkpoints/evidence_verification-checkpoint.json`

## Generated figures

1. `01_experiment_metric_comparison.png`: macro precision/recall/F1 and micro F1.
2. `02_macro_f1_progression.png`: headline score progression.
3. `03_per_label_f1_heatmap.png`: label-wise strengths and weaknesses.
4. `04_per_label_f1_delta_vs_exp01.png`: where each experiment helps or hurts.
5. `05_experiment_confusion_matrices.png`: aggregate error counts.
6. `06_best_experiment_label_diagnostics.png`: Experiment 5 label F1 and precision/recall.
7. `07_roc_curves_*.png`: strict and conventional ROC variants.
8. `08_pr_curves_*.png`: recommended for the imbalanced label setting.
9. `09_evidence_verification_dashboard.png`: study and label evidence distributions.
10. `10_evidence_label_risk_map.png`: labels combining intervention, gray-zone, and contradiction risk.
11. `11_evidence_policy_provenance.png`: policy counts and score distributions; provenance audit only.

## ROC/PR policies

- Strict Judge-compatible curves include 7 labels with at least five explicit-positive and five explicit-negative examples; sparse or single-class labels are omitted.
- Present-vs-not-present curves treat absent, uncertain, and unmentioned as negative; use these for conventional discrimination analysis, not as a reproduction of Judge F1.

## Headline metrics used

| Experiment | Run | Macro F1 | Micro F1 |
|---:|---|---:|---:|
| 1 | Vision only | 0.6971 | 0.7042 |
| 2 | Fusion, no retrieval | 0.6126 | 0.6240 |
| 4 | Deterministic retrieval fusion | 0.7246 | 0.7383 |
| 5 | LLM retrieval fusion (Llama) | 0.7257 | 0.7389 |
| 6 | Deterministic fusion + evidence | 0.7246 | 0.7383 |
