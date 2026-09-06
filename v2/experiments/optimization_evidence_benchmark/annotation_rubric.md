# MEDAGENT-X Optimization Evidence Benchmark Rubric

## Annotation Unit

Each row is one study-label fusion change from Exp 7. The annotator should judge
whether the retrieved evidence supports the final fused label decision.

## Primary Label: human_support_label

Use exactly one value:

- supported: retrieved evidence clearly supports the fused label.
- contradicted: retrieved evidence clearly argues against the fused label.
- mixed: retrieved evidence contains both support and contradiction, or is clinically ambiguous.
- insufficient: retrieved evidence is too weak, indirect, missing, or irrelevant
  to support the fused label.

## Optional Field: human_error_tags

Use zero or more comma-separated tags:

- cross_label_confusion: evidence appears to support a related but different label.
- negation_error: negated evidence was treated as positive, or positive evidence
  was treated as negated.
- historical_or_temporal_error: evidence refers to prior, resolved, changing, or temporal findings.
- irrelevant_retrieval: retrieved cases or snippets are not useful for this label decision.

## Notes

- Retrieved reports are from visually similar training cases, not the target study report.
- Judge evidence quality for the proposed label change, not whether the target
  patient truly has the disease.
- Prefer insufficient when evidence is merely generic, indirect, or absent.
- Use mixed when support and contradiction are both clinically meaningful.
