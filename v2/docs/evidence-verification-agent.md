# Evidence Verification Agent

## Purpose

The Evidence Verification Agent verifies whether the final predicted labels are supported by correct, relevant, and trustworthy evidence.

Its purpose is not to diagnose the study again and not to replace the Label Fusion Agent. Its purpose is to audit the evidence behind the final labels and decide whether the evidence used by the system makes sense.

The agent answers this question:

```text
Are the predicted labels supported by the evidence that the system used?
```

## Reason For The Agent

The pipeline uses multiple evidence sources:

- image-model probabilities
- threshold-based vision statuses
- retrieved similar cases
- retrieved report text
- deterministic fusion logic
- LLM-assisted fusion review

These sources can disagree. Retrieved reports can contain negated findings, historical findings, ambiguous statements, or label terms that are easy to confuse with other labels. A label may be technically predicted as `present`, but the supporting evidence may be weak, indirect, contradictory, or not clinically trustworthy.

The Evidence Verification Agent exists to catch those cases before report writing.

The agent is needed because:

- Keyword counts can mistake negated mentions for support.
- Retrieved reports may describe historical findings rather than current findings.
- Similar retrieved cases are supporting context, not direct ground truth.
- The Report Writer needs to know which labels are strongly supported and which require cautious wording.
- Low-confidence or contradicted predictions should be auditable and potentially flagged for review.

## What The Agent Does

The Evidence Verification Agent reviews the final fused labels and the evidence behind them.

By default, it reviews:

- all final `present` labels
- all final `uncertain` labels
- all labels changed by the Label Fusion Agent
- high-risk gray-zone `absent` labels close to the threshold

It does not review every clearly absent strong-zone label by default.

For each reviewed label, the agent receives:

- final fused status
- original vision status
- vision probability
- threshold
- gray-zone flag
- whether fusion changed the label
- deterministic fusion reason
- LLM fusion review rationale, if available
- retrieved reports
- retrieved case IDs
- similarity scores when available
- supporting and contradicting snippets when available

The agent then evaluates the quality of the evidence.

## Evidence Checks

### Evidence Relevance

The agent checks whether the evidence actually discusses the target label.

Good evidence:

```text
Label: Pleural Effusion
Report: "Small right pleural effusion."
```

Bad evidence:

```text
Label: Pleural Effusion
Report: "No pneumothorax."
```

The second example is not evidence for pleural effusion.

### Negation Correctness

The agent checks whether a finding is negated.

Example:

```text
"No pleural effusion."
```

This should contradict `Pleural Effusion = present`, not support it.

### Historical Versus Current Evidence

The agent checks whether the report is describing a current finding or a prior/resolved finding.

Example:

```text
"Previously seen pneumothorax has resolved."
```

This should not strongly support current `Pneumothorax = present`.

### Cross-Label Confusion

The agent checks whether evidence for one label was incorrectly used for another.

Examples:

- Evidence for `Lung Opacity` should not automatically support `Consolidation`.
- Evidence for `Edema` should not automatically support `Pleural Effusion`.
- Evidence for `Cardiomegaly` should not automatically support `Enlarged Cardiomediastinum`.

### Retrieval Trustworthiness

The agent checks whether the retrieved cases are trustworthy enough to support the prediction.

Important factors:

- retrieved case rank
- similarity score
- whether evidence appears across multiple cases
- whether support comes from only one weak neighbor
- whether top retrieved reports mostly support or contradict the label

### Vision-Retrieval Consistency

The agent checks whether image-model evidence and retrieval evidence are coherent.

Examples:

- A gray-zone probability just below threshold plus multiple supporting retrieved reports is plausible support for a promotion.
- A probability far below threshold plus weak retrieved evidence should be treated cautiously.
- A final `present` label with mostly contradictory retrieved evidence should be flagged.

## Structured Output

The Evidence Verification Agent should return structured JSON.

Example:

```json
{
  "study_key": "patient123/study4",
  "reviewed_labels": [
    {
      "label": "Pleural Effusion",
      "final_status": "present",
      "evidence_score": 4,
      "support_assessment": "supported",
      "evidence_quality": "good",
      "trust_concerns": [],
      "vision_support": "moderate",
      "retrieval_support": "strong",
      "contradiction_level": "none",
      "supporting_evidence": [
        {
          "case_id": "patient456/study1",
          "quote": "Small right pleural effusion.",
          "why_relevant": "Direct positive mention of the target label."
        }
      ],
      "contradicting_evidence": [],
      "verdict": "The label is supported by retrieved report evidence and is consistent with the gray-zone vision probability."
    }
  ],
  "overall_evidence_score": 4,
  "overall_verdict": "The predicted labels are mostly supported by the available evidence."
}
```

## Evidence Scores

The agent uses a 1 to 5 evidence score.

- `5`: strong, coherent evidence from vision and retrieval
- `4`: good evidence with minor uncertainty
- `3`: mixed, weak, or incomplete evidence
- `2`: questionable support or meaningful contradiction
- `1`: unsupported, contradicted, or evidence appears incorrect

## Trust Concerns

The agent should identify specific trust concerns, such as:

- `negated-evidence-used-as-support`
- `historical-finding`
- `cross-label-confusion`
- `weak-retrieval-similarity`
- `single-case-support`
- `mixed-retrieval-evidence`
- `vision-retrieval-disagreement`
- `insufficient-evidence`

## Guardrails

The Evidence Verification Agent cannot directly change labels.

It can only produce:

- evidence scores
- support assessments
- trust concerns
- supporting evidence
- contradicting evidence
- narrative verdicts
- review flags

The Label Fusion Agent remains responsible for final structured label statuses. The Report Writer uses Evidence Verification results to decide how strongly or cautiously to phrase findings.

If Evidence Verification finds that a final label is weakly supported, unsupported, or contradicted, it should flag the label clearly. It should not silently rewrite the label.

## Output

The Evidence Verification Agent should output:

- per-label evidence verification results
- overall evidence score
- supporting evidence snippets
- contradicting evidence snippets
- trust concerns
- final audit verdict
- report-writing guidance

This output becomes the main evidence-control input for the Report Writer Agent.

