from __future__ import annotations

from medagentx.paths import CHEXPERT_OUTPUT_DIR, DATA_DIR, FUSION_OUTPUT_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR, SRC_ROOT, VECTOR_DB_DIR

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from medagentx.fusion.calibration import (
    LUNG_OPACITY_MAX_FUSION_GAP,
    LUNG_OPACITY_MIN_ENSEMBLE,
    MODERATE_RECALL_LABELS,
    RECALL_LENIENT_LABELS,
    STRICT_PRESENT_LABELS,
)
DEFAULT_CLASSIFIER_PREDICTIONS_PATH = (
    str(FUSION_OUTPUT_DIR / "ensemble_classifier_predictions.csv")
)
DEFAULT_OUTPUT_PATH = str(CHEXPERT_OUTPUT_DIR / "disease_reasoning_results.csv")
DEFAULT_REPORT_PATH = str(CHEXPERT_OUTPUT_DIR / "report.md")
PROMPT_VERSION = "disease_reasoning_v3_fact_grounded_report_writer"

BORDERLINE_PRESENT_LOW = 0.50
MODERATE_PRESENT_LOW = 0.60
STRONG_PRESENT_LOW = 0.75
UNCERTAIN_LOW = 0.20


CHEXPERT_LABELS = [
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
    "Pneumonia",
    "Pneumothorax",
    "Fracture",
    "Lung Lesion",
    "Lung Opacity",
    "Enlarged Cardiomediastinum",
    "Pleural Other",
    "Support Devices",
    "No Finding",
]

BROAD_OR_NOISY_PRESENT_LABELS = {
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Lung Opacity",
    "Enlarged Cardiomediastinum",
}


LABEL_TERMS = {
    "Atelectasis": ["atelectasis", "volume loss"],
    "Cardiomegaly": ["cardiomegaly", "enlarged cardiac silhouette", "cardiac silhouette is enlarged"],
    "Consolidation": ["consolidation", "focal airspace opacity"],
    "Edema": ["pulmonary edema", "interstitial edema", "edema", "vascular congestion", "pulmonary venous hypertension"],
    "Pleural Effusion": ["pleural effusion", "effusion"],
    "Pneumonia": ["pneumonia", "infectious infiltrate"],
    "Pneumothorax": ["pneumothorax"],
    "Fracture": ["fracture"],
    "Lung Lesion": ["lung lesion", "nodule", "mass"],
    "Lung Opacity": ["lung opacity", "opacity", "airspace opacity", "infiltrate"],
    "Enlarged Cardiomediastinum": ["enlarged cardiomediastinum", "widened mediastinum"],
    "Pleural Other": ["pleural thickening", "pleural abnormality"],
    "Support Devices": ["catheter", "central venous catheter", "line", "tube", "pacemaker", "support device"],
}

NEGATION_TERMS = [
    "no ",
    "without ",
    "no evidence of ",
    "negative for ",
    "absent ",
    "clear of ",
    "free of ",
]

PLACEHOLDER_PHRASES = [
    "briefly explain",
    "list conflicts",
    "list unavailable",
    "using only controlled facts",
    "write a concise",
    "write a short",
]

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "predicted_findings_section": {"type": "string"},
        "predicted_impression_section": {"type": "string"},
        "evidence_summary": {"type": "string"},
        "conflicting_evidence": {
            "type": "array",
            "items": {"type": "string"},
        },
        "limitations": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "predicted_findings_section",
        "predicted_impression_section",
        "evidence_summary",
        "conflicting_evidence",
        "limitations",
    ],
}


SYSTEM_PROMPT = """
You are the Disease Reasoning Agent in MEDAGENT-X.

You write a predicted chest X-ray report from controlled factual evidence.

You are given:
1. Controlled disease facts computed from classifier probabilities and retrieval evidence.
2. Image classifier probabilities.
3. Retrieved similar-case reports.
4. Quality and metric evidence.

Rules:
- Do not invent diseases.
- Do not change controlled disease statuses.
- The controlled disease facts are binding.
- Use metrics, classifier evidence, and retrieval evidence to explain the report.
- Retrieved reports are similar-case context, not ground truth for the current case.
- Mention only findings marked present in controlled disease facts.
- You may mention absent findings only in negated form, such as "No pneumothorax."
- If a finding is uncertain, describe it as uncertain only if clinically useful.
- Do not say lungs are clear if edema, opacity, pneumonia, consolidation, atelectasis, or pleural effusion is present.
- Return only valid JSON matching the requested schema.
"""

def markdown_escape(value: Any) -> str:
    text = clean_string(value)
    return text.replace("|", "\\|")


def format_metric_value(value: Any) -> str:
    value = clean_value(value)

    if value is None:
        return ""

    if isinstance(value, float):
        return f"{value:.4f}"

    return clean_string(value)


def build_metric_table(metrics: dict[str, Any], max_rows: int = 40) -> str:
    if not metrics:
        return "_No current-case metrics available._"

    rows = []
    for key, value in sorted(metrics.items())[:max_rows]:
        rows.append(f"| `{markdown_escape(key)}` | {markdown_escape(format_metric_value(value))} |")

    table = [
        "| Metric | Value |",
        "|---|---:|",
        *rows,
    ]

    if len(metrics) > max_rows:
        table.append(f"\n_Showing {max_rows} of {len(metrics)} metrics._")

    return "\n".join(table)


def build_prediction_table(predictions: list[dict[str, Any]]) -> str:
    rows = []

    for item in predictions:
        rows.append(
            "| {label} | {status} | {confidence:.2f} | {evidence_type} | {evidence} |".format(
                label=markdown_escape(item.get("label")),
                status=markdown_escape(item.get("status")),
                confidence=normalize_confidence(item.get("confidence")),
                evidence_type=markdown_escape(item.get("evidence_type")),
                evidence=markdown_escape(item.get("evidence")),
            )
        )

    return "\n".join(
        [
            "| Disease | Status | Confidence | Evidence Type | Explanation |",
            "|---|---|---:|---|---|",
            *rows,
        ]
    )


