from __future__ import annotations

import re


def clean_dicom_path(path: str) -> str:
    path = str(path).strip().replace("\\", "/").lstrip("./")

    if "/train/" in path:
        path = path.split("/train/", maxsplit=1)[1]

    for prefix in ("train/", "DICOM_train/", "dicom_train/"):
        if path.startswith(prefix):
            path = path[len(prefix):]

    return path


def parse_study_key_from_dcm(path: str) -> str:
    """
    train/patient00003/study1/view1_frontal.dcm -> patient00003/study1
    """
    path = clean_dicom_path(path)
    match = re.search(r"(patient\d+/study\d+)", path)
    if match:
        return match.group(1)

    parts = path.split("/")
    if len(parts) >= 3 and parts[0].startswith("patient") and parts[1].startswith("study"):
        return f"{parts[0]}/{parts[1]}"

    return ""