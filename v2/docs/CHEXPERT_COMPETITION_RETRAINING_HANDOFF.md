# CheXpert Competition Retraining Handoff

## 1. Objective

Build a competition-aligned vision model that exceeds `0.80` five-label macro
AUROC on the released expert-labeled CheXpert test set. Only after the vision
baseline is locked should retrieval and continuous score fusion be evaluated.

This work replaces threshold tuning, discrete label fusion, and small-cohort
diagnostic experiments as the active implementation track.

## 2. Current Baseline

The verified checkpoint is:

```text
v2/artifacts/cohort_balanced_v1/vision/
raddino_finetuned_v1_last4_blocks/best_checkpoint.pt
```

Its relevant metadata is:

```text
model: microsoft/rad-dino
trainable_last_blocks: 4
pooling_mode: mean_max
training studies: 3,538
checkpoint selection: 12-label macro F1
best epoch: 2
```

Observed five-label macro AUROC:

| Evaluation set | Macro AUROC |
|---|---:|
| Internal test | 0.7997 |
| Competition validation | 0.5929 |
| Competition test | 0.6511 |

Last-two-block and last-four-block checkpoints both perform poorly on the
competition data. Exp18 also showed that simple JPEG normalization and
mean-versus-max view aggregation do not explain the gap. The active hypothesis
is therefore insufficient training scale plus mismatch between the custom
training labels and the expert competition evaluation protocol.

## 3. Locked Evaluation Scope

Use only the five competition labels, in this order:

1. Atelectasis
2. Cardiomegaly
3. Consolidation
4. Edema
5. Pleural Effusion

The primary metric is unweighted macro AUROC across these labels. AUROC must be
computed from continuous scores. Threshold selection, F1, precision, and recall
are secondary operating-point analyses and must not select the checkpoint.

The released splits have different roles:

| Split | Role |
|---|---|
| Full CheXpert training data | Parameter fitting |
| Patient-disjoint development split made from training data | Early stopping and routine experiments |
| Released 200-study expert validation set | Final architecture and policy selection |
| Released 500-study expert test set | Final locked evaluation only |

Do not repeatedly use the competition test set to select data policies,
hyperparameters, checkpoints, retrieval rules, or fusion weights.

## 4. Data Source and Required Audit

The intended image source is the complete CheXpert Plus `PNG_train` table. Use
the provided CheXpert/CheXpert Plus labels rather than reparsing reports for the
primary competition-aligned target.

Do not assume the PNG table and label table join correctly. The first executable
deliverable must inspect and record:

- PNG table identifier and schema.
- Label table identifier and schema.
- Stable patient, study, and image/view join keys.
- Number of unique patients, studies, and images before and after joining.
- Missing images and missing labels.
- Duplicate image and study keys.
- Label counts for `1`, `0`, `-1`, and missing values.
- Frontal and lateral view counts.
- Evidence that released validation/test patients are absent from training.
- Local file existence and readable-image checks.

The manifest builder must fail on leakage, duplicate keys, unsupported label
values, or missing required files. It must not silently drop rows.

## 5. Canonical Training Artifacts

Write the new data products under a fresh root:

```text
v2/artifacts/chexpert_competition_v1/
  manifests/
    all_views.csv
    train_views.csv
    dev_views.csv
    study_labels.csv
    manifest_audit.json
    label_distribution.csv
    excluded_rows.csv
  vision/
  retrieval/
  fusion/
```

`all_views.csv` must contain at least:

```text
patient_id
study_id
study_key
image_id
image_path
view
split
```

`study_labels.csv` must contain, for each competition label:

```text
raw_<label>
target_<label>
mask_<label>
```

Preserve the raw source value. Derived targets and masks must identify the
uncertainty policy version that produced them.

## 6. Patient-Level Development Split

Create the development split only from the full training population.

- Assign patients, never individual images or studies.
- Use a fixed seed and persist the patient assignment.
- Start with approximately 95% train and 5% development.
- Stratify approximately across the five positive labels where practical.
- Verify zero patient overlap between train and development.
- Verify zero overlap with released competition validation and test patients.

