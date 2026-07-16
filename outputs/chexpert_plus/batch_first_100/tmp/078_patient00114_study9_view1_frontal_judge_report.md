# MEDAGENT-X Judge Report

## Summary

- Total cases: `1`
- Concordant: `0`
- Partially concordant: `0`
- Discordant: `1`

## Case

- Study key: `patient00114/study9`
- DICOM path: `patient00114/study9/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.333`
- Label macro score: `0.464`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Edema', 'Pneumonia']

### Ground Truth Present Labels

- Consolidation
- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Edema
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `present`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INCREASING RIGHT LOWER LOBE CONSOLIDATION AND PLEURAL EFFUSION.

---
