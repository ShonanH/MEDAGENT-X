# MEDAGENT-X Topic Implementation Order Handoff

Date: 2026-09-02

## Decision

Implement the work in this order:

```text
Topic 1 light infrastructure
-> Topic 2 calibrated retrieval-prior fusion
-> Topic 1 final evidence-verification benchmark
```

The reason is that the paper thesis is now:

```text
calibrated retrieval-prior fusion for gray-zone medical image classification
with evidence-verification auditing
```

Therefore, the calibrated retrieval-prior fusion method must become the main experimental object before the final human evidence-verification benchmark is locked.

## Why Not Fully Implement Topic 1 First?

Topic 1 is the evidence-verification benchmark. The current Experiment 7 outputs are useful and should be used, but they come from the older keyword-count fusion policy.

If we fully build and annotate the final Topic 1 benchmark now, the benchmark will mostly evaluate evidence verification for keyword-count fusion. That would be misaligned with the planned ICLR thesis, where the main method is calibrated retrieval-prior fusion.

Experiment 7 should still be used for infrastructure and bootstrapping because it already contains:

- `fusion_label_predictions.csv`
- `llm_evidence_policy_audit.csv`
- `evidence_verification.csv`
- `evidence_verification.json`
- `graph_reasoning_results.jsonl`
- `run_config.json`

But Exp 7 should not be treated as the final benchmark source unless the paper remains focused on keyword-count fusion.

## Recommended Implementation Sequence

## Phase 1: Topic 1 Light Infrastructure

Goal:

```text
Make Experiment 7 usable for evidence-verification benchmark construction
without committing to the final annotation set.
```

Create:

```text
v2/src/medagentx/cli/export_evidence_benchmark_packets.py
```

Initial outputs:

```text
v2/experiments/evidence_benchmark/annotation_packets_exp07.jsonl
v2/experiments/evidence_benchmark/annotation_packets_exp07.csv
v2/experiments/evidence_benchmark/annotation_rubric.md
```

The exporter should join or extract information from:

- `v2/experiments/exp07_llm_fusion_evidence_verification_graph/qwen3_14b/fusion_label_predictions.csv`
- `v2/experiments/exp07_llm_fusion_evidence_verification_graph/qwen3_14b/llm_evidence_policy_audit.csv`
- `v2/experiments/exp07_llm_fusion_evidence_verification_graph/qwen3_14b/evidence_verification.json`
- `v2/experiments/exp07_llm_fusion_evidence_verification_graph/qwen3_14b/graph_reasoning_results.jsonl`

Each packet should contain:

```text
study_key
label
vision_status
fused_status
probability
threshold
in_gray_zone
fusion_changed
fusion_reason
retrieval_positive_count
retrieval_negative_count
deterministic_evidence_score
final_evidence_score
deterministic_retrieval_support
final_retrieval_support
deterministic_contradiction_level
final_contradiction_level
llm_reviewed
llm_confidence
llm_evidence_assessment
llm_supporting_case_ids
llm_contradicting_case_ids
supporting_evidence
contradicting_evidence
final_evidence_summary
```

Sampling should not be purely random. Exp 7 has many `supporting` and `mixed` cases, but relatively few `insufficient`, `contradictory`, and fallback cases. The exporter should support stratified sampling so the benchmark includes hard cases.

Important Exp 7 distribution:

```text
final fusion-changed labels: 387
supporting: 190
mixed: 164
insufficient: 17
contradictory: 7
blank/fallback: 9
```

Initial sampling recommendation:

```text
include all contradictory cases
include all insufficient cases
include all fallback/blank cases
include all demotions
oversample hard labels: Pneumothorax, Fracture, Lung Lesion, Pleural Other
sample supporting and mixed cases to fill the remaining quota
```

This phase should produce the packet schema and rubric, not the final human-labeled benchmark.

## Phase 2: Topic 2 Core Method

Goal:

```text
Implement calibrated retrieval-prior fusion as the main method.
```

Create:

```text
v2/src/medagentx/reasoning/retrieval_prior.py
v2/src/medagentx/reasoning/prior_fusion.py
v2/src/medagentx/cli/run_prior_fusion_eval.py
```

The retrieval prior should replace raw keyword-count evidence with structured, similarity-weighted label priors from retrieved training cases.

For each target study and label, compute:

```text
vision_probability
vision_threshold
probability_minus_threshold
in_gray_zone
retrieval_present_prior
retrieval_absent_prior
retrieval_uncertain_rate
retrieval_unmentioned_rate
retrieval_confidence
vision_retrieval_agreement
retrieval_contradiction_signal
```

Core prior:

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

Fusion rule:

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

Validation tuning should happen before test evaluation. The test set should remain locked until the validation policy is fixed.

Minimum comparison table:

```text
Vision only
Gray-zone abstention
Keyword-count fusion
Unweighted retrieval-prior fusion
Similarity-weighted retrieval-prior fusion
Calibrated retrieval-prior fusion
Calibrated retrieval-prior fusion + evidence audit
```

## Phase 3: Topic 1 Final Benchmark

Goal:

```text
Create the final human-labeled evidence-verification benchmark using calibrated
retrieval-prior fusion outputs.
```

Once Topic 2 exists and has produced calibrated prior-fusion outputs, rerun or extend the packet exporter.

Final benchmark sources should include:

- Calibrated retrieval-prior fusion changed labels.
- A subset of Exp 7 keyword-count fusion cases for baseline comparison.
- Hard negative or suspicious examples from both methods.

Human annotation labels:

```text
supported
contradicted
mixed
insufficient
cross_label_confusion
negation_error
historical_or_temporal_error
irrelevant_retrieval
```

Primary benchmark metrics:

```text
macro F1 over evidence-support classes
supported precision
contradiction recall
unsupported-evidence recall
confidence calibration
agreement with deterministic verifier
agreement with human annotators
error distribution by label
```

The final Topic 1 claim should be:

```text
Evidence-verification auditing can evaluate whether retrieval-grounded
gray-zone corrections are supported, mixed, contradicted, or insufficiently
supported by retrieved clinical evidence.
```

## Immediate Next Step

Start with Phase 1:

```text
v2/src/medagentx/cli/export_evidence_benchmark_packets.py
```

This is the right first coding task because it makes Exp 7 inspectable and reusable while avoiding premature commitment to a final benchmark before calibrated retrieval-prior fusion exists.

After the exporter and rubric are in place, move directly to:

```text
v2/src/medagentx/reasoning/retrieval_prior.py
```

That starts Topic 2, the main ICLR method.
