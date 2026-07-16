# MEDAGENT-X Judge Report

## Summary

- Total cases: `1`
- Concordant: `0`
- Partially concordant: `1`
- Discordant: `0`

## Case

- Study key: `patient00114/study10`
- DICOM path: `patient00114/study10/view1_frontal.dcm`
- Judge decision: **PARTIALLY_CONCORDANT**
- Disease F1: `0.750`
- Label macro score: `0.571`

### Explanation

Critical hallucinated disease labels: ['Atelectasis', 'Pneumonia'] Disease status mismatches: ['Atelectasis', 'Pneumonia']

### Ground Truth Present Labels

- Consolidation
- Edema
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> AGAIN SEEN ARE BILATERAL PLEURAL EFFUSIONS, PULMONARY EDEMA AND LEFT LOWER LOBE CONSOLIDATION. THE RIGHT-SIDED PICC LINE IS NOW REDIRECTED AND TERMINATES IN THE DISTAL SUPERIOR VENA CAVA.

---
