# Conservative Promotion Thresholds

This validation-only experiment simulates stricter absent-to-present promotion thresholds from saved last-4 fusion outputs.

Source: `v2/artifacts/cohort_balanced_v1/reasoning/fusion_eval_v1/val_last4_blocks_0818/val`
Selected variant: `baseline`

Variants:

- `baseline`: existing fused statuses.
- `global-positive-threshold-4`: revert current promotions with fewer than 4 positive mentions.
- `global-positive-threshold-5`: revert current promotions with fewer than 5 positive mentions.
- `label-specific-conservative`: use label-specific thresholds from `selected-policy.json`.

Demotions are intentionally unchanged in this experiment.
Strong-zone predictions are unchanged because only current promotions are eligible for reversion.


The conservative-threshold experiment ran successfully and produced the expected outputs.
Selected Variant
selected-policy.json chose:
baseline
So the current promotion threshold policy (>=3 positive mentions) remains best under the script’s selection criteria.
Metric Tradeoff
Baseline:
Full macro F1: 0.7713
Gray-zone macro F1: 0.8355
global-positive-threshold-4:
Full macro F1: 0.7683 (-0.0029)
Gray-zone macro F1: 0.8240 (-0.0115)
global-positive-threshold-5:
Full macro F1: 0.7625 (-0.0088)
Gray-zone macro F1: 0.8023 (-0.0332)
label-specific-conservative:
Full macro F1: 0.7691 (-0.0021)
Gray-zone macro F1: 0.8265 (-0.0091)
Interpretation
Conservative thresholds reduced promotions, but they mostly removed useful recall. The false-positive count was already low: baseline kept 288 promotions with 41 scored TPs, 5 scored FPs, and 242 unscored. Raising to threshold 4 reverted 45 promotions, including 4 true positives and 0 false positives, so it harmed recall without improving scored precision.
For Experiment 1, the result is: do not globally tighten promotion thresholds yet; keep baseline promotion threshold behavior.