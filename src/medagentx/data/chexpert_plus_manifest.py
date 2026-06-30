from numpy.ma import count
import pandas as pd

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

def query_chexpert_rows(dataset, row_limit=500):
   query = f"""
   SELECT
      {", ".join(MANIFEST_COLUMNS)}
   FROM `{CHEXPERT_PLUS_TABLE}`
   WHERE path_to_dcm IS NOT NULL
   LIMIT {int(row_limit)}
   """

   return dataset.query(query).to_pandas_dataframe()


def add_study_key(df):
    df = df.copy()

    study_key_pattern = r"(?P<study_key>patient\d+/study\d+)"

    extracted = df["path_to_dcm"].astype(str).str.extract(study_key_pattern)

    df["study_key"] = extracted["study_key"]

    return df


def build_study_manifest(df, study_limit=50):
    df = add_study_key(df)

    df = df.dropna(subset=["study_key"])

    grouped = (
        df.groupby("study_key", as_index=False)
        .agg(
            {
                "deid_patient_id": "first",
                "split": "first",
                "age": "first",
                "sex": "first",
                "race": "first",
                "ethnicity": "first",
                "path_to_dcm": list,
                "path_to_image": list,
                "frontal_lateral": list,
                "ap_pa": list,
                "report": "first",
                "section_findings": "first",
                "section_impression": "first",
            }
        )
    )

    grouped = grouped.rename(
        columns={
            "path_to_dcm": "dicom_paths",
            "path_to_image": "image_paths",
            "frontal_lateral": "frontal_lateral_views",
            "ap_pa": "ap_pa_views",
        }
    )

    grouped["image_count"] = grouped["dicom_paths"].apply(len)

    grouped = grouped.head(int(study_limit))

    return grouped
