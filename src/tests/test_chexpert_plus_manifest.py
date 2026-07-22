from medagentx.helpers.chexpert_plus_manifest import build_study_manifest_records


def _row(patient, study, image):
    path = f"DICOM_train/{patient}/{study}/{image}.dcm"
    return {
        "path_to_image": path.replace(".dcm", ".png"),
        "path_to_dcm": path,
        "frontal_lateral": "Frontal",
        "ap_pa": "PA",
        "deid_patient_id": patient,
        "patient_report_date_order": "1",
        "age": "50",
        "sex": "Male",
        "race": "",
        "ethnicity": "",
        "split": "train",
        "report": "",
        "section_findings": "",
        "section_impression": "",
    }


def test_build_study_manifest_records_keeps_all_images_for_selected_studies():
    rows = [
        _row("patient00001", "study1", "view1"),
        _row("patient00002", "study1", "view1"),
        _row("patient00001", "study1", "view2"),
        _row("patient00003", "study1", "view1"),
    ]

    manifest = build_study_manifest_records(rows, study_limit=2)

    assert len(manifest) == 2
    by_key = {record["study_key"]: record for record in manifest}
    assert by_key["patient00001/study1"]["image_count"] == 2
    assert by_key["patient00002/study1"]["image_count"] == 1
