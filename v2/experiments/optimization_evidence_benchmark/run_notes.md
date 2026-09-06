# MEDAGENT-X Optimization Evidence Benchmark Notes

Date: 2026-09-03

## Purpose

This folder contains Phase 1 evidence-verification benchmark artifacts exported
from Experiment 7.

The goal of this phase is to make Exp 7 fusion changes easier to inspect and
annotate. These files are a benchmark construction aid, not the final human
evidence-verification benchmark.

## Source Run

Default source:

```text
v2/experiments/exp07_llm_fusion_evidence_verification_graph/qwen3_14b
```

Source artifacts used:

- `fusion_label_predictions.csv`
- `llm_evidence_policy_audit.csv`
- `evidence_verification.json`
- `graph_reasoning_results.jsonl`
- `run_config.json`

## Generated Files

- `annotation_packets_exp07.csv`
  - Spreadsheet-friendly annotation packet table.
  - One row is one changed `study_key` + `label` packet.

- `annotation_packets_exp07.jsonl`
  - Machine-friendly version of the same packet set.
  - One JSON object per line.

- `annotation_rubric.md`
  - Human annotation instructions for `human_support_label`,
    `human_error_tags`, and `human_notes`.

## Packet Scope

The current packet set includes only labels where final fusion changed the
vision prediction:

```text
vision_status != fused_status
```

The default export target is 200 packets.

The first 40 selected packets are marked:

```text
is_pilot_packet = True
```

These 40 rows should be used as a pilot review set before committing to any
larger annotation effort.

## Sampling Policy

The exporter prioritizes hard and rare cases before filling the remaining
sample.

Mandatory inclusion groups:

- all `contradictory` LLM evidence assessments
- all `insufficient` LLM evidence assessments
- all fallback-like packets
- all demotions

Oversampled hard labels:

- `Pneumothorax`
- `Fracture`
- `Lung Lesion`
- `Pleural Other`

Remaining packet slots are filled from mixed, supporting, and remaining changed
fusion cases.

## Fallback-Like Packets

A packet is marked fallback-like when one or more signals suggest the evidence
or LLM audit path may be incomplete or policy-rejected.

Fallback reasons may include:

- `llm-evidence-assessment-blank`
- `llm-not-reviewed`
- `graph-trace-fallback-used`
- `missing-audit-row`
- `missing-label-evidence-detail`

Fallback-like does not necessarily mean the pipeline crashed. It usually means
the LLM output was missing, invalid, rejected by policy, or incomplete for that
study-label packet.

## Important Limitation

Experiment 7 used the older keyword-count fusion policy:

```text
deterministic_gray_zone_fusion_v2
```

Therefore, these Exp 7 packets should not be treated as the final benchmark for
the calibrated retrieval-prior fusion thesis.

The final benchmark should be built later from calibrated retrieval-prior fusion
outputs, with a smaller subset of Exp 7 cases retained for baseline comparison.

## Recommended Use

Use this folder for:

- inspecting Exp 7 fusion changes
- checking whether the packet schema is understandable
- running a 40-packet pilot annotation pass
- identifying common evidence-verification failure modes

Do not use this folder as:

- the final paper benchmark
- evidence that calibrated retrieval-prior fusion has been evaluated
- a replacement for validation-first Topic 2 experiments
