# MEDAGENT-X Judge Report

## Summary

- Total cases: `1`
- Concordant: `0`
- Partially concordant: `0`
- Discordant: `1`

## Case

- Study key: `patient00114/study12`
- DICOM path: `patient00114/study12/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.321`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Consolidation', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `uncertain`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. DIFFUSE RETICULAR OPACITIES SUGGESTIVE OF PULMONARY EDEMA. NO CHANGE. 2. TRACHEOSTOMY, POST-OPERATIVE CHANGES, AND RIGHT-SIDED PICC LINE, STABLE.

---
