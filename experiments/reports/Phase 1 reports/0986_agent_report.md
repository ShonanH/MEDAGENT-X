# MEDAGENT-X Image Quality Report

## Case
- Case ID: 0986
- Dataset: LDCTIQAC2023
- Modality: CT
- Image file: 0986.tif

## Model Outputs
- Predicted quality score: 1.7521
- Predicted clinical level: 2
- Uncertainty: 0.3226

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
The image quality assessment indicates a predicted quality score of 1.7521, which suggests limited quality. The clinical quality label confirms this limitation, recommending consideration of repeat or alternative imaging. The uncertainty value of 0.3226 contributes to confidence estimation, indicating a moderate level of uncertainty in the assessment. Additionally, the usability category is marked as limited, aligning with the overall quality evaluation. Moderate artifact concerns were detected, specifically flagged by high noise proxy, which may impact the clarity of the image. The routing assessment indicates that the final gate requires human review due to the predicted clinical level of 2 and the moderate artifact severity. This necessitates further evaluation by a qualified professional to determine the next steps. Overall, the image quality assessment highlights the need for careful consideration before proceeding.

## Limitations
- The predicted quality score indicates limited image quality.
- Moderate artifact severity may affect the interpretation of the image.
- The presence of uncertainty contributes to the need for human review.

## Conclusion
The image does not pass the MEDAGENT-X quality gate and requires human review for further evaluation. This output should be interpreted as an image-quality assessment only, not a diagnostic decision.
