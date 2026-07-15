# MEDAGENT-X Judge Report

## Summary

- Total cases: `1`
- Concordant: `0`
- Partially concordant: `1`
- Discordant: `0`

## Case

- Study key: `patient00114/study13`
- DICOM path: `patient00114/study13/view1_frontal.dcm`
- Judge decision: **PARTIALLY_CONCORDANT**
- Disease F1: `0.500`
- Label macro score: `0.536`

### Explanation

Ground-truth present disease labels predicted uncertain: ['Edema'] Critical hallucinated disease labels: ['Pleural Effusion'] Disease status mismatches: ['Pleural Effusion']

### Ground Truth Present Labels

- Edema
- Lung Opacity

### Predicted Present Labels

- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Edema: predicted `uncertain`, ground truth `present`
- Pleural Effusion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INTERVAL DECREASE IN PULMONARY EDEMA, MODERATE EDEMA REMAINS. 2. LEFT UPPER LUNG ZONE FOCAL OPACITY SUGGESTIVE OF PSEUDOANEURYSM ADJACENT TO THE POST-OPERATIVE CHANGES AGAIN NOTED.

---
