# Label Fusion Agent

## Purpose

The Label Fusion Agent produces the final structured disease-label predictions for one chest X-ray study by combining image-model predictions with retrieved historical report evidence.

Its purpose is not to replace the vision model. Its purpose is to improve decisions when the vision model is uncertain, especially when the model probability is close to the decision threshold. In those gray-zone cases, the agent uses retrieval evidence to decide whether a vision-only label should be kept, promoted, demoted, or marked uncertain.

## Reason For The Agent

The RAD-DINO vision model gives study-level probabilities and binary present/absent statuses for the 12 supervised disease labels. That is useful, but image-only predictions can be weak around the threshold. A probability just below threshold may still represent a real finding, and a probability just above threshold may be unsupported or contradicted by similar cases.

Retrieval gives the system a second evidence source. Similar train-set studies provide report text that can mention, negate, qualify, or contradict the target finding. The Label Fusion Agent exists to use this retrieved evidence in a controlled way.

The agent is needed because:

- Vision-only predictions are most error-prone near thresholds.
- Retrieval can recover true positives that the image model undercalls.
- Retrieval can sometimes identify weak or questionable positive calls.
- A deterministic fusion baseline gives measurable, auditable improvement.
- An LLM can read full retrieved reports more carefully than keyword counting alone.

The agent must remain constrained because retrieved reports are indirect evidence from similar cases, not ground truth for the current study. For that reason, fusion is only allowed inside the gray zone and every LLM decision must pass strict guardrails.

## What The Agent Does

The Label Fusion Agent runs in two stages.

```text
Stage 1: deterministic gray-zone fusion
Stage 2: LLM review of deterministic changes
```

### Stage 1: Deterministic Fusion

The deterministic stage takes:

- study key
- vision probability per label
- vision threshold per label
- vision status per label
- retrieved cases
- retrieved report text

For each of the 12 disease labels, it computes:

- whether the label is in the gray zone
- positive mention count from retrieved reports
- negative mention count from retrieved reports
- deterministic fused status
- deterministic refinement reason

The gray zone is:

```text
abs(probability - threshold) <= 0.15
```

Labels outside the gray zone are not changed by fusion.

For gray-zone labels:

- A vision `absent` label can be promoted to `present` when retrieved evidence is strongly positive.
- A vision `present` label can be demoted to `uncertain` or `absent` when retrieved evidence is negative enough.
- Labels with insufficient retrieval evidence keep the vision status.

This deterministic result is always available as a fallback.

### Stage 2: LLM Review

After deterministic fusion, the LLM reviews only labels where deterministic fusion changed the vision status.

The LLM receives one prompt per study containing:

- all deterministic fusion changes for that study
- full retrieved reports for all top-10 retrieved cases
- retrieved case IDs
- similarity scores when available
- vision probability, threshold, and status for each changed label
- deterministic fused status for each changed label
- deterministic mention counts
- deterministic refinement reasons

The LLM must return structured JSON.

Example response shape:

```json
{
  "reviewed_labels": [
    {
      "label": "Pleural Effusion",
      "action": "keep",
      "final_status": "present",
      "confidence": "moderate",
      "evidence_assessment": "supporting",
      "rationale": "Retrieved reports repeatedly mention pleural effusion without negation.",
      "supporting_case_ids": ["patient123/study4"],
      "contradicting_case_ids": []
    }
  ],
  "overall_notes": "The deterministic change is supported by retrieved report evidence."
}
```

Allowed `action` values:

- `keep`
- `veto`
- `uncertain`

Allowed `final_status` values:

- `present`
- `absent`
- `uncertain`

Allowed `confidence` values:

- `low`
- `moderate`
- `high`

Allowed `evidence_assessment` values:

- `supporting`
- `contradictory`
- `mixed`
- `insufficient`

## Guardrails

The LLM cannot create new changes.

It can only review labels that deterministic fusion already changed. It cannot promote, demote, or modify labels that deterministic fusion left unchanged.

For a deterministic promotion:

```text
vision_status: absent
deterministic_status: present
```

The LLM can:

- `keep`: final status remains `present`
- `veto`: final status reverts to `absent`
- `uncertain`: final status becomes `uncertain`

For a deterministic demotion:

```text
vision_status: present
deterministic_status: uncertain or absent
```

The LLM can:

- `keep`: final status remains the deterministic demotion
- `veto`: final status reverts to `present`
- `uncertain`: final status becomes `uncertain`

The LLM output is accepted only if:

- all reviewed labels were requested
- no unrequested labels are included
- every reviewed label is one of the 12 disease labels
- every reviewed label was changed by deterministic fusion
- every status is one of `present`, `absent`, or `uncertain`
- every action is consistent with the allowed action space
- referenced case IDs exist in the retrieved cases
- the response validates against the expected JSON schema

If the response is invalid, the system attempts one repair call. If the repaired output is still invalid, the agent falls back to deterministic fusion. If only one label review is invalid, only that label falls back to deterministic fusion.

## Output

The Label Fusion Agent should output:

- deterministic fusion result
- LLM review result
- final fusion result
- reviewed labels
- kept changes
- vetoed changes
- labels softened to `uncertain`
- fallback metadata
- per-label audit reasons

The final result is the structured label state used by downstream nodes, especially Evidence Verification and Report Writing.

