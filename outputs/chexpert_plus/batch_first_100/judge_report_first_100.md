# MEDAGENT-X Judge Report

## Summary

- Total cases: `100`
- Pass: `0`
- Review: `4`
- Fail: `96`

## Case

- Study key: `patient00003/study1`
- DICOM path: `patient00003/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.857`

### Explanation

Critical missed present labels: ['Edema']

### Ground Truth Present Labels

- Edema
- Support Devices

### Predicted Present Labels

- None

### Partial Or Mismatched Labels

- Edema: predicted `absent`, ground truth `present`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> Costophrenic angles sharp, without evidence of effusion. The cardiomediastinal silhouette is normal. Vessels mildly indistinct with prominence of interstitial structures, suggesting mild, pulmonary edema. Left subclavian central venous catheter is seen, tip in mid SVC. No pneumothorax. 1. NO EVIDENCE OF PNEUMOTHORAX. 2. MILD INTERSTITIAL PULMONARY EDEMA. NARRATIVE: CHEST, ONE VIEW: 2-10-2001 FINDINGS: Costophrenic angles sharp, without evidence of effusion. The cardiomediastinal silhouette is normal. Vessels mildly indistinct with prominence of interstitial structures, suggesting mild, pulmonary edema. Left subclavian central venous catheter is seen, tip in mid SVC. No pneumothorax. IMPRESSION: 1. NO EVIDENCE OF PNEUMOTHORAX. 2. MILD INTERSTITIAL PULMONARY EDEMA. END OF IMPRESSION: SUMMARY: 2 I have personally reviewed the images for this examination and agree with the report transcribed ...[truncated]

---

## Case

- Study key: `patient00009/study1`
- DICOM path: `patient00009/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.393`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Enlarged Cardiomediastinum', 'Lung Opacity', 'Pleural Effusion']

### Ground Truth Present Labels

- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Enlarged Cardiomediastinum
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. PA AND LATERAL CHEST RADIOGRAPH. THE HEART IS ENLARGED, WITH A CTR OF 16/29. NO CEPHALIZATION OR OVERT PULMONARY EDEMA. LINEAR SHADOWING IS SEEN AT BOTH LUNG BASES, SUGGESTING ATELECTASIS, MOST MARKED ON THE RIGHT. ON THE LATERAL VIEW, THIS APPEARS TO LIE WITHIN THE RIGHT MIDDLE LOBE. THE LUNG APICES APPEAR CLEAR. 2. DISC DEGENERATION IS SEEN THROUGHOUT THE THORACIC SPINE, WITHOUT SIGNIFICANT VERTEBRAL BODY COLLAPSE. NARRATIVE: CHEST X-RAY: 2/21/2006 COMPARISON: 2/21/2006. CLINICAL HISTORY: Dyspnea. Multiple myeloma. IMPRESSION: 1. PA AND LATERAL CHEST RADIOGRAPH. THE HEART IS ENLARGED, WITH A CTR OF 16/29. NO CEPHALIZATION OR OVERT PULMONARY EDEMA. LINEAR SHADOWING IS SEEN AT BOTH LUNG BASES, SUGGESTING ATELECTASIS, MOST MARKED ON THE RIGHT. ON THE LATERAL VIEW, THIS APPEARS TO LIE WITHIN THE RIGHT MIDDLE LOBE. THE LUNG APICES APPEAR CLEAR. 2. DISC DEGENERATION IS SEEN THROUGHOUT THE ...[truncated]

---

## Case

- Study key: `patient00009/study1`
- DICOM path: `patient00009/study1/view2_lateral.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.393`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Edema', 'Enlarged Cardiomediastinum', 'Lung Opacity', 'Pleural Effusion', 'Pneumonia']

### Ground Truth Present Labels

- Support Devices

### Predicted Present Labels

- Atelectasis
- Edema
- Enlarged Cardiomediastinum
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. PA AND LATERAL CHEST RADIOGRAPH. THE HEART IS ENLARGED, WITH A CTR OF 16/29. NO CEPHALIZATION OR OVERT PULMONARY EDEMA. LINEAR SHADOWING IS SEEN AT BOTH LUNG BASES, SUGGESTING ATELECTASIS, MOST MARKED ON THE RIGHT. ON THE LATERAL VIEW, THIS APPEARS TO LIE WITHIN THE RIGHT MIDDLE LOBE. THE LUNG APICES APPEAR CLEAR. 2. DISC DEGENERATION IS SEEN THROUGHOUT THE THORACIC SPINE, WITHOUT SIGNIFICANT VERTEBRAL BODY COLLAPSE. NARRATIVE: CHEST X-RAY: 2/21/2006 COMPARISON: 2/21/2006. CLINICAL HISTORY: Dyspnea. Multiple myeloma. IMPRESSION: 1. PA AND LATERAL CHEST RADIOGRAPH. THE HEART IS ENLARGED, WITH A CTR OF 16/29. NO CEPHALIZATION OR OVERT PULMONARY EDEMA. LINEAR SHADOWING IS SEEN AT BOTH LUNG BASES, SUGGESTING ATELECTASIS, MOST MARKED ON THE RIGHT. ON THE LATERAL VIEW, THIS APPEARS TO LIE WITHIN THE RIGHT MIDDLE LOBE. THE LUNG APICES APPEAR CLEAR. 2. DISC DEGENERATION IS SEEN THROUGHOUT THE ...[truncated]

---

## Case

- Study key: `patient00016/study1`
- DICOM path: `patient00016/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `1.000`
- Label macro score: `0.607`

### Explanation

Critical hallucinated present labels: ['Atelectasis'] Critical missed present labels: ['Consolidation', 'Lung Opacity', 'Pneumothorax']

### Ground Truth Present Labels

- Consolidation
- Fracture
- Lung Opacity
- Pleural Other
- Pneumothorax

### Predicted Present Labels

- Atelectasis

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `present`
- Pneumothorax: predicted `absent`, ground truth `present`
- Fracture: predicted `uncertain`, ground truth `present`
- Lung Opacity: predicted `uncertain`, ground truth `present`
- Pleural Other: predicted `absent`, ground truth `present`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. ACUTE TO SUBACUTE LEFT POSTERIOR SIXTH RIB FRACTURE.   2.NO EVIDENCE OF PNEUMOTHORAX.  MINIMAL LEFT PLEURAL THICKENING MAY  REPRESENT SMALL AMOUNT OF BLOOD IN THE PLEURAL SPACE.   3.SUBTLE OPACITY JUST LATERAL TO THE CARDIAC APEX IN THE LEFT BASE  MAY REPRESENT A SMALL AREA OF PULMONARY CONTUSION OR OTHER CAUSE FOR  SMALL FOCUS OF CONSOLIDATION.   4.RIGHT LUNG IS CLEAR.   5.LOW LUNG VOLUMES. NARRATIVE: Exam: Chest 2 Views, 08-06-2015   Clinical History: 53 years old Female with Fell 2 days ago, poss left  lower posterior rib fx's.  Rule out pneumothorax, hemothorax   Comparison: None   Impression:   1. ACUTE TO SUBACUTE LEFT POSTERIOR SIXTH RIB FRACTURE.   2.NO EVIDENCE OF PNEUMOTHORAX.  MINIMAL LEFT PLEURAL THICKENING MAY  REPRESENT SMALL AMOUNT OF BLOOD IN THE PLEURAL SPACE.   3.SUBTLE OPACITY JUST LATERAL TO THE CARDIAC APEX IN THE LEFT BASE  MAY REPRESENT A SMALL AREA OF PULMONARY ...[truncated]

---

## Case

- Study key: `patient00016/study1`
- DICOM path: `patient00016/study1/view2_lateral.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.400`
- Label macro score: `0.429`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Pleural Effusion', 'Pneumonia'] Critical missed present labels: ['Pneumothorax']

### Ground Truth Present Labels

- Consolidation
- Fracture
- Lung Opacity
- Pleural Other
- Pneumothorax

### Predicted Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `absent`, ground truth `present`
- Fracture: predicted `absent`, ground truth `present`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `absent`, ground truth `present`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. ACUTE TO SUBACUTE LEFT POSTERIOR SIXTH RIB FRACTURE.   2.NO EVIDENCE OF PNEUMOTHORAX.  MINIMAL LEFT PLEURAL THICKENING MAY  REPRESENT SMALL AMOUNT OF BLOOD IN THE PLEURAL SPACE.   3.SUBTLE OPACITY JUST LATERAL TO THE CARDIAC APEX IN THE LEFT BASE  MAY REPRESENT A SMALL AREA OF PULMONARY CONTUSION OR OTHER CAUSE FOR  SMALL FOCUS OF CONSOLIDATION.   4.RIGHT LUNG IS CLEAR.   5.LOW LUNG VOLUMES. NARRATIVE: Exam: Chest 2 Views, 08-06-2015   Clinical History: 53 years old Female with Fell 2 days ago, poss left  lower posterior rib fx's.  Rule out pneumothorax, hemothorax   Comparison: None   Impression:   1. ACUTE TO SUBACUTE LEFT POSTERIOR SIXTH RIB FRACTURE.   2.NO EVIDENCE OF PNEUMOTHORAX.  MINIMAL LEFT PLEURAL THICKENING MAY  REPRESENT SMALL AMOUNT OF BLOOD IN THE PLEURAL SPACE.   3.SUBTLE OPACITY JUST LATERAL TO THE CARDIAC APEX IN THE LEFT BASE  MAY REPRESENT A SMALL AREA OF PULMONARY ...[truncated]

---

## Case

- Study key: `patient00026/study1`
- DICOM path: `patient00026/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.857`
- Label macro score: `0.786`

### Explanation

Critical hallucinated present labels: ['Pleural Effusion']

### Ground Truth Present Labels

- Atelectasis
- Consolidation
- Lung Opacity

### Predicted Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> Low lung volumes. Discoid atelectasis and consolidation seen in the left lower lobe with an elevated left hemidiaphragm. This is unchanged from the previous chest x-ray. DISCOID CONSOLIDATION AND ATELECTASIS OF THE LEFT LOWER LOBE. UNCHANGED FROM THE PREVIOUS CHEST X-RAY. NARRATIVE: CHEST TWO VIEW: 10/12/2004 COMPARISON: Chest two view 10/12/2004. HISTORY: 42-year-old female with continued dyspnea after surgery, check for infiltrate. FINDINGS: Low lung volumes. Discoid atelectasis and consolidation seen in the left lower lobe with an elevated left hemidiaphragm. This is unchanged from the previous chest x-ray. IMPRESSION: DISCOID CONSOLIDATION AND ATELECTASIS OF THE LEFT LOWER LOBE. UNCHANGED FROM THE PREVIOUS CHEST X-RAY. END OF IMPRESSION: SUMMARY: 4 POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION I have personally reviewed the images for this examination and agree with the report trans ...[truncated]

---

## Case

- Study key: `patient00026/study1`
- DICOM path: `patient00026/study1/view2_lateral.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.667`
- Label macro score: `0.571`

### Explanation

Critical hallucinated present labels: ['Cardiomegaly', 'Pleural Effusion', 'Pneumonia']

### Ground Truth Present Labels

- Atelectasis
- Consolidation
- Lung Opacity

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> Low lung volumes. Discoid atelectasis and consolidation seen in the left lower lobe with an elevated left hemidiaphragm. This is unchanged from the previous chest x-ray. DISCOID CONSOLIDATION AND ATELECTASIS OF THE LEFT LOWER LOBE. UNCHANGED FROM THE PREVIOUS CHEST X-RAY. NARRATIVE: CHEST TWO VIEW: 10/12/2004 COMPARISON: Chest two view 10/12/2004. HISTORY: 42-year-old female with continued dyspnea after surgery, check for infiltrate. FINDINGS: Low lung volumes. Discoid atelectasis and consolidation seen in the left lower lobe with an elevated left hemidiaphragm. This is unchanged from the previous chest x-ray. IMPRESSION: DISCOID CONSOLIDATION AND ATELECTASIS OF THE LEFT LOWER LOBE. UNCHANGED FROM THE PREVIOUS CHEST X-RAY. END OF IMPRESSION: SUMMARY: 4 POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION I have personally reviewed the images for this examination and agree with the report trans ...[truncated]

---

## Case

- Study key: `patient00027/study1`
- DICOM path: `patient00027/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.600`
- Label macro score: `0.536`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Edema', 'Lung Opacity']

### Ground Truth Present Labels

- Consolidation
- Pleural Effusion
- Pneumothorax

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Fracture
- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1.FRONTAL AND LATERAL VIEWS OF THE CHEST DEMONSTRATE LOW LUNG VOLUMES  WITH BIBASILAR OPACITIES LIKELY REFLECTING ATELECTASIS.  NO EVIDENCE  OF FOCAL CONSOLIDATION, PLEURAL EFFUSIONS OR PNEUMOTHORAX.   2.THE CARDIOMEDIASTINAL SILHOUETTE AND PULMONARY VASCULATURE ARE  WITHIN NORMAL LIMITS.   3.VISUALIZED OSSEOUS STRUCTURES ARE INTACT. NARRATIVE: Exam: Chest 2 Views, 6-27-2010   Clinical History: 55 years Male with Chest Pain   Comparison: None   IMPRESSION:   1.FRONTAL AND LATERAL VIEWS OF THE CHEST DEMONSTRATE LOW LUNG VOLUMES  WITH BIBASILAR OPACITIES LIKELY REFLECTING ATELECTASIS.  NO EVIDENCE  OF FOCAL CONSOLIDATION, PLEURAL EFFUSIONS OR PNEUMOTHORAX.   2.THE CARDIOMEDIASTINAL SILHOUETTE AND PULMONARY VASCULATURE ARE  WITHIN NORMAL LIMITS.   3.VISUALIZED OSSEOUS STRUCTURES ARE INTACT.   SUMMARY:1-NO SIGNIFICANT ABNORMALITY I have personally reviewed the images for this examination and ...[truncated]

---

## Case

- Study key: `patient00027/study1`
- DICOM path: `patient00027/study1/view2_lateral.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.500`
- Label macro score: `0.643`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Lung Opacity', 'Pneumonia'] Critical missed present labels: ['Pneumothorax']

### Ground Truth Present Labels

- Consolidation
- Pleural Effusion
- Pneumothorax

### Predicted Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `present`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1.FRONTAL AND LATERAL VIEWS OF THE CHEST DEMONSTRATE LOW LUNG VOLUMES  WITH BIBASILAR OPACITIES LIKELY REFLECTING ATELECTASIS.  NO EVIDENCE  OF FOCAL CONSOLIDATION, PLEURAL EFFUSIONS OR PNEUMOTHORAX.   2.THE CARDIOMEDIASTINAL SILHOUETTE AND PULMONARY VASCULATURE ARE  WITHIN NORMAL LIMITS.   3.VISUALIZED OSSEOUS STRUCTURES ARE INTACT. NARRATIVE: Exam: Chest 2 Views, 6-27-2010   Clinical History: 55 years Male with Chest Pain   Comparison: None   IMPRESSION:   1.FRONTAL AND LATERAL VIEWS OF THE CHEST DEMONSTRATE LOW LUNG VOLUMES  WITH BIBASILAR OPACITIES LIKELY REFLECTING ATELECTASIS.  NO EVIDENCE  OF FOCAL CONSOLIDATION, PLEURAL EFFUSIONS OR PNEUMOTHORAX.   2.THE CARDIOMEDIASTINAL SILHOUETTE AND PULMONARY VASCULATURE ARE  WITHIN NORMAL LIMITS.   3.VISUALIZED OSSEOUS STRUCTURES ARE INTACT.   SUMMARY:1-NO SIGNIFICANT ABNORMALITY I have personally reviewed the images for this examination and ...[truncated]

---

## Case

- Study key: `patient00031/study1`
- DICOM path: `patient00031/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.333`
- Label macro score: `0.500`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Enlarged Cardiomediastinum', 'Lung Opacity']

### Ground Truth Present Labels

- Edema
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Enlarged Cardiomediastinum
- Lung Opacity

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `uncertain`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `uncertain`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. SINGLE PORTABLE AP VIEW OF THE CHEST IS LIMITED BY PATIENT POSITION WITH ROTATION TO THE RIGHT. CONSIDER REPEAT IMAGING WITH PA AND LATERAL VIEWS IF CLINICALLY WARRANTED. 2. ILL-DEFINED, FLUFFY PERIHILAR OPACITIES, RIGHT GREATER THAN LEFT, WHICH MAY REPRESENT EARLY INFILTRATES OR ATELECTASIS. 3. INTERSTITIAL PROMINENCE AND PERIBRONCHIAL CUFFING THAT MAY BE CHRONIC IN NATURE. 4. MILD CEPHALIZATION OF THE PULMONARY VASCULATURE, CONSISTENT WITH MILD EDEMA. 5. LEFT SUBCLAVIAN CENTRAL VENOUS LINE WITH TIP IN THE RIGHT ATRIUM. NARRATIVE: PORTABLE AP VIEW OF THE CHEST: 1-2-2016. CLINICAL HISTORY: 88-year-old male presents with periumbilical pain. COMPARISON: None. IMPRESSION: 1. SINGLE PORTABLE AP VIEW OF THE CHEST IS LIMITED BY PATIENT POSITION WITH ROTATION TO THE RIGHT. CONSIDER REPEAT IMAGING WITH PA AND LATERAL VIEWS IF CLINICALLY WARRANTED. 2. ILL-DEFINED, FLUFFY PERIHILAR OPACITIES, R ...[truncated]

---

## Case

- Study key: `patient00031/study3`
- DICOM path: `patient00031/study3/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.667`
- Label macro score: `0.536`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation']

### Ground Truth Present Labels

- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> Single frontal portable digital radiograph chest demonstrates rightward rotation and cardiomediastinal silhouette unchanged in size and contour.   There is new blunting of the right costophrenic sulcus suggesting right pleural effusion with an associated veiling opacity.  No definite area of consolidation or pneumothorax.  Diffuse sclerotic foci are present throughout the osseous and appendicular skeleton, unchanged. 1.  NEW RIGHT PLEURAL EFFUSION. 2.  DIFFUSE OSSEOUS SCLEROTIC DISEASE LIKELY METASTATIC FOCI. NARRATIVE: PORTABLE CHEST SINGLE VIEW:  4-29-2003 USC Center for Body Computing 1002 HOURS AND 39 SECONDS COMPARISON:  Chest dated 4/29/2003 USC Center for Body Computing 1904 hours. CLINICAL HISTORY:  Hypoxia, history of metastatic prostate cancer. FINDINGS:  Single frontal portable digital radiograph chest demonstrates rightward rotation and cardiomediastinal silhouette unchanged ...[truncated]

---

## Case

- Study key: `patient00031/study2`
- DICOM path: `patient00031/study2/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.286`
- Label macro score: `0.607`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Pleural Effusion'] Critical missed present labels: ['Edema', 'Pneumothorax']

### Ground Truth Present Labels

- Edema
- Lung Opacity
- Pneumothorax
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `present`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `present`
- Fracture: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. INTERVAL REPLACEMENT OF THE LEFT-SIDED CENTRAL VENOUS LINE, WITH TIP WITHIN THE SUPERIOR VENA CAVA. NO EVIDENCE FOR PNEUMOTHORAX. INTERVAL RESOLUTION OF MILD PULMONARY EDEMA SEEN ON PRIOR EXAM. RIGHT LOWER LOBE HAZY OPACITY, LIKELY ATELECTASIS. STABLE CARDIOMEDIASTINAL SILHOUETTE. NARRATIVE: ONE-VIEW CHEST: 9/1/2020 CLINICAL DATA: Systemic infection. Rule out sepsis. COMPARISON: Chest x-ray performed 9/1/20. IMPRESSION: 1. INTERVAL REPLACEMENT OF THE LEFT-SIDED CENTRAL VENOUS LINE, WITH TIP WITHIN THE SUPERIOR VENA CAVA. NO EVIDENCE FOR PNEUMOTHORAX. INTERVAL RESOLUTION OF MILD PULMONARY EDEMA SEEN ON PRIOR EXAM. RIGHT LOWER LOBE HAZY OPACITY, LIKELY ATELECTASIS. STABLE CARDIOMEDIASTINAL SILHOUETTE. END OF IMPRESSION: SUMMARY 2: ABNORMAL, PREVIOUSLY REPORTED I have personally reviewed the images for this examination and agree with the report transcribed above. By: Jasmine, Potts  on: ...[truncated]

---

## Case

- Study key: `patient00034/study1`
- DICOM path: `patient00034/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `1.000`
- Label macro score: `0.536`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Lung Opacity'] Critical missed present labels: ['Edema', 'Pneumothorax']