The split file is immutable after model experiments begin. Changing it creates a
new versioned artifact root.

## 7. Uncertainty Policy

CheXpert training labels may contain uncertain values. Do not collapse these
values before the audit.

Evaluate a small, predefined policy set on the internal development split:

1. `ignore_uncertain`: mask `-1` and missing cells.
2. `u_zero`: map `-1` to negative.
3. `u_one`: map `-1` to positive.
4. A documented label-specific U-Zero/U-One policy, if justified.

Use definite `1` and `0` labels consistently. Missing values must not be treated
as negative unless the source label contract explicitly defines that behavior.

Choose the policy using five-label macro AUROC on the internal development
split. Confirm the chosen policy once on competition validation. Do not search a
large per-label policy space on only 200 validation studies.

## 8. Required Code Changes

The existing vision stack is coupled to the old experiment:

- `StudyDataset` defaults to DICOM loading.
- `train_raddino.py` assumes a `dicom_root`.
- `RadDinoStudyClassifier` requires exactly 12 output labels.
- Checkpoint validation assumes the locked 12-label ordering.
- Training metrics and checkpoint selection average over all 12 labels.

Refactor these points narrowly:

1. Allow the training dataset to receive a raster image loader.
2. Rename generic path concepts from DICOM-only names where compatibility permits.
3. Make the classifier output label inventory configurable and checkpointed.
4. Preserve backward loading for existing 12-label checkpoints.
5. Compute training metrics over the checkpoint's configured label inventory.
6. Select checkpoints by five-label macro AUROC.
7. Store label order, data-policy version, split version, and image-source version in every checkpoint.

Do not modify the old balanced-cohort artifacts in place.

## 9. Vision Training Sequence

### 9.1 Smoke Test

Run a small end-to-end job before full training:

- 100-500 studies.
- At least one positive and one negative for each label.
- One training epoch.
- PNG loading, augmentation, multi-view collation, loss, metrics, checkpoint save,
  checkpoint reload, and prediction export must all complete.

The smoke test is a wiring test, not a performance result.

### 9.2 Primary RAD-DINO Baseline

Start with:

```text
backbone: microsoft/rad-dino
labels: five competition labels
pooling: mean_max
trainable blocks: last 4
loss: masked BCE
checkpoint metric: five-label macro AUROC
mixed precision: enabled
seed: 42
```

Determine the largest stable batch size on the RTX 4090, then use gradient
accumulation for a documented effective batch size. Record actual image count,
study count, optimizer steps, learning rates, and wall time.

Do not start with asymmetric loss or aggressive class reweighting. Establish the
full-data BCE baseline first.

### 9.3 Controlled Vision Variants

If the primary baseline remains below `0.80` on competition validation, compare
only a small controlled set:

- Classifier head only, if zero trainable transformer blocks are supported.
- Last four RAD-DINO blocks.
- Full RAD-DINO fine-tuning with a lower backbone learning rate.
- A standard DenseNet-121 CheXpert baseline.
- An average of the strongest RAD-DINO and DenseNet continuous scores.

Keep the data split, label policy, preprocessing, and metric fixed while changing
one model choice at a time.

## 10. Vision Acceptance Gates

A model may advance only when:

- All five labels have positive and negative examples in development evaluation.
- Checkpoint reload reproduces saved probabilities within numerical tolerance.
- Five-label internal development macro AUROC is recorded.
- Released competition validation macro AUROC is at least `0.80`.
- No threshold tuning is used to claim an AUROC improvement.
- The final configuration and checkpoint hash are locked before test evaluation.

The preferred validation target is `0.82-0.84`, providing margin for uncertainty
from the small validation set. Crossing `0.80` is a goal, not a guarantee.

## 11. Competition Evaluation

Retain the threshold-independent evaluator:

```text
v2/src/medagentx/cli/run_chexpert_competition_eval.py
```

It must continue to produce:

- One continuous score per study and label.
- Per-label AUROC and average precision.
- Five-label macro AUROC.
- Auditable study-label ranking cells.
- Exact checkpoint and input paths in `run_config.json`.

Add a validation-mode entry point or a separate validation evaluator rather than
using a threshold-calibration script.

