# MEDAGENT-X Judge Report

## Summary

- Total cases: `1`
- Concordant: `0`
- Partially concordant: `0`
- Discordant: `1`

## Case

- Study key: `patient00114/study13`
- DICOM path: `patient00114/study13/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.250`
- Label macro score: `0.393`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Consolidation', 'Pleural Effusion', 'Pneumonia', 'Enlarged Cardiomediastinum']

### Ground Truth Present Labels

- Edema
- Lung Opacity

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Enlarged Cardiomediastinum
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `present`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INTERVAL DECREASE IN PULMONARY EDEMA, MODERATE EDEMA REMAINS. 2. LEFT UPPER LUNG ZONE FOCAL OPACITY SUGGESTIVE OF PSEUDOANEURYSM ADJACENT TO THE POST-OPERATIVE CHANGES AGAIN NOTED.

---
