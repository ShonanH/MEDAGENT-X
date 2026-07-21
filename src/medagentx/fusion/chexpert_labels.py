from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from medagentx.fusion.constants import (
    DISEASE_LABELS,
    LABEL_VALUE_ABSENT,
    LABEL_VALUE_PRESENT,
    NON_DISEASE_LABELS,
    snake_label,
)
from medagentx.fusion.labels import derive_no_finding_status
from medagentx.fusion.paths import clean_dicom_path
from medagentx.helpers.redivis_query_client import normalize_text

ALL_CHEXPERT_LABELS = DISEASE_LABELS + NON_DISEASE_LABELS

CHEXPERT_VALUE_PRESENT = 1.0
CHEXPERT_VALUE_ABSENT = 0.0
CHEXPERT_VALUE_UNCERTAIN = -1.0

LABEL_SOURCE_CHEXPERT = "chexpert_labeler"


def parse_chexpert_raw_value(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip().lower()
        if stripped in {"", "nan", "none", "null", "na"}:
            return None
        try:
            value = float(stripped)
        except ValueError:
            return None
    if isinstance(value, (np.floating, float)) and (np.isnan(value) or np.isinf(value)):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric == CHEXPERT_VALUE_PRESENT:
        return CHEXPERT_VALUE_PRESENT
    if numeric == CHEXPERT_VALUE_ABSENT:
        return CHEXPERT_VALUE_ABSENT
    if numeric == CHEXPERT_VALUE_UNCERTAIN:
        return CHEXPERT_VALUE_UNCERTAIN
    return None


def chexpert_value_to_status(value: Any) -> str:
    parsed = parse_chexpert_raw_value(value)
    if parsed == CHEXPERT_VALUE_PRESENT:
        return "present"
    if parsed == CHEXPERT_VALUE_ABSENT:
        return "absent"
    if parsed == CHEXPERT_VALUE_UNCERTAIN:
        return "uncertain"
    return "unmentioned"


def chexpert_value_to_training_value(value: Any) -> float | None:
    parsed = parse_chexpert_raw_value(value)
    if parsed == CHEXPERT_VALUE_PRESENT:
        return LABEL_VALUE_PRESENT
    if parsed == CHEXPERT_VALUE_ABSENT:
        return LABEL_VALUE_ABSENT
    return None


def chexpert_status_to_evidence(label: str, status: str, raw_value: Any) -> str:
    parsed = parse_chexpert_raw_value(raw_value)
    if parsed is None and status == "unmentioned":
        return "CheXpert labeler: not mentioned."
    return f"CheXpert labeler: {label}={parsed if parsed is not None else 'blank'} ({status})."


def normalize_path_to_image(path: Any) -> str:
    return normalize_text(path)


def normalize_join_key_from_row(row: pd.Series) -> str:
    for column in ("path_to_image", "image_path", "path_to_dcm", "dicom_path"):
        if column in row.index:
            value = normalize_path_to_image(row.get(column))
            if value:
                if column in {"path_to_dcm", "dicom_path"}:
                    value = normalize_path_to_image(
                        str(value).replace(".dcm", ".jpg")
                    )
                return value
    return ""


def labels_from_chexpert_row(row: pd.Series) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}

    for label in DISEASE_LABELS:
        slug = snake_label(label)
        raw = row.get(label)
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            raw = row.get(f"chexpert_value_{slug}")
        status = chexpert_value_to_status(raw)
        output[label] = {
            "weak_status": status,
            "weak_value": chexpert_value_to_training_value(raw),
            "judge_status": status if status != "unmentioned" else "absent",
            "evidence": chexpert_status_to_evidence(label, status, raw),
            "chexpert_raw_value": parse_chexpert_raw_value(raw),
        }

    disease_statuses = {
        label: item["weak_status"]
        for label, item in output.items()
        if label != "No Finding"
    }

    support_raw = row.get("Support Devices")
    if support_raw is None or (isinstance(support_raw, float) and pd.isna(support_raw)):
        support_raw = row.get("chexpert_value_support_devices")
    support_status = chexpert_value_to_status(support_raw)
    output["Support Devices"] = {
        "weak_status": support_status,
        "weak_value": chexpert_value_to_training_value(support_raw),
        "judge_status": support_status if support_status != "unmentioned" else "absent",
        "evidence": chexpert_status_to_evidence("Support Devices", support_status, support_raw),
        "chexpert_raw_value": parse_chexpert_raw_value(support_raw),
    }

    no_finding_raw = row.get("No Finding")
    if no_finding_raw is None or (isinstance(no_finding_raw, float) and pd.isna(no_finding_raw)):
        no_finding_raw = row.get("chexpert_value_no_finding")
    if parse_chexpert_raw_value(no_finding_raw) is not None:
        no_finding_status = chexpert_value_to_status(no_finding_raw)
        if no_finding_status == "unmentioned":
            no_finding_status = derive_no_finding_status(disease_statuses)
    else:
        no_finding_status = derive_no_finding_status(disease_statuses)

    output["No Finding"] = {
        "weak_status": no_finding_status,
        "weak_value": chexpert_value_to_training_value(no_finding_raw),
        "judge_status": no_finding_status,
        "evidence": chexpert_status_to_evidence("No Finding", no_finding_status, no_finding_raw),
        "chexpert_raw_value": parse_chexpert_raw_value(no_finding_raw),
    }

    return output


