# Exp 08 Prior Fusion Default

This folder is the default output target for the first retrieval-prior fusion
experiment:

```text
default checkpoint vision thresholds + default prior-fusion rules
```

Run from the repository root:

```bash
python v2/experiments/optimization_prior_fusion_inputs/run_prior_fusion_eval.py
```

Use `--overwrite` to replace generated files in this folder.


Loads the fine-tuned RAD-DINO checkpoint.
Runs vision inference on the selected split.
Uses each study embedding to query the Chroma retrieval DB.
Computes retrieval priors from the retrieved train studies’ structured labels.
Applies prior_fusion.py rules.
Compares vision-only vs prior-fusion.