### Ground Truth Present Labels

- Edema
- Pneumothorax

### Predicted Present Labels

- Atelectasis
- Lung Opacity

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `present`
- Pneumothorax: predicted `absent`, ground truth `present`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> Diffuse reticular opacities which are nonspecific and could be  related to interstitial lung disease, pulmonary edema, or atypical  infection. No focal consolidation. No pleural effusion or  pneumothorax. The cardiomediastinal silhouette is within normal  limits. No acute osseous abnormality. 1.  Diffuse reticular opacities which are nonspecific and could be  related to interstitial lung disease, pulmonary edema, or atypical  infection.      I have personally reviewed the images for this examination and agreed with the report transcribed above. NARRATIVE: RADIOGRAPHIC EXAMINATION OF THE CHEST: 11 January 24th   CLINICAL HISTORY: 45 years of age, Male, Stroke Protocol.   COMPARISON: None.   PROCEDURE COMMENTS: Single view of the chest.    FINDINGS:   Diffuse reticular opacities which are nonspecific and could be  related to interstitial lung disease, pulmonary edema, or atypical  infectio ...[truncated]

---

## Case

- Study key: `patient00038/study1`
- DICOM path: `patient00038/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.500`
- Label macro score: `0.607`

### Explanation

Critical hallucinated present labels: ['Consolidation', 'Pleural Effusion'] Critical missed present labels: ['Pneumothorax']

### Ground Truth Present Labels

- Atelectasis
- Lung Opacity
- Pneumothorax
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Fracture
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `uncertain`
- Pneumothorax: predicted `uncertain`, ground truth `present`
- Fracture: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1.  AP SEMI-ERECT CHEST RADIOGRAPH.  THE PATIENT IS INTUBATED, WITH THE TIP OF THE ENDOTRACHEAL TUBE APPROXIMATELY 5.5 CM ABOVE THE CARINA.  A NASOGASTRIC TUBE IS PRESENT, WITH THE TIP AND SIDE PORT BELOW THE LEFT HEMIDIAPHRAGM.  A LEFT SUBCLAVIAN VENOUS LINE IS PRESENT WITH THE TIP IN MID SUPERIOR VENA CAVA. 2.  LUNG VOLUMES ARE LOW, WITH OPACIFICATION IN THE RETROCARDIAC REGION WHICH COULD REFLECT ATELECTASIS, EARLY INFILTRATE OR ASPIRATION.  THERE IS ALSO A  LIKELY SMALL PLEURAL EFFUSION ON THIS SIDE.  MINIMAL ATELECTASIS IS ALSO SEEN AT THE RIGHT BASE.  NO EVIDENCE OF A PNEUMOTHORAX. NARRATIVE: PORTABLE CHEST, SINGLE VIEW:   11/05/07 COMPARISON:   None. CLINICAL HISTORY:   AM x-ray. IMPRESSION: 1.  AP SEMI-ERECT CHEST RADIOGRAPH.  THE PATIENT IS INTUBATED, WITH THE TIP OF THE ENDOTRACHEAL TUBE APPROXIMATELY 5.5 CM ABOVE THE CARINA.  A NASOGASTRIC TUBE IS PRESENT, WITH THE TIP AND SID ...[truncated]

---

## Case

- Study key: `patient00038/study3`
- DICOM path: `patient00038/study3/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.333`
- Label macro score: `0.429`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Edema', 'Lung Opacity']

### Ground Truth Present Labels

- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1.  SINGLE FRONTAL SEMI-UPRIGHT VIEW OF THE CHEST DEMONSTRATES STABLE POSITION OF LINES AND TUBES.  THE ENDOTRACHEAL TUBE TIP IS HIGH, ALMOST 9 CM ABOVE THE CARINA. 2.  NO OTHER SIGNIFICANT INTERVAL CHANGE FROM THE PRIOR EXAMINATION, WITH REDEMONSTRATION OF BIBASILAR OPACITIES, LEFT GREATER THAN RIGHT AND BILATERAL PLEURAL EFFUSIONS. NARRATIVE: CHEST X-RAY:  8/28/2002. COMPARISON:  8-28-2002. CLINICAL HISTORY:  77-year-old male, follow-up. IMPRESSION: 1.  SINGLE FRONTAL SEMI-UPRIGHT VIEW OF THE CHEST DEMONSTRATES STABLE POSITION OF LINES AND TUBES.  THE ENDOTRACHEAL TUBE TIP IS HIGH, ALMOST 9 CM ABOVE THE CARINA. 2.  NO OTHER SIGNIFICANT INTERVAL CHANGE FROM THE PRIOR EXAMINATION, WITH REDEMONSTRATION OF BIBASILAR OPACITIES, LEFT GREATER THAN RIGHT AND BILATERAL PLEURAL EFFUSIONS. SUMMARY:4-POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION I have personally reviewed the images for this exam ...[truncated]

---

## Case

- Study key: `patient00044/study7`
- DICOM path: `patient00044/study7/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.667`
- Label macro score: `0.607`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Lung Opacity']

### Ground Truth Present Labels

- Cardiomegaly
- Edema
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. INTERVAL REMOVAL OF RIGHT INTERNAL JUGULAR CENTRAL VENOUS LINE. 2. CARDIOMEGALY AND MILD PULMONARY EDEMA. THE PULMONARY EDEMA HAS BEEN GRADUALLY IMPROVING OVER THE LAST SEVERAL CHEST RADIOGRAPHS. 3. STABLE PATCHY OPACITIES IN BILATERAL PERIHILAR REGIONS WHICH COULD REPRESENT FLUID OR ATELECTASIS. NARRATIVE: CHEST 2 VIEWS DATE OF STUDY: 1/11/2010 CLINICAL HISTORY: 48-year-old woman with mitral stenosis, tricuspid regurg, evaluate pleural effusion. COMPARISON STUDY: 6-15-2002 and 6-15-2002. IMPRESSION: 1. INTERVAL REMOVAL OF RIGHT INTERNAL JUGULAR CENTRAL VENOUS LINE. 2. CARDIOMEGALY AND MILD PULMONARY EDEMA. THE PULMONARY EDEMA HAS BEEN GRADUALLY IMPROVING OVER THE LAST SEVERAL CHEST RADIOGRAPHS. 3. STABLE PATCHY OPACITIES IN BILATERAL PERIHILAR REGIONS WHICH COULD REPRESENT FLUID OR ATELECTASIS. END OF IMPRESSION: SUMMARY:4-POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION I have persona ...[truncated]

---

## Case

- Study key: `patient00044/study7`
- DICOM path: `patient00044/study7/view2_lateral.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.600`
- Label macro score: `0.536`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Lung Opacity', 'Pneumonia']

### Ground Truth Present Labels

- Cardiomegaly
- Edema
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. INTERVAL REMOVAL OF RIGHT INTERNAL JUGULAR CENTRAL VENOUS LINE. 2. CARDIOMEGALY AND MILD PULMONARY EDEMA. THE PULMONARY EDEMA HAS BEEN GRADUALLY IMPROVING OVER THE LAST SEVERAL CHEST RADIOGRAPHS. 3. STABLE PATCHY OPACITIES IN BILATERAL PERIHILAR REGIONS WHICH COULD REPRESENT FLUID OR ATELECTASIS. NARRATIVE: CHEST 2 VIEWS DATE OF STUDY: 1/11/2010 CLINICAL HISTORY: 48-year-old woman with mitral stenosis, tricuspid regurg, evaluate pleural effusion. COMPARISON STUDY: 6-15-2002 and 6-15-2002. IMPRESSION: 1. INTERVAL REMOVAL OF RIGHT INTERNAL JUGULAR CENTRAL VENOUS LINE. 2. CARDIOMEGALY AND MILD PULMONARY EDEMA. THE PULMONARY EDEMA HAS BEEN GRADUALLY IMPROVING OVER THE LAST SEVERAL CHEST RADIOGRAPHS. 3. STABLE PATCHY OPACITIES IN BILATERAL PERIHILAR REGIONS WHICH COULD REPRESENT FLUID OR ATELECTASIS. END OF IMPRESSION: SUMMARY:4-POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION I have persona ...[truncated]

---

## Case

- Study key: `patient00044/study1`
- DICOM path: `patient00044/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.600`
- Label macro score: `0.536`

### Explanation

Critical hallucinated present labels: ['Consolidation', 'Enlarged Cardiomediastinum', 'Lung Opacity', 'Pleural Effusion']

### Ground Truth Present Labels

- Atelectasis
- Cardiomegaly
- Edema
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Enlarged Cardiomediastinum
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> Interval placement of ET tube with tip at the level of the clavicular heads. NG tube courses into the abdomen. Interval placement of right internal jugular venous central line with tip in the mid SVC. A right IJ sheath is also present. A mitral valve ring is unchanged. A right chest tube and mediastinal drain are in place. Moderate cardiomegaly. Bibasilar opacities, likely representing atelectasis. Mild interstitial pulmonary edema. 1. INTERVAL PLACEMENT OF LINES AND TUBES AS DESCRIBED. 2. PERSISTENT CARDIOMEGALY WITH MODERATE INTERSTITIAL PULMONARY EDEMA AND BIBASILAR ATELECTASIS. NARRATIVE: SINGLE VIEW PORTABLE CHEST: 10-15-2003 CLINICAL HISTORY: 48-year-old woman with history of mitral stenosis and tricuspid regurgitation. COMPARISON: 10-15-2003 FINDINGS: Interval placement of ET tube with tip at the level of the clavicular heads. NG tube courses into the abdomen. Interval placement o ...[truncated]

---

## Case

- Study key: `patient00044/study3`
- DICOM path: `patient00044/study3/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.286`
- Label macro score: `0.429`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Lung Opacity']

### Ground Truth Present Labels

- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. INTERVAL REMOVAL OF RIGHT INTERNAL JUGULAR LINE SHEATH. THE REMAINING LINES AND TUBES ARE UNCHANGED. 2. LARGE RIGHT PLEURAL EFFUSION HAS INCREASED SINCE THE PRIOR EXAM. STABLE MODERATE LEFT PLEURAL EFFUSION. 3. ENLARGED POSTOPERATIVE CARDIOMEDIASTINAL SILHOUETTE IS UNCHANGED WITH MITRAL ANNULAR RING. NARRATIVE: SINGLE VIEW OF THE CHEST: 5/20/21 CLINICAL HISTORY: Forty-eight-year-old female with history of mitral stenosis and tricuspid regurgitation. Status post surgery. COMPARISON: May 20th. IMPRESSION: 1. INTERVAL REMOVAL OF RIGHT INTERNAL JUGULAR LINE SHEATH. THE REMAINING LINES AND TUBES ARE UNCHANGED. 2. LARGE RIGHT PLEURAL EFFUSION HAS INCREASED SINCE THE PRIOR EXAM. STABLE MODERATE LEFT PLEURAL EFFUSION. 3. ENLARGED POSTOPERATIVE CARDIOMEDIASTINAL SILHOUETTE IS UNCHANGED WITH MITRAL ANNULAR RING. END OF IMPRESSION: SUMMARY:4-POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION   ACCES ...[truncated]

---

## Case

- Study key: `patient00044/study4`
- DICOM path: `patient00044/study4/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.286`
- Label macro score: `0.429`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Edema', 'Lung Opacity'] Critical missed present labels: ['Cardiomegaly']

### Ground Truth Present Labels

- Cardiomegaly
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `present`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> AP ERECT CHEST RADIOGRAPH. THERE HAS BEEN A MEDIAN STERNOTOMY, WITH PROSTHETIC VALVE REPLACEMENT. A RIGHT IJ VENOUS LINE REMAINS IN PLACE. THERE HAS BEEN INTERVAL PLACEMENT OF A RIGHT-SIDED CHEST TUBE WITH A PERSISTENT SMALL RIGHT PLEURAL EFFUSION, SLIGHTLY DECREASED IN SIZE IN COMPARISON TO PRIOR FILMS. MARKED CARDIOMEGALY IS PRESENT, WITH INCREASED OPACIFICATION SEEN IN THE RETROCARDIAC REGION, AND A LIKELY SMALL LEFT PLEURAL EFFUSION. NARRATIVE: PORTABLE CHEST, 2-1-2009: COMPARISON: 2-1-2009. CLINICAL HISTORY: Mitral stenosis and tricuspid regurgitation. Chest tube. IMPRESSION: AP ERECT CHEST RADIOGRAPH. THERE HAS BEEN A MEDIAN STERNOTOMY, WITH PROSTHETIC VALVE REPLACEMENT. A RIGHT IJ VENOUS LINE REMAINS IN PLACE. THERE HAS BEEN INTERVAL PLACEMENT OF A RIGHT-SIDED CHEST TUBE WITH A PERSISTENT SMALL RIGHT PLEURAL EFFUSION, SLIGHTLY DECREASED IN SIZE IN COMPARISON TO PRIOR FILMS. MARKED ...[truncated]

---

## Case

- Study key: `patient00044/study2`
- DICOM path: `patient00044/study2/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.545`
- Label macro score: `0.464`

### Explanation

Critical hallucinated present labels: ['Cardiomegaly', 'Consolidation', 'Enlarged Cardiomediastinum', 'Lung Opacity', 'Pneumonia']

### Ground Truth Present Labels

- Atelectasis
- Edema
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Enlarged Cardiomediastinum
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. INTERVAL EXTUBATION AND REMOVAL OF NASOGASTRIC TUBE. REMAINING LINES AND TUBES ARE UNCHANGED. 2. MODERATE RIGHT PLEURAL EFFUSION, INCREASED SINCE PRIOR EXAM. 3. BILATERAL LOW LUNG VOLUMES WITH INCREASE IN BIBASILAR ATELECTASIS. MODERATE INTERSTITIAL PULMONARY EDEMA IS UNCHANGED. NARRATIVE: PORTABLE CHEST SINGLE VIEW: 12-30-2014 CLINICAL HISTORY: 48-year-old woman with history of mitral stenosis and tricuspid regurgitation, postoperative. COMPARISON: 12/30/14. IMPRESSION: 1. INTERVAL EXTUBATION AND REMOVAL OF NASOGASTRIC TUBE. REMAINING LINES AND TUBES ARE UNCHANGED. 2. MODERATE RIGHT PLEURAL EFFUSION, INCREASED SINCE PRIOR EXAM. 3. BILATERAL LOW LUNG VOLUMES WITH INCREASE IN BIBASILAR ATELECTASIS. MODERATE INTERSTITIAL PULMONARY EDEMA IS UNCHANGED. END OF IMPRESSION: SUMMARY:4-POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION I have personally reviewed the images for this examination and ...[truncated]

---

## Case

- Study key: `patient00044/study5`
- DICOM path: `patient00044/study5/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.727`
- Label macro score: `0.571`

### Explanation

Critical hallucinated present labels: ['Enlarged Cardiomediastinum', 'Lung Opacity', 'Pleural Effusion']

### Ground Truth Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Enlarged Cardiomediastinum
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> The 0705 hours radiograph demonstrates no significant interval change in the chest allowing for technique. The lines and tubes are stable. Enlarged cardiomediastinal silhouette and moderate pulmonary edema are unchanged with patchy right lower lobe consolidation versus atelectasis. The 2310 hours examination demonstrates stable position of lines and tubes. Again seen are tricuspid and mitral annular rings. The right basilar consolidation versus atelectasis demonstrates mild interval increase in density. Stable marked cardiomegaly. MILD INCREASE IN RIGHT BASILAR CONSOLIDATION VERSUS ATELECTASIS. THE REMAINDER OF THE CHEST IS NOT SIGNIFICANTLY CHANGED. NARRATIVE: SINGLE RADIOGRAPH OF THE CHEST: 12/17/2019 CLINICAL HISTORY: 48-year-old woman with history of mitral stenosis and tricuspid regurgitation. COMPARISON: 12-2019. FINDINGS: The 0705 hours radiograph demonstrates no significant inter ...[truncated]

---

## Case

