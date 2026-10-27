# MEDAGENT-X

## Introduction

MEDAGENT-X is an offline, research-oriented pipeline for multi-label chest X-ray analysis using CheXpert-style findings. It builds a label-enriched DICOM cohort, filters unusable images, trains a RAD-DINO vision model, retrieves similar training studies, applies deterministic label fusion, and evaluates predictions with a structured offline Judge.

The maintained codebase lives in [`v2/src/medagentx`](v2/src/medagentx). Pipeline artifacts are written beneath `v2/artifacts/` by default and are intentionally not committed. The system is for research and evaluation only; it is not a clinical decision-support device.

The main workflow is:

```text
Redivis data -> balanced cohort -> DICOM quality gate -> labels and patient splits
             -> RAD-DINO training -> train-only retrieval index
             -> vision / deterministic fusion -> offline evaluation
```

## Setup

Use Python 3.10 or later. From the repository root, create an environment, install dependencies, and make the v2 source tree importable:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
export PYTHONPATH="$PWD/v2/src${PYTHONPATH:+:$PYTHONPATH}"
```

For CUDA 12.1 GPU environments, `requirements-nrp.txt` pins the PyTorch CUDA wheels used by `Dockerfile.nrp`:

```bash
python -m pip install -r requirements-nrp.txt
export PYTHONPATH="$PWD/v2/src${PYTHONPATH:+:$PYTHONPATH}"
```

The cohort-build command accesses Redivis. Set a token with access to the required MIMIC-CXR / CheXpert-aligned data before running it:

```bash
export REDIVIS_API_TOKEN='your_token'
```

Optional LLM graph workflows use a reachable Ollama server. Their defaults are `http://localhost:11434` and `gpt-oss:120b`; override them with `MEDAGENTX_OLLAMA_BASE_URL` and `MEDAGENTX_OLLAMA_MODEL`, or the corresponding CLI arguments.

## CLI Files to run in order to reproduce

Run commands as modules from the repository root. The sequence below is the canonical balanced-cohort workflow; each command's defaults use `v2/artifacts/cohort_balanced_v1` as the cohort root. It downloads source data and DICOMs, and training benefits substantially from a CUDA-capable GPU.

1. Build the label-enriched cohort. This is the data-acquisition step and writes `eligible_dicom_rows.csv`, report text, DICOMs, selection audits, and pre-quality labels.

   ```bash
   python -m medagentx.cli.build_balanced_cohort
   ```

2. Run the DICOM-only quality gate. Failed views are excluded, while studies with at least one usable view are retained.

   ```bash
   python -m medagentx.cli.run_quality_gate
   ```

3. Finalize the quality-passed cohort. This creates the canonical `study_label_table.csv` and deterministic patient-level `train` / `val` / `test` splits (70 / 15 / 15, seed 42).

   ```bash
   python -m medagentx.cli.finalize_balanced_cohort
   ```

4. Fine-tune the RAD-DINO multi-label vision model. The selected checkpoint is written to `vision/raddino_finetuned_v1/best_checkpoint.pt` under the cohort root.

   ```bash
   python -m medagentx.cli.train_raddino
   ```

5. Build a Chroma retrieval index from **train-split studies only**. This must precede fusion evaluation to avoid validation/test leakage.

   ```bash
   python -m medagentx.cli.build_retrieval_index
   ```

6. Evaluate vision and deterministic retrieval fusion on validation data. This produces the validation predictions needed for threshold tuning.

   ```bash
   python -m medagentx.cli.run_fusion_eval --split val
   ```

7. Tune constrained per-label vision thresholds using the validation outputs.

   ```bash
   python -m medagentx.cli.tune_vision_thresholds
   ```

8. Produce standalone test-split vision predictions using the tuned policy (optional, but useful for a vision-only baseline).

   ```bash
   python -m medagentx.cli.predict_raddino \
     --split test \
     --threshold-policy-json v2/artifacts/cohort_balanced_v1/reasoning/fusion_eval_v1/val/threshold_tuning/threshold_policy_v2.json
   ```

9. Run the final held-out fusion evaluation with the same threshold policy. Results, per-label metrics, confusion tables, and Judge summaries are written below `reasoning/fusion_eval_v1/test/`.

   ```bash
   python -m medagentx.cli.run_fusion_eval \
     --split test \
     --threshold-policy-json v2/artifacts/cohort_balanced_v1/reasoning/fusion_eval_v1/val/threshold_tuning/threshold_policy_v2.json
   ```

`build_patient_splits` is available when splits alone need to be regenerated after the quality gate, but it is already performed by `finalize_balanced_cohort` in the canonical sequence. `fetch_stage_a_data` and `build_study_labels` provide the earlier unbalanced acquisition/labeling path; do not insert them into the balanced workflow unless you are intentionally creating or auditing a separate cohort.

For a quick smoke test, add suitable limits such as `--max-studies 10` where supported. Do not treat a limited run as a reproduced evaluation. CLI options and their current defaults are available with:

```bash
python -m medagentx.cli.train_raddino --help
```

Run the test suite with:

```bash
PYTHONPATH=v2/src pytest v2/tests
```

## Acknowledgements

MEDAGENT-X builds on the MIMIC-CXR and CheXpert research ecosystems and requires users to follow the applicable dataset-access agreements, privacy requirements, and citation guidance. It uses RAD-DINO through Hugging Face Transformers, PyTorch and TorchVision for vision modeling, Chroma for retrieval storage, LangGraph for optional graph workflows, and Redivis for data access.

Please cite the relevant upstream datasets, models, and software when publishing results derived from this project.

## Repository layout and data handling

```text
v2/
  src/medagentx/       # Package: data, labels, quality, vision, retrieval, reasoning, graphs, CLIs
  tests/               # Unit and contract tests
  scripts/             # Experiment, audit, and documentation helpers
  artifacts/           # Generated data, models, indexes, and evaluations (not committed)
k8s/                   # Storage, setup-pod, and GPU smoke-test manifests
```

Do not commit DICOMs, datasets, access tokens, private metadata, model checkpoints, vector databases, or generated cohort artifacts. Keep those files under `v2/artifacts/` or another secure location outside version control.
