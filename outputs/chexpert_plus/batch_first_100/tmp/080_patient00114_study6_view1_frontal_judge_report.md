# MEDAGENT-X Judge Report

## Summary

- Total cases: `1`
- Concordant: `0`
- Partially concordant: `0`
- Discordant: `1`

## Case

- Study key: `patient00114/study6`
- DICOM path: `patient00114/study6/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.444`
- Label macro score: `0.429`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Consolidation', 'Pneumonia', 'Lung Opacity', 'Enlarged Cardiomediastinum']

### Ground Truth Present Labels

- Edema
- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Enlarged Cardiomediastinum
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> NO SIGNIFICANT CHANGE. AGAIN SEEN ARE PLEURAL EFFUSIONS AND PULMONARY EDEMA.

---
