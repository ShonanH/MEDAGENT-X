# MEDAGENT-X

MEDAGENT-X is a multi-agent medical imaging framework for image quality assessment (IQA) as the first safety gate before downstream diagnosis. Version 1 focuses on CT image quality assessment using LDCTIQAC2023.

The project is motivated by MedIQA, but it is not intended to replicate MedIQA. The goal is to build a competing agentic pipeline that combines a visual quality model with structured AI agents for uncertainty-aware, explainable clinical usability decisions.

## Research Goal

- Build a CT IQA pipeline that predicts image quality before diagnosis.
- Produce both a numeric quality score and a clinical usability recommendation.
- Use IQA as a safety gate before any future diagnosis agent makes clinical claims.
- Support both 2D CT slice workflows and future 3D CT volume aggregation.
- Use Llama 4 for agent reasoning, judging, reporting, and explanation.
- Use a visual model for pixel-level scoring and artifact evidence.

## Version 1 Scope

- Dataset: LDCTIQAC2023
- Modality: CT
- Input type: 2D CT slices first, then 3D volume aggregation
- Main model: ConvNeXt-Tiny baseline, followed by ConvNeXt-Tiny plus Transformer fusion head
- Learning setup: multi-task learning
- Agent system: custom Python orchestrator
- Downstream diagnosis: placeholder only in v1

## Expected Output

```json
{
	"quality_score": 3.6,
	"clinical_usability_level": 3,
	"clinical_usability_label": "Adequate with caution",
	"recommendation": "Use with caution; radiologist review required.",
	"confidence": 0.72,
	"requires_human_review": true
}
```

## Clinical Usability Scale

| Level | Label                 | Recommendation                                                       |
| ----- | --------------------- | -------------------------------------------------------------------- |
| 5     | Excellent             | Accept for diagnostic interpretation.                                |
| 4     | Good                  | Accept for routine diagnostic use.                                   |
| 3     | Adequate with caution | Use with caution; subtle findings may be limited.                    |
| 2     | Limited               | Restricted diagnostic value; consider repeat or alternative imaging. |
| 1     | Non-diagnostic        | Reject or repeat unless no alternative exists.                       |

## Project Areas

- `configs/`: experiment and runtime configuration files
- `data/`: local dataset storage; not committed to git
- `docs/`: project notes, dataset notes, design decisions, and research writeups
- `experiments/`: experiment logs, result summaries, and run metadata
- `notebooks/`: exploratory notebooks for data inspection and prototyping
- `scripts/`: command-line entry points for setup, training, evaluation, and inference
- `src/medagentx/`: reusable source code
- `tests/`: lightweight tests and sanity checks

## Implementation Phases

1. Repo setup
2. Dataset setup
3. Data loader
4. CT preprocessing
5. ConvNeXt-Tiny score baseline
6. Multi-task model
7. Clinical scale mapping
8. Agent layer
9. Diagnosis safety gate
10. Evaluation
11. Nautilus NRP training
12. First end-to-end milestone

## First Milestone

The first meaningful milestone is one LDCTIQAC2023 case running end to end:

- load image
- preprocess image
- predict quality score
- map score to clinical usability level
- generate structured JSON output
- route through placeholder agent pipeline

## Data Policy

Do not commit datasets, DICOM files, generated image data, checkpoints, logs, or private metadata. Keep dataset downloads under `data/`, which is ignored by git.

## Notes

This repository is in Phase 1. The priority is to establish a clean project structure before implementing dataset loading, training, or agents.