def labels_from_status_columns(row: pd.Series) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for label in ALL_CHEXPERT_LABELS:
        slug = snake_label(label)
        status = str(row.get(f"weak_status_{slug}", "")).strip().lower()
        if not status:
            raw = row.get(f"chexpert_value_{slug}")
            status = chexpert_value_to_status(raw)
        value = row.get(f"weak_value_{slug}")
        if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
            value = chexpert_value_to_training_value(row.get(f"chexpert_value_{slug}"))
        output[label] = {
            "weak_status": status if status else "unmentioned",
            "weak_value": value,
            "judge_status": status if status and status != "unmentioned" else "absent",
            "evidence": f"CheXpert label table status={status or 'unmentioned'}.",
            "chexpert_raw_value": parse_chexpert_raw_value(row.get(f"chexpert_value_{slug}")),
        }
    return output


def row_has_chexpert_label_columns(row: pd.Series) -> bool:
    if any(str(col).startswith("weak_status_") for col in row.index):
        return True
    return any(label in row.index for label in ALL_CHEXPERT_LABELS)


def ground_truth_label_items_from_row(row: pd.Series) -> list[dict[str, Any]]:
    if row_has_chexpert_label_columns(row):
        label_map = labels_from_status_columns(row)
    else:
        label_map = labels_from_chexpert_row(row)

    items = []
    for label in ALL_CHEXPERT_LABELS:
        item = label_map[label]
        items.append(
            {
                "label": label,
                "status": item["judge_status"],
                "evidence": item["evidence"],
            }
        )
    return items


def add_join_key_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "path_to_image" in out.columns:
        out["_join_key"] = out["path_to_image"].map(normalize_path_to_image)
    elif "path_to_dcm" in out.columns:
        out["_join_key"] = out["path_to_dcm"].map(
            lambda value: normalize_path_to_image(str(value).replace(".dcm", ".jpg"))
        )
    else:
        raise ValueError("Label table must include path_to_image or path_to_dcm.")
    return out


def merge_chexpert_labels(
    rows_df: pd.DataFrame,
    labels_df: pd.DataFrame,
) -> pd.DataFrame:
    left = add_join_key_columns(rows_df)
    right = add_join_key_columns(labels_df)

    label_value_columns = [label for label in ALL_CHEXPERT_LABELS if label in right.columns]
    keep_columns = ["_join_key"] + label_value_columns
    if "path_to_image" in right.columns:
        keep_columns.append("path_to_image")

    merged = left.merge(
        right[keep_columns].drop_duplicates(subset=["_join_key"], keep="last"),
        on="_join_key",
        how="left",
        suffixes=("", "_label"),
    )
    return merged.drop(columns=["_join_key"])


def study_label_conflict_flags(group: pd.DataFrame) -> dict[str, bool]:
    conflicts: dict[str, bool] = {}
    for label in ALL_CHEXPERT_LABELS:
        slug = snake_label(label)
        for col in (f"chexpert_raw_{slug}", f"chexpert_value_{slug}", label):
            if col not in group.columns:
                continue
            values = {
                parse_chexpert_raw_value(value)
                for value in group[col].tolist()
                if parse_chexpert_raw_value(value) is not None
            }
            conflicts[label] = len(values) > 1
            break
    return conflicts


def expand_label_columns(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in frame.iterrows():
        label_items = labels_from_chexpert_row(row)
        out = dict(row)
        for label in ALL_CHEXPERT_LABELS:
            slug = snake_label(label)
            item = label_items[label]
            out[f"chexpert_value_{slug}"] = item["chexpert_raw_value"]
            out[f"weak_status_{slug}"] = item["weak_status"]
            out[f"weak_value_{slug}"] = item["weak_value"]
            out[f"judge_status_{slug}"] = item["judge_status"]
            out[f"label_evidence_{slug}"] = item["evidence"]
        rows.append(out)
    return pd.DataFrame(rows)


def summarize_label_coverage(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label in ALL_CHEXPERT_LABELS:
        slug = snake_label(label)
        status_col = f"weak_status_{slug}"
        if status_col not in df.columns:
            raw_col = label if label in df.columns else f"chexpert_value_{slug}"
            if raw_col not in df.columns:
                continue
            statuses = df[raw_col].map(chexpert_value_to_status)
        else:
            statuses = df[status_col].astype(str).str.lower()

        total = len(df)
        counts = statuses.value_counts()
        rows.append(
            {
                "label": label,
                "rows": total,
                "present": int(counts.get("present", 0)),
                "absent": int(counts.get("absent", 0)),
                "uncertain": int(counts.get("uncertain", 0)),
                "unmentioned": int(counts.get("unmentioned", 0)),
                "masked_training": int(counts.get("uncertain", 0) + counts.get("unmentioned", 0)),
            }
        )
    return pd.DataFrame(rows)


def load_judge_ground_truth(
    ground_truth_path: str | Path,
    labels_path: str | Path | None = None,
) -> pd.DataFrame:
    from medagentx.fusion.constants import DEFAULT_CHEXPERT_LABELS_CSV

    gt_df = pd.read_csv(ground_truth_path, dtype=str)
    if any(str(col).startswith("weak_status_") for col in gt_df.columns):
        return gt_df

    labels_path = Path(labels_path or DEFAULT_CHEXPERT_LABELS_CSV)
    if not labels_path.exists():
        return gt_df

    labels_df = pd.read_csv(labels_path, dtype=str)
    if any(str(col).startswith("weak_status_") for col in labels_df.columns):
        merged = labels_df.copy()
    else:
        merged = merge_chexpert_labels(gt_df, labels_df)
        merged = expand_label_columns(merged)

    if "study_key" not in merged.columns and "path_to_dcm" in merged.columns:
        from medagentx.fusion.paths import parse_study_key_from_dcm

        merged["study_key"] = merged["path_to_dcm"].map(parse_study_key_from_dcm)
    if "dicom_path" not in merged.columns and "path_to_dcm" in merged.columns:
        from medagentx.fusion.paths import clean_dicom_path

        merged["dicom_path"] = merged["path_to_dcm"].map(clean_dicom_path)

    return merged
