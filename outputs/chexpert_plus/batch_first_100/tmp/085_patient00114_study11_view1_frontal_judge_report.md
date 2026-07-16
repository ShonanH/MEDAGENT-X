# MEDAGENT-X Judge Report

## Summary

- Total cases: `1`
- Concordant: `0`
- Partially concordant: `0`
- Discordant: `1`

## Case

- Study key: `patient00114/study11`
- DICOM path: `patient00114/study11/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.462`
- Label macro score: `0.429`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Edema
- Enlarged Cardiomediastinum
- Lung Opacity
- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. SLIGHT INTERVAL DECREASE IN PULMONARY EDEMA, MODERATE EDEMA REMAINS. WIDENED MEDIASTINUM AGAIN NOTED. LEFT APICAL POSSIBLE HEMATOMA AGAIN NOTED. RETROCARDIAC AIRSPACE OPACITY AND BILATERAL PLEURAL EFFUSIONS APPEAR STABLE. 2. NO SIGNIFICANT CHANGE IN SUPPORT EQUIPMENT.

---
