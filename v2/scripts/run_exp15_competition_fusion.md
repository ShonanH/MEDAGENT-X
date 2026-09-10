# Exp15: Exp05 Fusion on the CheXpert Competition Test Set

Run from the repository root on the GPU machine. Ollama must be running with
the same `llama3.1:8b` model used by the main Exp05 run.

```bash
export PYTHONPATH="$(pwd)/v2/src"
ollama serve
```

In a second terminal, confirm the model is installed:

```bash
ollama list
```

## Five-Study Smoke Test

```bash
python -m medagentx.cli.run_chexpert_competition_fusion \
  --max-studies 5 \
  --output-dir v2/experiments/exp15_competition_exp05_fusion/smoke \
  --progress-every 1 \
  --overwrite \
  --allow-llm-fallback
```

## Complete 500-Study Run

Run this only after inspecting the smoke-test output:

```bash
python -m medagentx.cli.run_chexpert_competition_fusion \
  --output-dir v2/experiments/exp15_competition_exp05_fusion/competition \
  --progress-every 10 \
  --overwrite \
  --allow-llm-fallback
```

The runner uses the same checkpoint, validation-tuned thresholds, retrieval
index, top-k value, gray-zone margin, Ollama model, and guarded LLM policy as
the main Exp05 run. Expert ground truth is loaded only after inference and
fusion finish. The five competition labels are evaluated as binary outputs;
raw fusion `uncertain` statuses are retained in the output and mapped to
`absent` only for F1, precision, and recall calculation.
