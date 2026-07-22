"""Command-line entry points for the MEDAGENT-X pipeline (01-16).

Recommended run order:

  01_fetch_redivis_chexpert_rows.py
  02_fetch_redivis_chexpert_labels.py
  03_build_fusion_report_label_table.py
  03a_build_patient_splits.py
  04_build_chexpert_manifest.py
  05_download_manifest_dicoms.py
  06_extract_convnext_features.py
  07_extract_raddino_features.py
  08_train_fusion_classifier.py
  09_build_unified_evidence_manifest.py
  10_build_quality_evidence_manifest.py
  11_run_quality_gate.py
  12_build_chexpert_vector_db.py
  13_run_densenet_predictions.py
  14_run_fusion_inference.py
  15_build_ensemble_classifier_predictions.py
  16_run_bulk_medagentx_and_judge.py
"""
