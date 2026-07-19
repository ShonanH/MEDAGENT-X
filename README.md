# MEDAGENT-X

Multi-agent medical imaging pipeline for CheXpert Plus chest X-ray analysis.

The project combines image classifiers (DenseNet, ConvNeXt + RAD-DINO fusion), retrieval over similar cases, deterministic disease labeling, and LLM-assisted report writing — with a quality gate as the first safety check.

## Project layout

Everything lives under `src/`:

```
src/
  medagentx/          # Python package (agents, fusion, classifiers, helpers)
    cli/              # Pipeline entry-point scripts
    agents/
    fusion/
    ...
  data/               # Local datasets and manifests (not committed)
  outputs/            # Pipeline artifacts and model outputs
  tests/              # Unit tests
```

Repo root keeps only packaging and docs:

- `README.md`
- `requirements.txt`
- `pyproject.toml`

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Set your Redivis token when fetching metadata:

```bash
export REDIVIS_ACCESS_TOKEN='your_token'
```

## Running the pipeline

Run scripts directly (from repo root):

```bash
python src/medagentx/cli/fetch_redivis_chexpert_rows.py
python src/medagentx/cli/09_build_fusion_report_label_table.py
python src/medagentx/cli/10_train_fusion_classifier.py
```

Or after `pip install -e .`:

```bash
PYTHONPATH=src python src/medagentx/cli/10_train_fusion_classifier.py
```

## Tests

```bash
pytest
```

## Data policy

Do not commit datasets, DICOM files, checkpoints, or private metadata. Keep downloads under `src/data/`.
