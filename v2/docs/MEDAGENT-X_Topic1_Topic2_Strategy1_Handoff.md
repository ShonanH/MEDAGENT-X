# MEDAGENT-X Research Handoff: Topic 1 and Topic 2 / Strategy 1

## Project Framing

MEDAGENT-X is not primarily a generic medical agentic pipeline. The central research framing is a medical imaging decision-support system where a vision model produces disease-label predictions, a constrained deterministic fusion layer proposes gray-zone corrections using retrieved similar cases, and an LLM is used for explainability, evidence verification, and auditability.

The LLM is not expected to improve label F1 directly. Its role is to audit whether deterministic changes are actually grounded in the retrieved clinical context.

Current pipeline scope:

```text
Vision model
-> Retrieval over visually similar train cases
-> Deterministic gray-zone label fusion
-> LLM evidence verification for changed / predicted labels
```

The Report Writer Agent is intentionally out of scope for now.

## Topic 1: Evidence-Verification Benchmark

The first major improvement is to turn the LLM evidence verifier into an independently evaluable research component.

Current Experiment 7 already produces useful audit outputs:

- `fusion_label_predictions.csv`: labels changed by fusion.
- `llm_evidence_policy_audit.csv`: deterministic evidence score vs LLM-reviewed evidence score.
- `evidence_verification.csv`: study-level evidence narratives, supporting evidence, contradicting evidence, and label evidence details.
- `graph_reasoning_results.jsonl`: per-study run trace with fusion and evidence-verification metadata.

The next step is to create a human-labeled evidence-verification benchmark from these outputs.

For each fusion-changed label, create an annotation packet containing:

```json
{
  "study_key": "...",
  "label": "Pleural Effusion",
  "vision_status": "absent",
  "fused_status": "present",
  "probability": 0.48,
  "threshold": 0.52,
  "fusion_reason": "promoted absent to present...",
  "retrieved_cases": [
    {
      "case_id": "...",
      "similarity": 0.83,
      "report_snippets": ["..."]
    }
  ],
  "llm_evidence_assessment": "supporting",
  "llm_confidence": "moderate",
  "llm_supporting_case_ids": ["..."],
  "llm_contradicting_case_ids": []
}
```

Human annotators should label whether the deterministic fusion change is:

- `supported`
- `contradicted`
- `mixed`
- `insufficient`
- `cross_label_confusion`
- `negation_error`
- `irrelevant_retrieval`

The initial benchmark can start with 150-250 examples sampled from the fusion-changed labels in Experiment 7.

Evaluation targets:

- LLM verifier macro F1 over evidence-support classes.
- Contradiction detection recall.
- Unsupported-evidence detection recall.
- Agreement between LLM evidence assessment and human labels.
- Calibration of LLM confidence.
- Error types: negation, historical findings, cross-label confusion, weak retrieval, irrelevant snippets.

This lets the paper claim that MEDAGENT-X does not merely generate explanations; it evaluates whether retrieval-grounded corrections are actually supported by evidence.

## Topic 2 / Strategy 1: Calibrated Retrieval-Prior Fusion

The current deterministic fusion logic relies too heavily on raw positive and negative keyword mention counts in retrieved reports. A stronger direction is to replace raw mention-count fusion with calibrated retrieval-prior fusion.

Instead of asking:

```text
How many retrieved reports mention this label?
```

the system should ask:

```text
Given visually similar retrieved cases, how likely is this label to be present?
```

For each target study and label, compute:

- `vision_probability`
- `vision_threshold`
- `probability_minus_threshold`
- `in_gray_zone`
- `retrieval_present_prior`
- `retrieval_absent_prior`
- `retrieval_uncertain_rate`
- `retrieval_confidence`
- `vision_retrieval_agreement`
- `retrieval_contradiction_signal`

The retrieval prior should come from structured labels of retrieved training cases, weighted by visual similarity:

```text
retrieval_present_prior =
    sum(similarity_i * is_present_i)
    / sum(similarity_i * is_scoreable_i)
```

Likewise:

```text
retrieval_absent_prior =
    sum(similarity_i * is_absent_i)
    / sum(similarity_i * is_scoreable_i)
```

Then the deterministic fusion layer can use a calibrated rule:

```text
if not in_gray_zone:
    keep vision status

if vision_status == absent
   and retrieval_present_prior >= label_specific_promotion_threshold
   and retrieval_confidence >= min_confidence
   and contradiction_signal is low:
       promote to present

elif vision_status == present
   and retrieval_absent_prior >= label_specific_demotion_threshold
   and retrieval_confidence >= min_confidence:
       demote to uncertain or absent

else:
    keep vision status
```

This is stronger than keyword counting because it uses similar-case label distributions as statistical evidence, remains deterministic and auditable, can be tuned on validation data, and gives a cleaner ICLR-style methods section.

Recommended implementation modules:

```text
src/medagentx/reasoning/retrieval_prior.py
src/medagentx/reasoning/prior_fusion.py
src/medagentx/cli/run_prior_fusion_eval.py
```

Suggested dataclass:

```python
@dataclass(frozen=True)
class RetrievalLabelPrior:
    label: str
    present_prior: float
    absent_prior: float
    uncertain_rate: float
    scoreable_weight: float
    mean_similarity: float
    top_supporting_cases: tuple[str, ...]
    top_contradicting_cases: tuple[str, ...]
```

The LLM can then be used after calibrated deterministic fusion proposes a gray-zone change:

```text
Calibrated retrieval-prior fusion proposes change
-> LLM reviews retrieved reports and evidence
-> final change accepted only if LLM says supported or mixed with sufficient confidence
-> contradicted or insufficient evidence blocks or softens the change
```

Recommended comparison table:

```text
Vision only
Keyword-count fusion
Retrieval-prior fusion
Retrieval-prior fusion + LLM audit
```

The strongest paper story is:

```text
MEDAGENT-X replaces naive keyword-count fusion with calibrated, similarity-weighted retrieval priors, applies fusion only to gray-zone vision predictions, and uses an LLM verifier to audit whether proposed corrections are grounded in retrieved clinical evidence.
```

## Immediate Next Implementation Step

Start with `retrieval_prior.py`.

Inputs:

- target `study_key`
- target label
- retrieved case IDs
- retrieved similarities
- structured label table for train studies

Output:

- one `RetrievalLabelPrior` per disease label.

After that, implement `prior_fusion.py` as a parallel alternative to the existing count-based `fuse.py`, then evaluate it against the existing Experiment 4 / Experiment 7 outputs.
