# MEDAGENT-X Implementation Report: Calibrated Retrieval-Prior Fusion for Gray-Zone Medical Image Classification with Evidence-Verification Auditing

Date: 2026-09-02

## Executive Thesis

MEDAGENT-X should be framed as a calibrated retrieval-prior fusion method for gray-zone medical image classification with evidence-verification auditing.

The system is not primarily a broad medical agent platform. Its core research contribution is a constrained decision-support pipeline for chest radiograph classification:

```text
study-level vision model
-> image-to-case retrieval over visually similar training studies
-> calibrated retrieval-prior fusion for gray-zone predictions
-> evidence-verification audit over accepted or proposed label decisions
-> structured report artifact
```

The agentic workflow remains important, but it is the orchestration mechanism rather than the main scientific claim. LangGraph is used to pass typed state through specialized agents for vision inference, retrieval, fusion, evidence verification, and reporting. The paper should present these agents as a reproducible audit trail around the calibrated fusion method, not as evidence that a generic LLM agent can diagnose chest radiographs.

The central claim should be:

```text
MEDAGENT-X improves uncertain medical image classification decisions by applying
similarity-weighted retrieval priors only near calibrated vision thresholds,
then auditing whether those decisions are supported by retrieved clinical evidence.
```

## Why This Framing Is Stronger

The current implementation already shows that retrieval helps where the vision model is uncertain. On the 906-study test split, deterministic retrieval-backed fusion improves full-test macro F1 from 0.6971 to 0.7246 and gray-zone macro F1 from 0.6310 to 0.7613 while keeping macro precision approximately flat.

Those results support a focused ML story:

- The vision model is high precision but misses positives.
- The uncertain region around each label threshold contains recoverable errors.
- Visually similar training studies provide useful local label information.
- Fusion should be constrained to the gray zone to avoid overriding confident visual evidence.
- Evidence verification can audit whether retrieval-grounded corrections are clinically supported.

The current LLM label-fusion experiments do not support a claim that the LLM itself improves label F1. The stronger and more defensible role for the LLM is evidence verification, contradiction detection, and auditability.

## Current Pipeline

The current MEDAGENT-X v2 pipeline contains the main pieces needed for this thesis.

### 1. Study-Level Vision Model

The vision model fine-tunes `microsoft/rad-dino` for study-level multi-label chest radiograph classification. It predicts 12 CheXpert-style disease labels:

```text
Atelectasis
Cardiomegaly
Consolidation
Edema
Pleural Effusion
Pneumonia
Pneumothorax
Fracture
Lung Lesion
Lung Opacity
Enlarged Cardiomediastinum
Pleural Other
```

The strongest saved configuration uses:

| Component | Current Choice |
| --- | --- |
| Backbone | `microsoft/rad-dino` |
| Prediction level | Study-level |
| Pooling | Mean-max pooling over views |
| Trainable backbone blocks | Last 4 transformer blocks |
| Loss | Masked binary cross entropy |
| Thresholds | Per-label validation-tuned thresholds |
| Selection metric | Validation macro F1 |

The model produces per-label probabilities and binary present/absent statuses using per-label thresholds.

### 2. Gray-Zone Identification

Fusion is allowed only near the learned threshold for each label:

```text
in_gray_zone(s, y) = abs(p_s,y - threshold_y) <= margin
```

The current default margin is 0.15.

This constraint is central to the thesis. The method does not allow retrieval or LLM review to freely override the vision model. Strong-zone predictions remain vision-dominant. The retrieval prior is used only where the calibrated vision score indicates uncertainty.

### 3. Image-to-Case Retrieval

Retrieval uses the fine-tuned RAD-DINO study embedding to retrieve visually similar training studies.

Current retrieval properties:

- Queries are image-based, not text-based.
- Retrieved cases come from the training split only.
- Same-study and same-patient retrieval leakage is excluded.
- Retrieved payloads include reports and metadata.
- Current evaluation uses `top_k=10`.

This makes the retrieved cases a local nonparametric memory over prior visually similar studies.

### 4. Existing Deterministic Fusion Baseline

The current fusion implementation uses keyword and negation mention counts from retrieved reports.

Current rule shape:

```text
if prediction is outside gray zone:
    keep vision status

if prediction is inside gray zone:
    promote absent -> present when retrieved positive mentions are strong
    demote present -> uncertain or absent when retrieved negatives dominate
    otherwise keep vision status
```