- Study key: `patient00045/study1`
- DICOM path: `patient00045/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `1.000`
- Label macro score: `0.607`

### Explanation

Critical hallucinated present labels: ['Cardiomegaly'] Critical missed present labels: ['Atelectasis', 'Edema', 'Pleural Effusion', 'Pneumonia']

### Ground Truth Present Labels

- Atelectasis
- Edema
- Pleural Effusion
- Pneumonia
- Support Devices

### Predicted Present Labels

- Cardiomegaly

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `present`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Edema: predicted `absent`, ground truth `present`
- Pleural Effusion: predicted `absent`, ground truth `present`
- Pneumonia: predicted `absent`, ground truth `present`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> Upright PA and lateral chest radiographs demonstrate a single lead AICD in place with the tip in the right ventricle.  Minimal linear stranding opacities are noted at bilateral lung bases, likely due to atelectasis.  No focal areas of consolidation.  No pneumothorax, pleural effusions, or pulmonary edema.  Calcified plaque is seen within the aortic arch.  The descending thoracic aorta is mildly tortuous. The cardiac silhouette size is within normal limits and otherwise the remainder of the cardiomediastinal silhouette is unremarkable.  The skeletal structures are grossly unremarkable. 1.  SINGLE LEAD AICD IN PLACE WITH THE TIP IN THE RIGHT VENTRICLE.  2.  MINIMAL BIBASILAR ATELECTASIS.  NO FOCAL CONSOLIDATION. NARRATIVE: TWO VIEWS OF THE CHEST:  March 10  COMPARISON:  None.  CLINICAL HISTORY:   A 69-year-old woman with atrial tachycardia. Bandemia status post procedure, rule out pneumoni ...[truncated]

---

## Case

- Study key: `patient00045/study1`
- DICOM path: `patient00045/study1/view2_lateral.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.667`
- Label macro score: `0.536`

### Explanation

Critical hallucinated present labels: ['Cardiomegaly', 'Consolidation', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Atelectasis
- Edema
- Pleural Effusion
- Pneumonia
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> Upright PA and lateral chest radiographs demonstrate a single lead AICD in place with the tip in the right ventricle.  Minimal linear stranding opacities are noted at bilateral lung bases, likely due to atelectasis.  No focal areas of consolidation.  No pneumothorax, pleural effusions, or pulmonary edema.  Calcified plaque is seen within the aortic arch.  The descending thoracic aorta is mildly tortuous. The cardiac silhouette size is within normal limits and otherwise the remainder of the cardiomediastinal silhouette is unremarkable.  The skeletal structures are grossly unremarkable. 1.  SINGLE LEAD AICD IN PLACE WITH THE TIP IN THE RIGHT VENTRICLE.  2.  MINIMAL BIBASILAR ATELECTASIS.  NO FOCAL CONSOLIDATION. NARRATIVE: TWO VIEWS OF THE CHEST:  March 10  COMPARISON:  None.  CLINICAL HISTORY:   A 69-year-old woman with atrial tachycardia. Bandemia status post procedure, rule out pneumoni ...[truncated]

---

## Case

- Study key: `patient00048/study1`
- DICOM path: `patient00048/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.500`
- Label macro score: `0.571`

### Explanation

Critical hallucinated present labels: ['Edema', 'Lung Opacity']

### Ground Truth Present Labels

- Pneumothorax
- Support Devices

### Predicted Present Labels

- Edema
- Lung Opacity
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> The left chest tube remains in place. There is now a small loculated pneumothorax at the lung base. PORTABLE CHEST, SINGLE VIEW, #0336146: 9-22-2005. FINDINGS: The loculated basilar pneumothorax is minimally larger after removal of the chest tube. 1.  SMALL LEFT PNEUMOTHORAX AFTER REMOVAL OF THE CHEST TUBE. NARRATIVE: PORTABLE CHEST, SINGLE VIEW, #227-862-903-031: 9/22/2005. FINDINGS: The left chest tube remains in place. There is now a small loculated pneumothorax at the lung base. PORTABLE CHEST, SINGLE VIEW, #0336146: 9-22-2005. FINDINGS: The loculated basilar pneumothorax is minimally larger after removal of the chest tube. IMPRESSION: 1.  SMALL LEFT PNEUMOTHORAX AFTER REMOVAL OF THE CHEST TUBE. SUMMARY:4-POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION.   ACCESSION NUMBER: 0336146 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associate ...[truncated]

---

## Case

- Study key: `patient00049/study2`
- DICOM path: `patient00049/study2/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.667`
- Label macro score: `0.607`

### Explanation

Critical hallucinated present labels: ['Atelectasis'] Critical missed present labels: ['Pneumothorax']

### Ground Truth Present Labels

- Edema
- Lung Opacity
- Pneumothorax
- Support Devices

### Predicted Present Labels

- Atelectasis
- Edema
- Lung Opacity

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Pleural Effusion: predicted `uncertain`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `present`
- Fracture: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1.  AP VIEW OF THE SEMIERECT CHEST DATED 11-19 AT 2019 HOURS SHOWS INTERVAL PLACEMENT OF RIGHT INTERNAL JUGULAR VENOUS CATHETER.  NO PNEUMOTHORAX.  2.  LUNG VOLUMES ARE LOW AND THERE ARE BILATERAL PATCHY OPACITIES PREDOMINANTLY IN THE MID LUNG ZONES, WHICH CAN BE CONSISTENT WITH THE LOW LUNG VOLUMES VERSUS PULMONARY EDEMA VERSUS INFILTRATES. NARRATIVE: SINGLE AP VIEW OF THE CHEST:  11/19/2006 AT 2019 HOURS  COMPARISON:  11-19-06 at 1548 hours.  CLINICAL HISTORY:  62-year-old male with periureteral abscess status post line placement.  IMPRESSION: 1.  AP VIEW OF THE SEMIERECT CHEST DATED 11-19 AT 2019 HOURS SHOWS INTERVAL PLACEMENT OF RIGHT INTERNAL JUGULAR VENOUS CATHETER.  NO PNEUMOTHORAX.  2.  LUNG VOLUMES ARE LOW AND THERE ARE BILATERAL PATCHY OPACITIES PREDOMINANTLY IN THE MID LUNG ZONES, WHICH CAN BE CONSISTENT WITH THE LOW LUNG VOLUMES VERSUS PULMONARY EDEMA VERSUS INFILTRATES.  SUM ...[truncated]

---

## Case

- Study key: `patient00049/study1`
- DICOM path: `patient00049/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.731`

### Explanation

Critical missed present labels: ['Edema', 'Pleural Effusion']

### Ground Truth Present Labels

- Edema
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- None

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Edema: predicted `absent`, ground truth `present`
- Pleural Effusion: predicted `absent`, ground truth `present`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> Lung volumes are decreased.  Trachea is midline.  Cardiomediastinal silhouette is normal in size and configuration.  Minimal atherosclerotic calcifications of the aortic knob are noted.  The bilateral hila are unremarkable.  The lung fields are clear, without focal opacities.  There is no evidence of pneumothorax, pulmonary edema or pleural effusions.  The visualized osseous structures reveal no acute abnormalities. 1.  LOW LUNG VOLUMES. 2.  NO EVIDENCE OF FOCAL PULMONARY PARENCHYMAL CONSOLIDATION OR OTHER ACUTE CARDIOPULMONARY ABNORMALITIES. NARRATIVE: PORTABLE CHEST RADIOGRAPH ONE VIEW: 5-25-2001: CLINICAL HISTORY: 62-year-old male presents with weakness. COMPARISON:  None. TECHNIQUE:  Portable AP upright view of the chest. FINDINGS: Lung volumes are decreased.  Trachea is midline.  Cardiomediastinal silhouette is normal in size and configuration.  Minimal atherosclerotic calcification ...[truncated]

---

## Case

- Study key: `patient00055/study2`
- DICOM path: `patient00055/study2/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `1.000`
- Label macro score: `0.643`

### Explanation

Critical hallucinated present labels: ['Consolidation'] Critical missed present labels: ['Pneumothorax']

### Ground Truth Present Labels

- Pneumothorax

### Predicted Present Labels

- Consolidation

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `absent`, ground truth `present`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> A significant left pneumothorax has developed. There is no evidence of left-to-right shift of the midline structures. The right lung is clear. The cardiac configuration is normal. LEFT PNEUMOTHORAX. RESULTS CALLED TO md grimes AT 1118 HOURS. NARRATIVE: CHEST, PA AND LATERAL PROJECTION: CLINICAL INFORMATION: 42-year-old female patient with cough and wheeze, postoperative right hepatic lobectomy. COMPARISON: 10-9-2017 FINDINGS: A significant left pneumothorax has developed. There is no evidence of left-to-right shift of the midline structures. The right lung is clear. The cardiac configuration is normal. IMPRESSION: LEFT PNEUMOTHORAX. RESULTS CALLED TO md grimes AT 1118 HOURS. END OF IMPRESSION:   ACCESSION NUMBER: 7734-5864-4 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00055/study2`
- DICOM path: `patient00055/study2/view2_lateral.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.250`
- Label macro score: `0.429`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Enlarged Cardiomediastinum', 'Lung Opacity', 'Pleural Effusion', 'Pneumonia']

### Ground Truth Present Labels

- Pneumothorax

### Predicted Present Labels

- Atelectasis
- Consolidation
- Enlarged Cardiomediastinum
- Lung Opacity
- Pleural Effusion
- Pneumonia
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> A significant left pneumothorax has developed. There is no evidence of left-to-right shift of the midline structures. The right lung is clear. The cardiac configuration is normal. LEFT PNEUMOTHORAX. RESULTS CALLED TO md grimes AT 1118 HOURS. NARRATIVE: CHEST, PA AND LATERAL PROJECTION: CLINICAL INFORMATION: 42-year-old female patient with cough and wheeze, postoperative right hepatic lobectomy. COMPARISON: 10-9-2017 FINDINGS: A significant left pneumothorax has developed. There is no evidence of left-to-right shift of the midline structures. The right lung is clear. The cardiac configuration is normal. IMPRESSION: LEFT PNEUMOTHORAX. RESULTS CALLED TO md grimes AT 1118 HOURS. END OF IMPRESSION:   ACCESSION NUMBER: 7734-5864-4 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00055/study3`
- DICOM path: `patient00055/study3/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.333`
- Label macro score: `0.571`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Lung Opacity', 'Pleural Effusion']

### Ground Truth Present Labels

- Pneumothorax
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. THERE HAS BEEN INTERVAL PLACEMENT OF A LEFT CHEST TUBE WITH ONLY A RESIDUAL AMOUNT OF LUCENCY SURROUNDING THE TIP OF THE CHEST TUBE, CONSISTENT WITH RESIDUAL PNEUMOTHORAX. THE LEFT LUNG IS ALMOST COMPLETELY RE-EXPANDED. 2. SOME PATCHY OPACITIES PERSIST IN THE LEFT LUNG BASE AND THE PERIPHERY OF THE LEFT LUNG, LIKELY RESIDUAL ATELECTASIS FOLLOWING RE-EXPANSION. 3. RIGHT LUNG IS CLEAR. NARRATIVE: PORTABLE CHEST, SINGLE VIEW: 7-3-2016 COMPARISON: 2016 JULY 3 IMPRESSION: 1. THERE HAS BEEN INTERVAL PLACEMENT OF A LEFT CHEST TUBE WITH ONLY A RESIDUAL AMOUNT OF LUCENCY SURROUNDING THE TIP OF THE CHEST TUBE, CONSISTENT WITH RESIDUAL PNEUMOTHORAX. THE LEFT LUNG IS ALMOST COMPLETELY RE-EXPANDED. 2. SOME PATCHY OPACITIES PERSIST IN THE LEFT LUNG BASE AND THE PERIPHERY OF THE LEFT LUNG, LIKELY RESIDUAL ATELECTASIS FOLLOWING RE-EXPANSION. 3. RIGHT LUNG IS CLEAR. END OF IMPRESSION. SUMMARY: 2 ABNOR ...[truncated]

---

## Case

- Study key: `patient00055/study1`
- DICOM path: `patient00055/study1/view1_frontal.dcm`
- Judge decision: **REVIEW**
- Disease F1: `1.000`
- Label macro score: `0.821`

### Explanation

Partial/uncertain matches: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Lung Opacity', 'Support Devices']

### Ground Truth Present Labels

- Support Devices

### Predicted Present Labels

- None

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. INTERVAL PLACEMENT OF RIGHT IJ VENOUS CATHETER WITH THE TIP IN THE SUPERIOR VENA CAVA. INTERVAL PLACEMENT OF NASOGASTRIC TUBE WITH THE TIP IN THE STOMACH AND SIDE PORT IN THE DISTAL ESOPHAGUS. NEW INTRA-ABDOMINAL DRAIN ALSO PARTIALLY VISUALIZED. 2. THE LUNGS ARE CLEAR. NO CONSOLIDATION OR PLEURAL EFFUSION. 3. CARDIOMEDIASTINAL SILHOUETTE WITHIN NORMAL LIMITS. NARRATIVE: PORTABLE CHEST RADIOGRAPH: 11/12/2003 COMPARISON: 11-12-2003 IMPRESSION: 1. INTERVAL PLACEMENT OF RIGHT IJ VENOUS CATHETER WITH THE TIP IN THE SUPERIOR VENA CAVA. INTERVAL PLACEMENT OF NASOGASTRIC TUBE WITH THE TIP IN THE STOMACH AND SIDE PORT IN THE DISTAL ESOPHAGUS. NEW INTRA-ABDOMINAL DRAIN ALSO PARTIALLY VISUALIZED. 2. THE LUNGS ARE CLEAR. NO CONSOLIDATION OR PLEURAL EFFUSION. 3. CARDIOMEDIASTINAL SILHOUETTE WITHIN NORMAL LIMITS. END OF IMPRESSION: SUMMARY: 4 POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION I have pe ...[truncated]

---

## Case

- Study key: `patient00058/study1`
- DICOM path: `patient00058/study1/view1_frontal.dcm`
- Judge decision: **REVIEW**
- Disease F1: `0.000`
- Label macro score: `0.769`

### Explanation

Partial/uncertain matches: ['Atelectasis', 'Consolidation', 'Fracture', 'Lung Lesion', 'Lung Opacity', 'Pleural Other'] Disease present-label F1 below threshold: 0.000

### Ground Truth Present Labels

- Fracture

### Predicted Present Labels

- None

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `present`
- Lung Lesion: predicted `absent`, ground truth `uncertain`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> On the current chest examination, there is fracture deformity of the right posterolateral eighth rib again noted. This is at upper limits of normal. Soft tissues are within normal limits. The lungs are clear. The previously possible lung nodule is no longer evident and may represent a confluence of normal shadows. 1. CHEST IS WITHIN NORMAL LIMITS. COMPARISON FROM THE PRIOR DAY'S EXAMINATION INDICATES NO LUNG NODULES ARE NOW EVIDENT. AGAIN SEEN ARE MULTIPLE RIB FRACTURE DEFORMITIES ON THE RIGHT. NARRATIVE: CHEST: 5-17-01. COMPARISON: 2001/5/17. FINDINGS: On the current chest examination, there is fracture deformity of the right posterolateral eighth rib again noted. This is at upper limits of normal. Soft tissues are within normal limits. The lungs are clear. The previously possible lung nodule is no longer evident and may represent a confluence of normal shadows. IMPRESSION: 1. CHEST IS ...[truncated]

---

## Case

- Study key: `patient00058/study1`
- DICOM path: `patient00058/study1/view2_lateral.dcm`
- Judge decision: **FAIL**
- Disease F1: `1.000`
- Label macro score: `0.538`

### Explanation

Critical hallucinated present labels: ['Consolidation', 'Lung Opacity', 'Pneumonia']

### Ground Truth Present Labels

- Fracture

### Predicted Present Labels

- Consolidation
- Lung Opacity
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `absent`, ground truth `present`
- Lung Lesion: predicted `absent`, ground truth `uncertain`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> On the current chest examination, there is fracture deformity of the right posterolateral eighth rib again noted. This is at upper limits of normal. Soft tissues are within normal limits. The lungs are clear. The previously possible lung nodule is no longer evident and may represent a confluence of normal shadows. 1. CHEST IS WITHIN NORMAL LIMITS. COMPARISON FROM THE PRIOR DAY'S EXAMINATION INDICATES NO LUNG NODULES ARE NOW EVIDENT. AGAIN SEEN ARE MULTIPLE RIB FRACTURE DEFORMITIES ON THE RIGHT. NARRATIVE: CHEST: 5-17-01. COMPARISON: 2001/5/17. FINDINGS: On the current chest examination, there is fracture deformity of the right posterolateral eighth rib again noted. This is at upper limits of normal. Soft tissues are within normal limits. The lungs are clear. The previously possible lung nodule is no longer evident and may represent a confluence of normal shadows. IMPRESSION: 1. CHEST IS ...[truncated]

---

## Case

- Study key: `patient00064/study1`
- DICOM path: `patient00064/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.400`
- Label macro score: `0.571`

### Explanation

Critical hallucinated present labels: ['Consolidation'] Critical missed present labels: ['Edema']

### Ground Truth Present Labels

- Edema
- Lung Opacity
- Support Devices

### Predicted Present Labels

- Consolidation
- Fracture
- Lung Opacity

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `absent`, ground truth `present`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> Portable AP supine view of the chest demonstrates an endotracheal tube  approximately 5 cm above the carina.  External pacer pads overlying the right hemithorax and the left costophrenic angle. Cardiomediastinal silhouette is unremarkable.  Ground-glass opacities bilaterally with mild peribronchial cuffing, cannot exclude interstitial edema.  Bony structures and soft tissues appear normal. 1.  ENDOTRACHEAL TUBE  WITH DISTAL TIP BETWEEN THE CLAVICLES AND CARINA.  2.  GROUND-GLASS OPACITY AND MILD PERIBRONCHIAL CUFFING, CANNOT EXCLUDE INTERSTITIAL EDEMA. NARRATIVE: SINGLE VIEW OF THE CHEST:   2/6/2007 at 2154 hours  CLINICAL HISTORY:   A 63-year-old male with a subdural hematoma.  COMPARISON:   None.  FINDINGS:  Portable AP supine view of the chest demonstrates an endotracheal tube  approximately 5 cm above the carina.  External pacer pads overlying the right hemithorax and the left costop ...[truncated]

---

## Case

- Study key: `patient00067/study4`
- DICOM path: `patient00067/study4/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.400`
- Label macro score: `0.607`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Lung Opacity']

### Ground Truth Present Labels

- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. LEFT SIDED INTERNAL JUGULAR LINE THAT HAS BEEN REMOVED. 2. SMALL RIGHT SIDED PLEURAL EFFUSION. 3. BILATERAL LOWER LUNG FIELD NODULAR DENSITIES WHICH MAY REPRESENT NIPPLE SHADOWS BUT IF CONCERN FOR OTHER ETIOLOGY, SUGGEST REPEAT STUDY WITH NIPPLE MARKERS. 4. LOW LUNG VOLUMES. 5. PREVIOUSLY NOTED LEFT SIDED CAVITARY LESION IS NOT VISUALIZED ON THE CURRENT STUDY, IN ITS LOCATION THERE IS A LINEAR DENSITY WHICH MAY REPRESENT AN INFECTIOUS PROCESS OR SCAR. 6. OTHERWISE, NO SIGNIFICANT INTERVAL CHANGE OF THE CHEST. NARRATIVE: SINGLE AP PORTABLE CHEST: DATE OF EXAMINATION: 1/30/2009 COMPARISON: 1/30/2009 HISTORY: 56 year old female pre-liver. Ascites. Concern for SBP. Status post thoracentesis of left pleural effusion. TECHNIQUE: Single AP semi-upright portable view of the chest. IMPRESSION: 1. LEFT SIDED INTERNAL JUGULAR LINE THAT HAS BEEN REMOVED. 2. SMALL RIGHT SIDED PLEURAL EFFUSION. 3. ...[truncated]

---

## Case

- Study key: `patient00067/study3`
- DICOM path: `patient00067/study3/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.800`
- Label macro score: `0.679`

### Explanation

Critical hallucinated present labels: ['Atelectasis']

### Ground Truth Present Labels

- Consolidation
- Pneumothorax
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. LEFT IJ LINE REMAINS IN PLACE. 2. THERE IS INTERVAL DEVELOPMENT OF A SMALL CAVITARY LESION IN THE LEFT MID LUNG ZONE, IN AN AREA WHERE A SMALL CONSOLIDATION WAS SEEN ON THE PRIOR CHEST FILMS ON 6/17/1998 THROUGH 6-20-1998. 3. A LINEAR SHADOW IN THE LEFT LOWER LATERAL HEMITHORAX MAY REPRESENT THE PATIENT'S BREAST SHADOW, ALTHOUGH A PNEUMOTHORAX IS NOT ENTIRELY EXCLUDED. RECOMMEND REPEAT PA AND LATERAL CHEST FILMS. LUNG FIELDS ARE OTHERWISE CLEAR. FINDINGS COMMUNICATED TO THE NURSE (Simmons Lucille, PA) TAKING CARE OF THE PATIENT. NARRATIVE: CHEST, TWO VIEWS: 3/22/2004. COMPARISON: 3-22-04. IMPRESSION: 1. LEFT IJ LINE REMAINS IN PLACE. 2. THERE IS INTERVAL DEVELOPMENT OF A SMALL CAVITARY LESION IN THE LEFT MID LUNG ZONE, IN AN AREA WHERE A SMALL CONSOLIDATION WAS SEEN ON THE PRIOR CHEST FILMS ON 6/17/1998 THROUGH 6-20-1998. 3. A LINEAR SHADOW IN THE LEFT LOWER LATERAL HEMITHORAX MAY REP ...[truncated]

