# MEDAGENT-X Judge Report

## Summary

- Total cases: `100`
- Concordant: `0`
- Partially concordant: `9`
- Discordant: `91`

## Case

- Study key: `patient00003/study1`
- DICOM path: `patient00003/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.250`
- Label macro score: `0.464`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Edema
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Edema
- Lung Lesion
- Lung Opacity
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Costophrenic angles sharp, without evidence of effusion. The cardiomediastinal silhouette is normal. Vessels mildly indistinct with prominence of interstitial structures, suggesting mild, pulmonary edema. Left subclavian central venous catheter is seen, tip in mid SVC. No pneumothorax. 1. NO EVIDENCE OF PNEUMOTHORAX. 2. MILD INTERSTITIAL PULMONARY EDEMA.

---

## Case

- Study key: `patient00009/study1`
- DICOM path: `patient00009/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.536`

### Explanation

Very low disease F1 with critical false positives: 0.000

### Ground Truth Present Labels

- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Lung Opacity
- Pleural Other

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. PA AND LATERAL CHEST RADIOGRAPH. THE HEART IS ENLARGED, WITH A CTR OF 16/29. NO CEPHALIZATION OR OVERT PULMONARY EDEMA. LINEAR SHADOWING IS SEEN AT BOTH LUNG BASES, SUGGESTING ATELECTASIS, MOST MARKED ON THE RIGHT. ON THE LATERAL VIEW, THIS APPEARS TO LIE WITHIN THE RIGHT MIDDLE LOBE. THE LUNG APICES APPEAR CLEAR. 2. DISC DEGENERATION IS SEEN THROUGHOUT THE THORACIC SPINE, WITHOUT SIGNIFICANT VERTEBRAL BODY COLLAPSE.

---

## Case

- Study key: `patient00009/study1`
- DICOM path: `patient00009/study1/view2_lateral.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.536`

### Explanation

Very low disease F1 with critical false positives: 0.000

### Ground Truth Present Labels

- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Lung Opacity
- Pleural Other

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. PA AND LATERAL CHEST RADIOGRAPH. THE HEART IS ENLARGED, WITH A CTR OF 16/29. NO CEPHALIZATION OR OVERT PULMONARY EDEMA. LINEAR SHADOWING IS SEEN AT BOTH LUNG BASES, SUGGESTING ATELECTASIS, MOST MARKED ON THE RIGHT. ON THE LATERAL VIEW, THIS APPEARS TO LIE WITHIN THE RIGHT MIDDLE LOBE. THE LUNG APICES APPEAR CLEAR. 2. DISC DEGENERATION IS SEEN THROUGHOUT THE THORACIC SPINE, WITHOUT SIGNIFICANT VERTEBRAL BODY COLLAPSE.

---

## Case

- Study key: `patient00016/study1`
- DICOM path: `patient00016/study1/view1_frontal.dcm`
- Judge decision: **PARTIALLY_CONCORDANT**
- Disease F1: `0.571`
- Label macro score: `0.679`

### Explanation

Ground-truth present disease labels predicted uncertain: ['Lung Opacity'] Critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly'] Disease status mismatches: ['Atelectasis', 'Cardiomegaly']

### Ground Truth Present Labels

- Fracture
- Lung Opacity
- Pleural Other

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Fracture
- Pleural Other

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. ACUTE TO SUBACUTE LEFT POSTERIOR SIXTH RIB FRACTURE.   2.NO EVIDENCE OF PNEUMOTHORAX.  MINIMAL LEFT PLEURAL THICKENING MAY  REPRESENT SMALL AMOUNT OF BLOOD IN THE PLEURAL SPACE.   3.SUBTLE OPACITY JUST LATERAL TO THE CARDIAC APEX IN THE LEFT BASE  MAY REPRESENT A SMALL AREA OF PULMONARY CONTUSION OR OTHER CAUSE FOR  SMALL FOCUS OF CONSOLIDATION.   4.RIGHT LUNG IS CLEAR.   5.LOW LUNG VOLUMES.

---

## Case

- Study key: `patient00016/study1`
- DICOM path: `patient00016/study1/view2_lateral.dcm`
- Judge decision: **PARTIALLY_CONCORDANT**
- Disease F1: `0.571`
- Label macro score: `0.679`

### Explanation

Ground-truth present disease labels predicted uncertain: ['Lung Opacity'] Critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly'] Disease status mismatches: ['Atelectasis', 'Cardiomegaly']

### Ground Truth Present Labels

- Fracture
- Lung Opacity
- Pleural Other

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Fracture
- Pleural Other

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> 1. ACUTE TO SUBACUTE LEFT POSTERIOR SIXTH RIB FRACTURE.   2.NO EVIDENCE OF PNEUMOTHORAX.  MINIMAL LEFT PLEURAL THICKENING MAY  REPRESENT SMALL AMOUNT OF BLOOD IN THE PLEURAL SPACE.   3.SUBTLE OPACITY JUST LATERAL TO THE CARDIAC APEX IN THE LEFT BASE  MAY REPRESENT A SMALL AREA OF PULMONARY CONTUSION OR OTHER CAUSE FOR  SMALL FOCUS OF CONSOLIDATION.   4.RIGHT LUNG IS CLEAR.   5.LOW LUNG VOLUMES.

---

## Case

- Study key: `patient00026/study1`
- DICOM path: `patient00026/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.500`
- Label macro score: `0.500`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Pleural Effusion', 'Lung Opacity']

### Ground Truth Present Labels

- Atelectasis
- Consolidation

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Fracture
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Low lung volumes. Discoid atelectasis and consolidation seen in the left lower lobe with an elevated left hemidiaphragm. This is unchanged from the previous chest x-ray. DISCOID CONSOLIDATION AND ATELECTASIS OF THE LEFT LOWER LOBE. UNCHANGED FROM THE PREVIOUS CHEST X-RAY.

---

## Case

- Study key: `patient00026/study1`
- DICOM path: `patient00026/study1/view2_lateral.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.500`
- Label macro score: `0.500`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Pleural Effusion', 'Lung Opacity']

### Ground Truth Present Labels

- Atelectasis
- Consolidation

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Fracture
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Low lung volumes. Discoid atelectasis and consolidation seen in the left lower lobe with an elevated left hemidiaphragm. This is unchanged from the previous chest x-ray. DISCOID CONSOLIDATION AND ATELECTASIS OF THE LEFT LOWER LOBE. UNCHANGED FROM THE PREVIOUS CHEST X-RAY.

---

## Case

- Study key: `patient00027/study1`
- DICOM path: `patient00027/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.607`

### Explanation

Very low disease F1 with critical false positives: 0.000

### Ground Truth Present Labels

- None

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Fracture
- Pleural Other

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1.FRONTAL AND LATERAL VIEWS OF THE CHEST DEMONSTRATE LOW LUNG VOLUMES  WITH BIBASILAR OPACITIES LIKELY REFLECTING ATELECTASIS.  NO EVIDENCE  OF FOCAL CONSOLIDATION, PLEURAL EFFUSIONS OR PNEUMOTHORAX.   2.THE CARDIOMEDIASTINAL SILHOUETTE AND PULMONARY VASCULATURE ARE  WITHIN NORMAL LIMITS.   3.VISUALIZED OSSEOUS STRUCTURES ARE INTACT.

---

## Case

- Study key: `patient00027/study1`
- DICOM path: `patient00027/study1/view2_lateral.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.607`

### Explanation

Very low disease F1 with critical false positives: 0.000

### Ground Truth Present Labels

- None

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Fracture
- Pleural Other

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1.FRONTAL AND LATERAL VIEWS OF THE CHEST DEMONSTRATE LOW LUNG VOLUMES  WITH BIBASILAR OPACITIES LIKELY REFLECTING ATELECTASIS.  NO EVIDENCE  OF FOCAL CONSOLIDATION, PLEURAL EFFUSIONS OR PNEUMOTHORAX.   2.THE CARDIOMEDIASTINAL SILHOUETTE AND PULMONARY VASCULATURE ARE  WITHIN NORMAL LIMITS.   3.VISUALIZED OSSEOUS STRUCTURES ARE INTACT.

---

## Case

- Study key: `patient00031/study1`
- DICOM path: `patient00031/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.222`
- Label macro score: `0.429`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Edema
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Edema
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `uncertain`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. SINGLE PORTABLE AP VIEW OF THE CHEST IS LIMITED BY PATIENT POSITION WITH ROTATION TO THE RIGHT. CONSIDER REPEAT IMAGING WITH PA AND LATERAL VIEWS IF CLINICALLY WARRANTED. 2. ILL-DEFINED, FLUFFY PERIHILAR OPACITIES, RIGHT GREATER THAN LEFT, WHICH MAY REPRESENT EARLY INFILTRATES OR ATELECTASIS. 3. INTERSTITIAL PROMINENCE AND PERIBRONCHIAL CUFFING THAT MAY BE CHRONIC IN NATURE. 4. MILD CEPHALIZATION OF THE PULMONARY VASCULATURE, CONSISTENT WITH MILD EDEMA. 5. LEFT SUBCLAVIAN CENTRAL VENOUS LINE WITH TIP IN THE RIGHT ATRIUM.

---

## Case

- Study key: `patient00031/study3`
- DICOM path: `patient00031/study3/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.200`
- Label macro score: `0.393`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Edema', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `uncertain`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Single frontal portable digital radiograph chest demonstrates rightward rotation and cardiomediastinal silhouette unchanged in size and contour.   There is new blunting of the right costophrenic sulcus suggesting right pleural effusion with an associated veiling opacity.  No definite area of consolidation or pneumothorax.  Diffuse sclerotic foci are present throughout the osseous and appendicular skeleton, unchanged. 1.  NEW RIGHT PLEURAL EFFUSION. 2.  DIFFUSE OSSEOUS SCLEROTIC DISEASE LIKELY METASTATIC FOCI.

