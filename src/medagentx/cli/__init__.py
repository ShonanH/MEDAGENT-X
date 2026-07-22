"""Command-line entry points for the MEDAGENT-X pipeline (01-17).

Recommended run order:

  01_fetch_redivis_chexpert_rows.py
  02_fetch_redivis_chexpert_labels.py
  03_build_fusion_report_label_table.py
  04_build_chexpert_manifest.py
  05_download_manifest_dicoms.py
  06_extract_convnext_features.py
  07_extract_raddino_features.py
  08_build_unified_evidence_manifest.py
  09_build_quality_evidence_manifest.py
  10_run_quality_gate.py
  11_build_patient_splits.py
  12_train_fusion_classifier.py
  13_build_chexpert_vector_db.py
  14_run_densenet_predictions.py
  15_run_fusion_inference.py
  16_build_ensemble_classifier_predictions.py
  17_run_bulk_medagentx_and_judge.py
"""
