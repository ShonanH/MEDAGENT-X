# MEDAGENT-X Image Quality Report

## Case
- Case ID: 0947
- Dataset: LDCTIQAC2023
- Modality: CT
- Image file: 0947.tif

## Model Outputs
- Predicted quality score: 1.9897
- Predicted clinical level: 2
- Uncertainty: 0.3589

## Clinical Quality
- Label: Limited
- Recommendation: Restricted diagnostic value; consider repeat or alternative imaging.

## Artifact Assessment
- Severity: moderate
- Flags: high_noise_proxy
- Summary: Moderate artifact concerns were detected. Consider further review.

## Routing
- Diagnosis gate: human_review
- Requires human review: True

## Explanation
The image quality assessment indicates a predicted quality score of 1.9897, which suggests limited image quality. The clinical quality label confirms this limitation, recommending restricted diagnostic value and suggesting consideration of repeat or alternative imaging. The uncertainty value of 0.3589 contributes to confidence estimation, indicating a moderate level of uncertainty in the assessment. Additionally, moderate artifact concerns were detected, specifically flagged by high noise proxy, which may impact the overall quality of the image. The usability category is also classified as limited, reinforcing the need for careful evaluation. Given these factors, the routing assessment has determined that human review is required due to the predicted clinical level of 2 and the moderate artifact severity. This decision underscores the importance of further scrutiny before any conclusions can be drawn. Overall, the image quality assessment highlights the necessity for additional review to ensure appropriate handling of the imaging data.

## Limitations
- The predicted quality score indicates limited image quality.
- Moderate artifact severity may affect the assessment.
- The presence of uncertainty contributes to confidence estimation.

## Conclusion
The image does not pass the MEDAGENT-X quality gate and requires human review for further evaluation. This output should be interpreted as an image-quality assessment only, not a diagnostic decision.