This baseline is useful and already improves performance, but it has a weakness: raw mention counts are report-text signals, not calibrated local label priors. Mention counts can overcount repeated phrases, confuse related labels, and depend on lexical coverage.

### 5. Evidence-Verification Auditing

The evidence verification stage produces:

- Study-level evidence scores.
- Per-label evidence scores.
- Vision support levels.
- Retrieval support levels.
- Contradiction levels.
- Supporting snippets.
- Contradicting snippets.
- Human-readable evidence narratives.

The verifier currently provides auditability without changing label-level metrics. This is appropriate. For the ICLR paper, the audit stage should be evaluated as an evidence-verification component rather than as a label optimizer.

## Current Empirical Baseline

The current saved experiment summaries establish the baseline that the new strategy must improve or refine.

### Evaluation Setup

| Quantity | Value |
| --- | ---: |
| Test studies | 906 |
| Disease labels | 12 |
| Study-label cells | 10,872 |
| Gray-zone margin | 0.15 |
| Gray-zone cells | 1,812 |
| Ground truth | CheXpert-derived study labels |

### Vision Only

| Scope | Macro F1 | Macro Precision | Macro Recall | Micro F1 |
| --- | ---: | ---: | ---: | ---: |
| Full test set | 0.6971 | 0.9108 | 0.5695 | 0.7042 |
| Gray-zone slice | 0.6310 | 0.8748 | 0.5090 | 0.6417 |

Interpretation: the vision model is precision-heavy and misses a meaningful number of positive findings.

### No-Retrieval Gray-Zone Abstention

| Scope | Macro F1 | Macro Precision | Macro Recall | Micro F1 |
| --- | ---: | ---: | ---: | ---: |
| Full test set | 0.6126 | 0.9241 | 0.4619 | 0.6240 |
| Gray-zone slice | null | null | 0.0000 | null |

Interpretation: simple uncertainty abstention is too conservative under the current Judge policy because `GT present + predicted uncertain` hurts recall.

### Keyword-Count Retrieval Fusion

| Scope | Macro F1 | Macro Precision | Macro Recall | Micro F1 |
| --- | ---: | ---: | ---: | ---: |
| Full test set | 0.7246 | 0.9117 | 0.6051 | 0.7383 |
| Gray-zone slice | 0.7613 | 0.8773 | 0.6950 | 0.8041 |

Interpretation: retrieval-backed fusion improves recall and F1 while preserving precision. The gain is concentrated in the gray zone, exactly where the fusion policy is allowed to intervene.

### LLM Label-Fusion Path

The current LLM label-fusion path runs, but it does not provide a reliable label-level improvement over deterministic retrieval fusion. The latest Qwen run matches the deterministic fusion headline metrics. Therefore, the LLM should not be presented as the source of classification performance gains.

## Proposed Core Method: Calibrated Retrieval-Prior Fusion

The next implementation step is to replace raw keyword-count fusion with calibrated retrieval-prior fusion.

Instead of asking:

```text
How many retrieved report snippets mention this label?
```

the new fusion module asks:

```text
Among visually similar prior studies with scoreable structured labels,
how likely is this label to be present, absent, or uncertain?
```

For each target study `s` and label `y`, compute:

| Signal | Meaning |
| --- | --- |
| `vision_probability` | RAD-DINO probability for label `y` |
| `vision_threshold` | Validation-tuned threshold for label `y` |
| `probability_minus_threshold` | Signed distance from threshold |
| `in_gray_zone` | Whether fusion is allowed |
| `retrieval_present_prior` | Similarity-weighted fraction of retrieved scoreable cases labeled present |
| `retrieval_absent_prior` | Similarity-weighted fraction of retrieved scoreable cases labeled absent |
| `retrieval_uncertain_rate` | Similarity-weighted uncertainty rate |
| `retrieval_confidence` | Effective scoreable retrieval mass |
| `vision_retrieval_agreement` | Whether vision and retrieval prior agree |
| `retrieval_contradiction_signal` | Whether retrieved labels or snippets conflict |

The primary prior is:

```text
retrieval_present_prior(s, y) =
    sum_i w_i * I[label_i,y = present]
    /
    sum_i w_i * I[label_i,y is scoreable]
```

where `w_i` is derived from visual similarity. Likewise:

```text
retrieval_absent_prior(s, y) =
    sum_i w_i * I[label_i,y = absent]
    /
    sum_i w_i * I[label_i,y is scoreable]
```

