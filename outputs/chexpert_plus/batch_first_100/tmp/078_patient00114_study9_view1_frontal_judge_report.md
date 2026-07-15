# MEDAGENT-X Judge Report

## Summary

- Total cases: `1`
- Concordant: `0`
- Partially concordant: `1`
- Discordant: `0`

## Case

- Study key: `patient00114/study9`
- DICOM path: `patient00114/study9/view1_frontal.dcm`
- Judge decision: **PARTIALLY_CONCORDANT**
- Disease F1: `0.500`
- Label macro score: `0.536`

### Explanation

Ground-truth present disease labels predicted uncertain: ['Consolidation'] Critical hallucinated disease labels: ['Lung Opacity'] Disease status mismatches: ['Lung Opacity']

### Ground Truth Present Labels

- Consolidation
- Pleural Effusion

### Predicted Present Labels

- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Consolidation: predicted `uncertain`, ground truth `present`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INCREASING RIGHT LOWER LOBE CONSOLIDATION AND PLEURAL EFFUSION.

---
