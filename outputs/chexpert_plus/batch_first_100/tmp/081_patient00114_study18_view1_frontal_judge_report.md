# MEDAGENT-X Judge Report

## Summary

- Total cases: `1`
- Concordant: `0`
- Partially concordant: `0`
- Discordant: `1`

## Case

- Study key: `patient00114/study18`
- DICOM path: `patient00114/study18/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.200`
- Label macro score: `0.321`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Edema
- Support Devices

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
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. RIGHT CENTRAL LINE, TRACHEOSTOMY, AND SURGICAL WIRES AND VALVES, NO CHANGE FROM PREVIOUS. 2. PERSISTENT MILD INTERSTITIAL EDEMA. 3. SLIGHT DECREASE IN LUNG VOLUMES WITH PERSISTENT LEFT LUNG OPACITIES.

---
