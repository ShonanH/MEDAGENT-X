# MEDAGENT-X Judge Report

## Summary

- Total cases: `1`
- Concordant: `0`
- Partially concordant: `1`
- Discordant: `0`

## Case

- Study key: `patient00122/study7`
- DICOM path: `patient00122/study7/view1_frontal.dcm`
- Judge decision: **PARTIALLY_CONCORDANT**
- Disease F1: `0.800`
- Label macro score: `0.571`

### Explanation

Critical hallucinated disease labels: ['Atelectasis'] Disease status mismatches: ['Atelectasis']

### Ground Truth Present Labels

- Edema
- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Edema
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THE LUNG VOLUMES ARE DECREASED. 2. PERSISTENT BIBASILAR OPACIFICATION, LEFT GREATER THAN RIGHT. 3. PERSISTENT BILATERAL PLEURAL EFFUSIONS, LEFT GREATER THAN RIGHT. 4. PERSISTENT MODERATE PULMONARY INTERSTITIAL EDEMA. 5. OVERALL, NO INTERVAL CHANGE.

---