def build_classifier_table(classifier_evidence: dict[str, Any]) -> str:
    labels = classifier_evidence.get("labels", [])

    if not labels:
        return "_No classifier evidence available._"

    rows = []
    for item in labels:
        probability = item.get("probability")
        probability_text = "" if probability is None else f"{normalize_confidence(probability):.4f}"

        rows.append(
            "| {label} | {status} | {probability} | {source_label} |".format(
                label=markdown_escape(item.get("label")),
                status=markdown_escape(item.get("status")),
                probability=probability_text,
                source_label=markdown_escape(item.get("source_label")),
            )
        )

    return "\n".join(
        [
            "| Classifier Label | Status | Probability | Source Label |",
            "|---|---|---:|---|",
            *rows,
        ]
    )


def build_retrieval_summary(retrieved_cases: list[dict[str, Any]], max_cases: int = 5) -> str:
    if not retrieved_cases:
        return "_No retrieved cases available._"

    sections = []

    for case in retrieved_cases[:max_cases]:
        document = truncate_text(case.get("retrieved_document"), 700)

        sections.append(
            "\n".join(
                [
                    f"### Retrieved Case Rank {case.get('rank')}",
                    "",
                    f"- Study key: `{clean_string(case.get('retrieved_study_key'))}`",
                    f"- DICOM path: `{clean_string(case.get('retrieved_dicom_path'))}`",
                    f"- Similarity score: `{format_metric_value(case.get('similarity_score') or case.get('retrieval_score') or case.get('retrieval_distance'))}`",
                    "",
                    "**Retrieved Document Excerpt**",
                    "",
                    f"> {document.replace(chr(10), ' ')}",
                ]
            )
        )

    return "\n\n".join(sections)


def build_case_markdown_section(
    evidence_packet: dict[str, Any],
    predictions: list[dict[str, Any]],
    primary_findings: list[str],
    predicted_findings_section: str,
    predicted_impression_section: str,
    evidence_summary: str,
    conflicting_evidence: list[str],
    limitations: list[str],
    consistency_warnings: list[str],
) -> str:
    case_identity = evidence_packet["case_identity"]
    classifier_evidence = evidence_packet["image_classifier_evidence"]
    current_metrics = evidence_packet["current_case_metrics"]
    retrieved_cases = evidence_packet["retrieved_cases"]

    present_predictions = [
        item for item in predictions if item.get("status") == "present"
    ]

    uncertain_predictions = [
        item for item in predictions if item.get("status") == "uncertain"
    ]

    absent_predictions = [
        item for item in predictions if item.get("status") == "absent"
    ]

    unavailable_predictions = [
        item for item in predictions if item.get("status") == "unavailable"
    ]

    primary_text = ", ".join(primary_findings) if primary_findings else "None"

    present_text = "\n".join(
        f"- **{item['label']}**: confidence `{normalize_confidence(item.get('confidence')):.2f}`. {clean_string(item.get('evidence'))}"
        for item in present_predictions
    ) or "- None"

    uncertain_text = "\n".join(
        f"- **{item['label']}**: confidence `{normalize_confidence(item.get('confidence')):.2f}`. {clean_string(item.get('evidence'))}"
        for item in uncertain_predictions
    ) or "- None"

    absent_text = ", ".join(item["label"] for item in absent_predictions) or "None"
    unavailable_text = ", ".join(item["label"] for item in unavailable_predictions) or "None"

    conflict_text = "\n".join(f"- {item}" for item in conflicting_evidence) or "- None"
    limitation_text = "\n".join(f"- {item}" for item in limitations) or "- None"
    warning_text = "\n".join(f"- {item}" for item in consistency_warnings) or "- None"

    return "\n".join(
        [
            f"# MEDAGENT-X Disease Reasoning Report",
            "",
            "## Case",
            "",
            f"- Study key: `{clean_string(case_identity.get('study_key'))}`",
            f"- DICOM path: `{clean_string(case_identity.get('dicom_path'))}`",
            f"- Age: `{format_metric_value(case_identity.get('age'))}`",
            f"- Sex: `{clean_string(case_identity.get('sex'))}`",
            f"- Race: `{clean_string(case_identity.get('race'))}`",
            f"- Ethnicity: `{clean_string(case_identity.get('ethnicity'))}`",
            "",
            "## Predicted Diseases",
            "",
            f"Primary predicted findings: **{primary_text}**",
            "",
            present_text,
            "",
            "## Predicted Report",
            "",
            "### Findings",
            "",
            predicted_findings_section,
            "",
            "### Impression",
            "",
            predicted_impression_section,
            "",
            "## Evidence Summary",
            "",
            evidence_summary,
            "",
            "## Uncertain Findings",
            "",
            uncertain_text,
            "",
            "## Absent Findings",
            "",
            absent_text,
            "",
            "## Unavailable Findings",
            "",
            unavailable_text,
            "",
            "## Disease Prediction Table",
            "",
            build_prediction_table(predictions),
            "",
            "## Image Classifier Evidence",
            "",
            f"- Model: `{clean_string(classifier_evidence.get('classifier_model'))}`",
            f"- Weights: `{clean_string(classifier_evidence.get('classifier_weights'))}`",
            "",
            build_classifier_table(classifier_evidence),
            "",
            "## Current Case Metrics",
            "",
            build_metric_table(current_metrics),
            "",
            "## Retrieved Cases",
            "",
            build_retrieval_summary(retrieved_cases),
            "",
            "## Conflicts",
            "",
            conflict_text,
            "",
            "## Limitations",
            "",
            limitation_text,
            "",
            "## Consistency Warnings",
            "",
            warning_text,
            "",
        ]
    )


