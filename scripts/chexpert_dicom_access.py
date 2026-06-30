import argparse
from pathlib import Path

import pandas as pd
import pydicom
import redivis


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DICOM_TRAIN_TABLE = "aimi.chexpert_plus:5yyj:v1_0.dicom_train:1934"

def parse_args():
   parser = argparse.ArgumentParser(
      description="Read one CheXpert Plus DICOM image from Redivis"
   )

   parser.add_argument("--manifest-path", type=Path, default=PROJECT_ROOT / "data" / "processed" / "chexpert_50_manifest.csv", help="Path to the study manifest CSV" )

   parser.add_argument("--row-index", type=int, default=0, help="Manifest row index to test")

   return parser.parse_args()


def get_first_dicom_path(dicom_paths):
   first_path = str(dicom_paths).split("|")[0]

   if first_path.startswith("train/"):
      first_path = first_path.removeprefix("train/")

   return first_path

def main():
   args = parse_args()

   manifest = pd.read_csv(args.manifest_path)

   if args.row_index < 0 or args.row_index >= len(manifest):
      raise IndexError(f"row-index must be between 0 and {len(manifest) - 1}")
   
   row = manifest.iloc[args.row_index]

   redivis_dicom_path = get_first_dicom_path(row["dicom_paths"])

   print("Study key:", row["study_key"])
   print("Manifest DICOM paths:", row["dicom_paths"])
   print("Redivis DICOM path:", redivis_dicom_path)

   table = redivis.table(DICOM_TRAIN_TABLE)
   dicom_file = table.file(redivis_dicom_path)

   print("Opening DICOM through Redivis....")

   with dicom_file.open("rb") as f:
      ds = pydicom.dcmread(f, stop_before_pixels=True)

   print("DICOM read passed!!")
   print()
   print("Selected DICOM metadata:")
   print("  Modality:", getattr(ds, "Modality", None))
   print("  PatientID:", getattr(ds, "PatientID", None))
   print("  StudyInstanceUID:", getattr(ds, "StudyInstanceUID", None))
   print("  SeriesInstanceUID:", getattr(ds, "SeriesInstanceUID", None))
   print("  ViewPosition:", getattr(ds, "ViewPosition", None))
   print("  Rows:", getattr(ds, "Rows", None))
   print("  Columns:", getattr(ds, "Columns", None))
   print("  PhotometricInterpretation:", getattr(ds, "PhotometricInterpretation", None))


if __name__ == "__main__":
    main()