Uncertain and unmentioned labels should not be silently treated as negatives. They should either be excluded from the scoreable denominator or represented explicitly through uncertainty and missingness rates.

## Proposed Fusion Rule

The calibrated fusion rule should remain deterministic and auditable.

```text
if not in_gray_zone:
    keep vision status

if vision_status == absent
   and retrieval_present_prior >= promotion_threshold_y
   and retrieval_confidence >= min_confidence_y
   and retrieval_contradiction_signal is low:
       promote to present

elif vision_status == present
   and retrieval_absent_prior >= demotion_threshold_y
   and retrieval_confidence >= min_confidence_y:
       demote to uncertain or absent

else:
    keep vision status
```

The thresholds should be selected on validation data only. The test set should remain locked until the final evaluation.

Recommended validation-tuned knobs:

| Parameter | Purpose |
| --- | --- |
| `gray_zone_margin_y` | Per-label or global intervention width |
| `promotion_threshold_y` | Minimum retrieval prior required for absent-to-present correction |
| `demotion_threshold_y` | Minimum absent prior required for present-to-uncertain or present-to-absent correction |
| `min_confidence_y` | Minimum scoreable retrieval mass |
| `top_k` | Number of retrieved studies |
| `similarity_weighting` | Raw similarity, clipped similarity, softmax similarity, or rank decay |

The safest initial version should keep a global gray-zone margin and tune label-specific promotion and demotion thresholds.

## Agentic Workflow

The LangGraph workflow should be described as a typed agentic audit pipeline around the calibrated fusion method.

```text
Vision Agent
    Inputs: DICOM study
    Outputs: probabilities, thresholds, statuses, study embedding

Retrieval Agent
    Inputs: study embedding
    Outputs: visually similar train studies, similarities, reports, structured labels

Retrieval-Prior Agent
    Inputs: retrieved cases, similarities, structured train labels
    Outputs: per-label retrieval priors and confidence metadata

Prior-Fusion Agent
    Inputs: vision predictions, retrieval priors
    Outputs: fused label statuses and deterministic reasons

Evidence-Verification Agent
    Inputs: fused labels, retrieved snippets, prior metadata
    Outputs: support/contradiction assessments, evidence scores, audit narrative

Report Writer Agent
    Inputs: fused labels and evidence audit
    Outputs: structured report artifact
```

The key design principle is separation of responsibilities:

- The vision agent predicts from images.
- The retrieval agent supplies local similar cases.
- The retrieval-prior agent estimates local label priors from structured labels.
- The fusion agent makes constrained deterministic label decisions.
- The evidence-verification agent audits whether those decisions are supported by retrieved clinical evidence.
- The report writer summarizes the final audited output, but it is not the scientific centerpiece.

## Evidence-Verification Benchmark

To make the audit component evaluable, create a human-labeled evidence-verification benchmark from fusion-changed labels.

Each annotation packet should include:

```json
{
  "study_key": "...",
  "label": "Pleural Effusion",
  "vision_status": "absent",
  "fused_status": "present",
  "probability": 0.48,
  "threshold": 0.52,
  "retrieval_present_prior": 0.82,
  "retrieval_absent_prior": 0.06,
  "retrieval_confidence": 0.91,
  "fusion_reason": "promoted absent to present by calibrated retrieval prior",
  "retrieved_cases": [
    {
      "case_id": "...",
      "similarity": 0.83,
      "structured_label": "present",
      "report_snippets": ["..."]
    }
  ],
  "verifier_assessment": "supporting",
  "verifier_confidence": "moderate",
  "supporting_case_ids": ["..."],
  "contradicting_case_ids": []
}
```

Human annotators should label whether the proposed fusion decision is:

| Label | Meaning |
| --- | --- |
| `supported` | Retrieved evidence supports the fused decision |
| `contradicted` | Retrieved evidence contradicts the fused decision |
| `mixed` | Both support and contradiction are present |
| `insufficient` | Retrieved evidence is too weak or nonspecific |
| `cross_label_confusion` | Evidence supports a related but different finding |
| `negation_error` | Evidence was misread due to negation |
| `historical_or_temporal_error` | Evidence refers to prior, resolved, or changing findings |
| `irrelevant_retrieval` | Retrieved cases are not clinically relevant to the target label |

Minimum target:

