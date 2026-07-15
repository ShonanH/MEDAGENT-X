from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


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

CRITICAL_DISEASE_LABELS = {
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
    "Pneumonia",
    "Pneumothorax",
    "Lung Lesion",
    "Lung Opacity",
    "Enlarged Cardiomediastinum",
}

NON_DISEASE_LABELS = {"Support Devices", "No Finding"}

DEFAULT_DISEASE_REASONING_PATH = "outputs/chexpert_plus/disease_reasoning_results.csv"
DEFAULT_GROUND_TRUTH_PATH = "outputs/chexpert_plus/retrieval_case_manifest.csv"
DEFAULT_OUTPUT_PATH = "outputs/chexpert_plus/judge_results.csv"
DEFAULT_REPORT_PATH = "outputs/chexpert_plus/judge_report.md"

PROMPT_VERSION = "judge_agent_v1_deterministic_report_label_eval"

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

NEGATION_CUES = [
    "no ",
    "without ",
    "no evidence of ",
    "negative for ",
    "absent ",
    "free of ",
    "clear of ",
]

UNCERTAINTY_CUES = [
    "possible",
    "possibly",
    "probable",
    "probably",
    "may represent",
    "could represent",
    "suggesting",
    "suggestive",
    "likely",
    "questionable",
]


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


def clean_string(value: Any) -> str:
    value = clean_value(value)
    if value is None:
        return ""
    return str(value).strip()


