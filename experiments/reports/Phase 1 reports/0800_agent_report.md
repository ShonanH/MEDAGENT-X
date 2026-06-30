# MEDAGENT-X Image Quality Report

## Case
- Case ID: 0800
- Dataset: LDCTIQAC2023
- Modality: CT
- Image file: 0800.tif

## Model Outputs
- Predicted quality score: 1.5687
- Predicted clinical level: 2
- Uncertainty: 0.2971

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
The image quality assessment indicates a predicted quality score of 1.5687, which suggests limited quality. The clinical quality label confirms this limitation, recommending consideration of repeat or alternative imaging. The usability category is also marked as limited, aligning with the overall assessment. The model uncertainty is quantified at 0.2971, contributing to confidence estimation in the quality review process. Moderate artifact concerns have been identified, specifically related to high noise levels. These artifacts may impact the overall quality and usability of the image. Given the predicted clinical level of 2 and the moderate artifact severity, the routing assessment indicates that human review is required. This decision is based on the combination of predicted clinical level, model uncertainty, and artifact severity. The presence of moderate artifacts necessitates further evaluation to ensure appropriate handling of the image.

## Limitations
- The predicted quality score indicates limited image quality.
- Moderate artifacts may affect the usability of the image.
- Human review is required due to the combination of factors affecting quality.

## Conclusion
The image does not pass the MEDAGENT-X quality gate and requires human review for further assessment. This output should be interpreted as an image-quality assessment only, not a diagnostic decision.