## 12. Retrieval Phase

Do not begin this phase until the locked vision baseline reaches the validation
gate.

Build a new retrieval index using embeddings from the retrained checkpoint:

- Index training studies only.
- Exclude internal development, competition validation, and competition test.
- Persist checkpoint hash and manifest version with the index.
- Use the same image preprocessing and study-level pooling as training.
- Assert that every retrieved neighbor belongs to the training split.

Replace unweighted positive/negative counting with continuous, similarity-aware
evidence. For label `l`, one initial retrieval score is:

```text
r_l = sum_i(weight_i * target_i,l * mask_i,l) /
      sum_i(weight_i * mask_i,l)
```

where `weight_i` is derived from embedding similarity. Neighbors masked for the
label contribute neither positive nor negative evidence. Save neighbor IDs,
similarities, label masks, and numerator/denominator terms for auditability.

Evaluate retrieval score AUROC by itself before fusion. If retrieval does not
rank labels above chance or add complementary signal, do not proceed to fusion.

## 13. Continuous Fusion Phase

Fusion must output continuous scores. Discrete present/absent/uncertain labels
cannot support a meaningful competition AUROC comparison.

Start with a constrained formulation such as:

```text
fused_logit_l = vision_logit_l + alpha_l * retrieval_logit_l
```

Requirements:

- Fit fusion parameters without competition-test data.
- Prefer regularized/shared parameters before per-label parameters because the
  expert validation set is small.
- Tune on internal development and use competition validation only for final
  selection.
- Compare vision-only, retrieval-only, and fused AUROC on identical cells.
- Use patient-level bootstrap confidence intervals for AUROC deltas.
- Advance only if fusion improves macro AUROC without severe per-label regressions.

LLM-generated categorical decisions are outside this initial AUROC fusion path.

## 14. Experiment Order

Implement and review one step at a time:

1. Inspect the Redivis `PNG_train` and label-table schemas.
2. Build and test the competition training manifest and leakage audit.
3. Add generic raster training support.
4. Generalize the model/checkpoint contract from 12 labels to a configured inventory.
5. Generalize metrics and checkpoint selection to five-label macro AUROC.
6. Run the smoke training job and checkpoint-reload check.
7. Train the full-data RAD-DINO last-four-block baseline.
8. Evaluate on internal development.
9. Evaluate once on competition validation.
10. Run controlled model variants only if the validation gate is missed.
11. Lock the best vision configuration and evaluate competition test.
12. Build the train-only retrieval index.
13. Evaluate continuous retrieval scores.
14. Fit and evaluate continuous fusion.
15. Run the final locked competition-test comparison.

## 15. Reproducibility Checklist

Every full run must save:

- Git commit.
- Checkpoint SHA-256.
- Input manifest SHA-256.
- Dataset and label-policy versions.
- Patient split seed and counts.
- Model label ordering.
- Image preprocessing configuration.
- Optimizer and scheduler configuration.
- Effective batch size.
- Best epoch and selection metric.
- Per-label and macro AUROC/AP.
- Continuous study-level predictions.
- Runtime and device information.

## 16. First Order of Business

The next file to implement is the PNG/label schema inspection and manifest audit.
Do not modify the trainer until the exact Redivis join keys, label values, image
counts, and patient exclusions are known.

The implemented audit entry point is:

```text
v2/src/medagentx/cli/audit_chexpert_competition_manifest.py
```

Example invocation (run only after the local PNG root and expert test
groundtruth path are confirmed):

```text
PYTHONPATH=v2/src python -m medagentx.cli.audit_chexpert_competition_manifest \
  --png-root /path/to/PNG_train \
  --expert-test-groundtruth v2/data/groundtruth.csv \
  --uncertainty-policy ignore_uncertain
```

It requires a local `PNG_train` root and the released expert test groundtruth
CSV. The explicit uncertainty policy is selected at invocation time; the
default is `ignore_uncertain`. It writes only to the fresh
`v2/artifacts/chexpert_competition_v1/` root and does not create a development
split. Development splitting remains a separate, immutable patient-level step.