def write_markdown_report(
    report_output_path: str,
    markdown_sections: list[str],
) -> None:
    report_path = Path(report_output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report_text = "\n\n---\n\n".join(markdown_sections).strip() + "\n"
    report_path.write_text(report_text, encoding="utf-8")

    
def is_placeholder_text(value: Any) -> bool:
    text = clean_string(value).lower()
    if not text:
        return True
    return any(phrase in text for phrase in PLACEHOLDER_PHRASES)


def get_prediction_by_label(
    predictions: list[dict[str, Any]],
    label: str,
) -> dict[str, Any] | None:
    for item in predictions:
        if item.get("label") == label:
            return item
    return None


def build_deterministic_evidence_summary(
    predictions: list[dict[str, Any]],
) -> str:
    present = [
        item
        for item in predictions
        if item.get("status") == "present"
    ]

    uncertain = [
        item
        for item in predictions
        if item.get("status") == "uncertain"
    ]

    absent_important = [
        item
        for item in predictions
        if item.get("label") in {"Pleural Effusion", "Pneumothorax"}
        and item.get("status") == "absent"
    ]

    parts = []

    if present:
        present_text = ", ".join(
            f"{item['label']} (confidence {item['confidence']:.2f})"
            for item in present
        )
        parts.append(f"Controlled evidence supports: {present_text}.")
    else:
        parts.append("Controlled evidence does not support any confidently present finding.")

    if absent_important:
        absent_text = ", ".join(
            f"{item['label']} (confidence {item['confidence']:.2f})"
            for item in absent_important
        )
        parts.append(f"Important excluded findings: {absent_text}.")

    borderline = [
        item
        for item in uncertain
        if item.get("label") in {
            "Cardiomegaly",
            "Enlarged Cardiomediastinum",
            "Atelectasis",
            "Lung Opacity",
        }
    ]

    if borderline:
        borderline_text = ", ".join(
            f"{item['label']} (confidence {item['confidence']:.2f})"
            for item in borderline
        )
        parts.append(f"Borderline or uncertain findings: {borderline_text}.")

    return " ".join(parts)


def build_deterministic_conflicts(
    predictions: list[dict[str, Any]],
) -> list[str]:
    conflicts = []

    for item in predictions:
        label = item.get("label")
        status = item.get("status")
        evidence = clean_string(item.get("evidence")).lower()

        if status == "uncertain":
            conflicts.append(
                f"{label}: controlled evidence is uncertain. {item.get('evidence')}"
            )

        if "borderline classifier probability" in evidence:
            conflicts.append(
                f"{label}: classifier probability is borderline, so this finding was not treated as strongly present."
            )

        if "retrieval positive mentions=" in evidence and "negative mentions=" in evidence:
            if "positive mentions=0" not in evidence and "negative mentions=0" not in evidence:
                conflicts.append(
                    f"{label}: retrieval evidence contains mixed positive and negative context."
                )

    return sorted(set(conflicts))


def build_deterministic_limitations(
    predictions: list[dict[str, Any]],
) -> list[str]:
    limitations = []

    unavailable = [
        item["label"]
        for item in predictions
        if item.get("status") == "unavailable"
    ]

    uncertain = [
        item["label"]
        for item in predictions
        if item.get("status") == "uncertain"
    ]

    if unavailable:
        limitations.append(
            "Classifier output was unavailable for: " + ", ".join(unavailable) + "."
        )

    if uncertain:
        limitations.append(
            "The following findings remained uncertain after combining classifier and retrieval evidence: "
            + ", ".join(uncertain)
            + "."
        )

    limitations.append(
        "Retrieved reports are similar-case context only and are not treated as ground truth for the current case."
    )

    return limitations


def validate_or_replace_explanations(
    llm_result: dict[str, Any],
    predictions: list[dict[str, Any]],
) -> tuple[str, list[str], list[str], list[str]]:
    warnings = []

    evidence_summary = clean_string(llm_result.get("evidence_summary"))
    if is_placeholder_text(evidence_summary):
        evidence_summary = build_deterministic_evidence_summary(predictions)
        warnings.append("LLM evidence_summary replaced with deterministic explanation.")

    conflicts = llm_result.get("conflicting_evidence", [])
    if not isinstance(conflicts, list):
        conflicts = []

    conflicts = [
        clean_string(item)
        for item in conflicts
        if not is_placeholder_text(item)
    ]

    if not conflicts:
        conflicts = build_deterministic_conflicts(predictions)
        warnings.append("LLM conflicting_evidence replaced with deterministic conflicts.")

    limitations = llm_result.get("limitations", [])
    if not isinstance(limitations, list):
        limitations = []

    limitations = [
        clean_string(item)
        for item in limitations
        if not is_placeholder_text(item)
    ]

    if not limitations:
        limitations = build_deterministic_limitations(predictions)
        warnings.append("LLM limitations replaced with deterministic limitations.")

    return evidence_summary, conflicts, limitations, warnings


def clean_value(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, np.generic):
        value = value.item()

    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    return value


def to_jsonable(value: Any) -> Any:
    value = clean_value(value)

    if value is None:
        return None

    if isinstance(value, dict):
        return {str(to_jsonable(k)): to_jsonable(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    if isinstance(value, np.bool_):
        return bool(value)

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None

    return value


def clean_string(value: Any) -> str:
    value = clean_value(value)
    if value is None:
        return ""
    return str(value).strip()


def truncate_text(text: Any, max_chars: int = 1800) -> str:
    text = clean_string(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + " ...[truncated]"


def first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def slugify_label(label: str) -> str:
    return label.lower().replace(" ", "_").replace("-", "_")


def safe_json_loads(value: Any, default: Any) -> Any:
    value = clean_value(value)
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def paths_match(a: Any, b: Any) -> bool:
    a = clean_string(a)
    b = clean_string(b)
    if not a or not b:
        return False
    return a == b or a.endswith(b) or b.endswith(a)


def normalize_label(value: Any) -> str:
    value = clean_string(value)
    for label in CHEXPERT_LABELS:
        if value.lower() == label.lower():
            return label
    return value


def normalize_status(value: Any) -> str:
    value = clean_string(value).lower()
    if value in {"present", "positive", "yes"}:
        return "present"
    if value in {"absent", "negative", "no"}:
        return "absent"
    if value in {"uncertain", "equivocal", "possible"}:
        return "uncertain"
    if value in {"unavailable", "not_available", "not computed", "not_computed"}:
        return "unavailable"
    return "uncertain"


def normalize_confidence(value: Any) -> float:
    value = clean_value(value)
    try:
        score = float(value)
    except Exception:
        return 0.0
    if math.isnan(score) or math.isinf(score):
        return 0.0
    return max(0.0, min(1.0, score))


def split_sentences(text: str) -> list[str]:
    text = clean_string(text).lower()
    pieces = re.split(r"[\n.;:]+", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def sentence_has_negation(sentence: str, term: str) -> bool:
    index = sentence.find(term)
    if index < 0:
        return False

    prefix = sentence[max(0, index - 70):index]
    return any(neg in prefix for neg in NEGATION_TERMS)


def contains_unnegated_label(text: str, label: str) -> bool:
    for sentence in split_sentences(text):
        for term in LABEL_TERMS.get(label, []):
            if term in sentence and not sentence_has_negation(sentence, term):
                return True
    return False


def compact_row_values(
    row: pd.Series,
    include_prefixes: tuple[str, ...],
    exclude_exact: set[str] | None = None,
    exclude_contains: tuple[str, ...] = (),
) -> dict[str, Any]:
    exclude_exact = exclude_exact or set()
    values: dict[str, Any] = {}

    for col in row.index:
        if not col.startswith(include_prefixes):
            continue
        if col in exclude_exact:
            continue
        if any(token in col for token in exclude_contains):
            continue

        value = clean_value(row[col])
        if value is None:
            continue

        if isinstance(value, str):
            value = truncate_text(value, 600)

        values[col] = value

    return values


def count_retrieval_mentions(retrieved_cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    counts = {}

    for label in CHEXPERT_LABELS:
        counts[label] = {
            "positive_count": 0,
            "negative_count": 0,
            "example_positive": "",
            "example_negative": "",
        }

    for case in retrieved_cases:
        document = clean_string(case.get("retrieved_document"))

        for label, terms in LABEL_TERMS.items():
            for sentence in split_sentences(document):
                matched_terms = [term for term in terms if term in sentence]
                if not matched_terms:
                    continue

                is_negative = any(sentence_has_negation(sentence, term) for term in matched_terms)

                if is_negative:
                    counts[label]["negative_count"] += 1
                    if not counts[label]["example_negative"]:
                        counts[label]["example_negative"] = sentence[:260]
                else:
                    counts[label]["positive_count"] += 1
                    if not counts[label]["example_positive"]:
                        counts[label]["example_positive"] = sentence[:260]

    return counts


def classifier_label_map(classifier_evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    output = {}

    for item in classifier_evidence.get("labels", []):
        label = normalize_label(item.get("label"))
        if label in CHEXPERT_LABELS:
            output[label] = item

    return output


def is_fusion_only_classifier(classifier_item: dict[str, Any]) -> bool:
    """True when disease reasoning is driven by fusion predictions, not ensemble."""
    source = clean_string(classifier_item.get("source_label")).lower()
    if source == "fusion":
        return True

    agreement = clean_string(classifier_item.get("ensemble_agreement"))
    if agreement:
        return False

    return (
        classifier_item.get("densenet_probability") is None
        and classifier_item.get("fusion_probability") is not None
    )


def refine_label_decision(
    label: str,
    status: str,
    classifier_item: dict[str, Any] | None,
    retrieval_counts: dict[str, Any],
) -> tuple[str, str | None]:
    if label == "No Finding" or classifier_item is None:
        return status, None

    probability = classifier_item.get("probability")
    agreement = clean_string(classifier_item.get("ensemble_agreement"))
    densenet_probability = classifier_item.get("densenet_probability")
    fusion_probability = classifier_item.get("fusion_probability")
    classifier_threshold = clean_value(classifier_item.get("threshold"))

    positive_count = int(retrieval_counts.get("positive_count", 0))
    negative_count = int(retrieval_counts.get("negative_count", 0))
    refinement_reason = None

    if label in STRICT_PRESENT_LABELS and status == "present":
        prob = normalize_confidence(probability)
        if (
            densenet_probability is not None
            and fusion_probability is not None
            and prob < LUNG_OPACITY_MIN_ENSEMBLE
        ):
            status = "uncertain"
            refinement_reason = "lung opacity demoted below strict ensemble gate"
        elif (
            densenet_probability is not None
            and fusion_probability is not None
            and float(fusion_probability) - float(densenet_probability) > LUNG_OPACITY_MAX_FUSION_GAP
        ):
            status = "uncertain"
            refinement_reason = "lung opacity demoted due to fusion inflation over DenseNet"

    fusion_only = is_fusion_only_classifier(classifier_item)

    if status == "absent" and fusion_only:
        if (
            label in RECALL_LENIENT_LABELS
            and positive_count >= 2
            and negative_count == 0
        ):
            status = "present"
            refinement_reason = (
                "fusion-only recall promotion: strong retrieval context overrides absent classifier"
            )
        elif (
            label in MODERATE_RECALL_LABELS
            and positive_count >= 2
            and negative_count == 0
        ):
            status = "uncertain"
            refinement_reason = (
                "fusion-only moderate promotion: retrieval context softens absent classifier"
            )

    if status == "uncertain" and classifier_threshold is not None and probability is not None:
        threshold = float(classifier_threshold)
        prob = normalize_confidence(probability)

        if label in RECALL_LENIENT_LABELS and agreement in {"weak_present", "strong_present"}:
            floor = 0.55 if label == "Edema" else threshold * 0.95
            if prob >= floor and negative_count <= positive_count:
                status = "present"
                refinement_reason = "recall-lenient promotion from weak ensemble agreement"

        elif (
            label in RECALL_LENIENT_LABELS
            and fusion_only
            and positive_count >= 2
            and negative_count == 0
        ):
            status = "present"
            refinement_reason = (
                "fusion-only recall promotion from retrieval with uncertain classifier"
            )

        elif label in MODERATE_RECALL_LABELS and agreement in {"weak_present", "strong_present"}:
            if prob >= threshold and negative_count == 0:
                status = "present"
                refinement_reason = "moderate-recall promotion with non-negative retrieval context"

        elif (
            label in MODERATE_RECALL_LABELS
            and fusion_only
            and positive_count >= 2
            and negative_count == 0
            and prob >= threshold
        ):
            status = "present"
            refinement_reason = (
                "fusion-only moderate promotion from retrieval with uncertain classifier"
            )

    if (
        status == "present"
        and label in BROAD_OR_NOISY_PRESENT_LABELS
        and negative_count > positive_count
    ):
        status = "uncertain"
        refinement_reason = "demoted broad label because retrieval negatives outweigh positives"

    return status, refinement_reason


def deterministic_label_decision(
    label: str,
    classifier_item: dict[str, Any] | None,
    retrieval_counts: dict[str, Any],
) -> dict[str, Any]:
    if label == "No Finding":
        return {
            "label": label,
            "status": "absent",
            "confidence": 0.95,
            "evidence": "No Finding is absent because disease-specific evidence is being evaluated.",
            "evidence_type": "combined",
        }

    if classifier_item is None:
        probability = None
        classifier_status = "unavailable"
        classifier_threshold = None
    else:
        probability = classifier_item.get("probability")
        classifier_status = normalize_status(classifier_item.get("status"))
        classifier_threshold = clean_value(classifier_item.get("threshold"))

    positive_count = int(retrieval_counts.get("positive_count", 0))
    negative_count = int(retrieval_counts.get("negative_count", 0))
    example_positive = clean_string(retrieval_counts.get("example_positive"))
    example_negative = clean_string(retrieval_counts.get("example_negative"))

    if classifier_status == "unavailable":
        if positive_count >= 2:
            status = "uncertain"
            confidence = 0.35
            reason = "classifier unavailable; retrieval mentions treated as contextual uncertainty only"
        else:
            status = "unavailable"
            confidence = 0.0
            reason = "classifier unavailable and retrieval context insufficient"
    elif classifier_status == "present":
        probability = normalize_confidence(probability)
        status = "present"
        confidence = min(0.95, probability if probability is not None else 0.85)
        reason = "calibrated classifier status=present"
    elif classifier_status == "absent":
        probability = normalize_confidence(probability)
        status = "absent"
        confidence = 0.85
        reason = "calibrated classifier status=absent"
    elif classifier_status == "uncertain":
        probability = normalize_confidence(probability)
        status = "uncertain"
        confidence = 0.45
        reason = "calibrated classifier status=uncertain"
    else:
        probability = normalize_confidence(probability)

        if probability is not None and classifier_threshold is not None:
            threshold = float(classifier_threshold)
            if probability >= threshold:
                status = "present"
                confidence = min(0.90, probability)
                reason = f"classifier probability above tuned threshold ({threshold:.2f})"
            elif probability <= UNCERTAIN_LOW:
                status = "absent"
                confidence = 0.85
                reason = "low classifier probability"
            else:
                status = "uncertain"
                confidence = 0.40
                reason = f"classifier probability below tuned threshold ({threshold:.2f})"
        elif probability >= STRONG_PRESENT_LOW:
            status = "present"
            confidence = min(0.95, probability)
            reason = "strong classifier probability"
        elif probability >= MODERATE_PRESENT_LOW:
            if label in BROAD_OR_NOISY_PRESENT_LABELS:
                status = "uncertain"
                confidence = 0.55
                reason = "moderate classifier probability for broad/noisy label; not promoted to present"
            else:
                status = "present"
                confidence = min(0.85, probability)
                reason = "moderate classifier probability"
        elif probability >= BORDERLINE_PRESENT_LOW:
            status = "uncertain"
            confidence = 0.45
            reason = "borderline classifier probability; retrieval mentions retained as context only"
        elif probability > UNCERTAIN_LOW:
            status = "uncertain"
            confidence = 0.35
            reason = "low-intermediate classifier probability"
        else:
            status = "absent"
            confidence = 0.85
            reason = "low classifier probability"

    classifier_item_for_refine = classifier_item or {}
    if classifier_item is not None:
        classifier_item_for_refine = dict(classifier_item)
    status, refinement_reason = refine_label_decision(
        label=label,
        status=status,
        classifier_item=classifier_item_for_refine if classifier_item is not None else None,
        retrieval_counts=retrieval_counts,
    )
    if refinement_reason:
        reason = refinement_reason
        if status == "present":
            confidence = max(confidence, 0.70)
        elif status == "uncertain":
            confidence = min(confidence, 0.50)

    evidence_parts = [
        f"Classifier status={classifier_status}.",
        f"Classifier probability={probability if probability is not None else 'unavailable'}.",
    ]
    if classifier_threshold is not None:
        evidence_parts.append(f"Classifier threshold={float(classifier_threshold):.3f}.")
    evidence_parts.extend(
        [
            f"Rule={reason}.",
            f"Retrieval positive mentions={positive_count}; negative mentions={negative_count}.",
        ]
    )

    if example_positive:
        evidence_parts.append(f"Example positive retrieval sentence: {example_positive}")
    if example_negative:
        evidence_parts.append(f"Example negative retrieval sentence: {example_negative}")

    return {
        "label": label,
        "status": status,
        "confidence": confidence,
        "evidence": " ".join(evidence_parts),
        "evidence_type": "combined",
    }
    

def build_deterministic_disease_evidence(evidence_packet: dict[str, Any]) -> list[dict[str, Any]]:
    classifier_items = classifier_label_map(evidence_packet["image_classifier_evidence"])
    retrieval_mentions = count_retrieval_mentions(evidence_packet["retrieved_cases"])

    predictions = []
    for label in CHEXPERT_LABELS:
        predictions.append(
            deterministic_label_decision(
                label=label,
                classifier_item=classifier_items.get(label),
                retrieval_counts=retrieval_mentions.get(label, {}),
            )
        )

    any_present = any(
        item["status"] == "present"
        for item in predictions
        if item["label"] != "No Finding"
    )

    if any_present:
        for item in predictions:
            if item["label"] == "No Finding":
                item["status"] = "absent"
                item["confidence"] = 0.95

    return predictions


def normalize_controlled_predictions(
    deterministic_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_label = {}

    for item in deterministic_evidence:
        label = normalize_label(item.get("label"))
        if label not in CHEXPERT_LABELS:
            continue

        by_label[label] = {
            "label": label,
            "status": normalize_status(item.get("status")),
            "confidence": normalize_confidence(item.get("confidence")),
            "evidence": clean_string(item.get("evidence")),
            "evidence_type": clean_string(item.get("evidence_type")) or "combined",
        }

    predictions = []
    for label in CHEXPERT_LABELS:
        predictions.append(
            by_label.get(
                label,
                {
                    "label": label,
                    "status": "uncertain",
                    "confidence": 0.0,
                    "evidence": "No controlled evidence was available for this label.",
                    "evidence_type": "insufficient",
                },
            )
        )

    return predictions


def primary_from_controlled_predictions(predictions: list[dict[str, Any]]) -> list[str]:
    return [
        item["label"]
        for item in predictions
        if item.get("status") == "present"
    ]


def report_text_has_fact_errors(
    findings_text: str,
    impression_text: str,
    predictions: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    report_text = f"{findings_text} {impression_text}"
    errors = []

    present_labels = {
        item["label"]
        for item in predictions
        if item.get("status") == "present"
    }

    for item in predictions:
        label = item["label"]
        status = item.get("status")

        if label == "No Finding":
            continue

        if status == "present":
            if not contains_unnegated_label(report_text, label):
                errors.append(f"Report omits present label: {label}")
        else:
            if contains_unnegated_label(report_text, label):
                errors.append(f"Report mentions non-present label: {label}")

    pulmonary_abnormalities = {
        "Edema",
        "Lung Opacity",
        "Pneumonia",
        "Consolidation",
        "Atelectasis",
        "Pleural Effusion",
    }

    if present_labels.intersection(pulmonary_abnormalities):
        lower_text = report_text.lower()
        clear_phrases = [
            "lungs are clear",
            "lungs appear clear",
            "lungs clear",
            "clear bilaterally",
        ]
        if any(phrase in lower_text for phrase in clear_phrases):
            errors.append("Report says lungs are clear despite pulmonary abnormality.")

    return len(errors) > 0, errors


def build_fallback_report(predictions: list[dict[str, Any]]) -> tuple[str, str]:
    present = [
        item["label"]
        for item in predictions
        if item.get("status") == "present"
    ]

    absent_important = [
        item["label"]
        for item in predictions
        if item["label"] in {"Pneumothorax", "Pleural Effusion"}
        and item.get("status") == "absent"
    ]

    if present:
        findings = "Predicted findings include " + ", ".join(present).lower() + "."
    else:
        findings = "No confidently present abnormality is predicted from the available evidence."

    if absent_important:
        findings += " No predicted " + " or ".join(absent_important).lower() + "."

    if present:
        impression_lines = [
            f"{index}. {label}."
            for index, label in enumerate(present, start=1)
        ]
    else:
        impression_lines = ["1. No confident acute cardiopulmonary abnormality predicted."]

    return findings, " ".join(impression_lines)


def validate_or_replace_report(
    llm_result: dict[str, Any],
    predictions: list[dict[str, Any]],
) -> tuple[str, str, list[str]]:
    findings = clean_string(llm_result.get("predicted_findings_section"))
    impression = clean_string(llm_result.get("predicted_impression_section"))

    has_errors, errors = report_text_has_fact_errors(
        findings_text=findings,
        impression_text=impression,
        predictions=predictions,
    )

    if not findings or not impression or has_errors:
        fallback_findings, fallback_impression = build_fallback_report(predictions)
        errors.append("LLM report text replaced with deterministic fallback report.")
        return fallback_findings, fallback_impression, errors

    return findings, impression, []


def extract_classifier_evidence(classifier_row: pd.Series | None) -> dict[str, Any]:
    if classifier_row is None:
        return {
            "available": False,
            "reason": "No matching image classifier row found.",
            "labels": [],
            "raw_predictions_top": [],
        }

    labels = []
    for label in CHEXPERT_LABELS:
        slug = slugify_label(label)
        prob_col = f"classifier_prob_{slug}"
        status_col = f"classifier_status_{slug}"
        source_col = f"classifier_source_label_{slug}"
        threshold_col = f"classifier_threshold_{slug}"
        densenet_prob_col = f"densenet_prob_{slug}"
        fusion_prob_col = f"fusion_prob_{slug}"
        ensemble_prob_col = f"ensemble_prob_{slug}"
        agreement_col = f"ensemble_agreement_{slug}"

        probability = clean_value(classifier_row.get(prob_col))
        if probability is None:
            probability = clean_value(classifier_row.get(ensemble_prob_col))
        status = clean_value(classifier_row.get(status_col))
        if status is None:
            status = clean_value(classifier_row.get(f"ensemble_status_{slug}"))
        source = clean_value(classifier_row.get(source_col))
        threshold = clean_value(classifier_row.get(threshold_col))
        if threshold is None:
            threshold = clean_value(classifier_row.get(f"ensemble_threshold_{slug}"))

        if probability is not None:
            probability = normalize_confidence(probability)

        labels.append(
            {
                "label": label,
                "probability": probability,
                "status": normalize_status(status),
                "source_label": clean_string(source) if source is not None else None,
                "threshold": normalize_confidence(threshold) if threshold is not None else None,
                "densenet_probability": normalize_confidence(classifier_row.get(densenet_prob_col))
                if clean_value(classifier_row.get(densenet_prob_col)) is not None
                else None,
                "fusion_probability": normalize_confidence(classifier_row.get(fusion_prob_col))
                if clean_value(classifier_row.get(fusion_prob_col)) is not None
                else None,
                "ensemble_agreement": clean_string(classifier_row.get(agreement_col)),
            }
        )

    raw_predictions = safe_json_loads(
        classifier_row.get("classifier_raw_predictions_json"),
        default={},
    )

    raw_predictions_top = []
    if isinstance(raw_predictions, dict):
        raw_predictions_top = [
            {"label": str(k), "probability": normalize_confidence(v)}
            for k, v in sorted(
                raw_predictions.items(),
                key=lambda item: normalize_confidence(item[1]),
                reverse=True,
            )[:12]
        ]

    return {
        "available": True,
        "classifier_model": clean_string(classifier_row.get("classifier_model")),
        "classifier_weights": clean_string(classifier_row.get("classifier_weights")),
        "present_threshold": clean_value(classifier_row.get("present_threshold")),
        "absent_threshold": clean_value(classifier_row.get("absent_threshold")),
        "labels": labels,
        "raw_predictions_top": raw_predictions_top,
    }


def find_classifier_row(
    classifier_df: pd.DataFrame,
    study_key: str,
    dicom_path: str,
) -> pd.Series | None:
    if classifier_df.empty:
        return None

    study_col = first_existing_column(classifier_df, ["study_key", "query_study_key"])
    dicom_col = first_existing_column(classifier_df, ["dicom_path", "query_dicom_path"])

    if study_col and dicom_col:
        exact = classifier_df[
            (classifier_df[study_col].astype(str) == str(study_key))
            & (classifier_df[dicom_col].astype(str) == str(dicom_path))
        ]
        if not exact.empty:
            return exact.iloc[0]

        same_study = classifier_df[classifier_df[study_col].astype(str) == str(study_key)]
        for _, row in same_study.iterrows():
            if paths_match(row.get(dicom_col), dicom_path):
                return row

    if dicom_col:
        for _, row in classifier_df.iterrows():
            if paths_match(row.get(dicom_col), dicom_path):
                return row

    if study_col:
        same_study = classifier_df[classifier_df[study_col].astype(str) == str(study_key)]
        if not same_study.empty:
            return same_study.iloc[0]

    return None


def build_retrieved_cases(group: pd.DataFrame, top_k: int) -> list[dict[str, Any]]:
    cases = []

    for rank, (_, row) in enumerate(group.head(top_k).iterrows(), start=1):
        retrieved_metrics = compact_row_values(
            row,
            include_prefixes=("retrieved_",),
            exclude_exact={
                "retrieved_document",
                "retrieved_patient_id",
                "retrieved_study_key",
                "retrieved_dicom_path",
                "retrieved_image_path",
            },
            exclude_contains=("document", "report"),
        )

        cases.append(
            {
                "rank": rank,
                "retrieved_study_key": clean_string(row.get("retrieved_study_key")),
                "retrieved_dicom_path": clean_string(row.get("retrieved_dicom_path")),
                "retrieved_age": clean_value(row.get("retrieved_age")),
                "retrieved_sex": clean_string(row.get("retrieved_sex")),
                "retrieved_race": clean_string(row.get("retrieved_race")),
                "retrieved_ethnicity": clean_string(row.get("retrieved_ethnicity")),
                "retrieved_document": truncate_text(row.get("retrieved_document"), 2200),
                "retrieval_score": clean_value(row.get("retrieval_score")),
                "retrieval_distance": clean_value(row.get("retrieval_distance")),
                "similarity_score": clean_value(row.get("similarity_score")),
                "retrieved_metrics": retrieved_metrics,
            }
        )

    return cases


def build_evidence_packet(
    retrieval_group: pd.DataFrame,
    classifier_df: pd.DataFrame,
    top_k: int,
) -> dict[str, Any]:
    first_row = retrieval_group.iloc[0]

    study_key = clean_string(
        first_row.get("query_study_key")
        if "query_study_key" in first_row.index
        else first_row.get("study_key")
    )
    dicom_path = clean_string(
        first_row.get("query_dicom_path")
        if "query_dicom_path" in first_row.index
        else first_row.get("dicom_path")
    )

    current_metrics = compact_row_values(
        first_row,
        include_prefixes=("query_", "current_"),
        exclude_exact={
            "query_study_key",
            "query_dicom_path",
            "query_patient_id",
            "query_document",
            "query_age",
            "query_sex",
            "query_race",
            "query_ethnicity",
        },
        exclude_contains=("document", "report"),
    )

    classifier_row = find_classifier_row(classifier_df, study_key, dicom_path)
    classifier_evidence = extract_classifier_evidence(classifier_row)

    evidence_packet = {
        "case_identity": {
            "study_key": study_key,
            "dicom_path": dicom_path,
            "age": clean_value(first_row.get("query_age")),
            "sex": clean_string(first_row.get("query_sex")),
            "race": clean_string(first_row.get("query_race")),
            "ethnicity": clean_string(first_row.get("query_ethnicity")),
        },
        "current_case_metrics": current_metrics,
        "image_classifier_evidence": classifier_evidence,
        "retrieved_cases": build_retrieved_cases(retrieval_group, top_k=top_k),
    }

    evidence_packet["deterministic_disease_evidence"] = build_deterministic_disease_evidence(
        evidence_packet
    )

    return evidence_packet





def build_user_prompt(evidence_packet: dict[str, Any]) -> str:
    payload = {
        "task": "Write a fact-grounded predicted chest X-ray report.",
        "controlled_disease_facts": evidence_packet["deterministic_disease_evidence"],
        "supporting_evidence": {
            "case_identity": evidence_packet["case_identity"],
            "image_classifier_evidence": evidence_packet["image_classifier_evidence"],
            "retrieved_cases": evidence_packet["retrieved_cases"],
            "current_case_metrics": evidence_packet["current_case_metrics"],
        },
        "output_instructions": {
            "predicted_findings_section": "Write a concise findings paragraph using only controlled facts.",
            "predicted_impression_section": "Write a short numbered impression using only controlled present findings and important negated findings.",
            "evidence_summary": "Briefly explain how classifier probabilities, retrieval context, and metrics support the report.",
            "conflicting_evidence": "List conflicts or borderline evidence.",
            "limitations": "List unavailable classifier outputs, borderline probabilities, or quality limitations.",
        },
    }

    return json.dumps(to_jsonable(payload), indent=2, allow_nan=False)


def ollama_chat_json(
    model: str,
    evidence_packet: dict[str, Any],
    ollama_url: str,
    temperature: float,
    timeout_seconds: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "stream": False,
        "format": RESPONSE_SCHEMA,
        "options": {
            "temperature": temperature,
            "num_ctx": 8192,
        },
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.strip()},
            {"role": "user", "content": build_user_prompt(evidence_packet)},
        ],
    }

    response = requests.post(
        f"{ollama_url.rstrip('/')}/api/chat",
        json=payload,
        timeout=timeout_seconds,
    )

    if response.status_code == 404:
        raise RuntimeError(
            "Ollama model was not found.\n"
            f"Requested model: {model}\n"
            "Run `ollama list` to see installed models, or pull one first."
        )

    if not response.ok:
        raise RuntimeError(
            "Ollama reasoning request failed.\n"
            f"HTTP status: {response.status_code}\n"
            f"Response: {response.text}"
        )

    data = response.json()
    content = data.get("message", {}).get("content", "")

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise RuntimeError(f"Ollama returned non-JSON content:\n{content}")


def run_disease_reasoning_agent(
    retrieval_results_path: str,
    image_classifier_predictions_path: str,
    output_path: str = DEFAULT_OUTPUT_PATH,
    report_output_path: str | None = DEFAULT_REPORT_PATH,
    model: str = "llama3.1:8b",
    ollama_url: str = "http://localhost:11434",
    top_k: int = 5,
    temperature: float = 0.0,
    timeout_seconds: int = 180,
    verbose: bool = True,
) -> pd.DataFrame:
    retrieval_path = Path(retrieval_results_path)
    classifier_path = Path(image_classifier_predictions_path)
    output_path_obj = Path(output_path)

    if verbose:
        print("[Disease Reasoning Agent] Loading retrieval evidence...")
    retrieval_df = pd.read_csv(retrieval_path)

    if verbose:
        print("[Disease Reasoning Agent] Loading image classifier evidence...")
    classifier_df = pd.read_csv(classifier_path)

    study_col = first_existing_column(retrieval_df, ["query_study_key", "study_key"])
    dicom_col = first_existing_column(retrieval_df, ["query_dicom_path", "dicom_path"])

    if study_col is None or dicom_col is None:
        raise ValueError(
            "retrieval_results.csv must contain query_study_key/query_dicom_path "
            "or study_key/dicom_path columns."
        )

    rows = []
    markdown_sections = []

    grouped = retrieval_df.groupby([study_col, dicom_col], sort=False, dropna=False)
    total_cases = len(grouped)

    for case_index, ((study_key, dicom_path), group) in enumerate(grouped, start=1):
        if verbose:
            print(
                f"[Disease Reasoning Agent] Reasoning case {case_index}/{total_cases}: "
                f"{study_key} | {dicom_path}"
            )

        evidence_packet = build_evidence_packet(
            retrieval_group=group,
            classifier_df=classifier_df,
            top_k=top_k,
        )

        result = ollama_chat_json(
            model=model,
            evidence_packet=evidence_packet,
            ollama_url=ollama_url,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )

        predictions = normalize_controlled_predictions(
            evidence_packet["deterministic_disease_evidence"]
        )

        primary_findings = primary_from_controlled_predictions(predictions)

        (
            predicted_findings_section,
            predicted_impression_section,
            report_validation_warnings,
        ) = validate_or_replace_report(
            llm_result=result,
            predictions=predictions,
        )

        (
            evidence_summary,
            conflicting_evidence,
            limitations,
            explanation_validation_warnings,
        ) = validate_or_replace_explanations(
            llm_result=result,
            predictions=predictions,
        )

        consistency_warnings = (
            report_validation_warnings
            + explanation_validation_warnings
        )

        rows.append(
            {
                "study_key": evidence_packet["case_identity"]["study_key"],
                "dicom_path": evidence_packet["case_identity"]["dicom_path"],
                "primary_predicted_findings": json.dumps(primary_findings),
                "predicted_findings_section": predicted_findings_section,
                "predicted_impression_section": predicted_impression_section,
                "finding_predictions_json": json.dumps(predictions),
                "evidence_summary": evidence_summary,
                "conflicting_evidence_json": json.dumps(conflicting_evidence),
                "limitations_json": json.dumps(limitations),
                "classifier_evidence_json": json.dumps(
                    evidence_packet["image_classifier_evidence"]
                ),
                "retrieval_evidence_json": json.dumps(
                    evidence_packet["retrieved_cases"]
                ),
                "controlled_disease_evidence_json": json.dumps(predictions),
                "consistency_warnings_json": json.dumps(consistency_warnings),
                "prompt_version": PROMPT_VERSION,
                "ollama_model": model,
                "route_next": "judge_agent",
            }
        )

        markdown_sections.append(
            build_case_markdown_section(
                evidence_packet=evidence_packet,
                predictions=predictions,
                primary_findings=primary_findings,
                predicted_findings_section=predicted_findings_section,
                predicted_impression_section=predicted_impression_section,
                evidence_summary=evidence_summary,
                conflicting_evidence=conflicting_evidence,
                limitations=limitations,
                consistency_warnings=consistency_warnings,
            )
        )

    output_df = pd.DataFrame(rows)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_path_obj, index=False)
    if report_output_path:
        write_markdown_report(
            report_output_path=report_output_path,
            markdown_sections=markdown_sections,
        )

        if verbose:
            print(f"[Disease Reasoning Agent] Saved report: {report_output_path}")

    if verbose:
        print(f"[Disease Reasoning Agent] Saved: {output_path_obj}")

    return output_df


def disease_reasoning_node(state: dict[str, Any]) -> dict[str, Any]:
    retrieval_results_path = state.get(
        "retrieval_results_path",
        str(CHEXPERT_OUTPUT_DIR / "retrieval_results.csv"),
    )
    image_classifier_predictions_path = state.get(
        "image_classifier_predictions_path",
        DEFAULT_CLASSIFIER_PREDICTIONS_PATH,
    )
    output_path = state.get(
        "disease_reasoning_results_path",
        DEFAULT_OUTPUT_PATH,
    )

    output_df = run_disease_reasoning_agent(
        retrieval_results_path=retrieval_results_path,
        image_classifier_predictions_path=image_classifier_predictions_path,
        output_path=output_path,
        model=state.get("ollama_reasoning_model", "llama3.1:8b"),
        ollama_url=state.get("ollama_url", "http://localhost:11434"),
        top_k=int(state.get("retrieval_top_k", 5)),
        temperature=float(state.get("reasoning_temperature", 0.0)),
        timeout_seconds=int(state.get("ollama_timeout_seconds", 180)),
        verbose=bool(state.get("verbose", True)),
        report_output_path=state.get(
            "disease_reasoning_report_path",
            DEFAULT_REPORT_PATH,
        )
    )

    return {
        **state,
        "disease_reasoning_results_path": output_path,
        "disease_reasoning_case_count": len(output_df),
        "route_next": "judge_agent",
        "disease_reasoning_report_path": state.get(
            "disease_reasoning_report_path",
            DEFAULT_REPORT_PATH,
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MEDAGENT-X Disease Reasoning Agent."
    )
    parser.add_argument(
        "--retrieval-results",
        default=str(CHEXPERT_OUTPUT_DIR / "retrieval_results.csv"),
    )
    parser.add_argument(
        "--image-classifier-predictions",
        default=DEFAULT_CLASSIFIER_PREDICTIONS_PATH,
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
    )
    parser.add_argument(
        "--model",
        default="llama3.1:8b",
        help="Installed Ollama reasoning model.",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
    )
    parser.add_argument(
        "--report-output",
        default=DEFAULT_REPORT_PATH,
        help="Path to write human-readable Markdown disease reasoning report.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    run_disease_reasoning_agent(
        retrieval_results_path=args.retrieval_results,
        image_classifier_predictions_path=args.image_classifier_predictions,
        output_path=args.output,
        report_output_path=args.report_output,
        model=args.model,
        ollama_url=args.ollama_url,
        top_k=args.top_k,
        temperature=args.temperature,
        timeout_seconds=args.timeout_seconds,
        verbose=True,
    )