---

## Case

- Study key: `patient00031/study2`
- DICOM path: `patient00031/study2/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.400`
- Label macro score: `0.536`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Edema
- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INTERVAL REPLACEMENT OF THE LEFT-SIDED CENTRAL VENOUS LINE, WITH TIP WITHIN THE SUPERIOR VENA CAVA. NO EVIDENCE FOR PNEUMOTHORAX. INTERVAL RESOLUTION OF MILD PULMONARY EDEMA SEEN ON PRIOR EXAM. RIGHT LOWER LOBE HAZY OPACITY, LIKELY ATELECTASIS. STABLE CARDIOMEDIASTINAL SILHOUETTE.

---

## Case

- Study key: `patient00034/study1`
- DICOM path: `patient00034/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.333`
- Label macro score: `0.571`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Edema

### Predicted Present Labels

- Cardiomegaly
- Edema
- Lung Lesion
- Lung Opacity
- Pleural Other

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Diffuse reticular opacities which are nonspecific and could be  related to interstitial lung disease, pulmonary edema, or atypical  infection. No focal consolidation. No pleural effusion or  pneumothorax. The cardiomediastinal silhouette is within normal  limits. No acute osseous abnormality. 1.  Diffuse reticular opacities which are nonspecific and could be  related to interstitial lung disease, pulmonary edema, or atypical  infection.      I have personally reviewed the images for this examination and agreed with the report transcribed above.

---

## Case

- Study key: `patient00038/study1`
- DICOM path: `patient00038/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.500`
- Label macro score: `0.536`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Edema', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Atelectasis
- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Edema
- Lung Lesion
- Lung Opacity
- Pneumonia

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1.  AP SEMI-ERECT CHEST RADIOGRAPH.  THE PATIENT IS INTUBATED, WITH THE TIP OF THE ENDOTRACHEAL TUBE APPROXIMATELY 5.5 CM ABOVE THE CARINA.  A NASOGASTRIC TUBE IS PRESENT, WITH THE TIP AND SIDE PORT BELOW THE LEFT HEMIDIAPHRAGM.  A LEFT SUBCLAVIAN VENOUS LINE IS PRESENT WITH THE TIP IN MID SUPERIOR VENA CAVA. 2.  LUNG VOLUMES ARE LOW, WITH OPACIFICATION IN THE RETROCARDIAC REGION WHICH COULD REFLECT ATELECTASIS, EARLY INFILTRATE OR ASPIRATION.  THERE IS ALSO A  LIKELY SMALL PLEURAL EFFUSION ON THIS SIDE.  MINIMAL ATELECTASIS IS ALSO SEEN AT THE RIGHT BASE.  NO EVIDENCE OF A PNEUMOTHORAX.

---

## Case

- Study key: `patient00038/study3`
- DICOM path: `patient00038/study3/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.250`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

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
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1.  SINGLE FRONTAL SEMI-UPRIGHT VIEW OF THE CHEST DEMONSTRATES STABLE POSITION OF LINES AND TUBES.  THE ENDOTRACHEAL TUBE TIP IS HIGH, ALMOST 9 CM ABOVE THE CARINA. 2.  NO OTHER SIGNIFICANT INTERVAL CHANGE FROM THE PRIOR EXAMINATION, WITH REDEMONSTRATION OF BIBASILAR OPACITIES, LEFT GREATER THAN RIGHT AND BILATERAL PLEURAL EFFUSIONS.

---

## Case

- Study key: `patient00044/study7`
- DICOM path: `patient00044/study7/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.364`
- Label macro score: `0.429`

### Explanation

