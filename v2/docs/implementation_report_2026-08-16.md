# MEDAGENT-X v2 Implementation Report - 2026-08-16

## Executive Summary

MEDAGENT-X v2 is a clean rebuild of the chest X-ray agentic pipeline around a label-enriched MIMIC-CXR / CheXpert workflow. The current implementation supports the full offline path from cohort construction through vision training, retrieval indexing, deterministic fusion, and offline Judge evaluation.

The best saved local result is the last-4 RAD-DINO run evaluated with retrieval `top_k=10`. On the 906-study test split, deterministic fusion improved full macro F1 from `0.697` to `0.725` and gray-zone macro F1 from `0.632` to `0.761`, while keeping macro precision nearly unchanged.

The next engineering work is to finalize validation-based fusion tuning, implement a proper LangGraph workflow, build the Report Writing Agent, and run Evidence Verification end to end.

## Current Pipeline

### Offline Build Pipeline

1. Data acquisition from Redivis
   - Fetches MIMIC-CXR train metadata, DICOM index rows, report sections, and `findings_fixed.json`.
   - Applies label-gated cohort rules so downstream stages only use studies with parseable CheXpert-style labels.
   - Main entry point: `python -m medagentx.cli.fetch_stage_a_data`

2. Label-enriched balanced cohort
   - Selects a patient-level cohort with better rare-label coverage.
   - Preserves patient-level split isolation.
   - Uses policy `label_enriched_cohort_policy_v2`.
   - Main entry point: `python -m medagentx.cli.build_balanced_cohort`

3. Study label construction
   - Parses CheXpert labels into structured label statuses.
   - Aggregates multi-view labels to study-level labels.
   - Builds 12 disease training targets plus masks.
   - Main entry point: `python -m medagentx.cli.build_study_labels`

4. DICOM quality gate
   - Computes technical DICOM quality metrics.
   - Drops failed views and keeps studies with at least one usable view.
   - Main entry point: `python -m medagentx.cli.run_quality_gate`

5. Final cohort and splits
   - Rebuilds study labels after quality filtering.
   - Writes deterministic patient-level train/val/test splits.
   - Audits post-quality label target coverage.
   - Main entry point: `python -m medagentx.cli.finalize_balanced_cohort`

6. RAD-DINO vision training
   - Fine-tunes `microsoft/rad-dino` for 12 disease labels.
   - Uses masked multi-label training so uncertain/unmentioned cells are not treated as ordinary negatives.
   - Current best saved run uses:
     - BCE loss
     - mean+max pooling
     - last 4 transformer blocks trainable
     - validation macro F1 checkpoint selection
   - Main entry point: `python -m medagentx.cli.train_raddino`

7. Vision prediction and threshold tuning
   - Generates study-level disease probabilities and binary present/absent statuses.
   - Tunes per-label thresholds on validation.
   - Main entry points:
     - `python -m medagentx.cli.predict_raddino`
     - `python -m medagentx.cli.tune_vision_thresholds`

8. Retrieval index
   - Builds a Chroma index over train studies only.
   - Uses fine-tuned RAD-DINO study embeddings for image similarity.
   - Stores report text payloads for retrieved train neighbors.
   - Excludes the same study and same patient at query time.
   - Default retrieval is now `top_k=10`.
   - `top_k` remains CLI-configurable for future ablation studies.
   - Main entry point: `python -m medagentx.cli.build_retrieval_index`

9. Deterministic label fusion
   - Fusion uses no LLM.
   - Fusion can override vision only inside the gray zone: `abs(probability - threshold) <= 0.15`.
   - Strong-zone vision predictions are preserved.
   - Retrieval evidence is counted from report keyword and negation matches.
   - Current policy: `deterministic_gray_zone_fusion_v2`.
   - Main entry point: `python -m medagentx.cli.run_fusion_eval`

10. Offline Judge evaluation
    - Compares vision-only and fusion outputs against structured study labels.
    - Judge is offline-only and is not part of live inference.
    - Reports full-test and gray-zone metrics.
    - Current metric policy: `judge_metric_policy_v1`.

## Current Inference Shape

The intended inference flow is:

```text
Vision -> Retrieval -> Label Fusion -> Evidence Verification -> Report Writer
```

Current implementation status:

- Vision backend exists and can produce study-level probabilities, thresholds, statuses, and embeddings.
- Retrieval helpers exist and query the train-only Chroma index.
- Deterministic fusion exists and produces structured fused label statuses.
- Evidence Verification Agent exists and produces evidence scores, summaries, supporting snippets, and contradicting snippets.
- LangGraph state and Evidence Verification node scaffolding exist.
- Full production LangGraph workflow still needs to be implemented properly.
- Report Writing Agent is not yet implemented.

## Current Results

### Vision Training: Last-4 RAD-DINO Run

Saved artifact root:

```text
v2/artifacts/Outputs_transformer_training_last4_blocks
```

Run configuration:

- Train studies: `3,538`
- Validation studies: `855`
- Test studies: `906`
- Model: `microsoft/rad-dino`
- Trainable transformer blocks: `4`
- Pooling: `mean_max`
- Loss: `bce`
- Selection metric: `macro_f1`

Validation metrics:

- Macro AUROC: `0.846`
- Macro average precision: `0.593`
- Macro F1: `0.596`

Test metrics:

- Macro AUROC: `0.815`
- Macro average precision: `0.559`
- Macro F1: `0.529`

The last-4 run improved over the saved last-2 run:

- Last-2 test macro AUROC: `0.800`
- Last-2 test macro F1: `0.492`
- Last-4 test macro AUROC: `0.815`
- Last-4 test macro F1: `0.529`

### Fusion Evaluation: Last-4, Retrieval Top-K 10

Saved artifact root:

```text
v2/artifacts/Evaluation_output_last4_blocks_top10/test
```

Configuration:

- Split: `test`
- Test studies: `906`
- Labels per study: `12`
- Total study-label cells: `10,872`
- Gray-zone rows: `1,813`
- Retrieval top-k: `10`
- Gray-zone margin: `0.15`
- Threshold policy: `vision_threshold_policy_v2`
- Fusion policy: `deterministic_gray_zone_fusion_v2`

Full-test Judge results:

| Run | Macro F1 | Macro Precision | Macro Recall | Micro F1 | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| Vision full | `0.697` | `0.911` | `0.570` | `0.705` | `0.149` |
| Fusion full | `0.725` | `0.912` | `0.605` | `0.738` | `0.149` |

Full-test change:

- Macro F1 gain: `+0.027`
- Macro recall gain: `+0.036`
- Macro precision change: approximately flat
- Micro F1 gain: `+0.034`

Gray-zone Judge results:

| Run | Macro F1 | Macro Precision | Macro Recall | Micro F1 | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| Vision gray zone | `0.632` | `0.876` | `0.509` | `0.643` | `0.185` |
| Fusion gray zone | `0.761` | `0.877` | `0.695` | `0.804` | `0.184` |

Gray-zone change:

- Macro F1 gain: `+0.130`
- Macro recall gain: `+0.186`
- Macro precision change: approximately flat
- Micro F1 gain: `+0.161`

Fusion changed-cell summary:

- Changed cells: `389`
- Main behavior: mostly absent-to-present promotions.
- The strongest full-test label gains were:
  - Edema: `+0.068` F1
  - Atelectasis: `+0.063` F1
  - Pleural Effusion: `+0.050` F1
  - Lung Lesion: `+0.042` F1
  - Lung Opacity: `+0.037` F1
- Labels with no full-test F1 change:
  - Enlarged Cardiomediastinum
  - Pleural Other
  - Pneumonia
- Pneumothorax slightly regressed:
  - `0.594` to `0.593`

## Important Caveats

- Heavy artifacts are not currently present in this workspace.
- The result CSV/JSON files under `v2/artifacts/` are local untracked artifacts.
- The code references `v2/artifacts/cohort_balanced_v1`, checkpoints, DICOMs, and Chroma indexes that are not currently available locally.
- The current reported metrics are based on saved result summaries, not a freshly rerun pipeline.
- Full validation-based fusion rule tuning has not yet been completed for the latest top-k 10 setup.
- Current testing was intentionally not run as part of this step, per project direction.

## Implemented Components

### Data and Cohort

- Redivis client and paginated row fetching.
- Findings JSON retrieval and indexing.
- Label-gated cohort selection.
- Label-enriched balanced patient selection.
- Quality filtering and post-quality cohort finalization.
- Deterministic patient splits.