def truncate_text(value: Any, max_chars: int = 1800) -> str:
    text = clean_string(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + " ...[truncated]"


def normalize_label(value: Any) -> str:
    value = clean_string(value)
    for label in CHEXPERT_LABELS:
        if value.lower() == label.lower():
            return label
    return value


def normalize_status(value: Any) -> str:
    value = clean_string(value).lower()
    if value in {"present", "positive", "yes", "1"}:
        return "present"
    if value in {"absent", "negative", "no", "0"}:
        return "absent"
    if value in {"uncertain", "equivocal", "possible", "-1"}:
        return "uncertain"
    if value in {"unavailable", "not_available", "not computed", "not_computed"}:
        return "unavailable"
    return "uncertain"


def parse_json_cell(value: Any, default: Any) -> Any:
    value = clean_value(value)
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def split_sentences(text: str) -> list[str]:
    text = clean_string(text).lower()
    pieces = re.split(r"[\n.;:]+", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def sentence_has_cue(sentence: str, term: str, cues: list[str], window: int = 80) -> bool:
    index = sentence.find(term)
    if index < 0:
        return False
    prefix = sentence[max(0, index - window):index]
    return any(cue in prefix for cue in cues)


def derive_study_key_from_path(path: Any) -> str:
    path = clean_string(path)
    match = re.search(r"(patient\d+/study\d+)", path)
    if match:
        return match.group(1)
    return ""


def paths_match(a: Any, b: Any) -> bool:
    a = clean_string(a)
    b = clean_string(b)
    if not a or not b:
        return False
    return a == b or a.endswith(b) or b.endswith(a)


def first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def extract_report_text(row: pd.Series) -> dict[str, str]:
    findings = clean_string(row.get("section_findings"))
    impression = clean_string(row.get("section_impression"))

    if not findings and not impression:
        findings = clean_string(row.get("findings"))
        impression = clean_string(row.get("impression"))

    report = clean_string(row.get("report"))
    if not report:
        report = clean_string(row.get("document"))
    if not report:
        report = clean_string(row.get("retrieved_document"))

    if not report:
        section_cols = [col for col in row.index if str(col).startswith("section_")]
        report = "\n".join(clean_string(row.get(col)) for col in section_cols if clean_string(row.get(col)))

    combined = "\n".join(part for part in [findings, impression, report] if part)

    return {
        "section_findings": findings,
        "section_impression": impression,
        "report_text": report,
        "combined_text": combined,
    }


def infer_label_from_text(text: str, label: str) -> dict[str, Any]:
    positive_examples = []
    negative_examples = []
    uncertain_examples = []

    for sentence in split_sentences(text):
        for term in LABEL_TERMS.get(label, []):
            if term not in sentence:
                continue

            has_negation = sentence_has_cue(sentence, term, NEGATION_CUES)
            has_uncertainty = sentence_has_cue(sentence, term, UNCERTAINTY_CUES)

            if has_negation:
                negative_examples.append(sentence[:260])
            elif has_uncertainty:
                uncertain_examples.append(sentence[:260])
            else:
                positive_examples.append(sentence[:260])

    if positive_examples:
        return {
            "label": label,
            "status": "present",
            "evidence": positive_examples[0],
        }

    if uncertain_examples:
        return {
            "label": label,
            "status": "uncertain",
            "evidence": uncertain_examples[0],
        }

    if negative_examples:
        return {
            "label": label,
            "status": "absent",
            "evidence": negative_examples[0],
        }

    return {
        "label": label,
        "status": "absent",
        "evidence": "No report evidence found for this label.",
    }


def infer_ground_truth_labels(report_text: str) -> list[dict[str, Any]]:
    labels = []

    for label in CHEXPERT_LABELS:
        if label == "No Finding":
            continue
        labels.append(infer_label_from_text(report_text, label))

    any_present = any(item["status"] == "present" for item in labels)
    any_uncertain = any(item["status"] == "uncertain" for item in labels)

    if any_present or any_uncertain:
        no_finding_status = "absent"
        no_finding_evidence = "At least one finding is present or uncertain in the report-derived labels."
    else:
        no_finding_status = "present"
        no_finding_evidence = "No report-derived findings were detected."

    labels.append(
        {
            "label": "No Finding",
            "status": no_finding_status,
            "evidence": no_finding_evidence,
        }
    )

    return labels


def predictions_by_label(predictions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output = {}
    for item in predictions:
        if not isinstance(item, dict):
            continue
        label = normalize_label(item.get("label"))
        if label in CHEXPERT_LABELS:
            output[label] = {
                "label": label,
                "status": normalize_status(item.get("status")),
                "confidence": item.get("confidence"),
                "evidence": clean_string(item.get("evidence")),
                "evidence_type": clean_string(item.get("evidence_type")),
            }
    return output


def find_ground_truth_row(
    ground_truth_df: pd.DataFrame,
    study_key: str,
    dicom_path: str,
) -> pd.Series | None:
    study_columns = [
        col for col in ["study_key", "query_study_key", "retrieved_study_key"]
        if col in ground_truth_df.columns
    ]

    dicom_columns = [
        col for col in [
            "dicom_path",
            "query_dicom_path",
            "retrieved_dicom_path",
            "path_to_dcm",
            "local_dicom_path",
            "image_path",
            "path_to_image",
        ]
        if col in ground_truth_df.columns
    ]

    if study_columns:
        for study_col in study_columns:
            same_study = ground_truth_df[
                ground_truth_df[study_col].astype(str) == str(study_key)
            ]
            if not same_study.empty:
                if dicom_columns:
                    for _, row in same_study.iterrows():
                        for dicom_col in dicom_columns:
                            if paths_match(row.get(dicom_col), dicom_path):
                                return row
                return same_study.iloc[0]

    for _, row in ground_truth_df.iterrows():
        derived_keys = []
        for col in dicom_columns:
            derived_keys.append(derive_study_key_from_path(row.get(col)))
        if study_key in derived_keys:
            if any(paths_match(row.get(col), dicom_path) for col in dicom_columns):
                return row
            return row

    return None


def compare_label(predicted: dict[str, Any], ground_truth: dict[str, Any]) -> dict[str, Any]:
    label = ground_truth["label"]
    predicted_status = normalize_status(predicted.get("status"))
    ground_truth_status = normalize_status(ground_truth.get("status"))

    if predicted_status == ground_truth_status:
        match_type = "exact"
        score = 1.0
    elif "uncertain" in {predicted_status, ground_truth_status}:
        match_type = "partial"
        score = 0.5
    elif predicted_status == "unavailable":
        match_type = "not_evaluable"
        score = None
    else:
        match_type = "mismatch"
        score = 0.0

    return {
        "label": label,
        "predicted_status": predicted_status,
        "ground_truth_status": ground_truth_status,
        "match_type": match_type,
        "score": score,
        "predicted_confidence": predicted.get("confidence"),
        "predicted_evidence": clean_string(predicted.get("evidence")),
        "ground_truth_evidence": clean_string(ground_truth.get("evidence")),
    }


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 1.0 if numerator == 0 else 0.0
    return numerator / denominator


def present_labels(label_map: dict[str, dict[str, Any]], include_non_disease: bool = True) -> set[str]:
    labels = {
        label
        for label, item in label_map.items()
        if normalize_status(item.get("status")) == "present"
    }

    if not include_non_disease:
        labels = labels - NON_DISEASE_LABELS

    return labels


def compute_present_metrics(
    predicted_map: dict[str, dict[str, Any]],
    ground_truth_map: dict[str, dict[str, Any]],
    include_non_disease: bool,
) -> dict[str, Any]:
    pred_present = present_labels(predicted_map, include_non_disease=include_non_disease)
    gt_present = present_labels(ground_truth_map, include_non_disease=include_non_disease)

    true_positive = sorted(pred_present & gt_present)
    false_positive = sorted(pred_present - gt_present)
    false_negative = sorted(gt_present - pred_present)

    precision = safe_divide(len(true_positive), len(true_positive) + len(false_positive))
    recall = safe_divide(len(true_positive), len(true_positive) + len(false_negative))
    f1 = safe_divide(2 * precision * recall, precision + recall)

    return {
        "predicted_present": sorted(pred_present),
        "ground_truth_present": sorted(gt_present),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def judge_decision_from_metrics(
    per_label: list[dict[str, Any]],
    disease_present_metrics: dict[str, Any],
) -> tuple[str, list[str]]:
    reasons = []

    critical_false_positive = [
        label
        for label in disease_present_metrics["false_positive"]
        if label in CRITICAL_DISEASE_LABELS
    ]
    critical_false_negative = [
        label
        for label in disease_present_metrics["false_negative"]
        if label in CRITICAL_DISEASE_LABELS
    ]

    partial_labels = [
        item["label"]
        for item in per_label
        if item["match_type"] == "partial"
    ]
    mismatch_labels = [
        item["label"]
        for item in per_label
        if item["match_type"] == "mismatch"
    ]

    if critical_false_positive:
        reasons.append(f"Critical hallucinated present labels: {critical_false_positive}")
    if critical_false_negative:
        reasons.append(f"Critical missed present labels: {critical_false_negative}")

    if critical_false_positive or critical_false_negative:
        return "fail", reasons

    if mismatch_labels:
        reasons.append(f"Non-critical status mismatches: {mismatch_labels}")
    if partial_labels:
        reasons.append(f"Partial/uncertain matches: {partial_labels}")

    if disease_present_metrics["f1"] < 0.75:
        reasons.append(f"Disease present-label F1 below threshold: {disease_present_metrics['f1']:.3f}")

    if reasons:
        return "review", reasons

    return "pass", ["Predicted disease labels match report-derived ground truth labels."]


def evaluate_case(
    prediction_row: pd.Series,
    ground_truth_df: pd.DataFrame,
) -> dict[str, Any]:
    study_key = clean_string(prediction_row.get("study_key"))
    dicom_path = clean_string(prediction_row.get("dicom_path"))

    gt_row = find_ground_truth_row(
        ground_truth_df=ground_truth_df,
        study_key=study_key,
        dicom_path=dicom_path,
    )

    if gt_row is None:
        return {
            "study_key": study_key,
            "dicom_path": dicom_path,
            "judge_decision": "fail",
            "judge_explanation": "No matching ground-truth report row found.",
            "ground_truth_present_labels": json.dumps([]),
            "predicted_present_labels": json.dumps([]),
            "disease_precision": 0.0,
            "disease_recall": 0.0,
            "disease_f1": 0.0,
            "label_macro_score": 0.0,
            "per_label_judgment_json": json.dumps([]),
            "judge_failure_reasons_json": json.dumps(["No matching ground-truth report row found."]),
            "ground_truth_report_excerpt": "",
        }

    report_parts = extract_report_text(gt_row)
    gt_labels = infer_ground_truth_labels(report_parts["combined_text"])

    predictions = parse_json_cell(prediction_row.get("finding_predictions_json"), [])
    predicted_map = predictions_by_label(predictions)
    ground_truth_map = predictions_by_label(gt_labels)

    per_label = []
    scores = []

    for label in CHEXPERT_LABELS:
        predicted = predicted_map.get(
            label,
            {
                "label": label,
                "status": "unavailable",
                "confidence": None,
                "evidence": "Prediction missing.",
                "evidence_type": "missing",
            },
        )
        ground_truth = ground_truth_map[label]
        judgment = compare_label(predicted, ground_truth)
        per_label.append(judgment)

        if judgment["score"] is not None:
            scores.append(judgment["score"])

    label_macro_score = sum(scores) / len(scores) if scores else 0.0

    all_present_metrics = compute_present_metrics(
        predicted_map=predicted_map,
        ground_truth_map=ground_truth_map,
        include_non_disease=True,
    )
    disease_present_metrics = compute_present_metrics(
        predicted_map=predicted_map,
        ground_truth_map=ground_truth_map,
        include_non_disease=False,
    )

    judge_decision, judge_reasons = judge_decision_from_metrics(
        per_label=per_label,
        disease_present_metrics=disease_present_metrics,
    )

    exact_count = sum(1 for item in per_label if item["match_type"] == "exact")
    partial_count = sum(1 for item in per_label if item["match_type"] == "partial")
    mismatch_count = sum(1 for item in per_label if item["match_type"] == "mismatch")

    return {
        "study_key": study_key,
        "dicom_path": dicom_path,
        "judge_decision": judge_decision,
        "judge_explanation": " ".join(judge_reasons),
        "exact_label_match_count": exact_count,
        "partial_label_match_count": partial_count,
        "mismatch_label_count": mismatch_count,
        "evaluable_label_count": len(scores),
        "label_macro_score": label_macro_score,
        "disease_precision": disease_present_metrics["precision"],
        "disease_recall": disease_present_metrics["recall"],
        "disease_f1": disease_present_metrics["f1"],
        "all_label_precision": all_present_metrics["precision"],
        "all_label_recall": all_present_metrics["recall"],
        "all_label_f1": all_present_metrics["f1"],
        "predicted_present_labels": json.dumps(all_present_metrics["predicted_present"]),
        "ground_truth_present_labels": json.dumps(all_present_metrics["ground_truth_present"]),
        "disease_false_positive_labels": json.dumps(disease_present_metrics["false_positive"]),
        "disease_false_negative_labels": json.dumps(disease_present_metrics["false_negative"]),
        "per_label_judgment_json": json.dumps(per_label),
        "ground_truth_labels_json": json.dumps(gt_labels),
        "predicted_labels_json": json.dumps(predictions),
        "judge_failure_reasons_json": json.dumps(judge_reasons),
        "ground_truth_findings": report_parts["section_findings"],
        "ground_truth_impression": report_parts["section_impression"],
        "ground_truth_report_excerpt": truncate_text(report_parts["combined_text"], 2200),
        "prompt_version": PROMPT_VERSION,
        "route_next": "complete",
    }


def markdown_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def build_judge_markdown(eval_df: pd.DataFrame) -> str:
    total = len(eval_df)
    passed = int((eval_df["judge_decision"] == "pass").sum()) if total else 0
    review = int((eval_df["judge_decision"] == "review").sum()) if total else 0
    failed = int((eval_df["judge_decision"] == "fail").sum()) if total else 0

    sections = [
        "# MEDAGENT-X Judge Report",
        "",
        "## Summary",
        "",
        f"- Total cases: `{total}`",
        f"- Pass: `{passed}`",
        f"- Review: `{review}`",
        f"- Fail: `{failed}`",
        "",
    ]

    for _, row in eval_df.iterrows():
        per_label = parse_json_cell(row.get("per_label_judgment_json"), [])
        mismatches = [
            f"{item['label']}: predicted `{item['predicted_status']}`, ground truth `{item['ground_truth_status']}`"
            for item in per_label
            if item.get("match_type") in {"partial", "mismatch"}
        ]

        sections.extend(
            [
                "## Case",
                "",
                f"- Study key: `{clean_string(row.get('study_key'))}`",
                f"- DICOM path: `{clean_string(row.get('dicom_path'))}`",
                f"- Judge decision: **{clean_string(row.get('judge_decision')).upper()}**",
                f"- Disease F1: `{float(row.get('disease_f1')):.3f}`",
                f"- Label macro score: `{float(row.get('label_macro_score')):.3f}`",
                "",
                "### Explanation",
                "",
                clean_string(row.get("judge_explanation")),
                "",
                "### Ground Truth Present Labels",
                "",
                markdown_list(parse_json_cell(row.get("ground_truth_present_labels"), [])),
                "",
                "### Predicted Present Labels",
                "",
                markdown_list(parse_json_cell(row.get("predicted_present_labels"), [])),
                "",
                "### Partial Or Mismatched Labels",
                "",
                markdown_list(mismatches),
                "",
                "### Ground Truth Report Excerpt",
                "",
                f"> {truncate_text(row.get('ground_truth_report_excerpt'), 900).replace(chr(10), ' ')}",
                "",
                "---",
                "",
            ]
        )

    return "\n".join(sections).strip() + "\n"


def run_judge_agent(
    disease_reasoning_results_path: str = DEFAULT_DISEASE_REASONING_PATH,
    ground_truth_path: str = DEFAULT_GROUND_TRUTH_PATH,
    output_path: str = DEFAULT_OUTPUT_PATH,
    report_output_path: str | None = DEFAULT_REPORT_PATH,
    verbose: bool = True,
) -> pd.DataFrame:
    disease_reasoning_path = Path(disease_reasoning_results_path)
    ground_truth_path_obj = Path(ground_truth_path)
    output_path_obj = Path(output_path)

    if verbose:
        print("[Judge Agent] Loading disease reasoning results...")
    disease_reasoning_df = pd.read_csv(disease_reasoning_path)

    if verbose:
        print("[Judge Agent] Loading ground-truth report source...")
    ground_truth_df = pd.read_csv(ground_truth_path_obj)

    rows = []
    total = len(disease_reasoning_df)

    for index, (_, prediction_row) in enumerate(disease_reasoning_df.iterrows(), start=1):
        if verbose:
            print(
                f"[Judge Agent] Judging case {index}/{total}: "
                f"{prediction_row.get('study_key')} | {prediction_row.get('dicom_path')}"
            )
        rows.append(evaluate_case(prediction_row, ground_truth_df))

    output_df = pd.DataFrame(rows)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_path_obj, index=False)

    if report_output_path:
        report_path = Path(report_output_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(build_judge_markdown(output_df), encoding="utf-8")

    if verbose:
        print(f"[Judge Agent] Saved: {output_path_obj}")
        if report_output_path:
            print(f"[Judge Agent] Saved report: {report_output_path}")

    return output_df


def judge_node(state: dict[str, Any]) -> dict[str, Any]:
    output_path = state.get("judge_results_path", DEFAULT_OUTPUT_PATH)
    report_output_path = state.get("judge_report_path", DEFAULT_REPORT_PATH)

    output_df = run_judge_agent(
        disease_reasoning_results_path=state.get(
            "disease_reasoning_results_path",
            DEFAULT_DISEASE_REASONING_PATH,
        ),
        ground_truth_path=state.get(
            "ground_truth_path",
            DEFAULT_GROUND_TRUTH_PATH,
        ),
        output_path=output_path,
        report_output_path=report_output_path,
        verbose=bool(state.get("verbose", True)),
    )

    return {
        **state,
        "judge_results_path": output_path,
        "judge_report_path": report_output_path,
        "judge_case_count": len(output_df),
        "route_next": "complete",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MEDAGENT-X Judge Agent."
    )
    parser.add_argument(
        "--disease-reasoning-results",
        default=DEFAULT_DISEASE_REASONING_PATH,
    )
    parser.add_argument(
        "--ground-truth",
        default=DEFAULT_GROUND_TRUTH_PATH,
        help="CSV containing ground-truth report sections from CheXpert Plus.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
    )
    parser.add_argument(
        "--report-output",
        default=DEFAULT_REPORT_PATH,
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    run_judge_agent(
        disease_reasoning_results_path=args.disease_reasoning_results,
        ground_truth_path=args.ground_truth,
        output_path=args.output,
        report_output_path=args.report_output,
        verbose=True,
    )