---

## Case

- Study key: `patient00067/study1`
- DICOM path: `patient00067/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.667`
- Label macro score: `0.643`

### Explanation

Critical hallucinated present labels: ['Lung Opacity']

### Ground Truth Present Labels

- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. INTERVAL PLACEMENT OF A LEFT INTERNAL JUGULAR LINE WITH ITS TIP IN THE LOW-SVC. NO PNEUMOTHORAX IS APPARENT. 2. ELEVATED RIGHT HEMIDIAPHRAGM WITH A POSSIBLE TINY RIGHT PLEURAL EFFUSION. THE LUNGS ARE OTHERWISE CLEAR. NO SIGNIFICANT INTERVAL CHANGE. NARRATIVE: CHEST: 11-16-2015 0832 hours COMPARISON: 11/16/2015 0640 hours CLINICAL HISTORY: 56 -year-old female, cirrhosis and hepatic encephalopathy. IMPRESSION: 1. INTERVAL PLACEMENT OF A LEFT INTERNAL JUGULAR LINE WITH ITS TIP IN THE LOW-SVC. NO PNEUMOTHORAX IS APPARENT. 2. ELEVATED RIGHT HEMIDIAPHRAGM WITH A POSSIBLE TINY RIGHT PLEURAL EFFUSION. THE LUNGS ARE OTHERWISE CLEAR. NO SIGNIFICANT INTERVAL CHANGE. END OF IMPRESSION: SUMMARY:2-ABNORMAL, PREVIOUSLY REPORTED I have personally reviewed the images for this examination and agree with the report transcribed above. By: Dalton, Christensen  on: 11-16-2015   ACCESSION NUMBER: 19400 This ...[truncated]

---

## Case

- Study key: `patient00067/study2`
- DICOM path: `patient00067/study2/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.400`
- Label macro score: `0.500`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Lung Opacity']

### Ground Truth Present Labels

- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THE PATIENT IS ROTATED TO THE RIGHT ON THIS FILM. OTHERWISE, THERE IS GROSSLY NO SIGNIFICANT INTERVAL CHANGE WITH STABLE POSITION OF SUPPORTIVE DEVICES AND PERSISTENT LOW LUNG VOLUMES. 2. REDEMONSTRATION OF SMALL RIGHT PLEURAL EFFUSION. THE LUNGS ARE, OTHERWISE, CLEAR BILATERALLY. NARRATIVE: SINGLE RADIOGRAPH OF THE CHEST: april 2018 COMPARISON: Prior chest dated 4/24/2018. CLINICAL HISTORY: This is a 56-year-old female with history of hepatic encephalopathy. IMPRESSION: 1. THE PATIENT IS ROTATED TO THE RIGHT ON THIS FILM. OTHERWISE, THERE IS GROSSLY NO SIGNIFICANT INTERVAL CHANGE WITH STABLE POSITION OF SUPPORTIVE DEVICES AND PERSISTENT LOW LUNG VOLUMES. 2. REDEMONSTRATION OF SMALL RIGHT PLEURAL EFFUSION. THE LUNGS ARE, OTHERWISE, CLEAR BILATERALLY. END OF IMPRESSION SUMMARY:4-POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION I have personally reviewed the images for this examination an ...[truncated]

---

## Case

- Study key: `patient00068/study1`
- DICOM path: `patient00068/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `1.000`
- Label macro score: `0.500`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Cardiomegaly', 'Lung Opacity'] Critical missed present labels: ['Edema']

### Ground Truth Present Labels

- Edema

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Lung Opacity

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `present`
- Pleural Effusion: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> Single AP portable view of the chest demonstrates cephalization of the central vessels consistent with pulmonary venous hypertension. No evidence of frank pulmonary edema is noted. Cardiomediastinal silhouette appears unremarkable. Lungs are clear bilaterally. Visualized bones are intact. No soft tissue abnormalities are appreciated. 1. NO EVIDENCE OF PNEUMOTHORAX. 2. CEPHALIZATION OF CENTRAL VESSELS SUGGESTIVE OF PULMONARY VENOUS HYPERTENSION WITH NO FRANK PULMONARY EDEMA. NARRATIVE: PORTABLE CHEST, SINGLE AP VIEW: 12/5/2019. COMPARISON: None. FINDINGS: Single AP portable view of the chest demonstrates cephalization of the central vessels consistent with pulmonary venous hypertension. No evidence of frank pulmonary edema is noted. Cardiomediastinal silhouette appears unremarkable. Lungs are clear bilaterally. Visualized bones are intact. No soft tissue abnormalities are appreciated. IMP ...[truncated]

---

## Case

- Study key: `patient00070/study1`
- DICOM path: `patient00070/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.769`

### Explanation

Critical missed present labels: ['Consolidation', 'Pleural Effusion', 'Pneumothorax']

### Ground Truth Present Labels

- Consolidation
- Pleural Effusion
- Pneumothorax

### Predicted Present Labels

- None

### Partial Or Mismatched Labels

- Consolidation: predicted `absent`, ground truth `present`
- Pleural Effusion: predicted `absent`, ground truth `present`
- Pneumothorax: predicted `absent`, ground truth `present`

### Ground Truth Report Excerpt

> 1.SINGLE FRONTAL VIEW OF THE CHEST DEMONSTRATES NO EVIDENCE OF FOCAL  AIR SPACE CONSOLIDATION, PLEURAL EFFUSION, OR PNEUMOTHORAX.   2.THE CARDIOMEDIASTINAL SILHOUETTE AND PULMONARY VASCULARITY ARE  WITHIN NORMAL LIMITS.   3.THE OSSEOUS STRUCTURES ARE NORMAL IN APPEARANCE. NARRATIVE: EXAM: CHEST 1 VIEW 1/9/2009   CLINICAL HISTORY: (+) PPD R/O ACTIVE TB   COMPARISON: NONE     IMPRESSION:   1.SINGLE FRONTAL VIEW OF THE CHEST DEMONSTRATES NO EVIDENCE OF FOCAL  AIR SPACE CONSOLIDATION, PLEURAL EFFUSION, OR PNEUMOTHORAX.   2.THE CARDIOMEDIASTINAL SILHOUETTE AND PULMONARY VASCULARITY ARE  WITHIN NORMAL LIMITS.   3.THE OSSEOUS STRUCTURES ARE NORMAL IN APPEARANCE.     SUMMARY:1-NO SIGNIFICANT ABNORMALITY   ACCESSION NUMBER: 7088267 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00076/study1`
- DICOM path: `patient00076/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.667`
- Label macro score: `0.643`

### Explanation

Critical hallucinated present labels: ['Consolidation', 'Edema']

### Ground Truth Present Labels

- Lung Opacity
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> AP portable chest, 5/4/2007 at 1536 hours is compared with 5/4/2007, 1/29/2013 two view chest. Substantially lower lung volumes. Focal right upper lobe peripheral parenchymal airspace opacity adjacent to the minor fissure may represent focal infection. Probable left pleural effusion. New right internal jugular central venous catheter in superior vena cava. Low lung volumes. No definite pneumothorax although motion artifact degrades image quality. 1. RIGHT IJ CENTRAL VENOUS PRESSURE SATISFACTORY. 2. NEW AIRSPACE OPACITY RIGHT UPPER LOBE AS DESCRIBED. 3. LIMITED BY MOTION ARTIFACT. 4. LOW LUNG VOLUMES AND POSSIBLE LEFT PLEURAL EFFUSION. NARRATIVE: PORTABLE CHEST, 5-4-2007 CLINICAL HISTORY: Intracranial aneurysm. Rule out subarachnoid hemorrhage. Status post central venous catheter placement. FINDINGS: AP portable chest, 5/4/2007 at 1536 hours is compared with 5/4/2007, 1/29/2013 two view c ...[truncated]

---

## Case

- Study key: `patient00078/study6`
- DICOM path: `patient00078/study6/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.500`
- Label macro score: `0.714`

### Explanation

Critical hallucinated present labels: ['Consolidation']

### Ground Truth Present Labels

- Pneumothorax

### Predicted Present Labels

- Consolidation
- Fracture
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> The left-sided pneumothorax appears slightly increased in size. No additional interval change. 6340977630: SINGLE VIEW PORTABLE CHEST: 5-6-2010 Health Plus Xpress 0620 HOURS FINDINGS: The left pneumothorax has decreased in size. No new abnormalities. DECREASED SIZE OF LEFT PNEUMOTHORAX ON THE MOST RECENT FILM. NARRATIVE: 9587870496: SINGLE VIEW PORTABLE CHEST: 5/6/10 Health Plus Xpress 0615 HOURS COMPARISON: MAY 2010 FINDINGS: The left-sided pneumothorax appears slightly increased in size. No additional interval change. 6340977630: SINGLE VIEW PORTABLE CHEST: 5-6-2010 Health Plus Xpress 0620 HOURS FINDINGS: The left pneumothorax has decreased in size. No new abnormalities. IMPRESSION: DECREASED SIZE OF LEFT PNEUMOTHORAX ON THE MOST RECENT FILM. END OF IMPRESSION: SUMMARY: 2 ABNORMAL, PREVIOUSLY REPORTED   ACCESSION NUMBER: 634.097.763.0 This report has been anonymized. All dates are offs ...[truncated]

---

## Case

- Study key: `patient00078/study7`
- DICOM path: `patient00078/study7/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.667`
- Label macro score: `0.714`

### Explanation

Critical hallucinated present labels: ['Consolidation']

### Ground Truth Present Labels

- Pneumothorax
- Support Devices

### Predicted Present Labels

- Consolidation
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> The left chest tube is again noted. The volume of pneumothorax has increased slightly. 49335592 SINGLE RADIOGRAPH OF THE CHEST: FINDINGS: No interval change. 402809495 SINGLE RADIOGRAPH OF THE CHEST: FINDINGS: The chest tube has been replaced by an apical pigtail catheter. The pneumothorax is not identified. DIMINISHED PNEUMOTHORAX AFTER PLACEMENT OF PIGTAIL CATHETER. NARRATIVE: SINGLE RADIOGRAPH OF THE CHEST: 1/14/2015 FINDINGS: The left chest tube is again noted. The volume of pneumothorax has increased slightly. 49335592 SINGLE RADIOGRAPH OF THE CHEST: FINDINGS: No interval change. 402809495 SINGLE RADIOGRAPH OF THE CHEST: FINDINGS: The chest tube has been replaced by an apical pigtail catheter. The pneumothorax is not identified. IMPRESSION: DIMINISHED PNEUMOTHORAX AFTER PLACEMENT OF PIGTAIL CATHETER. END OF IMPRESSION SUMMARY: 2 ABNORMAL, PREVIOUSLY REPORTED.   ACCESSION NUMBER: 402 ...[truncated]

---

## Case

- Study key: `patient00078/study9`
- DICOM path: `patient00078/study9/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.857`

### Explanation

Critical missed present labels: ['Pneumothorax']

### Ground Truth Present Labels

- Pneumothorax
- Support Devices

### Predicted Present Labels

- None

### Partial Or Mismatched Labels

- Consolidation: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `present`
- Fracture: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> The left chest tube is again noted. The volume of pneumothorax has increased slightly. 7172 SINGLE RADIOGRAPH OF THE CHEST: FINDINGS: No interval change. 2911246394 SINGLE RADIOGRAPH OF THE CHEST: FINDINGS: The chest tube has been replaced by an apical pigtail catheter. The pneumothorax is not identified. DIMINISHED PNEUMOTHORAX AFTER PLACEMENT OF PIGTAIL CATHETER. NARRATIVE: SINGLE RADIOGRAPH OF THE CHEST: 4/5/2000 FINDINGS: The left chest tube is again noted. The volume of pneumothorax has increased slightly. 7172 SINGLE RADIOGRAPH OF THE CHEST: FINDINGS: No interval change. 2911246394 SINGLE RADIOGRAPH OF THE CHEST: FINDINGS: The chest tube has been replaced by an apical pigtail catheter. The pneumothorax is not identified. IMPRESSION: DIMINISHED PNEUMOTHORAX AFTER PLACEMENT OF PIGTAIL CATHETER. END OF IMPRESSION SUMMARY: 2 ABNORMAL, PREVIOUSLY REPORTED.   ACCESSION NUMBER: #7172 This ...[truncated]

---

## Case

- Study key: `patient00078/study5`
- DICOM path: `patient00078/study5/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `1.000`
- Label macro score: `0.786`

### Explanation

Critical hallucinated present labels: ['Atelectasis'] Critical missed present labels: ['Pneumothorax']

### Ground Truth Present Labels

- Pneumothorax

### Predicted Present Labels

- Atelectasis

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `present`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> The left-sided pneumothorax appears slightly increased in size. No additional interval change. 865_804_567_991_957_3: SINGLE VIEW PORTABLE CHEST: 1/18/2017 USC Center for Body Computing 0620 HOURS FINDINGS: The left pneumothorax has decreased in size. No new abnormalities. DECREASED SIZE OF LEFT PNEUMOTHORAX ON THE MOST RECENT FILM. NARRATIVE: 397381515: SINGLE VIEW PORTABLE CHEST: 1-18-2017 usc center for body computing 0615 HOURS COMPARISON: 1/18/2017 FINDINGS: The left-sided pneumothorax appears slightly increased in size. No additional interval change. 865_804_567_991_957_3: SINGLE VIEW PORTABLE CHEST: 1/18/2017 USC Center for Body Computing 0620 HOURS FINDINGS: The left pneumothorax has decreased in size. No new abnormalities. IMPRESSION: DECREASED SIZE OF LEFT PNEUMOTHORAX ON THE MOST RECENT FILM. END OF IMPRESSION: SUMMARY: 2 ABNORMAL, PREVIOUSLY REPORTED   ACCESSION NUMBER: 39738 ...[truncated]

---

## Case

- Study key: `patient00078/study4`
- DICOM path: `patient00078/study4/view1_frontal.dcm`
- Judge decision: **REVIEW**
- Disease F1: `0.667`
- Label macro score: `0.857`

### Explanation

Non-critical status mismatches: ['Fracture'] Partial/uncertain matches: ['Lung Opacity', 'Support Devices'] Disease present-label F1 below threshold: 0.667

### Ground Truth Present Labels

- Pneumothorax

### Predicted Present Labels

- Fracture
- Pneumothorax

### Partial Or Mismatched Labels

- Fracture: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> The left pneumothorax has significantly decreased in size. No new abnormalities. #5153155048 SINGLE VIEW PORTABLE CHEST: 12-16-2005 at 0600 HOURS. FINDINGS: The left pneumothorax has increased slightly in size. 1. SLIGHT INCREASE IN LEFT APICAL PNEUMOTHORAX ON THE MOST RECENT FILM. NARRATIVE: 19952991367 SINGLE VIEW PORTABLE CHEST: 12/16/2005 AT 1550 HOURS. COMPARISON: December 16 AT 1432 HOURS. FINDINGS: The left pneumothorax has significantly decreased in size. No new abnormalities. #5153155048 SINGLE VIEW PORTABLE CHEST: 12-16-2005 at 0600 HOURS. FINDINGS: The left pneumothorax has increased slightly in size. IMPRESSION: 1. SLIGHT INCREASE IN LEFT APICAL PNEUMOTHORAX ON THE MOST RECENT FILM. END OF IMPRESSION: SUMMARY: 4 POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION.   ACCESSION NUMBER: 51.53.15.50.48 This report has been anonymized. All dates are offset from the actual dates by a fi ...[truncated]

---

## Case

- Study key: `patient00078/study1`
- DICOM path: `patient00078/study1/view1_frontal.dcm`
- Judge decision: **REVIEW**
- Disease F1: `1.000`
- Label macro score: `0.893`

### Explanation

Partial/uncertain matches: ['Fracture', 'Pleural Other', 'Support Devices']

### Ground Truth Present Labels

- Pneumothorax
- Support Devices

### Predicted Present Labels

- Pneumothorax

### Partial Or Mismatched Labels

- Fracture: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> Portable upright chest radiograph obtained in the recovery room demonstrates a left chest tube in place. The end of the chest tube is bent at the apex with the tip directed toward the mediastinum. Surgical suture material is seen to project over the right upper lung zone as well as the left upper lung zone. There are multiple linear densities projecting over the upper chest, likely external to the patient related to the sheets. This limits the evaluation for a pneumothorax; however, there may be a possible small left apical pneumothorax present. The lungs are otherwise clear with no pleural effusions or pulmonary edema. The cardiomediastinal silhouette is unremarkable. The skeletal structures are grossly unremarkable. 1. LEFT CHEST TUBE IN PLACE WITH THE TIP DIRECTED TOWARD THE MEDIASTINUM. 2. POSTOPERATIVE CHEST WITH ARTIFACTS PROJECTING OVER THE CHEST, WHICH LIMITS THE EVALUATION FOR A ...[truncated]

---

## Case

- Study key: `patient00078/study8`
- DICOM path: `patient00078/study8/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.893`

### Explanation

Critical missed present labels: ['Pneumothorax']

### Ground Truth Present Labels

- Pneumothorax
- Support Devices

### Predicted Present Labels

- None

### Partial Or Mismatched Labels

- Pneumothorax: predicted `uncertain`, ground truth `present`
- Fracture: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. REDEMONSTRATED LEFT PLEURAL PIGTAIL CATHETER IN THE LEFT APEX. 2. STABLE SMALL LEFT APICAL PNEUMOTHORAX. 3. THE LUNGS ARE CLEAR. 4. CARDIOMEDIASTINAL SILHOUETTE WITHIN NORMAL LIMITS. NARRATIVE: PORTABLE CHEST RADIOGRAPH: 1/20/16. COMPARISON: 1/20/2016. IMPRESSION: 1. REDEMONSTRATED LEFT PLEURAL PIGTAIL CATHETER IN THE LEFT APEX. 2. STABLE SMALL LEFT APICAL PNEUMOTHORAX. 3. THE LUNGS ARE CLEAR. 4. CARDIOMEDIASTINAL SILHOUETTE WITHIN NORMAL LIMITS. END OF IMPRESSION: SUMMARY: 2 ABNORMAL, PREVIOUSLY REPORTED I have personally reviewed the images for this examination and agree with the report transcribed above. By: Beck, Kendrick  on: 1/20/2016   ACCESSION NUMBER: 362952502370 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00078/study3`
- DICOM path: `patient00078/study3/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.333`
- Label macro score: `0.536`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Lung Opacity', 'Pleural Effusion']

### Ground Truth Present Labels

- Pneumothorax