### Labels

- CheXpert raw-value parsing.
- Study-level label aggregation.
- Training target and mask creation.
- No Finding contradiction handling.

### Vision

- RAD-DINO study classifier.
- Multi-view study batching.
- Masked multi-label loss support.
- BCE and asymmetric loss options.
- Training, prediction, and threshold-tuning CLIs.
- Study-level output contracts.

### Retrieval

- Train-only RAD-DINO embedding extraction.
- Chroma index writing and querying.
- Same-study and same-patient exclusion.
- Report payload construction from findings and impression text.
- Default `top_k=10`.
- CLI override support for fusion evaluation and Evidence Verification.

### Fusion

- Deterministic gray-zone fusion policy.
- Keyword and negation mention counting.
- Label-specific rule overrides.
- Vision-only vs fusion evaluation outputs.
- Changed-cell and per-label diagnostic artifacts.

### Evaluation

- Offline Judge.
- Full-split and gray-zone scoring.
- Macro/micro precision, recall, F1, and coverage.
- Per-label metrics, status confusion, uncertain-status diagnostics, and fusion change analysis.

### Evidence Verification

- Evidence Verification Agent.
- Per-label evidence scoring from vision and retrieval evidence.
- Supporting and contradicting snippets.
- CSV and JSON output contracts.
- CLI runner with configurable retrieval top-k.
- LangGraph node wrapper for Evidence Verification.

## Remaining Work

### 1. Validation-Based Fusion Rule Tuning

Goal:

- Tune fusion policy on validation only.
- Lock the selected policy.
- Run test only once after policy selection.

Likely tuning dimensions:

- Retrieval `top_k`
- Promotion positive-count thresholds
- Promotion negative-count limits
- Label-specific keyword lists
- Demotion thresholds
- Similarity weighting
- Requirements for evidence across multiple retrieved studies

Current priority:

- Use validation outputs to reduce noisy promotions while preserving gray-zone recall gains.

### 2. Proper LangGraph Workflow

Goal:

- Replace scaffold-only graph assembly with a production workflow using the current LangGraph patterns.

Target graph:

```text
START
  -> vision
  -> retrieval
  -> fusion
  -> evidence_verification
  -> report_writer
  -> END
```

Expected work:

- Define stable graph state.
- Implement concrete node functions for vision, retrieval, fusion, evidence verification, and report writing.
- Add validation at node boundaries.
- Support local/offline execution with artifact paths.
- Keep Judge outside the live graph.

### 3. Report Writing Agent

Goal:

- Generate a radiology-style report from fused labels and verified evidence.

Constraints:

- Fused labels should be binding facts.
- Evidence Verification should inform confidence and phrasing.
- Report Writer should not silently contradict fused labels.
- Output should include structured sections suitable for evaluation and audit.

Likely output:

- Findings
- Impression
- Structured label summary
- Evidence/confidence metadata

### 4. Evidence Verification End-to-End Evaluation

Goal:

- Run Evidence Verification across validation or test once required artifacts are available.
- Produce `evidence_verification.csv`, `evidence_verification.json`, and summary JSON.
- Analyze evidence score distributions and low-confidence patterns.

Key questions:

- How often does fusion have strong retrieval support?
- Which labels produce contradictory evidence?
- Which predictions should be flagged for human review?
- Does evidence verification help decide when Report Writer language should be cautious?

### 5. Documentation and Reproducibility

Goal:

- Keep this Markdown report and generated docs aligned with the actual current pipeline.
- Add a reproducible runbook once artifacts and final tuning decisions are settled.
- Clarify which outputs are tracked code, local artifacts, or heavyweight data/checkpoints.

## Agreed Plan For Today

1. Set default retrieval to `top_k=10` while preserving CLI configurability for future ablations.
2. Create this updated implementation report.
3. Ignore heavyweight artifacts for now.
4. Run full validation-based fusion rule tuning.
5. Implement a proper LangGraph workflow using the LangGraph workflows/agents documentation.
6. Build the Report Writing Agent.
7. Run and evaluate Evidence Verification outputs end to end.

## Current Step Status

- Step 1: completed.
- Step 2: completed by this report.
- Step 3: accepted as a constraint.
- Step 4: not started.
- Step 5: not started.
- Step 6: not started.
- Step 7: not started.

