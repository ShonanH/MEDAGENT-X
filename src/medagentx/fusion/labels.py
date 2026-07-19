from __future__ import annotations

from typing import Any

import pandas as pd

from medagentx.agents.judge_agent import (
    LABEL_TERMS,
    NEGATION_CUES,
    UNCERTAINTY_CUES,
    infer_label_from_text,
    normalize_report_sentence,
    split_sentences,
    sentence_has_cue,
)
from medagentx.fusion.constants import DISEASE_LABELS, LABEL_VALUE_ABSENT, LABEL_VALUE_PRESENT


def clean_string(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def build_report_text_for_weak_labels(row: pd.Series) -> tuple[str, str]:
    findings = clean_string(row.get("section_findings"))
    impression = clean_string(row.get("section_impression"))
    summary = clean_string(row.get("section_summary"))

    parts = [part for part in [findings, impression, summary] if part]
    if parts:
        return "\n".join(parts), "section_findings_plus_impression_plus_summary"

    report = clean_string(row.get("report"))
    if report:
        return report, "report_fallback"

    section_cols = [col for col in row.index if str(col).startswith("section_")]
    report = "\n".join(clean_string(row.get(col)) for col in section_cols if clean_string(row.get(col)))
    return report, "section_columns_fallback"


def infer_weak_label_status(text: str, label: str) -> str:
    """
    Returns one of: present, absent, uncertain, unmentioned
    """
    positive_examples = []
    negative_examples = []
    uncertain_examples = []
    mentioned = False

    for sentence in split_sentences(text):
        sentence_norm = normalize_report_sentence(sentence)

        for term in LABEL_TERMS.get(label, []):
            term_norm = normalize_report_sentence(term)
            if term_norm not in sentence_norm:
                continue

            mentioned = True
            has_negation = sentence_has_cue(sentence, term, NEGATION_CUES)
            has_uncertainty = sentence_has_cue(sentence, term, UNCERTAINTY_CUES)

            if has_negation:
                negative_examples.append(sentence[:260])
            elif has_uncertainty:
                uncertain_examples.append(sentence[:260])
            else:
                positive_examples.append(sentence[:260])

    if positive_examples:
        return "present"
    if uncertain_examples:
        return "uncertain"
    if negative_examples:
        return "absent"
    if mentioned:
        return "uncertain"
    return "unmentioned"


def weak_label_to_training_value(status: str) -> float | None:
    if status == "present":
        return LABEL_VALUE_PRESENT
    if status == "absent":
        return LABEL_VALUE_ABSENT
    return None  # uncertain / unmentioned -> mask out


def infer_study_weak_labels(report_text: str) -> dict[str, dict[str, Any]]:
    output = {}

    for label in DISEASE_LABELS:
        status = infer_weak_label_status(report_text, label)
        judge_item = infer_label_from_text(report_text, label)

        output[label] = {
            "weak_status": status,
            "weak_value": weak_label_to_training_value(status),
            "judge_status": judge_item["status"],
            "evidence": judge_item.get("evidence", ""),
        }

    return output


def derive_no_finding_status(disease_statuses: dict[str, str]) -> str:
    if any(status == "present" for status in disease_statuses.values()):
        return "absent"
    if any(status == "uncertain" for status in disease_statuses.values()):
        return "uncertain"
    return "present"