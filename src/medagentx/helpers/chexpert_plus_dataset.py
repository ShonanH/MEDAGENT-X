from pathlib import Path

import pandas as pd
import redivis
import torch
from torch.utils.data import Dataset

from src.medagentx.helpers.dicom_loader import load_normalized_dicom_image


DICOM_TRAIN_TABLE = "aimi.chexpert_plus:5yyj:v1_0.dicom_train:1934"

def clean_redivis_dicom_path(path):
    path = str(path)

    if path.startswith("train/"):
        path = path.removeprefix("train/")

    return path


def get_preferred_dicom_path(dicom_paths):
    paths = [clean_redivis_dicom_path(path) for path in str(dicom_paths).split("|")]

    for path in paths:
        if "frontal" in path.lower():
            return path

    return paths[0]

class CheXpertPlusDicomDataset(Dataset):
    def __init__(self, manifest_path, transform=None, dicom_table_ref=DICOM_TRAIN_TABLE):
        self.manifest_path = Path(manifest_path)
        self.transform = transform
        self.dicom_table_ref = dicom_table_ref

        self.manifest = pd.read_csv(self.manifest_path)
        self.dicom_table = redivis.table(self.dicom_table_ref)

    def __len__(self):
        return len(self.manifest)

    def __getitem__(self, idx):
        row = self.manifest.iloc[idx]

        redivis_dicom_path = get_preferred_dicom_path(row["dicom_paths"])        
        dicom_file = self.dicom_table.file(redivis_dicom_path)

        with dicom_file.open("rb") as f:
            image, ds = load_normalized_dicom_image(f)

        image = torch.from_numpy(image).float()

        #Shape of the image
        image = image.unsqueeze(0)

        if self.transform is not None:
            image = self.transform(image)
            
        return {
            "image": image,
            "study_key": row["study_key"],
            "dicom_path": redivis_dicom_path,
            "deid_patient_id": row["deid_patient_id"],
            "age": row["age"],
            "sex": row["sex"],
            "split": row["split"],
            "image_count": int(row["image_count"]),
            "frontal_lateral_views": row["frontal_lateral_views"],
            "ap_pa_views": row["ap_pa_views"],
            "report": row["report"],
            "section_findings": row.get("section_findings", ""),
            "section_impression": row["section_impression"],
            "rows": getattr(ds, "Rows", None),
            "columns": getattr(ds, "Columns", None),
            "photometric": getattr(ds, "PhotometricInterpretation", None),
            "view_position": getattr(ds, "ViewPosition", None),
        }