### Predicted Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> The left pneumothorax has significantly decreased in size. No new abnormalities. X830G995434 SINGLE VIEW PORTABLE CHEST: 2012/7/13 at 0600 HOURS. FINDINGS: The left pneumothorax has increased slightly in size. 1. SLIGHT INCREASE IN LEFT APICAL PNEUMOTHORAX ON THE MOST RECENT FILM. NARRATIVE: #61158122 SINGLE VIEW PORTABLE CHEST: 12, July 13 AT 1550 HOURS. COMPARISON: 7-13-2012 AT 1432 HOURS. FINDINGS: The left pneumothorax has significantly decreased in size. No new abnormalities. X830G995434 SINGLE VIEW PORTABLE CHEST: 2012/7/13 at 0600 HOURS. FINDINGS: The left pneumothorax has increased slightly in size. IMPRESSION: 1. SLIGHT INCREASE IN LEFT APICAL PNEUMOTHORAX ON THE MOST RECENT FILM. END OF IMPRESSION: SUMMARY: 4 POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION.   ACCESSION NUMBER: 611-581-22 This report has been anonymized. All dates are offset from the actual dates by a fixed inter ...[truncated]

---

## Case

- Study key: `patient00078/study2`
- DICOM path: `patient00078/study2/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.400`
- Label macro score: `0.607`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation']

### Ground Truth Present Labels

- Pneumothorax
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Fracture
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. RE-DEMONSTRATED LEFT CHEST TUBE. 2. RE-DEMONSTRATED MULTIPLE SUTURE LINES IN THE BILATERAL LUNG APICES. 3. INTERVAL MARKED INCREASE IN THE PREVIOUSLY NOTED LEFT PNEUMOTHORAX. NO EVIDENCE OF MEDIASTINAL SHIFT TO SUGGEST TENSION. 4. FINDINGS WERE DISCUSSED WITH Moyer, Miguel AT 9 AM ON 08/27/2016. NARRATIVE: PORTABLE CHEST RADIOGRAPH, 8/27/2016 AT 1432: Compared with 8/27/2016 at 0911. IMPRESSION: 1. RE-DEMONSTRATED LEFT CHEST TUBE. 2. RE-DEMONSTRATED MULTIPLE SUTURE LINES IN THE BILATERAL LUNG APICES. 3. INTERVAL MARKED INCREASE IN THE PREVIOUSLY NOTED LEFT PNEUMOTHORAX. NO EVIDENCE OF MEDIASTINAL SHIFT TO SUGGEST TENSION. 4. FINDINGS WERE DISCUSSED WITH Moyer, Miguel AT 9 AM ON 08/27/2016. END OF IMPRESSION SUMMARY: 4 POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION. I have personally reviewed the images for this examination and agree with the report transcribed above. By: Douglas Madel ...[truncated]

---

## Case

- Study key: `patient00087/study3`
- DICOM path: `patient00087/study3/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.500`

### Explanation

Critical hallucinated present labels: ['Cardiomegaly', 'Pleural Effusion', 'Pneumothorax']

### Ground Truth Present Labels

- None

### Predicted Present Labels

- Cardiomegaly
- Pleural Effusion
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `uncertain`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `present`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THE LUNGS APPEAR CLEAR WITHOUT A FOCAL PARENCHYMAL PROCESS. 2. THERE IS MINIMAL BLUNTING OF THE RIGHT COSTOPHRENIC ANGLE LIKELY REPRESENTING A SMALL PLEURAL EFFUSION. NARRATIVE: TWO VIEWS OF THE CHEST: 10/17/14. COMPARISON: Comparison is to previous exam from 14/10. IMPRESSION: 1. THE LUNGS APPEAR CLEAR WITHOUT A FOCAL PARENCHYMAL PROCESS. 2. THERE IS MINIMAL BLUNTING OF THE RIGHT COSTOPHRENIC ANGLE LIKELY REPRESENTING A SMALL PLEURAL EFFUSION. END OF IMPRESSION: I have personally reviewed the images for this examination and agree with the report transcribed above. By: Elleah E., Mcknight  on: 10-17-2014   ACCESSION NUMBER: 187-926-422-07 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00087/study3`
- DICOM path: `patient00087/study3/view2_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.692`

### Explanation

Critical hallucinated present labels: ['Consolidation']

### Ground Truth Present Labels

- None

### Predicted Present Labels

- Consolidation

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THE LUNGS APPEAR CLEAR WITHOUT A FOCAL PARENCHYMAL PROCESS. 2. THERE IS MINIMAL BLUNTING OF THE RIGHT COSTOPHRENIC ANGLE LIKELY REPRESENTING A SMALL PLEURAL EFFUSION. NARRATIVE: TWO VIEWS OF THE CHEST: 10/17/14. COMPARISON: Comparison is to previous exam from 14/10. IMPRESSION: 1. THE LUNGS APPEAR CLEAR WITHOUT A FOCAL PARENCHYMAL PROCESS. 2. THERE IS MINIMAL BLUNTING OF THE RIGHT COSTOPHRENIC ANGLE LIKELY REPRESENTING A SMALL PLEURAL EFFUSION. END OF IMPRESSION: I have personally reviewed the images for this examination and agree with the report transcribed above. By: Elleah E., Mcknight  on: 10-17-2014   ACCESSION NUMBER: 187-926-422-07 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00087/study3`
- DICOM path: `patient00087/study3/view3_lateral.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.500`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Lung Opacity', 'Pneumothorax']

### Ground Truth Present Labels

- None

### Predicted Present Labels

- Atelectasis
- Consolidation
- Fracture
- Lung Opacity
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THE LUNGS APPEAR CLEAR WITHOUT A FOCAL PARENCHYMAL PROCESS. 2. THERE IS MINIMAL BLUNTING OF THE RIGHT COSTOPHRENIC ANGLE LIKELY REPRESENTING A SMALL PLEURAL EFFUSION. NARRATIVE: TWO VIEWS OF THE CHEST: 10/17/14. COMPARISON: Comparison is to previous exam from 14/10. IMPRESSION: 1. THE LUNGS APPEAR CLEAR WITHOUT A FOCAL PARENCHYMAL PROCESS. 2. THERE IS MINIMAL BLUNTING OF THE RIGHT COSTOPHRENIC ANGLE LIKELY REPRESENTING A SMALL PLEURAL EFFUSION. END OF IMPRESSION: I have personally reviewed the images for this examination and agree with the report transcribed above. By: Elleah E., Mcknight  on: 10-17-2014   ACCESSION NUMBER: 187-926-422-07 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00087/study1`
- DICOM path: `patient00087/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.333`
- Label macro score: `0.536`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Edema'] Critical missed present labels: ['Pleural Effusion']

### Ground Truth Present Labels

- Lung Opacity
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Lung Opacity

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `uncertain`, ground truth `present`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. ENDOTRACHEAL TUBE, RIGHT IJ CENTRAL LINE, TWO MEDIASTINAL DRAINS WITH ONE OF THEM POSSIBLY PERICARDIAL, STERNOTOMY WIRES ARE UNCHANGED. 2. MILD CEPHALIZATION OF THE VESSELS WITH POSSIBLE LEFT PLEURAL EFFUSION. NARRATIVE: FRONTAL PORTABLE CHEST: 25-18.M. COMPARISON: 2/25/18.M. HISTORY: 52 -year-old male with dissection; check for infiltrates. IMPRESSION: 1. ENDOTRACHEAL TUBE, RIGHT IJ CENTRAL LINE, TWO MEDIASTINAL DRAINS WITH ONE OF THEM POSSIBLY PERICARDIAL, STERNOTOMY WIRES ARE UNCHANGED. 2. MILD CEPHALIZATION OF THE VESSELS WITH POSSIBLE LEFT PLEURAL EFFUSION. END OF IMPRESSION: SUMMARY 4: Possible significant abnormality/change, may need action. I have personally reviewed the images for this examination and agree with the report transcribed above. By: Weston, Lucero  on: 2/25/2018   ACCESSION NUMBER: LC-WI-UT-YS-Q This report has been anonymized. All dates are offset from the actua ...[truncated]

---

## Case

- Study key: `patient00087/study2`
- DICOM path: `patient00087/study2/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.571`
- Label macro score: `0.607`

### Explanation

Critical hallucinated present labels: ['Atelectasis'] Critical missed present labels: ['Cardiomegaly', 'Pneumothorax']

### Ground Truth Present Labels

- Cardiomegaly
- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Predicted Present Labels

- Atelectasis
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `present`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `present`
- Fracture: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THERE HAS BEEN SIGNIFICANT INTERVAL DECREASE IN CARDIOMEGALY, LIKELY RELATED TO RESOLUTION OF THE KNOWN PERICARDIAL EFFUSION. THE HEART SILHOUETTE IS NOW NORMAL. MILD ILL-DEFINED RIGHT PERIHILAR OPACITY, LIKELY RELATED TO RESIDUAL PARENCHYMAL OPACITY AS SEEN ON THE CT FROM 10 December. NO EVIDENCE OF PULMONARY EDEMA OR PNEUMOTHORAX OR PNEUMOMEDIASTINUM. NARRATIVE: CHEST: 2010 7 December. COMPARISON: 12/7/2010. CLINICAL HISTORY: 53-year-old male with pericardial effusion. IMPRESSION: 1. THERE HAS BEEN SIGNIFICANT INTERVAL DECREASE IN CARDIOMEGALY, LIKELY RELATED TO RESOLUTION OF THE KNOWN PERICARDIAL EFFUSION. THE HEART SILHOUETTE IS NOW NORMAL. MILD ILL-DEFINED RIGHT PERIHILAR OPACITY, LIKELY RELATED TO RESIDUAL PARENCHYMAL OPACITY AS SEEN ON THE CT FROM 10 December. NO EVIDENCE OF PULMONARY EDEMA OR PNEUMOTHORAX OR PNEUMOMEDIASTINUM. END OF IMPRESSION: SUMMARY 2: Abnormal, previously ...[truncated]

---

## Case

- Study key: `patient00095/study1`
- DICOM path: `patient00095/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.857`
- Label macro score: `0.786`

### Explanation

Critical hallucinated present labels: ['Cardiomegaly']

### Ground Truth Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Lung Opacity

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> The cardiomediastinal silhouette is at the upper limit of normal. The  aorta is tortuous. Pulmonary vessels are not distended.   No abnormality of the right costophrenic angle. The left costophrenic  angle is not included on the film. No pneumothorax. There is  retrocardiac airspace opacity with partial silhouetting of the left  hemidiaphragm and descending thoracic aorta. Linear opacities at the  right lung base likely represents scar or atelectasis. Lungs are  otherwise clear.   Diffuse osteopenia. No acute osseous abnormalities. 1.  Retrocardiac consolidation may represent infection, atelectasis,  or aspiration. Further evaluation with a lateral radiograph would be  helpful. A follow-up chest radiograph following treatment is also  recommended to document resolution. 2.  Mild right basilar atelectasis or scarring.   I have personally reviewed the images for this examination and agreed ...[truncated]

---

## Case

- Study key: `patient00096/study1`
- DICOM path: `patient00096/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.536`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Lung Opacity', 'Pleural Effusion']

### Ground Truth Present Labels

- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> Diffuse idiopathic skeletal hyperostosis coronary artery bypass graft. Trachea is midline. The mediastinum is unremarkable. No significant change in the heart size. Right subclavian line tip superior vena cava right atrium. No pneumothorax. Distended central pulmonary vessels without kerley "b" lines. Central pulmonary vessels more distended than noted on examination of 8/8/2005. Parenchymal density bilaterally. No evidence of lobar collapse. 1. HISTORY OF NEUTROPENIC FEVER WITH INCREASED VENOUS CONGESTION PRESENT BILATERALLY WITHOUT EVIDENCE OF FOCAL CONSOLIDATION. CONTINUED RADIOGRAPHIC FOLLOW-UP RECOMMENDED. NARRATIVE: CHEST AP AND LATERAL: 8/8/2005 COMPARISON: 8/8/2005. FINDINGS: Diffuse idiopathic skeletal hyperostosis coronary artery bypass graft. Trachea is midline. The mediastinum is unremarkable. No significant change in the heart size. Right subclavian line tip superior vena ca ...[truncated]

---

## Case

- Study key: `patient00096/study1`
- DICOM path: `patient00096/study1/view2_lateral.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.429`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Lung Opacity', 'Pleural Effusion']

### Ground Truth Present Labels

- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> Diffuse idiopathic skeletal hyperostosis coronary artery bypass graft. Trachea is midline. The mediastinum is unremarkable. No significant change in the heart size. Right subclavian line tip superior vena cava right atrium. No pneumothorax. Distended central pulmonary vessels without kerley "b" lines. Central pulmonary vessels more distended than noted on examination of 8/8/2005. Parenchymal density bilaterally. No evidence of lobar collapse. 1. HISTORY OF NEUTROPENIC FEVER WITH INCREASED VENOUS CONGESTION PRESENT BILATERALLY WITHOUT EVIDENCE OF FOCAL CONSOLIDATION. CONTINUED RADIOGRAPHIC FOLLOW-UP RECOMMENDED. NARRATIVE: CHEST AP AND LATERAL: 8/8/2005 COMPARISON: 8/8/2005. FINDINGS: Diffuse idiopathic skeletal hyperostosis coronary artery bypass graft. Trachea is midline. The mediastinum is unremarkable. No significant change in the heart size. Right subclavian line tip superior vena ca ...[truncated]

---

## Case

- Study key: `patient00096/study2`
- DICOM path: `patient00096/study2/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `1.000`
- Label macro score: `0.571`

### Explanation

Critical hallucinated present labels: ['Consolidation', 'Lung Opacity'] Critical missed present labels: ['Edema']

### Ground Truth Present Labels

- Edema
- Support Devices

### Predicted Present Labels

- Consolidation
- Lung Opacity

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `absent`, ground truth `present`
- Pleural Effusion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. REDEMONSTRATION OF RIGHT UPPER EXTREMITY PICC LINE. 2. REDEMONSTRATION OF POSTOPERATIVE CHANGES, CONSISTENT WITH PRIOR MEDIAN STERNOTOMY. 3. INTERVAL DEVELOPMENT OF MILD INTERSTITIAL PULMONARY EDEMA. NARRATIVE: HISTORY: 67-year-old man with neutropenic fever. EXAM: Single portable upright view of the chest, dated 11-4-2002 at 10:11 hours. COMPARISON: 11/4/02. IMPRESSION: 1. REDEMONSTRATION OF RIGHT UPPER EXTREMITY PICC LINE. 2. REDEMONSTRATION OF POSTOPERATIVE CHANGES, CONSISTENT WITH PRIOR MEDIAN STERNOTOMY. 3. INTERVAL DEVELOPMENT OF MILD INTERSTITIAL PULMONARY EDEMA. END OF IMPRESSION: SUMMARY: 4 POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION I have personally reviewed the images for this examination and agree with the report transcribed above. By: md thiago  on: 11/4/2002   ACCESSION NUMBER: #44902257155 This report has been anonymized. All dates are offset from the actual dates b ...[truncated]

---

## Case

- Study key: `patient00102/study1`
- DICOM path: `patient00102/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.786`

### Explanation

Critical missed present labels: ['Lung Opacity']

### Ground Truth Present Labels

- Lung Opacity
- Support Devices

### Predicted Present Labels

- None

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `present`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. A LEFT UPPER EXTREMITY PICC LINE IS UNCHANGED IN POSITION. 2. THERE ARE LOW LUNG VOLUMES, THE LUNGS ARE OTHERWISE CLEAR WITH NO EVIDENCE OF FOCAL OPACIFICATION OR PLEURAL EFFUSIONS. 3. NO PNEUMOTHORAX. NARRATIVE: PORTABLE CHEST, 6/4/2016 USC CENTER FOR BODY COMPUTING 0735 HOURS: CLINICAL HISTORY: Aortic dissection, evaluate for infiltrates. IMPRESSION: 1. A LEFT UPPER EXTREMITY PICC LINE IS UNCHANGED IN POSITION. 2. THERE ARE LOW LUNG VOLUMES, THE LUNGS ARE OTHERWISE CLEAR WITH NO EVIDENCE OF FOCAL OPACIFICATION OR PLEURAL EFFUSIONS. 3. NO PNEUMOTHORAX. END OF IMPRESSION: SUMMARY: 4 POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION I have personally reviewed the images for this examination and agree with the report transcribed above. By: Kaydence, Reed  on: 6/4/2016   ACCESSION NUMBER: 63 35 16 41 29 89 8 This report has been anonymized. All dates are offset from the actual dates by a fi ...[truncated]

---

## Case

- Study key: `patient00102/study3`
- DICOM path: `patient00102/study3/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `1.000`
- Label macro score: `0.607`

### Explanation

Critical hallucinated present labels: ['Lung Opacity'] Critical missed present labels: ['Pleural Effusion']

### Ground Truth Present Labels

- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Lung Opacity

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pleural Effusion: predicted `uncertain`, ground truth `present`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. INTACT MIDLINE STERNOTOMY WIRES ARE REDEMONSTRATED. A RIGHT UPPER EXTREMITY PICC LINE REMAINS IN PLACE WITH TIP NOW IN THE PROXIMAL SVC. 2. LOW LUNG VOLUMES WITHOUT PULMONARY EDEMA, CONSOLIDATION, OR PLEURAL EFFUSION. 3. THE CARDIOMEDIASTINAL SILHOUETTE IS STABLE AND WITHIN NORMAL LIMITS. NARRATIVE: CHEST SINGLE VIEW PORTABLE: 5/20/2002 CLINICAL HISTORY: Leukemia, rule out infection. COMPARISON: 5/20 IMPRESSION: 1. INTACT MIDLINE STERNOTOMY WIRES ARE REDEMONSTRATED. A RIGHT UPPER EXTREMITY PICC LINE REMAINS IN PLACE WITH TIP NOW IN THE PROXIMAL SVC. 2. LOW LUNG VOLUMES WITHOUT PULMONARY EDEMA, CONSOLIDATION, OR PLEURAL EFFUSION. 3. THE CARDIOMEDIASTINAL SILHOUETTE IS STABLE AND WITHIN NORMAL LIMITS. END OF IMPRESSION: I have personally reviewed the images for this examination and agree with the report transcribed above. By: SALINAS, JOSEPH  on: 5/20/02   ACCESSION NUMBER: #8221-5883 T ...[truncated]

---

## Case

- Study key: `patient00102/study2`
- DICOM path: `patient00102/study2/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.400`
- Label macro score: `0.500`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Cardiomegaly', 'Edema']

### Ground Truth Present Labels

- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Edema
- Lung Opacity

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `uncertain`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. INTERVAL PLACEMENT OF A RIGHT INTERNAL JUGULAR SHEATH WITH ITS TIP IN THE INTERNAL JUGULAR/RIGHT SUBCLAVIAN JUNCTION. THERE IS STABLE REDEMONSTRATION ON THE LEFT UPPER EXTREMITY PICC LINE AND STERNAL WIRES. 2. THERE IS ABUNDANT MOTION ARTIFACT IN THE CURRENT FILM BUT THERE IS NO EVIDENCE OF INFILTRATES, EFFUSIONS OR PNEUMOTHORAX. NARRATIVE: PORTABLE CHEST ONE VIEW: 2007 August 17 Koan Health 08:45 HOURS COMPARISON: 8-17-2007 KOAN HEALTH 00:09 CLINICAL HISTORY: This is a 54-year-old gentleman with fever, neutropenia, sepsis and hypotension here to evaluate for infiltrates. IMPRESSION: 1. INTERVAL PLACEMENT OF A RIGHT INTERNAL JUGULAR SHEATH WITH ITS TIP IN THE INTERNAL JUGULAR/RIGHT SUBCLAVIAN JUNCTION. THERE IS STABLE REDEMONSTRATION ON THE LEFT UPPER EXTREMITY PICC LINE AND STERNAL WIRES. 2. THERE IS ABUNDANT MOTION ARTIFACT IN THE CURRENT FILM BUT THERE IS NO EVIDENCE OF INFILTRATES ...[truncated]

---

## Case

- Study key: `patient00107/study1`
- DICOM path: `patient00107/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `1.000`
- Label macro score: `0.654`

