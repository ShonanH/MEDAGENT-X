CHEXPERT_PLUS_TABLE = "df_chexpert_plus_240401"

MANIFEST_COLUMNS = [
    "path_to_image",
    "path_to_dcm",
    "frontal_lateral",
    "ap_pa",
    "deid_patient_id",
    "patient_report_date_order",
    "age",
    "sex",
    "race",
    "ethnicity",
    "split",
    "report",
    "section_findings",
    "section_impression",
]


def build_query(row_limit):
    selected_columns = ",\n        ".join(MANIFEST_COLUMNS)

    return f"""
    SELECT
        {selected_columns}
    FROM `{CHEXPERT_PLUS_TABLE}`
    WHERE path_to_dcm IS NOT NULL
    LIMIT {int(row_limit)}
    """


def extract_study_key(path_to_dcm):
    if path_to_dcm is None:
        return None

    parts = str(path_to_dcm).split("/")

    if len(parts) < 4:
        return None

    patient_id = parts[1]
    study_id = parts[2]

    if not patient_id.startswith("patient"):
        return None

    if not study_id.startswith("study"):
        return None

    return f"{patient_id}/{study_id}"


def row_to_plain_dict(row):
    plain = {}

    for column in MANIFEST_COLUMNS:
        value = row.get(column)

        if value is None:
            plain[column] = ""
        else:
            plain[column] = value

    plain["study_key"] = extract_study_key(plain["path_to_dcm"])

    return plain


def build_study_manifest_records(rows, study_limit):
    studies = {}

    for row in rows:
        row = row_to_plain_dict(row)
        study_key = row["study_key"]

        if study_key is None:
            continue

        if study_key not in studies:
            studies[study_key] = {
                "study_key": study_key,
                "deid_patient_id": row["deid_patient_id"],
                "split": row["split"],
                "age": row["age"],
                "sex": row["sex"],
                "race": row["race"],
                "ethnicity": row["ethnicity"],
                "dicom_paths": [],
                "image_paths": [],
                "frontal_lateral_views": [],
                "ap_pa_views": [],
                "report": row["report"],
                "section_findings": row["section_findings"],
                "section_impression": row["section_impression"],
            }

        studies[study_key]["dicom_paths"].append(row["path_to_dcm"])
        studies[study_key]["image_paths"].append(row["path_to_image"])
        studies[study_key]["frontal_lateral_views"].append(row["frontal_lateral"])
        studies[study_key]["ap_pa_views"].append(row["ap_pa"])

        if len(studies) >= int(study_limit):
            break

    manifest = []

    for study in studies.values():
        study["image_count"] = len(study["dicom_paths"])
        study["dicom_paths"] = "|".join(study["dicom_paths"])
        study["image_paths"] = "|".join(study["image_paths"])
        study["frontal_lateral_views"] = "|".join(study["frontal_lateral_views"])
        study["ap_pa_views"] = "|".join(study["ap_pa_views"])
        manifest.append(study)

    return manifest