Multiple critical hallucinated disease labels: ['Consolidation', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Cardiomegaly
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

- Atelectasis: predicted `present`, ground truth `uncertain`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INTERVAL REMOVAL OF RIGHT INTERNAL JUGULAR CENTRAL VENOUS LINE. 2. CARDIOMEGALY AND MILD PULMONARY EDEMA. THE PULMONARY EDEMA HAS BEEN GRADUALLY IMPROVING OVER THE LAST SEVERAL CHEST RADIOGRAPHS. 3. STABLE PATCHY OPACITIES IN BILATERAL PERIHILAR REGIONS WHICH COULD REPRESENT FLUID OR ATELECTASIS.

---

## Case

- Study key: `patient00044/study7`
- DICOM path: `patient00044/study7/view2_lateral.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.364`
- Label macro score: `0.429`

### Explanation

Multiple critical hallucinated disease labels: ['Consolidation', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Cardiomegaly
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

- Atelectasis: predicted `present`, ground truth `uncertain`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INTERVAL REMOVAL OF RIGHT INTERNAL JUGULAR CENTRAL VENOUS LINE. 2. CARDIOMEGALY AND MILD PULMONARY EDEMA. THE PULMONARY EDEMA HAS BEEN GRADUALLY IMPROVING OVER THE LAST SEVERAL CHEST RADIOGRAPHS. 3. STABLE PATCHY OPACITIES IN BILATERAL PERIHILAR REGIONS WHICH COULD REPRESENT FLUID OR ATELECTASIS.

---

## Case

- Study key: `patient00044/study1`
- DICOM path: `patient00044/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.364`
- Label macro score: `0.393`

### Explanation

Multiple critical hallucinated disease labels: ['Consolidation', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Atelectasis
- Cardiomegaly
- Edema
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

- Cardiomegaly: predicted `uncertain`, ground truth `present`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Interval placement of ET tube with tip at the level of the clavicular heads. NG tube courses into the abdomen. Interval placement of right internal jugular venous central line with tip in the mid SVC. A right IJ sheath is also present. A mitral valve ring is unchanged. A right chest tube and mediastinal drain are in place. Moderate cardiomegaly. Bibasilar opacities, likely representing atelectasis. Mild interstitial pulmonary edema. 1. INTERVAL PLACEMENT OF LINES AND TUBES AS DESCRIBED. 2. PERSISTENT CARDIOMEGALY WITH MODERATE INTERSTITIAL PULMONARY EDEMA AND BIBASILAR ATELECTASIS.

---

## Case

- Study key: `patient00044/study3`
- DICOM path: `patient00044/study3/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.200`
- Label macro score: `0.321`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Pleural Effusion
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
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INTERVAL REMOVAL OF RIGHT INTERNAL JUGULAR LINE SHEATH. THE REMAINING LINES AND TUBES ARE UNCHANGED. 2. LARGE RIGHT PLEURAL EFFUSION HAS INCREASED SINCE THE PRIOR EXAM. STABLE MODERATE LEFT PLEURAL EFFUSION. 3. ENLARGED POSTOPERATIVE CARDIOMEDIASTINAL SILHOUETTE IS UNCHANGED WITH MITRAL ANNULAR RING.

---

## Case

- Study key: `patient00044/study4`
- DICOM path: `patient00044/study4/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.200`
- Label macro score: `0.357`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Consolidation', 'Edema', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Cardiomegaly
- Pleural Effusion
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
- Cardiomegaly: predicted `uncertain`, ground truth `present`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> AP ERECT CHEST RADIOGRAPH. THERE HAS BEEN A MEDIAN STERNOTOMY, WITH PROSTHETIC VALVE REPLACEMENT. A RIGHT IJ VENOUS LINE REMAINS IN PLACE. THERE HAS BEEN INTERVAL PLACEMENT OF A RIGHT-SIDED CHEST TUBE WITH A PERSISTENT SMALL RIGHT PLEURAL EFFUSION, SLIGHTLY DECREASED IN SIZE IN COMPARISON TO PRIOR FILMS. MARKED CARDIOMEGALY IS PRESENT, WITH INCREASED OPACIFICATION SEEN IN THE RETROCARDIAC REGION, AND A LIKELY SMALL LEFT PLEURAL EFFUSION.

---

## Case

- Study key: `patient00044/study2`
- DICOM path: `patient00044/study2/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.500`
- Label macro score: `0.464`

### Explanation

Multiple critical hallucinated disease labels: ['Consolidation', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Atelectasis
- Edema
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INTERVAL EXTUBATION AND REMOVAL OF NASOGASTRIC TUBE. REMAINING LINES AND TUBES ARE UNCHANGED. 2. MODERATE RIGHT PLEURAL EFFUSION, INCREASED SINCE PRIOR EXAM. 3. BILATERAL LOW LUNG VOLUMES WITH INCREASE IN BIBASILAR ATELECTASIS. MODERATE INTERSTITIAL PULMONARY EDEMA IS UNCHANGED.

---

## Case

- Study key: `patient00044/study5`
- DICOM path: `patient00044/study5/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.462`
- Label macro score: `0.464`

### Explanation

Multiple critical hallucinated disease labels: ['Pleural Effusion', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `uncertain`, ground truth `present`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> The 0705 hours radiograph demonstrates no significant interval change in the chest allowing for technique. The lines and tubes are stable. Enlarged cardiomediastinal silhouette and moderate pulmonary edema are unchanged with patchy right lower lobe consolidation versus atelectasis. The 2310 hours examination demonstrates stable position of lines and tubes. Again seen are tricuspid and mitral annular rings. The right basilar consolidation versus atelectasis demonstrates mild interval increase in density. Stable marked cardiomegaly. MILD INCREASE IN RIGHT BASILAR CONSOLIDATION VERSUS ATELECTASIS. THE REMAINDER OF THE CHEST IS NOT SIGNIFICANTLY CHANGED.

---

## Case

- Study key: `patient00045/study1`
- DICOM path: `patient00045/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.333`
- Label macro score: `0.500`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Pleural Effusion', 'Lung Opacity']

### Ground Truth Present Labels

- Atelectasis
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Fracture
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Upright PA and lateral chest radiographs demonstrate a single lead AICD in place with the tip in the right ventricle.  Minimal linear stranding opacities are noted at bilateral lung bases, likely due to atelectasis.  No focal areas of consolidation.  No pneumothorax, pleural effusions, or pulmonary edema.  Calcified plaque is seen within the aortic arch.  The descending thoracic aorta is mildly tortuous. The cardiac silhouette size is within normal limits and otherwise the remainder of the cardiomediastinal silhouette is unremarkable.  The skeletal structures are grossly unremarkable. 1.  SINGLE LEAD AICD IN PLACE WITH THE TIP IN THE RIGHT VENTRICLE.  2.  MINIMAL BIBASILAR ATELECTASIS.  NO FOCAL CONSOLIDATION.

---

## Case

- Study key: `patient00045/study1`
- DICOM path: `patient00045/study1/view2_lateral.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.333`
- Label macro score: `0.500`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Pleural Effusion', 'Lung Opacity']

### Ground Truth Present Labels

- Atelectasis
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Fracture
- Lung Opacity
- Pleural Effusion

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Upright PA and lateral chest radiographs demonstrate a single lead AICD in place with the tip in the right ventricle.  Minimal linear stranding opacities are noted at bilateral lung bases, likely due to atelectasis.  No focal areas of consolidation.  No pneumothorax, pleural effusions, or pulmonary edema.  Calcified plaque is seen within the aortic arch.  The descending thoracic aorta is mildly tortuous. The cardiac silhouette size is within normal limits and otherwise the remainder of the cardiomediastinal silhouette is unremarkable.  The skeletal structures are grossly unremarkable. 1.  SINGLE LEAD AICD IN PLACE WITH THE TIP IN THE RIGHT VENTRICLE.  2.  MINIMAL BIBASILAR ATELECTASIS.  NO FOCAL CONSOLIDATION.

---

## Case

- Study key: `patient00048/study1`
- DICOM path: `patient00048/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.400`
- Label macro score: `0.571`

### Explanation

Multiple critical hallucinated disease labels: ['Edema', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Pneumothorax
- Support Devices

### Predicted Present Labels

- Edema
- Lung Lesion
- Pneumonia
- Pneumothorax

### Partial Or Mismatched Labels

- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> The left chest tube remains in place. There is now a small loculated pneumothorax at the lung base. PORTABLE CHEST, SINGLE VIEW, #0336146: 9-22-2005. FINDINGS: The loculated basilar pneumothorax is minimally larger after removal of the chest tube. 1.  SMALL LEFT PNEUMOTHORAX AFTER REMOVAL OF THE CHEST TUBE.

---

## Case

- Study key: `patient00049/study2`
- DICOM path: `patient00049/study2/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.400`
- Label macro score: `0.429`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Edema
- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Lung Lesion
- Lung Opacity
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1.  AP VIEW OF THE SEMIERECT CHEST DATED 11-19 AT 2019 HOURS SHOWS INTERVAL PLACEMENT OF RIGHT INTERNAL JUGULAR VENOUS CATHETER.  NO PNEUMOTHORAX.  2.  LUNG VOLUMES ARE LOW AND THERE ARE BILATERAL PATCHY OPACITIES PREDOMINANTLY IN THE MID LUNG ZONES, WHICH CAN BE CONSISTENT WITH THE LOW LUNG VOLUMES VERSUS PULMONARY EDEMA VERSUS INFILTRATES.

---

## Case

- Study key: `patient00049/study1`
- DICOM path: `patient00049/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.538`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Lung Lesion']

### Ground Truth Present Labels

- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Lung Lesion
- Pleural Other

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Lung volumes are decreased.  Trachea is midline.  Cardiomediastinal silhouette is normal in size and configuration.  Minimal atherosclerotic calcifications of the aortic knob are noted.  The bilateral hila are unremarkable.  The lung fields are clear, without focal opacities.  There is no evidence of pneumothorax, pulmonary edema or pleural effusions.  The visualized osseous structures reveal no acute abnormalities. 1.  LOW LUNG VOLUMES. 2.  NO EVIDENCE OF FOCAL PULMONARY PARENCHYMAL CONSOLIDATION OR OTHER ACUTE CARDIOPULMONARY ABNORMALITIES.

---

## Case

- Study key: `patient00055/study2`
- DICOM path: `patient00055/study2/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.400`
- Label macro score: `0.500`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Pneumonia']

### Ground Truth Present Labels

- Pneumothorax

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Pneumonia
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> A significant left pneumothorax has developed. There is no evidence of left-to-right shift of the midline structures. The right lung is clear. The cardiac configuration is normal. LEFT PNEUMOTHORAX. RESULTS CALLED TO md grimes AT 1118 HOURS.

---

## Case

- Study key: `patient00055/study2`
- DICOM path: `patient00055/study2/view2_lateral.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.400`
- Label macro score: `0.500`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Pneumonia']

### Ground Truth Present Labels

- Pneumothorax

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Pneumonia
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> A significant left pneumothorax has developed. There is no evidence of left-to-right shift of the midline structures. The right lung is clear. The cardiac configuration is normal. LEFT PNEUMOTHORAX. RESULTS CALLED TO md grimes AT 1118 HOURS.

---

## Case

- Study key: `patient00055/study3`
- DICOM path: `patient00055/study3/view1_frontal.dcm`
- Judge decision: **PARTIALLY_CONCORDANT**
- Disease F1: `0.500`
- Label macro score: `0.571`

### Explanation

Predicted present disease labels with uncertain ground truth: ['Atelectasis'] Critical hallucinated disease labels: ['Pneumonia'] Disease status mismatches: ['Pneumonia']

### Ground Truth Present Labels

- Pneumothorax
- Support Devices

### Predicted Present Labels

- Atelectasis
- Pneumonia
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Pneumonia: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THERE HAS BEEN INTERVAL PLACEMENT OF A LEFT CHEST TUBE WITH ONLY A RESIDUAL AMOUNT OF LUCENCY SURROUNDING THE TIP OF THE CHEST TUBE, CONSISTENT WITH RESIDUAL PNEUMOTHORAX. THE LEFT LUNG IS ALMOST COMPLETELY RE-EXPANDED. 2. SOME PATCHY OPACITIES PERSIST IN THE LEFT LUNG BASE AND THE PERIPHERY OF THE LEFT LUNG, LIKELY RESIDUAL ATELECTASIS FOLLOWING RE-EXPANSION. 3. RIGHT LUNG IS CLEAR.

---

## Case

- Study key: `patient00055/study1`
- DICOM path: `patient00055/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.429`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Edema', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Support Devices

### Predicted Present Labels

- Atelectasis
- Edema
- Lung Lesion
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INTERVAL PLACEMENT OF RIGHT IJ VENOUS CATHETER WITH THE TIP IN THE SUPERIOR VENA CAVA. INTERVAL PLACEMENT OF NASOGASTRIC TUBE WITH THE TIP IN THE STOMACH AND SIDE PORT IN THE DISTAL ESOPHAGUS. NEW INTRA-ABDOMINAL DRAIN ALSO PARTIALLY VISUALIZED. 2. THE LUNGS ARE CLEAR. NO CONSOLIDATION OR PLEURAL EFFUSION. 3. CARDIOMEDIASTINAL SILHOUETTE WITHIN NORMAL LIMITS.

---

## Case

- Study key: `patient00058/study1`
- DICOM path: `patient00058/study1/view1_frontal.dcm`
- Judge decision: **PARTIALLY_CONCORDANT**
- Disease F1: `0.500`
- Label macro score: `0.731`

### Explanation

Critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly'] Disease status mismatches: ['Atelectasis', 'Cardiomegaly']

### Ground Truth Present Labels

- Fracture

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Fracture

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> On the current chest examination, there is fracture deformity of the right posterolateral eighth rib again noted. This is at upper limits of normal. Soft tissues are within normal limits. The lungs are clear. The previously possible lung nodule is no longer evident and may represent a confluence of normal shadows. 1. CHEST IS WITHIN NORMAL LIMITS. COMPARISON FROM THE PRIOR DAY'S EXAMINATION INDICATES NO LUNG NODULES ARE NOW EVIDENT. AGAIN SEEN ARE MULTIPLE RIB FRACTURE DEFORMITIES ON THE RIGHT.

---

## Case

- Study key: `patient00058/study1`
- DICOM path: `patient00058/study1/view2_lateral.dcm`
- Judge decision: **PARTIALLY_CONCORDANT**
- Disease F1: `0.500`
- Label macro score: `0.731`

### Explanation

Critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly'] Disease status mismatches: ['Atelectasis', 'Cardiomegaly']

### Ground Truth Present Labels

- Fracture

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Fracture

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> On the current chest examination, there is fracture deformity of the right posterolateral eighth rib again noted. This is at upper limits of normal. Soft tissues are within normal limits. The lungs are clear. The previously possible lung nodule is no longer evident and may represent a confluence of normal shadows. 1. CHEST IS WITHIN NORMAL LIMITS. COMPARISON FROM THE PRIOR DAY'S EXAMINATION INDICATES NO LUNG NODULES ARE NOW EVIDENT. AGAIN SEEN ARE MULTIPLE RIB FRACTURE DEFORMITIES ON THE RIGHT.

---

## Case

- Study key: `patient00064/study1`
- DICOM path: `patient00064/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.571`
- Label macro score: `0.607`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Lung Lesion']

### Ground Truth Present Labels

- Edema
- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Edema
- Lung Lesion
- Lung Opacity

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Portable AP supine view of the chest demonstrates an endotracheal tube  approximately 5 cm above the carina.  External pacer pads overlying the right hemithorax and the left costophrenic angle. Cardiomediastinal silhouette is unremarkable.  Ground-glass opacities bilaterally with mild peribronchial cuffing, cannot exclude interstitial edema.  Bony structures and soft tissues appear normal. 1.  ENDOTRACHEAL TUBE  WITH DISTAL TIP BETWEEN THE CLAVICLES AND CARINA.  2.  GROUND-GLASS OPACITY AND MILD PERIBRONCHIAL CUFFING, CANNOT EXCLUDE INTERSTITIAL EDEMA.

---

## Case

- Study key: `patient00067/study4`
- DICOM path: `patient00067/study4/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.222`
- Label macro score: `0.357`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Edema', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. LEFT SIDED INTERNAL JUGULAR LINE THAT HAS BEEN REMOVED. 2. SMALL RIGHT SIDED PLEURAL EFFUSION. 3. BILATERAL LOWER LUNG FIELD NODULAR DENSITIES WHICH MAY REPRESENT NIPPLE SHADOWS BUT IF CONCERN FOR OTHER ETIOLOGY, SUGGEST REPEAT STUDY WITH NIPPLE MARKERS. 4. LOW LUNG VOLUMES. 5. PREVIOUSLY NOTED LEFT SIDED CAVITARY LESION IS NOT VISUALIZED ON THE CURRENT STUDY, IN ITS LOCATION THERE IS A LINEAR DENSITY WHICH MAY REPRESENT AN INFECTIOUS PROCESS OR SCAR. 6. OTHERWISE, NO SIGNIFICANT INTERVAL CHANGE OF THE CHEST.

---

## Case

- Study key: `patient00067/study3`
- DICOM path: `patient00067/study3/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.222`
- Label macro score: `0.321`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Consolidation
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Pneumothorax: predicted `absent`, ground truth `uncertain`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. LEFT IJ LINE REMAINS IN PLACE. 2. THERE IS INTERVAL DEVELOPMENT OF A SMALL CAVITARY LESION IN THE LEFT MID LUNG ZONE, IN AN AREA WHERE A SMALL CONSOLIDATION WAS SEEN ON THE PRIOR CHEST FILMS ON 6/17/1998 THROUGH 6-20-1998. 3. A LINEAR SHADOW IN THE LEFT LOWER LATERAL HEMITHORAX MAY REPRESENT THE PATIENT'S BREAST SHADOW, ALTHOUGH A PNEUMOTHORAX IS NOT ENTIRELY EXCLUDED. RECOMMEND REPEAT PA AND LATERAL CHEST FILMS. LUNG FIELDS ARE OTHERWISE CLEAR. FINDINGS COMMUNICATED TO THE NURSE (Simmons Lucille, PA) TAKING CARE OF THE PATIENT.

---

## Case

- Study key: `patient00067/study1`
- DICOM path: `patient00067/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.286`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `uncertain`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INTERVAL PLACEMENT OF A LEFT INTERNAL JUGULAR LINE WITH ITS TIP IN THE LOW-SVC. NO PNEUMOTHORAX IS APPARENT. 2. ELEVATED RIGHT HEMIDIAPHRAGM WITH A POSSIBLE TINY RIGHT PLEURAL EFFUSION. THE LUNGS ARE OTHERWISE CLEAR. NO SIGNIFICANT INTERVAL CHANGE.

---

## Case

- Study key: `patient00067/study2`
- DICOM path: `patient00067/study2/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.200`
- Label macro score: `0.321`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

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
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THE PATIENT IS ROTATED TO THE RIGHT ON THIS FILM. OTHERWISE, THERE IS GROSSLY NO SIGNIFICANT INTERVAL CHANGE WITH STABLE POSITION OF SUPPORTIVE DEVICES AND PERSISTENT LOW LUNG VOLUMES. 2. REDEMONSTRATION OF SMALL RIGHT PLEURAL EFFUSION. THE LUNGS ARE, OTHERWISE, CLEAR BILATERALLY.

---

## Case

- Study key: `patient00068/study1`
- DICOM path: `patient00068/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.250`
- Label macro score: `0.429`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Edema

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Edema
- Lung Lesion
- Lung Opacity
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Single AP portable view of the chest demonstrates cephalization of the central vessels consistent with pulmonary venous hypertension. No evidence of frank pulmonary edema is noted. Cardiomediastinal silhouette appears unremarkable. Lungs are clear bilaterally. Visualized bones are intact. No soft tissue abnormalities are appreciated. 1. NO EVIDENCE OF PNEUMOTHORAX. 2. CEPHALIZATION OF CENTRAL VESSELS SUGGESTIVE OF PULMONARY VENOUS HYPERTENSION WITH NO FRANK PULMONARY EDEMA.

---

## Case

- Study key: `patient00070/study1`
- DICOM path: `patient00070/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.462`

### Explanation

Very low disease F1 with critical false positives: 0.000

### Ground Truth Present Labels

- No Finding

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Fracture
- Pleural Other

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1.SINGLE FRONTAL VIEW OF THE CHEST DEMONSTRATES NO EVIDENCE OF FOCAL  AIR SPACE CONSOLIDATION, PLEURAL EFFUSION, OR PNEUMOTHORAX.   2.THE CARDIOMEDIASTINAL SILHOUETTE AND PULMONARY VASCULARITY ARE  WITHIN NORMAL LIMITS.   3.THE OSSEOUS STRUCTURES ARE NORMAL IN APPEARANCE.

---

## Case

- Study key: `patient00076/study1`
- DICOM path: `patient00076/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.222`
- Label macro score: `0.393`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Lung Opacity
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

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `uncertain`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> AP portable chest, 5/4/2007 at 1536 hours is compared with 5/4/2007, 1/29/2013 two view chest. Substantially lower lung volumes. Focal right upper lobe peripheral parenchymal airspace opacity adjacent to the minor fissure may represent focal infection. Probable left pleural effusion. New right internal jugular central venous catheter in superior vena cava. Low lung volumes. No definite pneumothorax although motion artifact degrades image quality. 1. RIGHT IJ CENTRAL VENOUS PRESSURE SATISFACTORY. 2. NEW AIRSPACE OPACITY RIGHT UPPER LOBE AS DESCRIBED. 3. LIMITED BY MOTION ARTIFACT. 4. LOW LUNG VOLUMES AND POSSIBLE LEFT PLEURAL EFFUSION.

---

## Case

- Study key: `patient00078/study6`
- DICOM path: `patient00078/study6/view1_frontal.dcm`
- Judge decision: **PARTIALLY_CONCORDANT**
- Disease F1: `0.500`
- Label macro score: `0.607`

### Explanation

Critical hallucinated disease labels: ['Cardiomegaly', 'Lung Lesion'] Disease status mismatches: ['Cardiomegaly', 'Lung Lesion']

### Ground Truth Present Labels

- Pneumothorax

### Predicted Present Labels

- Cardiomegaly
- Lung Lesion
- Pneumothorax

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> The left-sided pneumothorax appears slightly increased in size. No additional interval change. 6340977630: SINGLE VIEW PORTABLE CHEST: 5-6-2010 Health Plus Xpress 0620 HOURS FINDINGS: The left pneumothorax has decreased in size. No new abnormalities. DECREASED SIZE OF LEFT PNEUMOTHORAX ON THE MOST RECENT FILM.

---

## Case

- Study key: `patient00078/study7`
- DICOM path: `patient00078/study7/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.333`
- Label macro score: `0.536`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Pneumothorax
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Lung Lesion
- Pneumonia
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> The left chest tube is again noted. The volume of pneumothorax has increased slightly. 49335592 SINGLE RADIOGRAPH OF THE CHEST: FINDINGS: No interval change. 402809495 SINGLE RADIOGRAPH OF THE CHEST: FINDINGS: The chest tube has been replaced by an apical pigtail catheter. The pneumothorax is not identified. DIMINISHED PNEUMOTHORAX AFTER PLACEMENT OF PIGTAIL CATHETER.

---

## Case

- Study key: `patient00078/study9`
- DICOM path: `patient00078/study9/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.400`
- Label macro score: `0.607`

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

> The left chest tube is again noted. The volume of pneumothorax has increased slightly. 7172 SINGLE RADIOGRAPH OF THE CHEST: FINDINGS: No interval change. 2911246394 SINGLE RADIOGRAPH OF THE CHEST: FINDINGS: The chest tube has been replaced by an apical pigtail catheter. The pneumothorax is not identified. DIMINISHED PNEUMOTHORAX AFTER PLACEMENT OF PIGTAIL CATHETER.

---

## Case

- Study key: `patient00078/study5`
- DICOM path: `patient00078/study5/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.333`
- Label macro score: `0.571`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Pneumothorax

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Lung Lesion
- Pneumonia
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> The left-sided pneumothorax appears slightly increased in size. No additional interval change. 865_804_567_991_957_3: SINGLE VIEW PORTABLE CHEST: 1/18/2017 USC Center for Body Computing 0620 HOURS FINDINGS: The left pneumothorax has decreased in size. No new abnormalities. DECREASED SIZE OF LEFT PNEUMOTHORAX ON THE MOST RECENT FILM.

---

## Case

- Study key: `patient00078/study4`
- DICOM path: `patient00078/study4/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.286`
- Label macro score: `0.500`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Pneumothorax

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Lung Lesion
- Lung Opacity
- Pneumonia
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> The left pneumothorax has significantly decreased in size. No new abnormalities. #5153155048 SINGLE VIEW PORTABLE CHEST: 12-16-2005 at 0600 HOURS. FINDINGS: The left pneumothorax has increased slightly in size. 1. SLIGHT INCREASE IN LEFT APICAL PNEUMOTHORAX ON THE MOST RECENT FILM.

---

## Case

- Study key: `patient00078/study1`
- DICOM path: `patient00078/study1/view1_frontal.dcm`
- Judge decision: **PARTIALLY_CONCORDANT**
- Disease F1: `0.500`
- Label macro score: `0.643`

### Explanation

Critical hallucinated disease labels: ['Cardiomegaly', 'Lung Lesion'] Disease status mismatches: ['Cardiomegaly', 'Lung Lesion']

### Ground Truth Present Labels

- Pneumothorax
- Support Devices

### Predicted Present Labels

- Cardiomegaly
- Lung Lesion
- Pneumothorax

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Portable upright chest radiograph obtained in the recovery room demonstrates a left chest tube in place. The end of the chest tube is bent at the apex with the tip directed toward the mediastinum. Surgical suture material is seen to project over the right upper lung zone as well as the left upper lung zone. There are multiple linear densities projecting over the upper chest, likely external to the patient related to the sheets. This limits the evaluation for a pneumothorax; however, there may be a possible small left apical pneumothorax present. The lungs are otherwise clear with no pleural effusions or pulmonary edema. The cardiomediastinal silhouette is unremarkable. The skeletal structures are grossly unremarkable. 1. LEFT CHEST TUBE IN PLACE WITH THE TIP DIRECTED TOWARD THE MEDIASTINUM. 2. POSTOPERATIVE CHEST WITH ARTIFACTS PROJECTING OVER THE CHEST, WHICH LIMITS THE EVALUATION FOR A ...[truncated]

---

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

## Case

- Study key: `patient00078/study3`
- DICOM path: `patient00078/study3/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.333`
- Label macro score: `0.536`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Pneumothorax

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Lung Lesion
- Pneumonia
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> The left pneumothorax has significantly decreased in size. No new abnormalities. X830G995434 SINGLE VIEW PORTABLE CHEST: 2012/7/13 at 0600 HOURS. FINDINGS: The left pneumothorax has increased slightly in size. 1. SLIGHT INCREASE IN LEFT APICAL PNEUMOTHORAX ON THE MOST RECENT FILM.

---

## Case

- Study key: `patient00078/study2`
- DICOM path: `patient00078/study2/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.286`
- Label macro score: `0.464`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Pneumothorax
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Lung Lesion
- Lung Opacity
- Pneumonia
- Pneumothorax

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. RE-DEMONSTRATED LEFT CHEST TUBE. 2. RE-DEMONSTRATED MULTIPLE SUTURE LINES IN THE BILATERAL LUNG APICES. 3. INTERVAL MARKED INCREASE IN THE PREVIOUSLY NOTED LEFT PNEUMOTHORAX. NO EVIDENCE OF MEDIASTINAL SHIFT TO SUGGEST TENSION. 4. FINDINGS WERE DISCUSSED WITH Moyer, Miguel AT 9 AM ON 08/27/2016.

---

## Case

- Study key: `patient00087/study3`
- DICOM path: `patient00087/study3/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.462`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Lung Lesion']

### Ground Truth Present Labels

- None

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Fracture
- Lung Lesion
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `uncertain`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THE LUNGS APPEAR CLEAR WITHOUT A FOCAL PARENCHYMAL PROCESS. 2. THERE IS MINIMAL BLUNTING OF THE RIGHT COSTOPHRENIC ANGLE LIKELY REPRESENTING A SMALL PLEURAL EFFUSION.

---

## Case

- Study key: `patient00087/study3`
- DICOM path: `patient00087/study3/view2_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.462`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Lung Lesion']

### Ground Truth Present Labels

- None

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Fracture
- Lung Lesion
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `uncertain`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THE LUNGS APPEAR CLEAR WITHOUT A FOCAL PARENCHYMAL PROCESS. 2. THERE IS MINIMAL BLUNTING OF THE RIGHT COSTOPHRENIC ANGLE LIKELY REPRESENTING A SMALL PLEURAL EFFUSION.

---

## Case

- Study key: `patient00087/study3`
- DICOM path: `patient00087/study3/view3_lateral.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.464`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Lung Lesion']

### Ground Truth Present Labels

- None

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Fracture
- Lung Lesion
- Pleural Effusion

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `uncertain`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THE LUNGS APPEAR CLEAR WITHOUT A FOCAL PARENCHYMAL PROCESS. 2. THERE IS MINIMAL BLUNTING OF THE RIGHT COSTOPHRENIC ANGLE LIKELY REPRESENTING A SMALL PLEURAL EFFUSION.

---

## Case

- Study key: `patient00087/study1`
- DICOM path: `patient00087/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.250`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

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
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `uncertain`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. ENDOTRACHEAL TUBE, RIGHT IJ CENTRAL LINE, TWO MEDIASTINAL DRAINS WITH ONE OF THEM POSSIBLY PERICARDIAL, STERNOTOMY WIRES ARE UNCHANGED. 2. MILD CEPHALIZATION OF THE VESSELS WITH POSSIBLE LEFT PLEURAL EFFUSION.

---

## Case

- Study key: `patient00087/study2`
- DICOM path: `patient00087/study2/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.364`
- Label macro score: `0.464`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Consolidation', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Cardiomegaly
- Lung Opacity

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `uncertain`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THERE HAS BEEN SIGNIFICANT INTERVAL DECREASE IN CARDIOMEGALY, LIKELY RELATED TO RESOLUTION OF THE KNOWN PERICARDIAL EFFUSION. THE HEART SILHOUETTE IS NOW NORMAL. MILD ILL-DEFINED RIGHT PERIHILAR OPACITY, LIKELY RELATED TO RESIDUAL PARENCHYMAL OPACITY AS SEEN ON THE CT FROM 10 December. NO EVIDENCE OF PULMONARY EDEMA OR PNEUMOTHORAX OR PNEUMOMEDIASTINUM.

---

## Case

- Study key: `patient00095/study1`
- DICOM path: `patient00095/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.444`
- Label macro score: `0.500`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Edema', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Edema
- Lung Lesion
- Lung Opacity
- Pneumonia

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `present`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> The cardiomediastinal silhouette is at the upper limit of normal. The  aorta is tortuous. Pulmonary vessels are not distended.   No abnormality of the right costophrenic angle. The left costophrenic  angle is not included on the film. No pneumothorax. There is  retrocardiac airspace opacity with partial silhouetting of the left  hemidiaphragm and descending thoracic aorta. Linear opacities at the  right lung base likely represents scar or atelectasis. Lungs are  otherwise clear.   Diffuse osteopenia. No acute osseous abnormalities. 1.  Retrocardiac consolidation may represent infection, atelectasis,  or aspiration. Further evaluation with a lateral radiograph would be  helpful. A follow-up chest radiograph following treatment is also  recommended to document resolution. 2.  Mild right basilar atelectasis or scarring.   I have personally reviewed the images for this examination and agreed ...[truncated]

---

## Case

- Study key: `patient00096/study1`
- DICOM path: `patient00096/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.500`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Lung Lesion
- Lung Opacity
- Pleural Other

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Diffuse idiopathic skeletal hyperostosis coronary artery bypass graft. Trachea is midline. The mediastinum is unremarkable. No significant change in the heart size. Right subclavian line tip superior vena cava right atrium. No pneumothorax. Distended central pulmonary vessels without kerley "b" lines. Central pulmonary vessels more distended than noted on examination of 8/8/2005. Parenchymal density bilaterally. No evidence of lobar collapse. 1. HISTORY OF NEUTROPENIC FEVER WITH INCREASED VENOUS CONGESTION PRESENT BILATERALLY WITHOUT EVIDENCE OF FOCAL CONSOLIDATION. CONTINUED RADIOGRAPHIC FOLLOW-UP RECOMMENDED.

---

## Case

- Study key: `patient00096/study1`
- DICOM path: `patient00096/study1/view2_lateral.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.500`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Lung Lesion
- Lung Opacity
- Pleural Other

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Diffuse idiopathic skeletal hyperostosis coronary artery bypass graft. Trachea is midline. The mediastinum is unremarkable. No significant change in the heart size. Right subclavian line tip superior vena cava right atrium. No pneumothorax. Distended central pulmonary vessels without kerley "b" lines. Central pulmonary vessels more distended than noted on examination of 8/8/2005. Parenchymal density bilaterally. No evidence of lobar collapse. 1. HISTORY OF NEUTROPENIC FEVER WITH INCREASED VENOUS CONGESTION PRESENT BILATERALLY WITHOUT EVIDENCE OF FOCAL CONSOLIDATION. CONTINUED RADIOGRAPHIC FOLLOW-UP RECOMMENDED.

---

## Case

- Study key: `patient00096/study2`
- DICOM path: `patient00096/study2/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.222`
- Label macro score: `0.429`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Edema
- Support Devices

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. REDEMONSTRATION OF RIGHT UPPER EXTREMITY PICC LINE. 2. REDEMONSTRATION OF POSTOPERATIVE CHANGES, CONSISTENT WITH PRIOR MEDIAN STERNOTOMY. 3. INTERVAL DEVELOPMENT OF MILD INTERSTITIAL PULMONARY EDEMA.

---

## Case

- Study key: `patient00102/study1`
- DICOM path: `patient00102/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.286`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

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

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. A LEFT UPPER EXTREMITY PICC LINE IS UNCHANGED IN POSITION. 2. THERE ARE LOW LUNG VOLUMES, THE LUNGS ARE OTHERWISE CLEAR WITH NO EVIDENCE OF FOCAL OPACIFICATION OR PLEURAL EFFUSIONS. 3. NO PNEUMOTHORAX.

---

## Case

- Study key: `patient00102/study3`
- DICOM path: `patient00102/study3/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.250`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pleural Effusion', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

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
- Pleural Other

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INTACT MIDLINE STERNOTOMY WIRES ARE REDEMONSTRATED. A RIGHT UPPER EXTREMITY PICC LINE REMAINS IN PLACE WITH TIP NOW IN THE PROXIMAL SVC. 2. LOW LUNG VOLUMES WITHOUT PULMONARY EDEMA, CONSOLIDATION, OR PLEURAL EFFUSION. 3. THE CARDIOMEDIASTINAL SILHOUETTE IS STABLE AND WITHIN NORMAL LIMITS.

---

## Case

- Study key: `patient00102/study2`
- DICOM path: `patient00102/study2/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.214`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

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
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INTERVAL PLACEMENT OF A RIGHT INTERNAL JUGULAR SHEATH WITH ITS TIP IN THE INTERNAL JUGULAR/RIGHT SUBCLAVIAN JUNCTION. THERE IS STABLE REDEMONSTRATION ON THE LEFT UPPER EXTREMITY PICC LINE AND STERNAL WIRES. 2. THERE IS ABUNDANT MOTION ARTIFACT IN THE CURRENT FILM BUT THERE IS NO EVIDENCE OF INFILTRATES, EFFUSIONS OR PNEUMOTHORAX.

---

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

## Case

- Study key: `patient00113/study1`
- DICOM path: `patient00113/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.200`
- Label macro score: `0.357`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pleural Effusion', 'Lung Lesion']

### Ground Truth Present Labels

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

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `uncertain`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INCREASING PATCHY AIRSPACE OPACITY AT THE RIGHT LUNG BASE WORRISOME FOR POSSIBLE PNEUMONIA. WOULD RECOMMEND CLINICAL CORRELATION. THIS IS SLIGHTLY INCREASED RETICULAR OPACITIES ALSO NOTED IN THE RIGHT MID AND UPPER LUNG ZONES. 2. LOW LUNG VOLUMES WITH POST-SURGICAL CHANGES AND LEFT SIDED PACEMAKER AGAIN SEEN IN PLACE ALL UNCHANGED.

---

## Case

- Study key: `patient00113/study2`
- DICOM path: `patient00113/study2/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.182`
- Label macro score: `0.286`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Pleural Effusion
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
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. AP PORTABLE UPRIGHT VIEW OF THE CHEST DATED 6/26/2005 REDEMONSTRATES A DUAL LEAD PACEMAKER WITH ONE LEAD PROJECTING TO THE RIGHT ATRIUM AND ONE TO THE RIGHT VENTRICLE.  REDEMONSTRATION OF STERNOTOMY WIRES.  2. NEW RIGHT PLEURAL EFFUSION AND ATELECTATIC CHANGES OF THE RIGHT LUNG.

---

## Case

- Study key: `patient00114/study5`
- DICOM path: `patient00114/study5/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.545`
- Label macro score: `0.464`

### Explanation

Multiple critical hallucinated disease labels: ['Edema', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Atelectasis
- Consolidation
- Lung Opacity
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

- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> ENDOTRACHEAL TUBE, RIGHT IJ LINE, FEEDING TUBE, STENT AND STERNAL SUTURE WIRES ARE GROSSLY UNCHANGED IN CONFIGURATION. THERE IS INTERVAL IMPROVEMENT IN RIGHT LUNG AERATION WITH DECREASING ALVEOLAR OPACITY. THE LEFT LUNG APPEARS SLIGHTLY BETTER AERATED AS WELL. THE LARGE OVOID SOFT TISSUE STRUCTURE IN THE LEFT UPPER LOBE IS AGAIN NOTED AND UNCHANGED. THERE IS PERSISTENT LEFT LOWER LOBE ATELECTASIS AND/OR CONSOLIDATION.

---

## Case

- Study key: `patient00114/study10`
- DICOM path: `patient00114/study10/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.500`
- Label macro score: `0.464`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Consolidation
- Edema
- Pleural Effusion
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
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> AGAIN SEEN ARE BILATERAL PLEURAL EFFUSIONS, PULMONARY EDEMA AND LEFT LOWER LOBE CONSOLIDATION. THE RIGHT-SIDED PICC LINE IS NOW REDIRECTED AND TERMINATES IN THE DISTAL SUPERIOR VENA CAVA.

---

## Case

- Study key: `patient00114/study15`
- DICOM path: `patient00114/study15/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.250`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

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
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. TRACHEOSTOMY TUBE, MEDIAN STERNOTOMY WIRES, STENT, AND PSEUDOANEURYSM COILS ARE UNCHANGED. 2. NO SIGNIFICANT CHANGE IN DIFFUSE INTERSTITIAL PATTERN IN THE LUNGS WHICH IS LIKELY A SEQUELA OF PRIOR INFECTIONS. NO NEW CONSOLIDATION.

---

## Case

- Study key: `patient00114/study16`
- DICOM path: `patient00114/study16/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.200`
- Label macro score: `0.321`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Lung Opacity

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
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. NO SIGNIFICANT INTERVAL CHANGE IN TRACHEOSTOMY, MEDIAN STERNOTOMY WIRES, STENT, AND PSEUDOANEURYSM COILS. 2. REDEMONSTRATION OF OPACITY IN THE LEFT UPPER LUNG FIELD CONSISTENT WITH PSEUDOANEURYSM IN THIS AREA. 3. NO SIGNIFICANT CHANGE IN LEFT LOWER LOBE OPACITY AND LEFT PLEURAL EFFUSION.

---

## Case

- Study key: `patient00114/study20`
- DICOM path: `patient00114/study20/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.462`
- Label macro score: `0.429`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Consolidation', 'Edema', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Atelectasis
- Lung Opacity
- Pleural Effusion
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
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. LEFT UPPER EXTREMITY PICC LINE, DISTAL TIP OF WHICH IS STILL  WITHIN THE LEFT AXILLA. 2. RIGHT CENTRAL LINE, TRACHEOSTOMY, POSTSURGICAL WIRES, AORTIC  VALVE, AND STENT GRAFT UNCHANGED FROM PREVIOUS. 3. INCREASED OPACIFICATION OF THE LEFT LUNG BASE CONSISTENT WITH  ATELECTASIS VERSUS INFECTION WITH PERSISTENT LEFT PLEURAL  EFFUSION. 4. LEFT UPPER LUNG OPACITY IS UNCHANGED FROM PREVIOUS. 5. NO INTERSTITIAL EDEMA.

---

## Case

- Study key: `patient00114/study3`
- DICOM path: `patient00114/study3/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.400`
- Label macro score: `0.393`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Edema', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Consolidation
- Lung Opacity
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
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> THE ENDOTRACHEAL TUBE, NASOGASTRIC TUBE, FEEDING TUBE AND RIGHT INTERNAL JUGULAR CENTRAL VENOUS CATHETERS ALL APPEAR UNCHANGED IN CONFIGURATION. AGAIN NOTED IS A STENT GRAFT IN THE AORTA AT THE LEVEL OF THE ARCH. PERSISTENT OVOID OPACITY IN THE LEFT UPPER LUNG ZONE, GROSSLY UNCHANGED. EXTENSIVE ALVEOLAR OPACITY OF THE RIGHT LUNG, ALSO GROSSLY UNCHANGED. PERSISTENT LEFT LOWER LOBE CONSOLIDATION. THE OVERALL APPEARANCE OF THE CHEST DOES NOT SIGNIFICANTLY DIFFER FROM THE PRIOR STUDY.

---

## Case

- Study key: `patient00114/study17`
- DICOM path: `patient00114/study17/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.400`
- Label macro score: `0.429`

### Explanation

Multiple critical hallucinated disease labels: ['Edema', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Atelectasis
- Consolidation
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

- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> AP SEMI-ERECT FILM. THE RIGHT SUBCLAVIAN VENOUS LINE AND TRACHEOSTOMY TUBE REMAIN UNCHANGED. THERE IS A RIGHT-SIDED PICC LINE IN PLACE. THERE HAS BEEN A MEDIAN STERNOTOMY WITH METALLIC MESH IN THE AORTIC ARCH. THE PREVIOUSLY NOTED PATCHY CONSOLIDATION AT THE RIGHT BASE HAS RESOLVED. THE RIGHT LUNG NOW APPEARS CLEAR. A ROUNDED DENSITY IS ONCE AGAIN DEMONSTRATED ADJACENT TO THE AORTIC ARCH, UNCHANGED IN APPEARANCE. THERE IS ALSO PERSISTENT LEFT LOWER LOBE ATELECTASIS OR CONSOLIDATION.

---

## Case

- Study key: `patient00114/study13`
- DICOM path: `patient00114/study13/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.364`
- Label macro score: `0.357`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Edema
- Lung Opacity

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

### Ground Truth Report Excerpt

> 1. INTERVAL DECREASE IN PULMONARY EDEMA, MODERATE EDEMA REMAINS. 2. LEFT UPPER LUNG ZONE FOCAL OPACITY SUGGESTIVE OF PSEUDOANEURYSM ADJACENT TO THE POST-OPERATIVE CHANGES AGAIN NOTED.

---

## Case

- Study key: `patient00114/study19`
- DICOM path: `patient00114/study19/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.182`
- Label macro score: `0.286`

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
- Pleural Other
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
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. LEFT UPPER EXTREMITY PICC LINE STILL LOCATED WITHIN THE AXILLA. 2. RIGHT INTERNAL JUGULAR LINE, TRACHEOSTOMY, POST SURGICAL WIRES, AND VALVE UNCHANGED FROM PREVIOUS. 3. PERSISTENT MILD INTERSTITIAL EDEMA. 4. INTERVAL IMPROVEMENT IN LUNG VOLUMES WITH STABLE LEFT UPPER LUNG ZONE AND LOWER LUNG ZONE OPACITIES, AS PREVIOUSLY DESCRIBED.

---

## Case

- Study key: `patient00114/study7`
- DICOM path: `patient00114/study7/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.250`
- Label macro score: `0.429`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Consolidation
- Edema
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Edema
- Fracture
- Lung Lesion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `present`
- Pleural Effusion: predicted `uncertain`, ground truth `present`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> There is increasing opacification of the left hemithorax. There is persistent pulmonary edema on the right. ET-tube remains approximately 8 cm above the carina. A right subclavian line has its distal tip in the SVC. Aortic stent graft is located in the proximal descending thoracic aorta. 1. WORSENING LEFT LUNG CONSOLIDATION AND/OR EFFUSION. 2. PERSISTENT PATTERN OF PULMONARY EDEMA ON THE RIGHT.

---

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

## Case

- Study key: `patient00114/study9`
- DICOM path: `patient00114/study9/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.222`
- Label macro score: `0.357`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Edema', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Consolidation
- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `present`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INCREASING RIGHT LOWER LOBE CONSOLIDATION AND PLEURAL EFFUSION.

---

## Case

- Study key: `patient00114/study1`
- DICOM path: `patient00114/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.615`
- Label macro score: `0.500`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Atelectasis
- Consolidation
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

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> In the interval since the 02/16 chest radiograph, the patient has undergone cardiothoracic surgery. Numerous midline sternal suture wires are now identified with right and left-sided chest tubes as well as a mediastinal drain now in place. The left-sided chest tube extends into the region of the left lung base. The right-sided tube extends to the upper right lung zone. The patient is now intubated with the endotracheal tube tip at the level of the clavicles. A nasogastric tube is now identified as well, however the tip is not visualized on the current study. Stent graft is again noted in the region of the aortic arch with apparent embolization coils again noted. There is now more confluent appearing opacity in the left upper lobe which again may represent hemorrhage or possibly infection. There is minimal aerated left lung. Significant atelectasis and/or consolidation of the left lower l ...[truncated]

---

## Case

- Study key: `patient00114/study6`
- DICOM path: `patient00114/study6/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.364`
- Label macro score: `0.393`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Edema
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
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> NO SIGNIFICANT CHANGE. AGAIN SEEN ARE PLEURAL EFFUSIONS AND PULMONARY EDEMA.

---

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

## Case

- Study key: `patient00114/study4`
- DICOM path: `patient00114/study4/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.400`
- Label macro score: `0.429`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Consolidation', 'Pleural Effusion', 'Pneumonia', 'Lung Opacity']

### Ground Truth Present Labels

- Edema
- Lung Lesion
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
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. TUBES AND LINES STABLE. 2. DECREASE IN PULMONARY EDEMA, AND CLEARANCE OF THE RIGHT LOWER LUNG. COMPARE WITH PRIOR STUDY. 3. PERSISTENT MASS LATERAL TO THE AORTIC ARCH, UNCHANGED. 4. POSITION OF THE AORTIC ARCH STENT GRAFT AND EMBOLIZATION COILS UNCHANGED.

---

## Case

- Study key: `patient00114/study8`
- DICOM path: `patient00114/study8/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `1.000`
- Label macro score: `0.321`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Edema', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Consolidation
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `uncertain`, ground truth `present`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `uncertain`, ground truth `present`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THE FEEDING TUBE HAS BEEN REMOVED. THE ENDOTRACHEAL TUBE AND RIGHT SUBCLAVIAN VENOUS CATHETER ARE UNCHANGED IN POSITION. AGAIN SEEN IS LEFT LOWER LOBE CONSOLIDATION AND PATCHY AIR SPACE OPACITIES BILATERALLY, WHICH ARE NOT SIGNIFICANTLY CHANGED. THE RIGHT PLEURAL EFFUSION MAY BE SLIGHTLY LARGER OR LAYERING MOST POSTERIORLY THAN ON PRIOR EXAMINATION.

---

## Case

- Study key: `patient00114/study14`
- DICOM path: `patient00114/study14/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.364`
- Label macro score: `0.393`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Consolidation', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Edema
- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. INTERVAL REMOVAL OF SWAN-GANZ CATHETER. TRACHEOSTOMY TUBE, STENT, RIGHT CHEST TUBE, AND PSEUDOANEURYSM COILS APPEAR UNCHANGED. 2. PERSISTENT LEFT BASE OPACITY. 3. INTERVAL IMPROVEMENT IN PULMONARY EDEMA.

---

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

## Case

- Study key: `patient00115/study2`
- DICOM path: `patient00115/study2/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.464`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- None

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Lung Lesion
- Lung Opacity
- Pleural Other

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `uncertain`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `absent`, ground truth `uncertain`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> THERE HAS BEEN INTERVAL DEVELOPMENT OF PATCHY OPACITIES  PREDOMINATELY AT THE LUNG BASES, THAT COULD REPRESENT ATELECTASIS OR  CONSOLIDATION.

---

## Case

- Study key: `patient00120/study1`
- DICOM path: `patient00120/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.500`

### Explanation

Very low disease F1 with critical false positives: 0.000

### Ground Truth Present Labels

- No Finding

### Predicted Present Labels

- Fracture
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1.  SINGLE FRONTAL RADIOGRAPH OF THE CHEST DEMONSTRATES A NORMAL  CARDIOMEDIASTINAL SILHOUETTE.     2.  LUNGS DEMONSTRATE NO FOCAL OPACITY.  NO PLEURAL EFFUSIONS.  NO  PNEUMOTHORAX.     3.  VISUALIZED OSSEOUS STRUCTURES AND SOFT TISSUES UNREMARKABLE.

---

## Case

- Study key: `patient00121/study1`
- DICOM path: `patient00121/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.357`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Edema', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- No Finding

### Predicted Present Labels

- Cardiomegaly
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Other

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. LIMITED PORTABLE SUPINE VIEW ON BACKBOARD DEMONSTRATES A WIDENED APPEARANCE OF THE MEDIASTINUM. THIS MAY BE RELATED TO TECHNIQUE AND WOULD RECOMMEND UPRIGHT PA VIEW WHEN PATIENT IS ABLE. 2. LUNGS CLEAR WITHOUT EDEMA, EFFUSION, FOCAL OPACITY, OR PNEUMOTHORAX. 3. NO GROSS OSSEOUS ABNORMALITY.

---

## Case

- Study key: `patient00122/study3`
- DICOM path: `patient00122/study3/view1_frontal.dcm`
- Judge decision: **PARTIALLY_CONCORDANT**
- Disease F1: `0.500`
- Label macro score: `0.571`

### Explanation

Ground-truth present disease labels predicted uncertain: ['Pleural Other'] Critical hallucinated disease labels: ['Consolidation', 'Edema'] Disease status mismatches: ['Consolidation', 'Edema', 'Fracture']

### Ground Truth Present Labels

- Atelectasis
- Pleural Effusion
- Pleural Other
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Fracture
- Pleural Effusion

### Partial Or Mismatched Labels

- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> Initial chest x-ray dated november 2003 at 0847 hours shows an irregular left pleural effusion and a smaller right effusion. Left lower lobe atelectasis present. A left chest tube is present. Follow-up chest x-ray dated 11-11-2003 at 1033 hours shows interval removal of left sided chest tube with no pneumothorax visible. 1. IRREGULAR LEFT PLEURAL THICKENING AND SMALL RIGHT EFFUSION WITH LEFT LOWER LOBE ATELECTASIS. 2. NO PNEUMOTHORAX.

---

## Case

- Study key: `patient00122/study3`
- DICOM path: `patient00122/study3/view2_lateral.dcm`
- Judge decision: **PARTIALLY_CONCORDANT**
- Disease F1: `0.500`
- Label macro score: `0.571`

### Explanation

Ground-truth present disease labels predicted uncertain: ['Pleural Other'] Critical hallucinated disease labels: ['Consolidation', 'Edema'] Disease status mismatches: ['Consolidation', 'Edema', 'Fracture']

### Ground Truth Present Labels

- Atelectasis
- Pleural Effusion
- Pleural Other
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Fracture
- Pleural Effusion

### Partial Or Mismatched Labels

- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Pleural Other: predicted `uncertain`, ground truth `present`

### Ground Truth Report Excerpt

> Initial chest x-ray dated november 2003 at 0847 hours shows an irregular left pleural effusion and a smaller right effusion. Left lower lobe atelectasis present. A left chest tube is present. Follow-up chest x-ray dated 11-11-2003 at 1033 hours shows interval removal of left sided chest tube with no pneumothorax visible. 1. IRREGULAR LEFT PLEURAL THICKENING AND SMALL RIGHT EFFUSION WITH LEFT LOWER LOBE ATELECTASIS. 2. NO PNEUMOTHORAX.

---

## Case

- Study key: `patient00122/study5`
- DICOM path: `patient00122/study5/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.200`
- Label macro score: `0.357`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Consolidation', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Lung Opacity
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `uncertain`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. UNCHANGED POSITION OF RIGHT CHEST TUBE. 2. LOW LUNG VOLUMES WITH BIBASILAR OPACITIES. 3. RIGHT MID LUNG OPACITY. 4. THE ABOVE FINDINGS HAVE WORSENED IN APPEARANCE COMPARED TO THE PRIOR EXAM AND ARE SUGGESTIVE OF INCREASE IN EDEMA VERSUS INCREASING INFECTION.

---

## Case

- Study key: `patient00122/study1`
- DICOM path: `patient00122/study1/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.200`
- Label macro score: `0.357`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pneumonia', 'Lung Opacity']

### Ground Truth Present Labels

- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Fracture
- Lung Opacity
- Pleural Effusion
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> In comparison to the prior examination, there has been significant reduction in a left pleural effusion. A moderate-sized layering left effusion, however, still remains. No pneumothorax is evident. There is significant destruction identified of the left sixth rib. In addition, a calcified granuloma is noted within the left mid- lung. Surgical clips are noted within the right axilla. There has been a right mastectomy. 1. EVIDENCE OF LEFT MODERATE-SIZED PLEURAL EFFUSION WITH CONTINUED EVIDENCE OF BONY METASTATIC DISEASE INVOLVING THE LEFT SIXTH RIB. 2. POST-SURGICAL CHANGES IDENTIFIED CONSISTENT WITH RIGHT MASTECTOMY AND AXILLARY NODE DISSECTION. 3. NO NEW EFFUSION OR MASS IS IDENTIFIED.

---

## Case

- Study key: `patient00122/study4`
- DICOM path: `patient00122/study4/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.364`
- Label macro score: `0.429`

### Explanation

Multiple critical hallucinated disease labels: ['Edema', 'Pleural Effusion', 'Pneumonia', 'Lung Lesion']

### Ground Truth Present Labels

- Atelectasis
- Lung Opacity

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Consolidation: predicted `present`, ground truth `uncertain`
- Edema: predicted `present`, ground truth `absent`
- Pleural Effusion: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. SINGLE VIEW OF THE CHEST FROM 1748 HOURS DEMONSTRATES PERSISTENT LEFT PLEURAL FLUID. DECREASED LUNG VOLUMES WITH ATELECTASIS AT THE BILATERAL BASES. RETROCARDIAC OPACITY PERSISTS, WHICH MAY REPRESENT ATELECTASIS VERSUS CONSOLIDATION. 2. SINGLE VIEW OF THE CHEST FROM 2011 HOURS DEMONSTRATES LUCENCY OVERLYING THE RIGHT UPPER QUADRANT. THIS MOST LIKELY REPRESENTS BOWEL, BUT CANNOT EXCLUDE INTRA-ABDOMINAL FREE FLUID. IF THERE IS CONCERN FOR AN INTRA-ABDOMINAL PROCESS, RECOMMEND ABDOMINAL FILMS WITH LEFT LATERAL DECUBITUS. NO SIGNIFICANT CHANGE IN CARDIOPULMONARY STATUS. FINDINGS DISCUSSED WITH Horne, CNP IN THE ED AT APPROXIMATELY 2300 HOURS ON 5/6/2002.

---

## Case

- Study key: `patient00122/study8`
- DICOM path: `patient00122/study8/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.364`
- Label macro score: `0.393`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Edema', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Consolidation
- Pleural Effusion
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
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. REDEMONSTRATION OF RIGHT INTERNAL JUGULAR CENTRAL VENOUS CATHETER WITH STABLE POSITION. 2. STABLE APPEARANCE OF BILATERAL PLEURAL EFFUSION AND ASSOCIATED BASILAR CONSOLIDATIONS.

---

## Case

- Study key: `patient00122/study7`
- DICOM path: `patient00122/study7/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.364`
- Label macro score: `0.393`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Consolidation', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Edema
- Pleural Effusion

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Fracture
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. THE LUNG VOLUMES ARE DECREASED. 2. PERSISTENT BIBASILAR OPACIFICATION, LEFT GREATER THAN RIGHT. 3. PERSISTENT BILATERAL PLEURAL EFFUSIONS, LEFT GREATER THAN RIGHT. 4. PERSISTENT MODERATE PULMONARY INTERSTITIAL EDEMA. 5. OVERALL, NO INTERVAL CHANGE.

---

## Case

- Study key: `patient00122/study6`
- DICOM path: `patient00122/study6/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.182`
- Label macro score: `0.286`

### Explanation

Multiple critical hallucinated disease labels: ['Atelectasis', 'Cardiomegaly', 'Consolidation', 'Edema', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

### Ground Truth Present Labels

- Pleural Effusion
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
- Pleural Other
- Pneumonia

### Partial Or Mismatched Labels

- Atelectasis: predicted `present`, ground truth `absent`
- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Fracture: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. REDEMONSTRATION OF RIGHT-SIDED INTERNAL JUGULAR VENOUS CATHETER WITH TIP IN THE SUPERIOR VENA CAVA AS WELL AS ONE RIGHT-SIDED CHEST TUBE WITH PORT WITHIN THE CHEST WALL. 2. IMPROVED LUNG VOLUMES BILATERALLY. 3. PERSISTENT BIBASILAR OPACIFICATION, UNCHANGED FROM PREVIOUS EXAMINATION. 4. PERSISTENT LEFT-SIDED PLEURAL EFFUSION, SLIGHTLY IMPROVED FROM PREVIOUS EXAMINATION.

---

## Case

- Study key: `patient00124/study6`
- DICOM path: `patient00124/study6/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.000`
- Label macro score: `0.500`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Edema', 'Lung Lesion']

### Ground Truth Present Labels

- No Finding

### Predicted Present Labels

- Cardiomegaly
- Edema
- Lung Lesion
- Pleural Other

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Edema: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Pleural Other: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. LIMITED SUPINE PORTABLE CHEST RADIOGRAPH WITH THE PATIENT ON THE TRAUMA BOARD DEMONSTRATES NO ACUTE DISEASE. 2. NO EVIDENCE FOR FRACTURES OR PNEUMOTHORAX.

---

## Case

- Study key: `patient00124/study4`
- DICOM path: `patient00124/study4/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.545`
- Label macro score: `0.500`

### Explanation

Multiple critical hallucinated disease labels: ['Cardiomegaly', 'Consolidation', 'Pneumonia', 'Lung Lesion', 'Lung Opacity']

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
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `present`, ground truth `absent`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. LINES AND TUBES UNCHANGED IN POSITION. 2. MODERATE PULMONARY EDEMA AGAIN SEEN ASSOCIATED WITH LOW VOLUMES, BILATERAL PLEURAL EFFUSIONS, RIGHT GREATER THAN LEFT AND LEFT RETROCARDIAC ATELECTASIS.

---

## Case

- Study key: `patient00124/study2`
- DICOM path: `patient00124/study2/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.769`
- Label macro score: `0.643`

### Explanation

Multiple critical hallucinated disease labels: ['Pneumonia', 'Lung Lesion', 'Lung Opacity']

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
- Lung Lesion
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Pneumonia: predicted `present`, ground truth `absent`
- Lung Lesion: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> Submitted for review is a single frontal portable view of the chest dated 3/6/2009 at 06:23. An endotracheal tube is seen with its tip in the trachea. A nasogastric tube is seen with its tip below the diaphragm. A central venous catheter is seen with its tip in the superior vena cava from a right internal jugular vein approach. The cardiac silhouette and main pulmonary arterial segment are again seen to enlarged. The cardiomediastinal silhouette is otherwise unremarkable. The lungs demonstrate diffuse increased reticular markings with indistinct pulmonary vessels and diffuse alveolar opacification, more predominant in the bases. There is blunting of the costophrenic angles bilaterally. These findings appear to have progressed from the prior examination. 1. CARDIOMEGALY WITH WORSENING PULMONARY EDEMA AND BILATERAL BASILAR ATELECTASIS VERSUS CONSOLIDATION AND BILATERAL PLEURAL EFFUSIONS.

---

## Case

- Study key: `patient00124/study3`
- DICOM path: `patient00124/study3/view1_frontal.dcm`
- Judge decision: **DISCORDANT**
- Disease F1: `0.600`
- Label macro score: `0.536`

### Explanation

Multiple critical hallucinated disease labels: ['Consolidation', 'Pneumonia', 'Lung Opacity']

### Ground Truth Present Labels

- Atelectasis
- Cardiomegaly
- Edema
- Pleural Effusion
- Support Devices

### Predicted Present Labels

- Atelectasis
- Consolidation
- Edema
- Lung Opacity
- Pleural Effusion
- Pneumonia

### Partial Or Mismatched Labels

- Cardiomegaly: predicted `uncertain`, ground truth `present`
- Consolidation: predicted `present`, ground truth `absent`
- Pneumonia: predicted `present`, ground truth `absent`
- Lung Opacity: predicted `present`, ground truth `absent`

### Ground Truth Report Excerpt

> 1. ET TUBE, NASOGASTRIC TUBE, FEEDING TUBE AND RIGHT INTERNAL JUGULAR LINE IN PLACE, UNCHANGED. 2. UNCHANGED CARDIOPULMONARY STATUS; BORDERLINE CARDIOMEGALY, MILD INTERSTITIAL EDEMA, LARGE RIGHT PLEURAL EFFUSION AND POSSIBLY A SMALL LEFT PLEURAL EFFUSION. PARTIAL ATELECTASIS OF BOTH LOWER LOBES. 3. INCIDENTALLY SEEN IS A TIPS SHUNT.

---
