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
   LIMT {int(row_limit)}
   """

   return dataset.query(query).to_pandas_dataframe()


def add_study_key(df):
   df = df.copy()

   df["study_key"] = df["path_to_dcm"].str.extract(
      r"(patient\d+/study\d+)", expand=False
   )

   return df


def build_study_manifest(df, study_limit=50):
   df = add_study_key(df)

   df = df.dropna(subset=["study_key"])

   grouped = (
      df.groupby("study_key", as_index=False)
      .agg(
         deid_patient_id=("deid_patient_id", "first"),
         split=("split", "first"),
         age=("age", "first"),
         sex=("sex", "first"),
         race=("race", "first"),
         ethnicity=("ethnicity", "first"),
         dicom_path={"path_to_dcm", list},
         image_path=("path_to_image", list),
         frontal_lateral_view=("frontal_lateral", list),
         ap_pa_views=("ap_pa", list),
         report=("report", "first"),
         section_findings=("section_findings", "first"),
         section_impression=("section_impression", "first"),
         image_count=("path_to_dcm", "count"),
      )
   )
   grouped = grouped.head(int(study_limit))

   return grouped