### Explanation

Critical hallucinated present labels: ['Pneumothorax'] Critical missed present labels: ['Lung Opacity', 'Pleural Effusion']

### Ground Truth Present Labels

- Lung Opacity
- Pleural Effusion

### Predicted Present Labels

- Pneumothorax

### Partial Or Mismatched Labels

- Consolidation: predicted `uncertain`, ground truth `absent`
- Pleural Effusion: predicted `absent`, ground truth `present`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `absent`, ground truth `present`
- Pleural Other: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. NORMAL CARDIOMEDIASTINAL SILHOUETTE. NO FOCAL PARENCHYMAL OPACITY OR PLEURAL EFFUSION. PULMONARY VESSELS ARE UNREMARKABLE. NO ACUTE OSSEOUS ABNORMALITY. NARRATIVE: CHEST SINGLE VIEW: 1/26/2001 COMPARISON: None. IMPRESSION: 1. NORMAL CARDIOMEDIASTINAL SILHOUETTE. NO FOCAL PARENCHYMAL OPACITY OR PLEURAL EFFUSION. PULMONARY VESSELS ARE UNREMARKABLE. NO ACUTE OSSEOUS ABNORMALITY. END OF IMPRESSION: SUMMARY 1: No significant abnormality. I have personally reviewed the images for this examination and agree with the report transcribed above. By: zamora, anderson  on: 01 January  __________________________________   ACCESSION NUMBER: 3533831 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00113/study1`
- DICOM path: `patient00113/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.333`
- Label macro score: `0.464`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Edema', 'Pleural Effusion']

### Ground Truth Present Labels

- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `absent`, ground truth `uncertain`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. INCREASING PATCHY AIRSPACE OPACITY AT THE RIGHT LUNG BASE WORRISOME FOR POSSIBLE PNEUMONIA. WOULD RECOMMEND CLINICAL CORRELATION. THIS IS SLIGHTLY INCREASED RETICULAR OPACITIES ALSO NOTED IN THE RIGHT MID AND UPPER LUNG ZONES. 2. LOW LUNG VOLUMES WITH POST-SURGICAL CHANGES AND LEFT SIDED PACEMAKER AGAIN SEEN IN PLACE ALL UNCHANGED. NARRATIVE: SINGLE AP PORTABLE VIEW OF THE CHEST, JANUARY 2018: COMPARISON: Comparison is made with previous study dated 1/12/2018. IMPRESSION: 1. INCREASING PATCHY AIRSPACE OPACITY AT THE RIGHT LUNG BASE WORRISOME FOR POSSIBLE PNEUMONIA. WOULD RECOMMEND CLINICAL CORRELATION. THIS IS SLIGHTLY INCREASED RETICULAR OPACITIES ALSO NOTED IN THE RIGHT MID AND UPPER LUNG ZONES. 2. LOW LUNG VOLUMES WITH POST-SURGICAL CHANGES AND LEFT SIDED PACEMAKER AGAIN SEEN IN PLACE ALL UNCHANGED. END OF IMPRESSION: SUMMARY 4: Possible significant abnormality/change, may need act ...[truncated]

---

## Case

- Study key: `patient00113/study2`
- DICOM path: `patient00113/study2/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.250`
- Label macro score: `0.357`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Lung Opacity', 'Pneumothorax']

### Ground Truth Present Labels

- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `present`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. AP PORTABLE UPRIGHT VIEW OF THE CHEST DATED 6/26/2005 REDEMONSTRATES A DUAL LEAD PACEMAKER WITH ONE LEAD PROJECTING TO THE RIGHT ATRIUM AND ONE TO THE RIGHT VENTRICLE.  REDEMONSTRATION OF STERNOTOMY WIRES.  2. NEW RIGHT PLEURAL EFFUSION AND ATELECTATIC CHANGES OF THE RIGHT LUNG. NARRATIVE: CHEST 1 VIEW PORTABLE: 6/26/2005  PREVIOUS EXAM: 6/26/05  CLINICAL HISTORY: 78 year old, shortness of breath.  IMPRESSION:  1. AP PORTABLE UPRIGHT VIEW OF THE CHEST DATED 6/26/2005 REDEMONSTRATES A DUAL LEAD PACEMAKER WITH ONE LEAD PROJECTING TO THE RIGHT ATRIUM AND ONE TO THE RIGHT VENTRICLE.  REDEMONSTRATION OF STERNOTOMY WIRES.  2. NEW RIGHT PLEURAL EFFUSION AND ATELECTATIC CHANGES OF THE RIGHT LUNG.  SUMMARY:4-POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION I have personally reviewed the images for this examination and agreed with the report transcribed above.   ACCESSION NUMBER: 7154407945477 Th ...[truncated]

---

## Case

- Study key: `patient00114/study5`
- DICOM path: `patient00114/study5/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.667`
- Label macro score: `0.607`

### Explanation

Critical hallucinated present labels: ['Pleural Effusion', 'Pneumothorax']

### Ground Truth Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Fracture
- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> ENDOTRACHEAL TUBE, RIGHT IJ LINE, FEEDING TUBE, STENT AND STERNAL SUTURE WIRES ARE GROSSLY UNCHANGED IN CONFIGURATION. THERE IS INTERVAL IMPROVEMENT IN RIGHT LUNG AERATION WITH DECREASING ALVEOLAR OPACITY. THE LEFT LUNG APPEARS SLIGHTLY BETTER AERATED AS WELL. THE LARGE OVOID SOFT TISSUE STRUCTURE IN THE LEFT UPPER LOBE IS AGAIN NOTED AND UNCHANGED. THERE IS PERSISTENT LEFT LOWER LOBE ATELECTASIS AND/OR CONSOLIDATION. NARRATIVE: CHEST: 11-2-2008. COMPARISON: 11/2/2008. IMPRESSION: ENDOTRACHEAL TUBE, RIGHT IJ LINE, FEEDING TUBE, STENT AND STERNAL SUTURE WIRES ARE GROSSLY UNCHANGED IN CONFIGURATION. THERE IS INTERVAL IMPROVEMENT IN RIGHT LUNG AERATION WITH DECREASING ALVEOLAR OPACITY. THE LEFT LUNG APPEARS SLIGHTLY BETTER AERATED AS WELL. THE LARGE OVOID SOFT TISSUE STRUCTURE IN THE LEFT UPPER LOBE IS AGAIN NOTED AND UNCHANGED. THERE IS PERSISTENT LEFT LOWER LOBE ATELECTASIS AND/OR CONSOLI ...[truncated]

---

## Case

- Study key: `patient00114/study10`
- DICOM path: `patient00114/study10/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.667`
- Label macro score: `0.571`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Lung Opacity', 'Pneumothorax']

### Ground Truth Present Labels

- Consolidation
- Edema
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `present`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> AGAIN SEEN ARE BILATERAL PLEURAL EFFUSIONS, PULMONARY EDEMA AND LEFT LOWER LOBE CONSOLIDATION. THE RIGHT-SIDED PICC LINE IS NOW REDIRECTED AND TERMINATES IN THE DISTAL SUPERIOR VENA CAVA. NARRATIVE: SINGLE VIEW CHEST: 9/16/2015 1323 hours IMPRESSION: AGAIN SEEN ARE BILATERAL PLEURAL EFFUSIONS, PULMONARY EDEMA AND LEFT LOWER LOBE CONSOLIDATION. THE RIGHT-SIDED PICC LINE IS NOW REDIRECTED AND TERMINATES IN THE DISTAL SUPERIOR VENA CAVA. END OF IMPRESSION: SUMMARY: 2 I have personally reviewed the images for this examination and agree with the report transcribed above. By: Dr. Berry Eva  on: 9/16/2015   ACCESSION NUMBER: 2192937625613 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00114/study15`
- DICOM path: `patient00114/study15/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.286`
- Label macro score: `0.429`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Lung Opacity', 'Pleural Effusion', 'Pneumothorax']

### Ground Truth Present Labels

- Consolidation
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Fracture
- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. TRACHEOSTOMY TUBE, MEDIAN STERNOTOMY WIRES, STENT, AND PSEUDOANEURYSM COILS ARE UNCHANGED. 2. NO SIGNIFICANT CHANGE IN DIFFUSE INTERSTITIAL PATTERN IN THE LUNGS WHICH IS LIKELY A SEQUELA OF PRIOR INFECTIONS. NO NEW CONSOLIDATION. NARRATIVE: PORTABLE CHEST, SINGLE VIEW: 9/11/2011. COMPARISON: 9/11/2011. CLINICAL DATA: Aortic arch pseudoaneurysm. IMPRESSION: 1. TRACHEOSTOMY TUBE, MEDIAN STERNOTOMY WIRES, STENT, AND PSEUDOANEURYSM COILS ARE UNCHANGED. 2. NO SIGNIFICANT CHANGE IN DIFFUSE INTERSTITIAL PATTERN IN THE LUNGS WHICH IS LIKELY A SEQUELA OF PRIOR INFECTIONS. NO NEW CONSOLIDATION. END OF IMPRESSION: SUMMARY 2: Abnormal, previously reported. I have personally reviewed the images for this examination and agree with the report transcribed above. By: Dr. Alivia Owens  on: 9-11-2011   ACCESSION NUMBER: 56095 This report has been anonymized. All dates are offset from the actual dates by ...[truncated]

---

## Case

- Study key: `patient00114/study16`
- DICOM path: `patient00114/study16/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.444`
- Label macro score: `0.464`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pneumothorax']

### Ground Truth Present Labels

- Lung Opacity
- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `present`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. NO SIGNIFICANT INTERVAL CHANGE IN TRACHEOSTOMY, MEDIAN STERNOTOMY WIRES, STENT, AND PSEUDOANEURYSM COILS. 2. REDEMONSTRATION OF OPACITY IN THE LEFT UPPER LUNG FIELD CONSISTENT WITH PSEUDOANEURYSM IN THIS AREA. 3. NO SIGNIFICANT CHANGE IN LEFT LOWER LOBE OPACITY AND LEFT PLEURAL EFFUSION. NARRATIVE: CHEST ONE VIEW: 17/03 COMPARISON: 3/13/2017  CLINICAL HISTORY: Aneurysm. IMPRESSION: 1. NO SIGNIFICANT INTERVAL CHANGE IN TRACHEOSTOMY, MEDIAN STERNOTOMY WIRES, STENT, AND PSEUDOANEURYSM COILS. 2. REDEMONSTRATION OF OPACITY IN THE LEFT UPPER LUNG FIELD CONSISTENT WITH PSEUDOANEURYSM IN THIS AREA. 3. NO SIGNIFICANT CHANGE IN LEFT LOWER LOBE OPACITY AND LEFT PLEURAL EFFUSION. END OF IMPRESSION: SUMMARY 2: Abnormal, previously reported. I have personally reviewed the images for this examination and agree with the report transcribed above. By: BENSON,  DR.  on: 3-13-2017   ACCESSION NUMBER: 49_ ...[truncated]

---

## Case

- Study key: `patient00114/study20`
- DICOM path: `patient00114/study20/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.750`
- Label macro score: `0.607`

### Explanation

Critical hallucinated present labels: ['Consolidation']

### Ground Truth Present Labels

- Atelectasis
- Lung Opacity
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Fracture
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. LEFT UPPER EXTREMITY PICC LINE, DISTAL TIP OF WHICH IS STILL  WITHIN THE LEFT AXILLA. 2. RIGHT CENTRAL LINE, TRACHEOSTOMY, POSTSURGICAL WIRES, AORTIC  VALVE, AND STENT GRAFT UNCHANGED FROM PREVIOUS. 3. INCREASED OPACIFICATION OF THE LEFT LUNG BASE CONSISTENT WITH  ATELECTASIS VERSUS INFECTION WITH PERSISTENT LEFT PLEURAL  EFFUSION. 4. LEFT UPPER LUNG OPACITY IS UNCHANGED FROM PREVIOUS. 5. NO INTERSTITIAL EDEMA. NARRATIVE: PORTABLE CHEST, ONE VIEW: 1-4-2017 PREVIOUS COMPARISON: One-view chest 1/4/2017. HISTORY: Ascending aortic aneurysm. IMPRESSION: 1. LEFT UPPER EXTREMITY PICC LINE, DISTAL TIP OF WHICH IS STILL  WITHIN THE LEFT AXILLA. 2. RIGHT CENTRAL LINE, TRACHEOSTOMY, POSTSURGICAL WIRES, AORTIC  VALVE, AND STENT GRAFT UNCHANGED FROM PREVIOUS. 3. INCREASED OPACIFICATION OF THE LEFT LUNG BASE CONSISTENT WITH  ATELECTASIS VERSUS INFECTION WITH PERSISTENT LEFT PLEURAL  EFFUSION. 4. LE ...[truncated]

---

## Case

- Study key: `patient00114/study3`
- DICOM path: `patient00114/study3/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.444`
- Label macro score: `0.464`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Edema', 'Pleural Effusion', 'Pneumonia']

### Ground Truth Present Labels

- Consolidation
- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Fracture
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> THE ENDOTRACHEAL TUBE, NASOGASTRIC TUBE, FEEDING TUBE AND RIGHT INTERNAL JUGULAR CENTRAL VENOUS CATHETERS ALL APPEAR UNCHANGED IN CONFIGURATION. AGAIN NOTED IS A STENT GRAFT IN THE AORTA AT THE LEVEL OF THE ARCH. PERSISTENT OVOID OPACITY IN THE LEFT UPPER LUNG ZONE, GROSSLY UNCHANGED. EXTENSIVE ALVEOLAR OPACITY OF THE RIGHT LUNG, ALSO GROSSLY UNCHANGED. PERSISTENT LEFT LOWER LOBE CONSOLIDATION. THE OVERALL APPEARANCE OF THE CHEST DOES NOT SIGNIFICANTLY DIFFER FROM THE PRIOR STUDY. NARRATIVE: CHEST, 3/11/2015 COMPARISON: Comparison is made with 3-11-2015. IMPRESSION: THE ENDOTRACHEAL TUBE, NASOGASTRIC TUBE, FEEDING TUBE AND RIGHT INTERNAL JUGULAR CENTRAL VENOUS CATHETERS ALL APPEAR UNCHANGED IN CONFIGURATION. AGAIN NOTED IS A STENT GRAFT IN THE AORTA AT THE LEVEL OF THE ARCH. PERSISTENT OVOID OPACITY IN THE LEFT UPPER LUNG ZONE, GROSSLY UNCHANGED. EXTENSIVE ALVEOLAR OPACITY OF THE RIGHT L ...[truncated]

---

## Case

- Study key: `patient00114/study17`
- DICOM path: `patient00114/study17/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.400`
- Label macro score: `0.429`

### Explanation

Critical hallucinated present labels: ['Cardiomegaly', 'Edema', 'Lung Opacity', 'Pleural Effusion'] Critical missed present labels: ['Pneumonia']

### Ground Truth Present Labels

- Atelectasis
- Consolidation
- Pneumonia
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Fracture
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `present`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> AP SEMI-ERECT FILM. THE RIGHT SUBCLAVIAN VENOUS LINE AND TRACHEOSTOMY TUBE REMAIN UNCHANGED. THERE IS A RIGHT-SIDED PICC LINE IN PLACE. THERE HAS BEEN A MEDIAN STERNOTOMY WITH METALLIC MESH IN THE AORTIC ARCH. THE PREVIOUSLY NOTED PATCHY CONSOLIDATION AT THE RIGHT BASE HAS RESOLVED. THE RIGHT LUNG NOW APPEARS CLEAR. A ROUNDED DENSITY IS ONCE AGAIN DEMONSTRATED ADJACENT TO THE AORTIC ARCH, UNCHANGED IN APPEARANCE. THERE IS ALSO PERSISTENT LEFT LOWER LOBE ATELECTASIS OR CONSOLIDATION. NARRATIVE: CHEST X-RAY: 11/25/2002 COMPARISON: 11-25-2002 CLINICAL INFORMATION: Aortic aneurysm of the ascending aorta and arch. Rule out pneumonia. IMPRESSION: AP SEMI-ERECT FILM. THE RIGHT SUBCLAVIAN VENOUS LINE AND TRACHEOSTOMY TUBE REMAIN UNCHANGED. THERE IS A RIGHT-SIDED PICC LINE IN PLACE. THERE HAS BEEN A MEDIAN STERNOTOMY WITH METALLIC MESH IN THE AORTIC ARCH. THE PREVIOUSLY NOTED PATCHY CONSOLIDATION ...[truncated]

---

## Case

- Study key: `patient00114/study13`
- DICOM path: `patient00114/study13/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.400`
- Label macro score: `0.393`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Enlarged Cardiomediastinum', 'Pleural Effusion', 'Pneumothorax']

### Ground Truth Present Labels

