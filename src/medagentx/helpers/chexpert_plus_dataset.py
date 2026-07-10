from pathlib import Path

import pandas as pd
import redivis
import torch
from torch.utils.data import Dataset

from src.medagentx.helpers.dicom_loader import load_normalized_dicom_image


DICOM_TRAIN_TABLE = "aimi.chexpert_plus:5yyj:v1_0.dicom_train:1934"


def clean_redivis_dicom_path(path):
    path = str(path).strip()

    if path.startswith("train/"):
        path = path.removeprefix("train/")

    return path


def get_candidate_dicom_paths(dicom_paths):
    paths = [clean_redivis_dicom_path(path) for path in str(dicom_paths).split("|")]
    paths = [path for path in paths if path]

    frontal_paths = [path for path in paths if "frontal" in path.lower()]
    other_paths = [path for path in paths if path not in frontal_paths]

    return frontal_paths + other_paths


class CheXpertPlusDicomDataset(Dataset):
    def __init__(
        self,
        manifest_path,
        transform=None,
        dicom_table_ref=DICOM_TRAIN_TABLE,
        local_dicom_root=None,
    ):
        self.manifest_path = Path(manifest_path)
        self.transform = transform
        self.dicom_table_ref = dicom_table_ref
        self.local_dicom_root = Path(local_dicom_root) if local_dicom_root else None

        self.manifest = pd.read_csv(self.manifest_path)

        if self.local_dicom_root is None:
            self.dicom_table = redivis.table(self.dicom_table_ref)
        else:
            self.dicom_table = None

    def __len__(self):
        return len(self.manifest)

    def load_dicom(self, dicom_paths):
        last_error = None

        for dicom_path in get_candidate_dicom_paths(dicom_paths):
            try:
                if self.local_dicom_root is not None:
                    local_path = self.local_dicom_root / dicom_path

                    if not local_path.exists():
                        raise FileNotFoundError(local_path)

                    with local_path.open("rb") as f:
                        image, ds = load_normalized_dicom_image(f)

                    return image, ds, dicom_path

                dicom_file = self.dicom_table.file(dicom_path)

                with dicom_file.open("rb") as f:
                    image, ds = load_normalized_dicom_image(f)

                return image, ds, dicom_path

            except Exception as error:
                last_error = error

        raise FileNotFoundError(
            f"No readable DICOM found for paths: {dicom_paths}"
        ) from last_error

    def __getitem__(self, idx):
        row = self.manifest.iloc[idx]

        image, ds, dicom_path = self.load_dicom(row["dicom_paths"])

        image = torch.from_numpy(image).float()
        image = image.unsqueeze(0)

        if self.transform is not None:
            image = self.transform(image)

        return {
            "image": image,
            "study_key": row["study_key"],
            "dicom_path": dicom_path,
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