- 150-250 fusion-changed label examples for the first benchmark.
- Label-balanced or stratified sampling, especially for rare labels.
- At least two annotators for a subset.
- Inter-annotator agreement reported.
- Adjudicated labels for final evaluation.

Evaluation metrics:

- Macro F1 over evidence-support classes.
- Contradiction detection recall.
- Unsupported-evidence detection recall.
- Confidence calibration.
- Error distribution by label.
- Error distribution by retrieval-prior strength.

## Paper Contribution Claims

The ICLR paper should make three concrete claims.

### Claim 1: Gray-Zone Retrieval Fusion Improves Classification

Constrained retrieval fusion improves chest radiograph label classification by focusing interventions near calibrated vision thresholds.

Required evidence:

- Full-test metrics.
- Gray-zone metrics.
- Per-label deltas.
- Precision-recall tradeoff.
- Ablation of gray-zone margin.
- Ablation of retrieval `top_k`.

### Claim 2: Structured Retrieval Priors Are Better Than Raw Mention Counts

Similarity-weighted structured label priors should be more stable and auditable than raw keyword counts from retrieved reports.

Required evidence:

- Keyword-count fusion baseline.
- Unweighted structured prior baseline.
- Similarity-weighted structured prior.
- Calibrated prior thresholds.
- Error analysis on labels where keyword counts fail.

### Claim 3: Evidence Verification Makes Fusion Auditable

The evidence-verification agent can detect whether proposed retrieval-grounded corrections are supported, contradicted, or insufficiently supported by retrieved clinical context.

Required evidence:

- Human-labeled evidence-verification benchmark.
- LLM verifier vs deterministic verifier.
- Contradiction recall.
- Unsupported decision recall.
- Examples of accepted and rejected fusion changes.

## Recommended Experiment Table

The main results table should compare:

| Method | Uses Retrieval | Uses Structured Priors | Uses LLM Audit | Full Macro F1 | Gray-Zone Macro F1 | Notes |
| --- | --- | --- | --- | ---: | ---: | --- |
| Vision only | No | No | No | 0.6971 | 0.6310 | Current RAD-DINO baseline |
| Gray-zone abstention | No | No | No | 0.6126 | null | Too conservative |
| Keyword-count fusion | Yes | No | No | 0.7246 | 0.7613 | Current deterministic baseline |
| Unweighted retrieval-prior fusion | Yes | Yes | No | TBD | TBD | New baseline |
| Similarity-weighted retrieval-prior fusion | Yes | Yes | No | TBD | TBD | New core method |
| Calibrated retrieval-prior fusion | Yes | Yes | No | TBD | TBD | Main classification method |
| Calibrated retrieval-prior fusion + audit | Yes | Yes | Yes | TBD | TBD | Main audited system |

The LLM audit row should not be expected to improve F1 unless it actually accepts/rejects fusion decisions in a way that changes labels. Its primary metrics should be evidence-verification metrics.

## Implementation Plan

### Step 1: Retrieval Prior Module

Create:

```text
v2/src/medagentx/reasoning/retrieval_prior.py
```

Primary dataclass:

```python
@dataclass(frozen=True)
class RetrievalLabelPrior:
    label: str
    present_prior: float
    absent_prior: float
    uncertain_rate: float
    unmentioned_rate: float
    scoreable_weight: float
    total_weight: float
    mean_similarity: float
    effective_k: int
    top_present_cases: tuple[str, ...]
    top_absent_cases: tuple[str, ...]
```

Inputs:

- Target `study_key`.
- Retrieved case IDs.
- Retrieved similarities.
- Structured train label table.
- Disease label set.

Outputs:

- One `RetrievalLabelPrior` per disease label.
- Audit metadata sufficient for downstream evidence verification.

### Step 2: Prior Fusion Module

Create:

```text
v2/src/medagentx/reasoning/prior_fusion.py
```

This should be a parallel alternative to the current keyword-count fusion module. It should preserve the same high-level interface shape where possible so the evaluation code can compare both policies cleanly.

### Step 3: Evaluation CLI

Create:

```text
v2/src/medagentx/cli/run_prior_fusion_eval.py
```

This CLI should:

- Load vision predictions.
- Load retrieval results.
- Load train structured label table.
- Compute retrieval priors.
- Apply prior fusion.
- Run Judge evaluation.
- Emit comparable CSV and JSON summaries.

### Step 4: Validation Tuning

Add validation-only tuning for:

- Promotion prior threshold.
- Demotion prior threshold.
- Minimum scoreable retrieval confidence.
- Similarity weighting.
- Optional per-label gray-zone margin.