- Edema
- Lung Opacity

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Enlarged Cardiomediastinum
- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `present`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INTERVAL DECREASE IN PULMONARY EDEMA, MODERATE EDEMA REMAINS. 2. LEFT UPPER LUNG ZONE FOCAL OPACITY SUGGESTIVE OF PSEUDOANEURYSM ADJACENT TO THE POST-OPERATIVE CHANGES AGAIN NOTED. NARRATIVE: PORTABLE CHEST, SINGLE VIEW: 4/29/2005. COMPARISON: 4/29/2005. IMPRESSION: 1. INTERVAL DECREASE IN PULMONARY EDEMA, MODERATE EDEMA REMAINS. 2. LEFT UPPER LUNG ZONE FOCAL OPACITY SUGGESTIVE OF PSEUDOANEURYSM ADJACENT TO THE POST-OPERATIVE CHANGES AGAIN NOTED. END OF IMPRESSION: SUMMARY: 2   ACCESSION NUMBER: 3363597287 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00114/study19`
- DICOM path: `patient00114/study19/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.333`
- Label macro score: `0.464`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Lung Opacity', 'Pleural Effusion']

### Ground Truth Present Labels

- Edema
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. LEFT UPPER EXTREMITY PICC LINE STILL LOCATED WITHIN THE AXILLA. 2. RIGHT INTERNAL JUGULAR LINE, TRACHEOSTOMY, POST SURGICAL WIRES, AND VALVE UNCHANGED FROM PREVIOUS. 3. PERSISTENT MILD INTERSTITIAL EDEMA. 4. INTERVAL IMPROVEMENT IN LUNG VOLUMES WITH STABLE LEFT UPPER LUNG ZONE AND LOWER LUNG ZONE OPACITIES, AS PREVIOUSLY DESCRIBED. NARRATIVE: ONE VIEW CHEST: 12-28-2004 AT 1355 HOURS. COMPARISON: One view chest 12-28-2004. CLINICAL HISTORY: Ascending aortic arch aneurysm. IMPRESSION: 1. LEFT UPPER EXTREMITY PICC LINE STILL LOCATED WITHIN THE AXILLA. 2. RIGHT INTERNAL JUGULAR LINE, TRACHEOSTOMY, POST SURGICAL WIRES, AND VALVE UNCHANGED FROM PREVIOUS. 3. PERSISTENT MILD INTERSTITIAL EDEMA. 4. INTERVAL IMPROVEMENT IN LUNG VOLUMES WITH STABLE LEFT UPPER LUNG ZONE AND LOWER LUNG ZONE OPACITIES, AS PREVIOUSLY DESCRIBED. END OF IMPRESSION: SUMMARY 4: Possible significant abnormality/change, m ...[truncated]

---

## Case

- Study key: `patient00114/study7`
- DICOM path: `patient00114/study7/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.667`
- Label macro score: `0.536`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Lung Opacity']

### Ground Truth Present Labels

- Consolidation
- Edema
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Fracture
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> There is increasing opacification of the left hemithorax. There is persistent pulmonary edema on the right. ET-tube remains approximately 8 cm above the carina. A right subclavian line has its distal tip in the SVC. Aortic stent graft is located in the proximal descending thoracic aorta. 1. WORSENING LEFT LUNG CONSOLIDATION AND/OR EFFUSION. 2. PERSISTENT PATTERN OF PULMONARY EDEMA ON THE RIGHT. NARRATIVE: AP CHEST: 7-2-2001 USC CENTER FOR BODY COMPUTING 1207 COMPARISON: 7-2-2001 USC Center for Body Computing 1707 FINDINGS: There is increasing opacification of the left hemithorax. There is persistent pulmonary edema on the right. ET-tube remains approximately 8 cm above the carina. A right subclavian line has its distal tip in the SVC. Aortic stent graft is located in the proximal descending thoracic aorta. IMPRESSION: 1. WORSENING LEFT LUNG CONSOLIDATION AND/OR EFFUSION. 2. PERSISTENT PA ...[truncated]

---

## Case

- Study key: `patient00114/study2`
- DICOM path: `patient00114/study2/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.364`
- Label macro score: `0.357`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Enlarged Cardiomediastinum', 'Pleural Effusion', 'Pneumonia', 'Pneumothorax']

### Ground Truth Present Labels

- Edema
- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Enlarged Cardiomediastinum
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
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 7/14/2018 USC CENTER FOR BODY COMPUTING 1352 hours: interval removal of right-sided chest tube. No pneumothorax identified. The right IJ line, aortic stent graft in the region of the aortic arch. Two mediastinal drains remain in place. There is persistent pulmonary edema and near confluent opacity involving the left hemithorax. 7/14/2018 USC Center for Body Computing 1449 hours: No significant interval change. 1. INTERVAL REMOVAL OF RIGHT-SIDED CHEST TUBE. OTHER LINES AND TUBES INCLUDING MEDIASTINAL DRAIN AND RIGHT IJ LINE IN PLACE. AORTIC ARCH STENT GRAFT AGAIN NOTED. 2. PERSISTENT, NEAR CONFLUENT OPACITY INVOLVING THE LEFT HEMITHORAX. 3. PERSISTENT PULMONARY EDEMA. NARRATIVE: PORTABLE CHEST, 7-14-2018 USC Center for Body Computing 1449 HOURS, AND 7-14-18 USC Center for Body Computing 1352 HOURS: COMPARISON: Comparison is made to study dated 2018/14 USC CENTER FOR BODY COMPUTING 0402 ho ...[truncated]

---

## Case

- Study key: `patient00114/study12`
- DICOM path: `patient00114/study12/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.464`

### Explanation

Critical hallucinated present labels: ['Consolidation', 'Lung Opacity', 'Pleural Effusion', 'Pneumonia']

### Ground Truth Present Labels

- Support Devices

### Predicted Present Labels

- Consolidation
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. DIFFUSE RETICULAR OPACITIES SUGGESTIVE OF PULMONARY EDEMA. NO CHANGE. 2. TRACHEOSTOMY, POST-OPERATIVE CHANGES, AND RIGHT-SIDED PICC LINE, STABLE. NARRATIVE: PORTABLE CHEST, 04/01: COMPARISON: Comparison is made to study dated 4/1/2001. IMPRESSION: 1. DIFFUSE RETICULAR OPACITIES SUGGESTIVE OF PULMONARY EDEMA. NO CHANGE. 2. TRACHEOSTOMY, POST-OPERATIVE CHANGES, AND RIGHT-SIDED PICC LINE, STABLE. END OF IMPRESSION: SUMMARY: 2 I have personally reviewed the images for this examination and agree with the report transcribed above. By: Hensley, MD  on: 01/04/01   ACCESSION NUMBER: 55018253 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00114/study9`
- DICOM path: `patient00114/study9/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.571`
- Label macro score: `0.500`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Lung Opacity', 'Pneumothorax']

### Ground Truth Present Labels

- Consolidation
- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `present`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INCREASING RIGHT LOWER LOBE CONSOLIDATION AND PLEURAL EFFUSION. NARRATIVE: PORTABLE CHEST, SINGLE VIEW: 2/14/19. IMPRESSION: 1. INCREASING RIGHT LOWER LOBE CONSOLIDATION AND PLEURAL EFFUSION. END OF IMPRESSION: SUMMARY: Possible Significant Abnormality/Change, may need action. I have personally reviewed the images for this examination and agree with the report transcribed above. By: jaxson fallahi, md.  on: 2-14-2019  __________________________________   ACCESSION NUMBER: efyvmerk This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00114/study1`
- DICOM path: `patient00114/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.667`
- Label macro score: `0.571`

### Explanation

Critical hallucinated present labels: ['Pleural Effusion'] Critical missed present labels: ['Edema']

### Ground Truth Present Labels

- Atelectasis
- Consolidation
- Edema
- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Fracture
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Edema: predicted `uncertain`, ground truth `present`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> In the interval since the 02/16 chest radiograph, the patient has undergone cardiothoracic surgery. Numerous midline sternal suture wires are now identified with right and left-sided chest tubes as well as a mediastinal drain now in place. The left-sided chest tube extends into the region of the left lung base. The right-sided tube extends to the upper right lung zone. The patient is now intubated with the endotracheal tube tip at the level of the clavicles. A nasogastric tube is now identified as well, however the tip is not visualized on the current study. Stent graft is again noted in the region of the aortic arch with apparent embolization coils again noted. There is now more confluent appearing opacity in the left upper lobe which again may represent hemorrhage or possibly infection. There is minimal aerated left lung. Significant atelectasis and/or consolidation of the left lower l ...[truncated]

---

## Case

- Study key: `patient00114/study6`
- DICOM path: `patient00114/study6/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.500`
- Label macro score: `0.500`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Enlarged Cardiomediastinum', 'Lung Opacity']

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

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> NO SIGNIFICANT CHANGE. AGAIN SEEN ARE PLEURAL EFFUSIONS AND PULMONARY EDEMA. NARRATIVE: PORTABLE CHEST: 1-9-02 COMPARISON: 1-9-02 IMPRESSION: NO SIGNIFICANT CHANGE. AGAIN SEEN ARE PLEURAL EFFUSIONS AND PULMONARY EDEMA. END OF IMPRESSION: SUMMARY: 2 I have personally reviewed the images for this examination and agree with the report transcribed above. By: Omar A. Stevens, MD  on: 1/9/2002   ACCESSION NUMBER: 777351636 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00114/study18`
- DICOM path: `patient00114/study18/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.250`
- Label macro score: `0.357`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Lung Opacity', 'Pleural Effusion']

### Ground Truth Present Labels

- Edema
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Fracture
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. RIGHT CENTRAL LINE, TRACHEOSTOMY, AND SURGICAL WIRES AND VALVES, NO CHANGE FROM PREVIOUS. 2. PERSISTENT MILD INTERSTITIAL EDEMA. 3. SLIGHT DECREASE IN LUNG VOLUMES WITH PERSISTENT LEFT LUNG OPACITIES. NARRATIVE: ONE VIEW PORTABLE CHEST: 8/7/2005 AT 1100 HOURS. COMPARISON: 2005-8-7 at 0400 hours. CLINICAL HISTORY: Aortic arch aneurysm. IMPRESSION: 1. RIGHT CENTRAL LINE, TRACHEOSTOMY, AND SURGICAL WIRES AND VALVES, NO CHANGE FROM PREVIOUS. 2. PERSISTENT MILD INTERSTITIAL EDEMA. 3. SLIGHT DECREASE IN LUNG VOLUMES WITH PERSISTENT LEFT LUNG OPACITIES. END OF IMPRESSION: SUMMARY 2: Abnormal, previously reported. I have personally reviewed the images for this examination and agree with the report transcribed above. By: Charles, Eden  on: 8/7/2005   ACCESSION NUMBER: 97485514674 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the ...[truncated]

---

## Case

- Study key: `patient00114/study4`
- DICOM path: `patient00114/study4/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.200`
- Label macro score: `0.286`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Enlarged Cardiomediastinum', 'Lung Opacity', 'Pleural Effusion', 'Pneumonia'] Critical missed present labels: ['Lung Lesion']

### Ground Truth Present Labels

- Edema
- Lung Lesion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Enlarged Cardiomediastinum
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `absent`, ground truth `present`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. TUBES AND LINES STABLE. 2. DECREASE IN PULMONARY EDEMA, AND CLEARANCE OF THE RIGHT LOWER LUNG. COMPARE WITH PRIOR STUDY. 3. PERSISTENT MASS LATERAL TO THE AORTIC ARCH, UNCHANGED. 4. POSITION OF THE AORTIC ARCH STENT GRAFT AND EMBOLIZATION COILS UNCHANGED. NARRATIVE: CHEST ONE VIEW: COMPARISON: 7/21/2003. CLINICAL HISTORY: 55-year-old man with aortic arch aneurysm. IMPRESSION: 1. TUBES AND LINES STABLE. 2. DECREASE IN PULMONARY EDEMA, AND CLEARANCE OF THE RIGHT LOWER LUNG. COMPARE WITH PRIOR STUDY. 3. PERSISTENT MASS LATERAL TO THE AORTIC ARCH, UNCHANGED. 4. POSITION OF THE AORTIC ARCH STENT GRAFT AND EMBOLIZATION COILS UNCHANGED. END OF IMPRESSION: S2   ACCESSION NUMBER: 49313855513 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00114/study8`
- DICOM path: `patient00114/study8/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.400`
- Label macro score: `0.393`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Cardiomegaly', 'Edema', 'Enlarged Cardiomediastinum', 'Lung Opacity']

### Ground Truth Present Labels

- Consolidation
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Enlarged Cardiomediastinum
- Fracture
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. THE FEEDING TUBE HAS BEEN REMOVED. THE ENDOTRACHEAL TUBE AND RIGHT SUBCLAVIAN VENOUS CATHETER ARE UNCHANGED IN POSITION. AGAIN SEEN IS LEFT LOWER LOBE CONSOLIDATION AND PATCHY AIR SPACE OPACITIES BILATERALLY, WHICH ARE NOT SIGNIFICANTLY CHANGED. THE RIGHT PLEURAL EFFUSION MAY BE SLIGHTLY LARGER OR LAYERING MOST POSTERIORLY THAN ON PRIOR EXAMINATION. NARRATIVE: PORTABLE CHEST, SINGLE VIEW: 1-21-07. COMPARISON: 1/21/2007. IMPRESSION: 1. THE FEEDING TUBE HAS BEEN REMOVED. THE ENDOTRACHEAL TUBE AND RIGHT SUBCLAVIAN VENOUS CATHETER ARE UNCHANGED IN POSITION. AGAIN SEEN IS LEFT LOWER LOBE CONSOLIDATION AND PATCHY AIR SPACE OPACITIES BILATERALLY, WHICH ARE NOT SIGNIFICANTLY CHANGED. THE RIGHT PLEURAL EFFUSION MAY BE SLIGHTLY LARGER OR LAYERING MOST POSTERIORLY THAN ON PRIOR EXAMINATION. END OF IMPRESSION. SUMMARY: 2 I have personally reviewed the images for this examination and agree with th ...[truncated]

---

## Case

- Study key: `patient00114/study14`
- DICOM path: `patient00114/study14/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.571`
- Label macro score: `0.536`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Pleural Effusion']

### Ground Truth Present Labels

- Edema
- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. INTERVAL REMOVAL OF SWAN-GANZ CATHETER. TRACHEOSTOMY TUBE, STENT, RIGHT CHEST TUBE, AND PSEUDOANEURYSM COILS APPEAR UNCHANGED. 2. PERSISTENT LEFT BASE OPACITY. 3. INTERVAL IMPROVEMENT IN PULMONARY EDEMA. NARRATIVE: CHEST ONE VIEW: 7/10/2014 COMPARISON: 7/10/2014 CLINICAL HISTORY: Ascending aortic aneurysm. IMPRESSION: 1. INTERVAL REMOVAL OF SWAN-GANZ CATHETER. TRACHEOSTOMY TUBE, STENT, RIGHT CHEST TUBE, AND PSEUDOANEURYSM COILS APPEAR UNCHANGED. 2. PERSISTENT LEFT BASE OPACITY. 3. INTERVAL IMPROVEMENT IN PULMONARY EDEMA. END OF IMPRESSION: SUMMARY 2: Abnormal, previously reported. I have personally reviewed the images for this examination and agree with the report transcribed above. By: Genevieve, MD  on: 7/10/14   ACCESSION NUMBER: #5450501 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00114/study11`
- DICOM path: `patient00114/study11/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.800`
- Label macro score: `0.607`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation']

### Ground Truth Present Labels

- Edema
- Enlarged Cardiomediastinum
- Lung Opacity
- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Enlarged Cardiomediastinum
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. SLIGHT INTERVAL DECREASE IN PULMONARY EDEMA, MODERATE EDEMA REMAINS. WIDENED MEDIASTINUM AGAIN NOTED. LEFT APICAL POSSIBLE HEMATOMA AGAIN NOTED. RETROCARDIAC AIRSPACE OPACITY AND BILATERAL PLEURAL EFFUSIONS APPEAR STABLE. 2. NO SIGNIFICANT CHANGE IN SUPPORT EQUIPMENT. NARRATIVE: PORTABLE CHEST, 8/21/2015: COMPARISON: Comparison is made to study dated August 2015. IMPRESSION: 1. SLIGHT INTERVAL DECREASE IN PULMONARY EDEMA, MODERATE EDEMA REMAINS. WIDENED MEDIASTINUM AGAIN NOTED. LEFT APICAL POSSIBLE HEMATOMA AGAIN NOTED. RETROCARDIAC AIRSPACE OPACITY AND BILATERAL PLEURAL EFFUSIONS APPEAR STABLE. 2. NO SIGNIFICANT CHANGE IN SUPPORT EQUIPMENT. END OF IMPRESSION: I have personally reviewed the images for this examination and agree with the report transcribed above. By: MD FIGUEROA.  on: 8-21-2015   ACCESSION NUMBER: 0 2 3 5 1 5 This report has been anonymized. All dates are offset from t ...[truncated]

---

## Case

- Study key: `patient00115/study2`
- DICOM path: `patient00115/study2/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.857`

### Explanation

Critical missed present labels: ['Consolidation']

### Ground Truth Present Labels

- Consolidation

### Predicted Present Labels

- None

### Partial Or Mismatched Labels

