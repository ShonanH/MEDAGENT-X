# MEDAGENT-X Judge Report

## Summary

- Total cases: `1`
- Concordant: `0`
- Partially concordant: `0`
- Discordant: `1`

## Case

- Study key: `patient00114/study2`
- DICOM path: `patient00114/study2/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.333`
- Label macro score: `0.321`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Pleural Effusion', 'Pneumonia', 'Pneumothorax', 'Lung Lesion']

### Ground Truth Present Labels

- Edema
- Lung Opacity
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
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 7/14/2018 USC CENTER FOR BODY COMPUTING 1352 hours: interval removal of right-sided chest tube. No pneumothorax identified. The right IJ line, aortic stent graft in the region of the aortic arch. Two mediastinal drains remain in place. There is persistent pulmonary edema and near confluent opacity involving the left hemithorax. 7/14/2018 USC Center for Body Computing 1449 hours: No significant interval change. 1. INTERVAL REMOVAL OF RIGHT-SIDED CHEST TUBE. OTHER LINES AND TUBES INCLUDING MEDIASTINAL DRAIN AND RIGHT IJ LINE IN PLACE. AORTIC ARCH STENT GRAFT AGAIN NOTED. 2. PERSISTENT, NEAR CONFLUENT OPACITY INVOLVING THE LEFT HEMITHORAX. 3. PERSISTENT PULMONARY EDEMA.

---
