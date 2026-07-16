# MEDAGENT-X Judge Report

## Summary

- Total cases: `1`
- Concordant: `0`
- Partially concordant: `0`
- Discordant: `1`

## Case

- Study key: `patient00107/study1`
- DICOM path: `patient00107/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.346`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- No Finding

### Predicted Present Labels

- Atelectasis
- Fracture
- Lung Lesion
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. NORMAL CARDIOMEDIASTINAL SILHOUETTE. NO FOCAL PARENCHYMAL OPACITY OR PLEURAL EFFUSION. PULMONARY VESSELS ARE UNREMARKABLE. NO ACUTE OSSEOUS ABNORMALITY.

---