- Atelectasis: predicted `absent`, ground truth `uncertain`
- Consolidation: predicted `absent`, ground truth `present`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> THERE HAS BEEN INTERVAL DEVELOPMENT OF PATCHY OPACITIES  PREDOMINATELY AT THE LUNG BASES, THAT COULD REPRESENT ATELECTASIS OR  CONSOLIDATION. NARRATIVE: SINGLE VIEW CHEST:  16/18/11.    CLINICAL HISTORY:  Critical care follow up.    COMPARISON:  11/18/2016.    TECHNIQUE:  Single frontal view of the chest.    IMPRESSION:     THERE HAS BEEN INTERVAL DEVELOPMENT OF PATCHY OPACITIES  PREDOMINATELY AT THE LUNG BASES, THAT COULD REPRESENT ATELECTASIS OR  CONSOLIDATION.    SUMMARY:4-POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION      I have personally reviewed the images for this examination and agreed with the report transcribed above.   ACCESSION NUMBER: 081948588 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00120/study1`
- DICOM path: `patient00120/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.769`

### Explanation

Critical missed present labels: ['Pneumothorax']

### Ground Truth Present Labels

- Pneumothorax
- Support Devices

### Predicted Present Labels

- None

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `absent`, ground truth `present`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1.  SINGLE FRONTAL RADIOGRAPH OF THE CHEST DEMONSTRATES A NORMAL  CARDIOMEDIASTINAL SILHOUETTE.     2.  LUNGS DEMONSTRATE NO FOCAL OPACITY.  NO PLEURAL EFFUSIONS.  NO  PNEUMOTHORAX.     3.  VISUALIZED OSSEOUS STRUCTURES AND SOFT TISSUES UNREMARKABLE. NARRATIVE: EXAM: Chest 1 View, 2-22-2005.   HISTORY: 68 years Female, Baseline CXR for this homeless pt.    COMPARISON: NONE.   IMPRESSION:   1.  SINGLE FRONTAL RADIOGRAPH OF THE CHEST DEMONSTRATES A NORMAL  CARDIOMEDIASTINAL SILHOUETTE.     2.  LUNGS DEMONSTRATE NO FOCAL OPACITY.  NO PLEURAL EFFUSIONS.  NO  PNEUMOTHORAX.     3.  VISUALIZED OSSEOUS STRUCTURES AND SOFT TISSUES UNREMARKABLE.     SUMMARY:1-NO SIGNIFICANT ABNORMALITY I have personally reviewed the images for this examination and agreed with the report transcribed above.   ACCESSION NUMBER: X830G995434 This report has been anonymized. All dates are offset from the actual dates by ...[truncated]

---

## Case

- Study key: `patient00121/study1`
- DICOM path: `patient00121/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.714`

### Explanation

Critical missed present labels: ['Pneumothorax']

### Ground Truth Present Labels

- Pneumothorax

### Predicted Present Labels

- None

### Partial Or Mismatched Labels

- Atelectasis: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `absent`, ground truth `present`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. LIMITED PORTABLE SUPINE VIEW ON BACKBOARD DEMONSTRATES A WIDENED APPEARANCE OF THE MEDIASTINUM. THIS MAY BE RELATED TO TECHNIQUE AND WOULD RECOMMEND UPRIGHT PA VIEW WHEN PATIENT IS ABLE. 2. LUNGS CLEAR WITHOUT EDEMA, EFFUSION, FOCAL OPACITY, OR PNEUMOTHORAX. 3. NO GROSS OSSEOUS ABNORMALITY. NARRATIVE: CHEST SINGLE VIEW: 6-21-2008. COMPARISON: None. CLINICAL DATA: A 68-year-old male status post motorcycle accident. IMPRESSION: 1. LIMITED PORTABLE SUPINE VIEW ON BACKBOARD DEMONSTRATES A WIDENED APPEARANCE OF THE MEDIASTINUM. THIS MAY BE RELATED TO TECHNIQUE AND WOULD RECOMMEND UPRIGHT PA VIEW WHEN PATIENT IS ABLE. 2. LUNGS CLEAR WITHOUT EDEMA, EFFUSION, FOCAL OPACITY, OR PNEUMOTHORAX. 3. NO GROSS OSSEOUS ABNORMALITY. END OF IMPRESSION: SUMMARY: 4 POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION I have personally reviewed the images for this examination and agree with the report transcribe ...[truncated]

---

## Case

- Study key: `patient00122/study3`
- DICOM path: `patient00122/study3/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.667`
- Label macro score: `0.714`

### Explanation

Critical hallucinated present labels: ['Consolidation']

### Ground Truth Present Labels

- Atelectasis
- Pleural Effusion
- Pleural Other
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Pleural Effusion

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `present`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> Initial chest x-ray dated november 2003 at 0847 hours shows an irregular left pleural effusion and a smaller right effusion. Left lower lobe atelectasis present. A left chest tube is present. Follow-up chest x-ray dated 11-11-2003 at 1033 hours shows interval removal of left sided chest tube with no pneumothorax visible. 1. IRREGULAR LEFT PLEURAL THICKENING AND SMALL RIGHT EFFUSION WITH LEFT LOWER LOBE ATELECTASIS. 2. NO PNEUMOTHORAX. NARRATIVE: CHEST X-RAY, PA AND LATERAL: 11/11/2003 AT 0847 HOURS. CHEST X-RAY, PA AND LATERAL: NOVEMBER 03 AT 1033 HOURS. CLINICAL HISTORY: Mild pleural effusions after talc pleurodesis. FINDINGS: Initial chest x-ray dated november 2003 at 0847 hours shows an irregular left pleural effusion and a smaller right effusion. Left lower lobe atelectasis present. A left chest tube is present. Follow-up chest x-ray dated 11-11-2003 at 1033 hours shows interval remo ...[truncated]

---

## Case

- Study key: `patient00122/study3`
- DICOM path: `patient00122/study3/view2_lateral.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.444`
- Label macro score: `0.429`

### Explanation

Critical hallucinated present labels: ['Consolidation', 'Edema', 'Lung Opacity', 'Pneumonia']

### Ground Truth Present Labels

- Atelectasis
- Pleural Effusion
- Pleural Other
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `absent`, ground truth `present`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> Initial chest x-ray dated november 2003 at 0847 hours shows an irregular left pleural effusion and a smaller right effusion. Left lower lobe atelectasis present. A left chest tube is present. Follow-up chest x-ray dated 11-11-2003 at 1033 hours shows interval removal of left sided chest tube with no pneumothorax visible. 1. IRREGULAR LEFT PLEURAL THICKENING AND SMALL RIGHT EFFUSION WITH LEFT LOWER LOBE ATELECTASIS. 2. NO PNEUMOTHORAX. NARRATIVE: CHEST X-RAY, PA AND LATERAL: 11/11/2003 AT 0847 HOURS. CHEST X-RAY, PA AND LATERAL: NOVEMBER 03 AT 1033 HOURS. CLINICAL HISTORY: Mild pleural effusions after talc pleurodesis. FINDINGS: Initial chest x-ray dated november 2003 at 0847 hours shows an irregular left pleural effusion and a smaller right effusion. Left lower lobe atelectasis present. A left chest tube is present. Follow-up chest x-ray dated 11-11-2003 at 1033 hours shows interval remo ...[truncated]

---

## Case

- Study key: `patient00122/study5`
- DICOM path: `patient00122/study5/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.286`
- Label macro score: `0.464`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Edema', 'Pleural Effusion', 'Pneumonia']

### Ground Truth Present Labels

- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `uncertain`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. UNCHANGED POSITION OF RIGHT CHEST TUBE. 2. LOW LUNG VOLUMES WITH BIBASILAR OPACITIES. 3. RIGHT MID LUNG OPACITY. 4. THE ABOVE FINDINGS HAVE WORSENED IN APPEARANCE COMPARED TO THE PRIOR EXAM AND ARE SUGGESTIVE OF INCREASE IN EDEMA VERSUS INCREASING INFECTION. NARRATIVE: CHEST X-RAY: 5/15/2010 USC Center for Body Computing 1626 COMPARISON:  5/15/2010  USC Center for Body Computing 0904 hours. HISTORY: A 72-year-old female with shortness of breath after line placement. IMPRESSION: 1. UNCHANGED POSITION OF RIGHT CHEST TUBE. 2. LOW LUNG VOLUMES WITH BIBASILAR OPACITIES. 3. RIGHT MID LUNG OPACITY. 4. THE ABOVE FINDINGS HAVE WORSENED IN APPEARANCE COMPARED TO THE PRIOR EXAM AND ARE SUGGESTIVE OF INCREASE IN EDEMA VERSUS INCREASING INFECTION. END OF IMPRESSION: SUMMARY: 4 POSSIBLE SIGNIFICANT FINDINGS, MAY NEED ACTION I have personally reviewed the images for this examination and agree with t ...[truncated]

---

## Case

- Study key: `patient00122/study1`
- DICOM path: `patient00122/study1/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.500`
- Label macro score: `0.607`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation']

### Ground Truth Present Labels

- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Consolidation
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> In comparison to the prior examination, there has been significant reduction in a left pleural effusion. A moderate-sized layering left effusion, however, still remains. No pneumothorax is evident. There is significant destruction identified of the left sixth rib. In addition, a calcified granuloma is noted within the left mid- lung. Surgical clips are noted within the right axilla. There has been a right mastectomy. 1. EVIDENCE OF LEFT MODERATE-SIZED PLEURAL EFFUSION WITH CONTINUED EVIDENCE OF BONY METASTATIC DISEASE INVOLVING THE LEFT SIXTH RIB. 2. POST-SURGICAL CHANGES IDENTIFIED CONSISTENT WITH RIGHT MASTECTOMY AND AXILLARY NODE DISSECTION. 3. NO NEW EFFUSION OR MASS IS IDENTIFIED. NARRATIVE: SINGLE FRONTAL RADIOGRAPH OF THE CHEST: 18-02-04. COMPARISON: FEBRUARY 2018. CLINICAL DATA: Status post thoracentesis. FINDINGS: In comparison to the prior examination, there has been significan ...[truncated]

---

## Case

- Study key: `patient00122/study4`
- DICOM path: `patient00122/study4/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.545`
- Label macro score: `0.500`

### Explanation

Critical hallucinated present labels: ['Consolidation', 'Edema', 'Enlarged Cardiomediastinum']

### Ground Truth Present Labels

- Atelectasis
- Lung Opacity
- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Enlarged Cardiomediastinum
- Fracture
- Lung Opacity
- Pleural Effusion
- Pleural Other

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `uncertain`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. SINGLE VIEW OF THE CHEST FROM 1748 HOURS DEMONSTRATES PERSISTENT LEFT PLEURAL FLUID. DECREASED LUNG VOLUMES WITH ATELECTASIS AT THE BILATERAL BASES. RETROCARDIAC OPACITY PERSISTS, WHICH MAY REPRESENT ATELECTASIS VERSUS CONSOLIDATION. 2. SINGLE VIEW OF THE CHEST FROM 2011 HOURS DEMONSTRATES LUCENCY OVERLYING THE RIGHT UPPER QUADRANT. THIS MOST LIKELY REPRESENTS BOWEL, BUT CANNOT EXCLUDE INTRA-ABDOMINAL FREE FLUID. IF THERE IS CONCERN FOR AN INTRA-ABDOMINAL PROCESS, RECOMMEND ABDOMINAL FILMS WITH LEFT LATERAL DECUBITUS. NO SIGNIFICANT CHANGE IN CARDIOPULMONARY STATUS. FINDINGS DISCUSSED WITH Horne, CNP IN THE ED AT APPROXIMATELY 2300 HOURS ON 5/6/2002. NARRATIVE: SINGLE VIEW CHEST SERIES, 5/6/2002: COMPARISON: Comparison is made to study dated 5/6/2002. CLINICAL HISTORY: Pain at suture site. Upright, rule out effusion. IMPRESSION: 1. SINGLE VIEW OF THE CHEST FROM 1748 HOURS DEMONSTRATES ...[truncated]

---

## Case

- Study key: `patient00122/study8`
- DICOM path: `patient00122/study8/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.571`
- Label macro score: `0.536`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Edema', 'Lung Opacity']

### Ground Truth Present Labels

- Consolidation
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. REDEMONSTRATION OF RIGHT INTERNAL JUGULAR CENTRAL VENOUS CATHETER WITH STABLE POSITION. 2. STABLE APPEARANCE OF BILATERAL PLEURAL EFFUSION AND ASSOCIATED BASILAR CONSOLIDATIONS. NARRATIVE: CHEST: CLINICAL HISTORY: 72 -year-old female with history of shortness of breath. COMPARISON: 28th october 11 TECHNIQUE: AP, semi-erect view of the chest. IMPRESSION: 1. REDEMONSTRATION OF RIGHT INTERNAL JUGULAR CENTRAL VENOUS CATHETER WITH STABLE POSITION. 2. STABLE APPEARANCE OF BILATERAL PLEURAL EFFUSION AND ASSOCIATED BASILAR CONSOLIDATIONS. END OF IMPRESSION: SUMMARY 2: ABNORMAL, PREVIOUSLY REPORTED I have personally reviewed the images for this examination and agree with the report transcribed above. By: Leia C., Jennings  on: 10/28/2011   ACCESSION NUMBER: #634 097 763 0 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient ...[truncated]

---

## Case

- Study key: `patient00122/study7`
- DICOM path: `patient00122/study7/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.500`
- Label macro score: `0.536`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Lung Opacity', 'Pneumothorax']

### Ground Truth Present Labels

- Edema
- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `present`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THE LUNG VOLUMES ARE DECREASED. 2. PERSISTENT BIBASILAR OPACIFICATION, LEFT GREATER THAN RIGHT. 3. PERSISTENT BILATERAL PLEURAL EFFUSIONS, LEFT GREATER THAN RIGHT. 4. PERSISTENT MODERATE PULMONARY INTERSTITIAL EDEMA. 5. OVERALL, NO INTERVAL CHANGE. NARRATIVE: ONE VIEW OF THE CHEST: 1/19 AT 1131 HOURS. COMPARISON: 1-19-2005 at 1033 hours. DIAGNOSIS: Shortness of breath. CLINICAL DATA: Pleural effusion. IMPRESSION: 1. THE LUNG VOLUMES ARE DECREASED. 2. PERSISTENT BIBASILAR OPACIFICATION, LEFT GREATER THAN RIGHT. 3. PERSISTENT BILATERAL PLEURAL EFFUSIONS, LEFT GREATER THAN RIGHT. 4. PERSISTENT MODERATE PULMONARY INTERSTITIAL EDEMA. 5. OVERALL, NO INTERVAL CHANGE. END OF IMPRESSION: SUMMARY: 2 ABNORMAL, PREVIOUSLY REPORTED I have personally reviewed the images for this examination and agree with the report transcribed above. By: Diego Dawson, MD  on: January 19th, 05   ACCESSION NUMBER: # ...[truncated]

---

## Case

- Study key: `patient00122/study6`
- DICOM path: `patient00122/study6/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.286`
- Label macro score: `0.429`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Edema', 'Enlarged Cardiomediastinum', 'Lung Opacity']

### Ground Truth Present Labels

- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Enlarged Cardiomediastinum
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `present`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. REDEMONSTRATION OF RIGHT-SIDED INTERNAL JUGULAR VENOUS CATHETER WITH TIP IN THE SUPERIOR VENA CAVA AS WELL AS ONE RIGHT-SIDED CHEST TUBE WITH PORT WITHIN THE CHEST WALL. 2. IMPROVED LUNG VOLUMES BILATERALLY. 3. PERSISTENT BIBASILAR OPACIFICATION, UNCHANGED FROM PREVIOUS EXAMINATION. 4. PERSISTENT LEFT-SIDED PLEURAL EFFUSION, SLIGHTLY IMPROVED FROM PREVIOUS EXAMINATION. NARRATIVE: PORTABLE CHEST ONE VIEW: 1/11/2000 at 0826 hours COMPARISON: January 11th, 2000 at 1656 hours DIAGNOSIS: Shortness of breath. CLINICAL DATA: Pleural effusion. IMPRESSION: 1. REDEMONSTRATION OF RIGHT-SIDED INTERNAL JUGULAR VENOUS CATHETER WITH TIP IN THE SUPERIOR VENA CAVA AS WELL AS ONE RIGHT-SIDED CHEST TUBE WITH PORT WITHIN THE CHEST WALL. 2. IMPROVED LUNG VOLUMES BILATERALLY. 3. PERSISTENT BIBASILAR OPACIFICATION, UNCHANGED FROM PREVIOUS EXAMINATION. 4. PERSISTENT LEFT-SIDED PLEURAL EFFUSION, SLIGHTLY IMPR ...[truncated]

---

## Case

- Study key: `patient00124/study6`
- DICOM path: `patient00124/study6/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.000`
- Label macro score: `0.429`

### Explanation

Critical hallucinated present labels: ['Atelectasis', 'Consolidation', 'Pneumothorax']

### Ground Truth Present Labels

- No Finding

### Predicted Present Labels

- Atelectasis
- Consolidation
- Fracture
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `uncertain`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `absent`
- No Finding: predicted `absent`, ground truth `present`

### Ground Truth Report Excerpt

> 1. LIMITED SUPINE PORTABLE CHEST RADIOGRAPH WITH THE PATIENT ON THE TRAUMA BOARD DEMONSTRATES NO ACUTE DISEASE. 2. NO EVIDENCE FOR FRACTURES OR PNEUMOTHORAX. NARRATIVE: DATE OF EXAM: 2/23/2001 COMPARISON: There are no studies for comparison. BRIEF HISTORY: This is a 45-year-old woman status post trauma. IMPRESSION: 1. LIMITED SUPINE PORTABLE CHEST RADIOGRAPH WITH THE PATIENT ON THE TRAUMA BOARD DEMONSTRATES NO ACUTE DISEASE. 2. NO EVIDENCE FOR FRACTURES OR PNEUMOTHORAX. END OF IMPRESSION: SUMMARY 1: NO SIGNIFICANT ABNORMALITY. I have personally reviewed the images for this examination and agree with the report transcribed above. By: Church Madisyn CNM  on: 2/23/2001   ACCESSION NUMBER: 879383 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00124/study4`
- DICOM path: `patient00124/study4/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.667`
- Label macro score: `0.536`

### Explanation

Critical hallucinated present labels: ['Cardiomegaly', 'Consolidation', 'Lung Opacity']

### Ground Truth Present Labels

- Atelectasis
- Edema
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. LINES AND TUBES UNCHANGED IN POSITION. 2. MODERATE PULMONARY EDEMA AGAIN SEEN ASSOCIATED WITH LOW VOLUMES, BILATERAL PLEURAL EFFUSIONS, RIGHT GREATER THAN LEFT AND LEFT RETROCARDIAC ATELECTASIS. NARRATIVE: CHEST ONE VIEW: CLINICAL HISTORY: GI-bleed. COMPARISON: 3/18/2007, 3-18-2007. IMPRESSION: 1. LINES AND TUBES UNCHANGED IN POSITION. 2. MODERATE PULMONARY EDEMA AGAIN SEEN ASSOCIATED WITH LOW VOLUMES, BILATERAL PLEURAL EFFUSIONS, RIGHT GREATER THAN LEFT AND LEFT RETROCARDIAC ATELECTASIS. END OF IMPRESSION: SUMMARY S2:   ACCESSION NUMBER: 7154407945477 This report has been anonymized. All dates are offset from the actual dates by a fixed interval associated with the patient.

---

## Case

- Study key: `patient00124/study2`
- DICOM path: `patient00124/study2/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.833`
- Label macro score: `0.643`

### Explanation

Critical hallucinated present labels: ['Lung Opacity', 'Pneumothorax']

### Ground Truth Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion
- Pneumothorax

### Partial Or Mismatched Labels

- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `present`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Lesion: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> Submitted for review is a single frontal portable view of the chest dated 3/6/2009 at 06:23. An endotracheal tube is seen with its tip in the trachea. A nasogastric tube is seen with its tip below the diaphragm. A central venous catheter is seen with its tip in the superior vena cava from a right internal jugular vein approach. The cardiac silhouette and main pulmonary arterial segment are again seen to enlarged. The cardiomediastinal silhouette is otherwise unremarkable. The lungs demonstrate diffuse increased reticular markings with indistinct pulmonary vessels and diffuse alveolar opacification, more predominant in the bases. There is blunting of the costophrenic angles bilaterally. These findings appear to have progressed from the prior examination. 1. CARDIOMEGALY WITH WORSENING PULMONARY EDEMA AND BILATERAL BASILAR ATELECTASIS VERSUS CONSOLIDATION AND BILATERAL PLEURAL EFFUSIONS. N ...[truncated]

---

## Case

- Study key: `patient00124/study3`
- DICOM path: `patient00124/study3/view1_frontal.dcm`
- Judge decision: **FAIL**
- Disease F1: `0.800`
- Label macro score: `0.643`

### Explanation

Critical hallucinated present labels: ['Consolidation', 'Lung Opacity']

### Ground Truth Present Labels

- Atelectasis
- Cardiomegaly
- Edema
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `uncertain`, ground truth `absent`
- Pneumothorax: predicted `uncertain`, ground truth `absent`
- Fracture: predicted `uncertain`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Enlarged Cardiomediastinum: predicted `uncertain`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `absent`
- Support Devices: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. ET TUBE, NASOGASTRIC TUBE, FEEDING TUBE AND RIGHT INTERNAL JUGULAR LINE IN PLACE, UNCHANGED. 2. UNCHANGED CARDIOPULMONARY STATUS; BORDERLINE CARDIOMEGALY, MILD INTERSTITIAL EDEMA, LARGE RIGHT PLEURAL EFFUSION AND POSSIBLY A SMALL LEFT PLEURAL EFFUSION. PARTIAL ATELECTASIS OF BOTH LOWER LOBES. 3. INCIDENTALLY SEEN IS A TIPS SHUNT. NARRATIVE: SINGLE VIEW CHEST: 6/25/2007 COMPARISON: 06/25. IMPRESSION: 1. ET TUBE, NASOGASTRIC TUBE, FEEDING TUBE AND RIGHT INTERNAL JUGULAR LINE IN PLACE, UNCHANGED. 2. UNCHANGED CARDIOPULMONARY STATUS; BORDERLINE CARDIOMEGALY, MILD INTERSTITIAL EDEMA, LARGE RIGHT PLEURAL EFFUSION AND POSSIBLY A SMALL LEFT PLEURAL EFFUSION. PARTIAL ATELECTASIS OF BOTH LOWER LOBES. 3. INCIDENTALLY SEEN IS A TIPS SHUNT. END OF IMPRESSION: SUMMARY: 2   ACCESSION NUMBER: 78Z771gb01  This report has been anonymized. All dates are offset from the actual dates by a fixed interval a ...[truncated]

---
