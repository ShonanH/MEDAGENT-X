# MEDAGENT-X Judge Report

## Summary

- Total cases: `1`
- Concordant: `0`
- Partially concordant: `0`
- Discordant: `1`

## Case

- Study key: `patient00078/study8`
- DICOM path: `patient00078/study8/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.400`
- Label macro score: `0.571`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Pneumothorax
- Support Devices

### Predicted Present Labels

- Cardiomegaly
- Lung Lesion
- Pneumonia
- Pneumothorax

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. REDEMONSTRATED LEFT PLEURAL PIGTAIL CATHETER IN THE LEFT APEX. 2. STABLE SMALL LEFT APICAL PNEUMOTHORAX. 3. THE LUNGS ARE CLEAR. 4. CARDIOMEDIASTINAL SILHOUETTE WITHIN NORMAL LIMITS.

---
