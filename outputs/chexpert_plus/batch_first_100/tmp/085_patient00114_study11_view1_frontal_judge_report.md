# MEDAGENT-X Judge Report

## Summary

- Total cases: `1`
- Concordant: `0`
- Partially concordant: `1`
- Discordant: `0`

## Case

- Study key: `patient00114/study11`
- DICOM path: `patient00114/study11/view1_frontal.dcm`
- Judge decision: **PARTIALLY_CONCORDANT**
- Disease F1: `0.667`
- Label macro score: `0.607`

### Explanation

Ground-truth present disease labels predicted uncertain: ['Edema', 'Enlarged Cardiomediastinum']

### Ground Truth Present Labels

- Edema
- Enlarged Cardiomediastinum
- Lung Opacity
- Pleural Effusion

### Predicted Present Labels

- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Edema: predicted `uncertain`, ground truth `present`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. SLIGHT INTERVAL DECREASE IN PULMONARY EDEMA, MODERATE EDEMA REMAINS. WIDENED MEDIASTINUM AGAIN NOTED. LEFT APICAL POSSIBLE HEMATOMA AGAIN NOTED. RETROCARDIAC AIRSPACE OPACITY AND BILATERAL PLEURAL EFFUSIONS APPEAR STABLE. 2. NO SIGNIFICANT CHANGE IN SUPPORT EQUIPMENT.

---