The test set should be used only once the validation policy is fixed.

### Step 5: Evidence Audit Integration

Extend evidence verification inputs to include retrieval-prior metadata.

The verifier should be able to explain:

- Which retrieved cases drove the prior.
- Whether report snippets support the structured prior.
- Whether contradictory snippets exist.
- Whether the fusion decision should be considered supported, mixed, contradicted, or insufficient.

### Step 6: Annotation Packet Export

Create an export script for human evidence-verification packets.

Suggested output:

```text
v2/experiments/evidence_benchmark/annotation_packets.jsonl
v2/experiments/evidence_benchmark/annotation_packets.csv
```

The packets should be sampled from fusion-changed labels and stratified by:

- Label.
- Promotion vs demotion.
- Retrieval-prior strength.
- Evidence-verifier confidence.
- Presence of contradictions.

## Risks and Mitigations

| Risk | Why It Matters | Mitigation |
| --- | --- | --- |
| Retrieval priors reproduce training label noise | Structured labels are derived from reports | Report label-source limitations, add human audit subset |
| Similar cases are visually similar but clinically different | Retrieval can mislead fusion | Require confidence, gray-zone constraint, contradiction audit |
| Prior fusion overfits validation | Many tunable knobs | Keep tuning small, report constrained search, lock test |
| LLM audit is inconsistent | LLM outputs can vary | Use deterministic schemas, temperature 0, compare deterministic verifier |
| ICLR reviewers see this as an application system | System framing may look incremental | Center method, ablations, calibration, benchmark, reproducibility |
| Human benchmark too small | Weak audit claims | Report it as initial benchmark unless annotation scale is expanded |

## Recommended Paper Title Direction

Possible title:

```text
Calibrated Retrieval-Prior Fusion for Gray-Zone Chest Radiograph Classification
```

Possible subtitle or framing phrase:

```text
An Agentic Evidence-Verification Workflow for Auditable Similar-Case Correction
```

Avoid titles that imply a general medical agent, autonomous diagnosis system, or broad clinical assistant.

## Recommended Abstract Direction

Draft abstract shape:

```text
Medical image classifiers often produce uncertain predictions near learned decision
thresholds, where small probability changes can alter clinical labels. We introduce
MEDAGENT-X, a calibrated retrieval-prior fusion framework for gray-zone chest
radiograph classification. Given a study-level vision prediction, MEDAGENT-X retrieves
visually similar training studies, estimates similarity-weighted structured label
priors, and permits deterministic label correction only within a calibrated gray zone
around each label threshold. A LangGraph-based evidence-verification workflow then
audits whether accepted or proposed corrections are supported, contradicted, or
insufficiently supported by retrieved clinical evidence. On a 906-study test split,
the current keyword-count retrieval-fusion baseline improves full-test macro F1 from
0.6971 to 0.7246 and gray-zone macro F1 from 0.6310 to 0.7613 while preserving macro
precision. We further replace raw mention-count fusion with calibrated retrieval
priors and evaluate evidence verification against a human-labeled audit benchmark.
```

This abstract should be updated after the retrieval-prior experiments are complete.

## Definition of Done for the ICLR Submission

The strategy becomes ICLR-ready only if the following are completed:

- Retrieval-prior fusion implemented and tested.
- Validation-tuned fusion policy frozen before test evaluation.
- Main table includes vision, abstention, keyword-count fusion, prior fusion, and audited prior fusion.
- Gray-zone and full-test metrics are both reported.
- Per-label deltas and failure cases are reported.
- Evidence-verification benchmark is created and evaluated.
- Code path is reproducible from documented commands.
- The paper clearly distinguishes classification metrics from evidence-audit metrics.
- The ethics and limitations sections address clinical deployment, label noise, privacy, and non-diagnostic use.

## Bottom Line

This is a good strategy if the paper is narrowed around the calibrated fusion method and the audit benchmark.

The defensible ICLR story is not:

```text
MEDAGENT-X is a broad agentic medical AI system.
```

The defensible ICLR story is:

```text
MEDAGENT-X is an agent-orchestrated implementation of calibrated retrieval-prior
fusion for gray-zone medical image classification, with evidence-verification
auditing to make similar-case corrections inspectable and testable.
```

The next implementation work should start with `retrieval_prior.py`, then `prior_fusion.py`, then a validation-tuned evaluation CLI.
