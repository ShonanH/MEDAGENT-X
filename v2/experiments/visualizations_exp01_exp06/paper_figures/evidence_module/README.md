# Evidence-verification module figures

The two verification methods are plotted in separate directories.
No figure in these directories mixes policy records.

| Directory | Paper experiment | Verification method | Studies |
|---|---:|---|---:|
| `without_llm/` | 5 | `evidence_verification_without_LLM` | 415 |
| `with_llm_qwen/` | 6 | `llm_evidence_verification` | 491 |

Each directory contains separate study-score, label-score, retrieval-support, and changed-vs-unchanged figures as PNG and PDF, plus the filtered study- and label-level CSV files.

Important: these records come from a mixed checkpoint and represent different study subsets. The figures are descriptive module audits, not a paired or randomized comparison between policies.
