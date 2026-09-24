# Atomic conference-paper figures

Every figure is exported as a 300+ DPI PNG and a vector PDF.
Internal chart gridlines and white scatter-point outlines are disabled.

## Paper experiment numbering

| Paper experiment | Configuration | Historical source |
|---:|---|---|
| 1 | Vision only | exp01 |
| 2 | Fusion without retrieval | exp03 |
| 3 | Deterministic retrieval fusion | exp04 artifacts |
| 4 | LLM retrieval fusion | exp05 |
| 5 | Deterministic fusion + evidence verification | exp06; labels inherited from Exp. 3 |
| 6 | Qwen fusion + LLM evidence verification | historical exp07 |

## Confusion-matrix interpretation

Each cell shows only the aggregate count across the 12 labels.
Experiments 5 and 6 use their upstream label predictions because evidence verification assesses support but does not modify diagnostic predictions.

## Evidence method names

- `evidence_verification_without_LLM`
- `llm_evidence_verification`

The policy plots are descriptive provenance summaries because the checkpoint mixes the two methods across studies; they are not a randomized head-to-head comparison.
Files beginning `exp06_qwen_` are filtered to the 491 `llm_evidence_verification` records and exclude the 415 non-LLM verification records.
