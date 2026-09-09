# MEDAGENT-X Source Inventory

Last updated: 2026-09-08

This file records the sources used to design, implement, and evaluate MEDAGENT-X
through Experiment 12. It separates external scientific sources from local
project evidence so that a paper does not accidentally cite an experiment result
as published evidence, or describe a background paper as code that was directly
implemented.

## 1. Datasets and Evaluation Benchmarks

### CheXpert

- [CheXpert paper (AAAI 2019)](https://ojs.aaai.org/index.php/AAAI/article/view/3834)
  - Primary reference for the 14 CheXpert observations, report-derived labels,
    uncertainty labels, and expert-reference validation and test sets.
  - DOI: [10.1609/aaai.v33i01.3301590](https://doi.org/10.1609/aaai.v33i01.3301590)
- [Official CheXpert dataset page](https://aimi.stanford.edu/datasets/chexpert-chest-x-rays)
  - Official dataset-access source.
- [Official CheXpert competition and leaderboard](https://stanfordmlgroup.github.io/competitions/chexpert/)
  - Source for the competition protocol, leaderboard results, and the five
    competition labels: Atelectasis, Cardiomegaly, Consolidation, Edema, and
    Pleural Effusion.
- [Released CheXpert test-set labels](https://github.com/rajpurkarlab/cheXpert-test-set-labels)
  - Source for the 500-study expert-labeled test reference standard and released
    model/radiologist outputs.

### CheXpert Plus

- [Official CheXpert Plus dataset page](https://aimi.stanford.edu/datasets/chexpert-plus)
  - Source dataset used by this repository, accessed through Redivis.
- [CheXpert Plus paper](https://arxiv.org/abs/2405.19538)
  - Primary description of the linked reports, images, demographics, metadata,
    labels, and RadGraph annotations.
- [Official CheXpert Plus repository](https://github.com/Stanford-AIMI/chexpert-plus)
  - Dataset documentation and supporting code.
- Repository dataset identifier: `aimi.chexpert_plus:5yyj:v1_0`
  - Locked in `v2/src/medagentx/data/constants.py`.
  - The implementation uses the Redivis REST API and the dataset tables recorded
    in that file.

## 2. Vision Model

- [RAD-DINO paper: Exploring Scalable Medical Image Encoders Beyond Text
  Supervision](https://www.nature.com/articles/s42256-024-00965-w)
  - Scientific basis for the image encoder used for classification and retrieval
    embeddings.
- [Microsoft RAD-DINO model card and weights](https://huggingface.co/microsoft/rad-dino)
  - Exact pretrained backbone loaded by the repository as
    `microsoft/rad-dino`.

## 3. Research Paper Bibliography

This section collects the research papers discussed during the work so far,
including papers used for direct technical context and papers considered as
comparisons or future directions. MEDAGENT-X does not claim to reimplement every
paper listed here.

### Dataset, Label, and Encoder Papers

- [CheXpert: A Large Chest Radiograph Dataset with Uncertainty Labels and Expert
  Comparison](https://ojs.aaai.org/index.php/AAAI/article/view/3834)
  - Irvin et al., AAAI, 2019.
  - Defines the dataset, report-derived label states, and expert-reference
    evaluation used throughout our discussion.
- [CheXpert Plus: Augmenting a Large Chest X-ray Dataset with Text Radiology
  Reports, Patient Demographics and Additional Image
  Formats](https://arxiv.org/abs/2405.19538)
  - Chambon et al., 2024.
  - Describes the expanded dataset used by this repository.
- [Exploring Scalable Medical Image Encoders Beyond Text
  Supervision](https://www.nature.com/articles/s42256-024-00965-w)
  - Perez-Garcia et al., Nature Machine Intelligence, 2025.
  - Introduces RAD-DINO, the vision backbone and retrieval embedding source used
    in MEDAGENT-X.
- [ChestX-ray8: Hospital-Scale Chest X-Ray Database and Benchmarks on
  Weakly-Supervised Classification and Localization of Common Thorax
  Diseases](https://openaccess.thecvf.com/content_cvpr_2017/html/Wang_ChestX-ray8_Hospital-Scale_Chest_CVPR_2017_paper.html)
  - Wang et al., CVPR, 2017.
  - Earlier precedent for report-derived, multi-label chest X-ray supervision.

### CheXpert Competition and Classification Papers

- [Large-scale Robust Deep AUC Maximization: A New Surrogate Loss and Empirical
  Studies on Medical Image Classification](https://arxiv.org/abs/2012.03173)
  - Yuan et al., ICCV, 2021.
  - Paper associated with the `DeepAUC-v1` ensemble at the top of the published
    CheXpert leaderboard.
- [Interpreting Chest X-rays via CNNs that Exploit Hierarchical Disease
  Dependencies and Uncertainty Labels](https://arxiv.org/abs/1911.06475)
  - Pham et al., Neurocomputing/MIDL, 2020.
  - CheXpert leaderboard method using label dependencies and label smoothing for
    uncertain examples.
- [Anatomy-XNet: An Anatomy Aware Convolutional Neural Network for Thoracic
  Disease Classification in Chest X-rays](https://doi.org/10.1109/JBHI.2022.3199594)
  - Kamal et al., IEEE Journal of Biomedical and Health Informatics, 2022.
  - Anatomy-guided CheXpert classification approach represented on the
    competition leaderboard.
- [Expert-level Detection of Pathologies from Unannotated Chest X-ray Images via
  Self-supervised Learning](https://www.nature.com/articles/s41551-022-00936-9)
  - Tiu et al., Nature Biomedical Engineering, 2022.
  - Introduces CheXzero and provides an example of evaluation against the
    expert-labeled CheXpert test set and radiologist performance.
- [Distribution-Aware Multi-Label FixMatch for Semi-Supervised Learning on
  CheXpert](https://openaccess.thecvf.com/content/CVPR2024W/DCAMI/html/Ihler_Distribution-Aware_Multi-Label_FixMatch_for_Semi-Supervised_Learning_on_CheXpert._CVPRW_2024_paper.html)
  - Ihler et al., CVPR Workshops, 2024.
  - Relevant to class imbalance, partially labeled data, and per-label behavior.
- [CXPMRG-Bench: Pre-training and Benchmarking for X-ray Medical Report
  Generation on CheXpert Plus Dataset](https://arxiv.org/abs/2410.00379)
  - Wang et al., 2024.
  - CheXpert Plus-specific benchmark and report-generation reference considered
    for broader comparisons; it is not the current classification protocol.

### Uncertain and Missing Labels

- [Learn To Be Uncertain: Leveraging Uncertain Labels In Chest X-rays With
  Bayesian Neural Networks](https://openaccess.thecvf.com/content_CVPRW_2019/html/Uncertainty_and_Robustness_in_Deep_Visual_Learning/Yang_Learn_To_Be_Uncertain_Leveraging_Uncertain_Labels_In_Chest_X-rays_CVPRW_2019_paper.html)
  - Yang et al., CVPR Workshops, 2019.
  - Examines uncertain CheXpert labels and predictive uncertainty. It was
    discussed as context, not implemented as a Bayesian model here.
- [Interpreting Chest X-rays via CNNs that Exploit Hierarchical Disease
  Dependencies and Uncertainty Labels](https://arxiv.org/abs/1911.06475)
  - Pham et al., 2020.
  - Also relevant here because it treats uncertainty as part of the multi-label
    learning problem rather than silently equating every uncertain value with a
    definitive negative.
- [Distribution-Aware Multi-Label FixMatch for Semi-Supervised Learning on
  CheXpert](https://openaccess.thecvf.com/content/CVPR2024W/DCAMI/html/Ihler_Distribution-Aware_Multi-Label_FixMatch_for_Semi-Supervised_Learning_on_CheXpert._CVPRW_2024_paper.html)
  - Ihler et al., 2024.
  - Also relevant to missing-label and imbalance concerns raised during the
    per-label calibration discussion.

### Medical Image and Report Retrieval

- [Retrieval-Based Chest X-Ray Report Generation Using a Pre-trained Contrastive
  Language-Image Model](https://proceedings.mlr.press/v158/endo21a.html)
  - Endo et al., ML4H, 2021.
  - Introduces CXR-RePaiR and provides medical image-to-case/report retrieval
    precedent.
- [Multimodal Image-Text Matching Improves Retrieval-based Chest X-Ray Report
  Generation](https://proceedings.mlr.press/v227/jeong24a.html)
  - Jeong et al., MIDL, 2024.
  - Shows why clinically meaningful retrieval can require finer image-text
    matching than raw global cosine similarity.
- [Computer-aided Diagnosis through Medical Image Retrieval in
  Radiology](https://pmc.ncbi.nlm.nih.gov/articles/PMC9715673/)
  - Silva et al., Scientific Reports, 2022.
  - Studies visually and clinically similar chest X-ray retrieval for decision
    support and emphasizes that visual similarity is not automatically equal to
    disease similarity.
- [Deep Metric Learning-based Image Retrieval System for Chest Radiograph and
  its Clinical Applications in COVID-19](https://pmc.ncbi.nlm.nih.gov/articles/PMC8032481/)
  - Zhong et al., Medical Image Analysis, 2021.
  - Relevant precedent for label-aware chest radiograph embedding and retrieval.

### Calibration, Validation, and Overfitting

- [On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html)
  - Guo et al., ICML, 2017.
  - Background for fitting calibration parameters on validation data rather
    than selecting them on the test split.
- [Beta Calibration: A Well-founded and Easily Implemented Improvement on
  Logistic Calibration for Binary Classifiers](https://proceedings.mlr.press/v54/kull17a.html)
  - Kull, Silva Filho, and Flach, AISTATS, 2017.
  - Parametric calibration method considered during discussion but not
    implemented in the current retrieval-prior policy.
- [Evaluating Model Calibration in
  Classification](https://proceedings.mlr.press/v89/vaicenavicius19a.html)
  - Vaicenavicius et al., AISTATS, 2019.
  - Context for separating predictive discrimination, decision thresholds, and
    probability calibration.
- [Calibration: The Achilles Heel of Predictive
  Analytics](https://doi.org/10.1186/s12916-019-1466-7)
  - Van Calster et al., BMC Medicine, 2019.
  - Clinical prediction perspective on calibration, sample size, validation,
    and overfitting.
- [Bias in Error Estimation When Using Cross-validation for Model
  Selection](https://doi.org/10.1186/1471-2105-7-91)
  - Varma and Simon, BMC Bioinformatics, 2006.
  - Supports keeping model/policy selection separate from final performance
    estimation.

The current Experiment 11 implementation uses deterministic validation search,
patient-grouped cross-validation, bootstrap stability checks, support floors,
and partial pooling. It does not fit logistic calibration, beta calibration,
Gaussian discriminant analysis, or a Bayesian neural network.

## 4. Software and Runtime Resources

- [Redivis API documentation](https://apidocs.redivis.com/)
  - Data queries and raw-file downloads.
- [Hugging Face Transformers documentation](https://huggingface.co/docs/transformers/)
  - RAD-DINO model and image-processor loading.
- [Chroma documentation](https://docs.trychroma.com/)
  - Persistent nearest-neighbor retrieval index.
- [LangGraph documentation](https://docs.langchain.com/oss/python/langgraph/overview)
  - Typed graph orchestration for the reasoning pipeline.
- [Ollama API documentation](https://docs.ollama.com/api/introduction)
  - Local LLM inference used by the fusion and evidence-verification agents.
- [Ollama Llama 3.1 model page](https://ollama.com/library/llama3.1)
  - Model used in the main Experiment 5 run.
- [Ollama Qwen3 model page](https://ollama.com/library/qwen3)
  - `qwen3:14b` model used in the alternate Experiment 5 run and referenced by
    the evidence-verification workflow.

The exact Python package requirements are recorded in the repository root
`pyproject.toml`. Package documentation is an implementation reference, not
scientific evidence for the method.

## 5. Internal Design Documents

- `v2/docs/MEDAGENT-X_Topic1_Topic2_Strategy1_Handoff.md`
  - Original specification for evidence verification and calibrated,
    similarity-weighted retrieval priors.
- `v2/docs/MEDAGENT-X_Topic_Implementation_Order_Handoff.md`
  - Phase ordering and required experimental comparisons.
- `v2/docs/MEDAGENT-X_Calibrated_Retrieval_Prior_Fusion_Implementation_Report_2026-09-02.md`
  - Consolidated architecture, baseline results, proposed method, and paper
    framing before the calibrated experiments were completed.
- `v2/docs/implementation_report_2026-08-16.md`
  - Earlier end-to-end implementation status and keyword-count fusion baseline.
- `v2/docs/label-fusion-agent.md`
  - Label-fusion behavior and LLM guardrails.
- `v2/docs/evidence-verification-agent.md`
  - Evidence-verification inputs, verdicts, error taxonomy, and output schema.
- `v2/experiments/optimization_evidence_benchmark/annotation_rubric.md`
  - Human evidence-audit annotation definitions.
- `v2/experiments/optimization_evidence_benchmark/run_notes.md`
  - Provenance and limitations of the provisional evidence benchmark.

## 6. Data Inputs and Policies

- `v2/experiments/optimization_prior_fusion_inputs/splits/view_splits.csv`
  - Patient-separated train, validation, and test view assignments used by the
    prior-fusion experiments.
- `v2/experiments/optimization_prior_fusion_inputs/splits/study_label_table.csv`
  - Study-level `status_*` ground truth and the structured train labels used to
    calculate retrieval priors.
- `v2/artifacts/cohort_balanced_v1/vision/raddino_finetuned_v1_last4_blocks/best_checkpoint.pt`
  - Fine-tuned RAD-DINO checkpoint used by Experiments 9, 10, and 12.
  - Referenced by the run configurations but not present in this workspace.
- `v2/artifacts/cohort_balanced_v1/reasoning/fusion_eval_v1/val_last4_blocks/val/threshold_tuning/threshold_policy_v2.json`
  - Validation-tuned vision thresholds used by Experiments 9 through 12.
  - Referenced by the run configurations but not present in this workspace.
- `v2/artifacts/cohort_balanced_v1/retrieval/raddino_train_v1_last4_blocks/chroma`
  - Train-only RAD-DINO retrieval index used by Experiments 9, 10, and 12.
  - Referenced by the run configurations but not present in this workspace.
- `v2/experiments/exp11_prior_fusion_per_label_tuning/best_prior_fusion_policy.json`
  - Frozen validation-selected per-label fusion policy evaluated in Experiment
    12.

These local files contain derived CheXpert Plus data or trained artifacts and
must not be redistributed unless their source licenses and data-use terms allow
it.

## 7. Local Implementation Sources

- `v2/experiments/optimization_prior_fusion_inputs/retrieval_prior.py`
  - Computes similarity-weighted present, absent, uncertain, and unmentioned
    retrieval statistics.
- `v2/experiments/optimization_prior_fusion_inputs/prior_fusion.py`
  - Applies deterministic gray-zone promotion and demotion gates.
- `v2/experiments/optimization_prior_fusion_inputs/run_prior_fusion_eval.py`
  - Produces vision predictions, retrieval-prior features, fused predictions,
    and Judge metrics.
- `v2/experiments/optimization_prior_fusion_inputs/tune_prior_fusion_global_gates.py`
  - Experiment 10 global validation grid search.
- `v2/experiments/optimization_prior_fusion_inputs/tune_prior_fusion_per_label_gates.py`
  - Experiment 11 per-label validation search with support, precision,
    cross-validation, bootstrap, and partial-pooling safeguards.

## 8. Experiment Evidence Used So Far

### Experiment 5: keyword-count and LLM fusion baseline

- `v2/experiments/exp05_llm_fusion_with_retrieval_graph/run_config.json`
- `v2/experiments/exp05_llm_fusion_with_retrieval_graph/judge_evaluation/judge_summary.json`
- `v2/experiments/exp05_llm_fusion_with_retrieval_graph/judge_evaluation/per_label_metrics.csv`
- `v2/experiments/exp05_llm_fusion_with_retrieval_graph/judge_evaluation/fusion_changed_cells.csv`
- `v2/experiments/exp05_llm_fusion_with_retrieval_graph/qwen3_14b/run_config.json`
- `v2/experiments/exp05_llm_fusion_with_retrieval_graph/qwen3_14b/judge_evaluation/judge_summary.json`

### Experiments 8 and 9: uncalibrated retrieval-prior baselines

- `v2/experiments/exp08_prior_fusion_default/`
  - Default checkpoint and default thresholds; retained as a diagnostic run.
- `v2/experiments/exp09_prior_fusion_last4_tuned/`
  - Last-four-block checkpoint and tuned vision thresholds, but unvalidated
    fusion gates.

### Experiment 10: validation features and global gate search

- `v2/experiments/exp10_prior_fusion_val_features/`
  - Validation-set prediction and retrieval-prior feature table.
- `v2/experiments/exp10_prior_fusion_gate_tuning/global_gate_grid_results.csv`
- `v2/experiments/exp10_prior_fusion_gate_tuning/best_prior_fusion_policy.json`
- `v2/experiments/exp10_prior_fusion_gate_tuning/best_changed_cells.csv`

### Experiment 11: per-label gate calibration

- `v2/experiments/exp11_prior_fusion_per_label_tuning/per_label_gate_grid_results.csv`
- `v2/experiments/exp11_prior_fusion_per_label_tuning/per_label_gate_selection.csv`
- `v2/experiments/exp11_prior_fusion_per_label_tuning/best_prior_fusion_policy.json`
- `v2/experiments/exp11_prior_fusion_per_label_tuning/best_changed_cells.csv`
- `v2/experiments/exp11_prior_fusion_per_label_tuning/run_config.json`

### Experiment 12: locked test evaluation

- `v2/experiments/exp12_prior_fusion_test/judge_summary.json`
- `v2/experiments/exp12_prior_fusion_test/per_label_metrics.csv`
- `v2/experiments/exp12_prior_fusion_test/prior_fusion_changed_cells.csv`
- `v2/experiments/exp12_prior_fusion_test/prior_fusion_change_analysis.csv`
- `v2/experiments/exp12_prior_fusion_test/retrieval_prior_features.csv`
- `v2/experiments/exp12_prior_fusion_test/run_config.json`

Experiment 12 is the current result for calibrated retrieval-prior fusion. The
Experiment 5 result remains the keyword-count comparison baseline; it is not the
same fusion method.

## 9. Referenced but Not Present in the Current Workspace

The implementation-order handoff and provisional benchmark notes refer to:

- `v2/experiments/exp07_llm_fusion_evidence_verification_graph/qwen3_14b/`

The directory exists in this workspace, but the required result files are not
present; only placeholder/checkpoint metadata is available. Its outputs should
not be treated as independently rechecked local evidence until the artifacts are
restored. The provisional files under
`v2/experiments/optimization_evidence_benchmark/` preserve notes about how those
outputs were previously used.

## 10. Citation Boundary for Future Writing

- Cite the CheXpert and CheXpert Plus papers for the data and label definitions.
- Cite the official competition page and released test-label repository for
  competition comparisons.
- Cite the RAD-DINO paper and model card for the image encoder.
- Cite external method papers only for background or related work.
- Cite MEDAGENT-X experiment directories for this project's numerical results.
- Do not describe Experiment 5 as calibrated retrieval-prior fusion.
- Do not use Experiment 12 as final competition evidence: it uses the project's
  current split and 12-label Judge evaluation, not the official five-label,
  expert-labeled CheXpert competition protocol.
