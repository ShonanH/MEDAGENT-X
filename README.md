# MEDAGENT-X

Multi-agent medical imaging pipeline for CheXpert Plus chest X-ray analysis.

The project combines image classifiers (DenseNet, ConvNeXt + RAD-DINO fusion), retrieval over similar cases, deterministic disease labeling, and LLM-assisted report writing — with a quality gate as the first safety check.

## Project layout

Everything lives under `src/`:

```
src/
  medagentx/          # Python package (agents, fusion, classifiers, helpers)
    cli/              # Pipeline scripts numbered 01-16 in run order
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

CLI scripts are numbered **01–16** in recommended run order under `src/medagentx/cli/`.

```bash
# Labels + metadata
python src/medagentx/cli/01_fetch_redivis_chexpert_rows.py
python src/medagentx/cli/02_fetch_redivis_chexpert_labels.py --download-findings
python src/medagentx/cli/03_build_fusion_report_label_table.py
python src/medagentx/cli/03a_build_patient_splits.py  # optional: rebuild frozen splits only

# DICOMs + image features
python src/medagentx/cli/04_build_chexpert_manifest.py
python src/medagentx/cli/05_download_manifest_dicoms.py
python src/medagentx/cli/06_extract_convnext_features.py
python src/medagentx/cli/07_extract_raddino_features.py

# Fusion training
python src/medagentx/cli/08_train_fusion_classifier.py

# Agent workflow
python src/medagentx/cli/09_build_unified_evidence_manifest.py
python src/medagentx/cli/10_build_quality_evidence_manifest.py
python src/medagentx/cli/11_run_quality_gate.py
python src/medagentx/cli/12_build_chexpert_vector_db.py
python src/medagentx/cli/13_run_densenet_predictions.py
python src/medagentx/cli/14_run_fusion_inference.py
python src/medagentx/cli/15_build_ensemble_classifier_predictions.py
python src/medagentx/cli/16_run_bulk_medagentx_and_judge.py
```

See `src/medagentx/cli/__init__.py` for the full list.

## Tests

```bash
pytest
```

## Data policy

Do not commit datasets, DICOM files, checkpoints, or private metadata. Keep downloads under `src/data/`.
