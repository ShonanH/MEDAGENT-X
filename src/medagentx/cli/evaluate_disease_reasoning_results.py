from __future__ import annotations

from medagentx.paths import CHEXPERT_OUTPUT_DIR, DATA_DIR, FUSION_OUTPUT_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR, SRC_ROOT, VECTOR_DB_DIR

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

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

REQUIRED_COLUMNS = [
    "study_key",
    "dicom_path",
    "primary_predicted_findings",
    "predicted_findings_section",
    "predicted_impression_section",
    "finding_predictions_json",
    "evidence_summary",
    "conflicting_evidence_json",
    "limitations_json",
    "classifier_evidence_json",
    "retrieval_evidence_json",
    "route_next",
]

JSON_COLUMNS = [
    "primary_predicted_findings",
    "finding_predictions_json",
    "conflicting_evidence_json",
    "limitations_json",
    "classifier_evidence_json",
    "retrieval_evidence_json",
    "consistency_warnings_json",
]

LABEL_TERMS = {
    "Atelectasis": ["atelectasis", "volume loss"],
    "Cardiomegaly": ["cardiomegaly", "enlarged cardiac silhouette", "cardiac silhouette is enlarged"],
    "Consolidation": ["consolidation", "focal airspace opacity"],
    "Edema": ["pulmonary edema", "interstitial edema", "edema", "vascular congestion", "pulmonary venous hypertension"],
    "Pleural Effusion": ["pleural effusion", "effusion"],
    "Pneumonia": ["pneumonia"],
    "Pneumothorax": ["pneumothorax"],
    "Fracture": ["fracture"],
    "Lung Lesion": ["lung lesion", "nodule", "mass"],
    "Lung Opacity": ["lung opacity", "opacity", "airspace opacity", "infiltrate"],
    "Enlarged Cardiomediastinum": ["enlarged cardiomediastinum", "widened mediastinum"],
    "Pleural Other": ["pleural thickening", "pleural abnormality"],
    "Support Devices": ["support device", "catheter", "central venous catheter", "line", "tube", "pacemaker"],
    "No Finding": ["no finding"],
}

NEGATION_CUES = [
    "no ",
    "without ",
    "negative for ",
    "absent ",
    "free of ",
    "clear of ",
    "no evidence of ",
    "no focal ",
]

CLEAR_LUNGS_PHRASES = [
    "lungs are clear",
    "lungs appear clear",
    "lungs clear",
    "clear bilaterally",
    "no focal parenchymal process",
]


def clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
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


def parse_json_cell(value: Any, default: Any) -> tuple[Any, bool]:
    value = clean_value(value)
    if value is None:
        return default, False
    if isinstance(value, (dict, list)):
        return value, True
    try:
        return json.loads(str(value)), True
    except Exception:
        return default, False


def normalize_label(label: Any) -> str:
    label = clean_string(label)
    for expected in CHEXPERT_LABELS:
        if label.lower() == expected.lower():
            return expected
    return label


def normalize_status(status: Any) -> str:
    status = clean_string(status).lower()
    if status in {"present", "positive", "yes"}:
        return "present"
    if status in {"absent", "negative", "no"}:
        return "absent"
    if status in {"uncertain", "equivocal", "possible"}:
        return "uncertain"
    if status in {"unavailable", "not_available", "not computed", "not_computed"}:
        return "unavailable"
    return status or "uncertain"


def normalize_probability(value: Any) -> float | None:
    value = clean_value(value)
    if value is None:
        return None
    try:
        value = float(value)
    except Exception:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return max(0.0, min(1.0, value))


def split_sentences(text: str) -> list[str]:
    text = clean_string(text).lower()
    pieces = re.split(r"[\n.;:]+", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def sentence_has_negation(sentence: str, term: str) -> bool:
    index = sentence.find(term)
    if index < 0:
        return False
    prefix = sentence[max(0, index - 70):index]
    return any(cue in prefix for cue in NEGATION_CUES)


def contains_unnegated_label(text: str, label: str) -> bool:
    terms = LABEL_TERMS.get(label, [])
    for sentence in split_sentences(text):
        for term in terms:
            if term in sentence and not sentence_has_negation(sentence, term):
                return True
    return False


def contains_negated_label(text: str, label: str) -> bool:
    terms = LABEL_TERMS.get(label, [])
    for sentence in split_sentences(text):
        for term in terms:
            if term in sentence and sentence_has_negation(sentence, term):
                return True
    return False


def parse_predictions(row: pd.Series) -> tuple[list[dict[str, Any]], bool]:
    predictions, ok = parse_json_cell(row.get("finding_predictions_json"), [])
    if not isinstance(predictions, list):
        return [], False

    normalized = []
    for item in predictions:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "label": normalize_label(item.get("label")),
                "status": normalize_status(item.get("status")),
                "confidence": item.get("confidence"),
                "evidence": clean_string(item.get("evidence")),
                "evidence_type": clean_string(item.get("evidence_type")),
            }
        )

    return normalized, ok


def predictions_by_label(predictions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["label"]: item for item in predictions}


def parse_primary_findings(row: pd.Series) -> tuple[list[str], bool]:
    primary, ok = parse_json_cell(row.get("primary_predicted_findings"), [])
    if not isinstance(primary, list):
        return [], False
    return [normalize_label(item) for item in primary], ok


def parse_classifier_evidence(row: pd.Series) -> tuple[dict[str, dict[str, Any]], bool]:
    evidence, ok = parse_json_cell(row.get("classifier_evidence_json"), {})
    labels = {}

    if not isinstance(evidence, dict):
        return labels, False

    for item in evidence.get("labels", []):
        if not isinstance(item, dict):
            continue
        label = normalize_label(item.get("label"))
        if label in CHEXPERT_LABELS:
            labels[label] = {
                "probability": normalize_probability(item.get("probability")),
                "status": normalize_status(item.get("status")),
                "source_label": clean_string(item.get("source_label")),
            }

    return labels, ok


def parse_retrieval_cases(row: pd.Series) -> tuple[list[dict[str, Any]], bool]:
    cases, ok = parse_json_cell(row.get("retrieval_evidence_json"), [])
    if not isinstance(cases, list):
        return [], False

    normalized = []
    for item in cases:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "rank": item.get("rank"),
                "retrieved_study_key": clean_string(item.get("retrieved_study_key")),
                "retrieved_dicom_path": clean_string(item.get("retrieved_dicom_path")),
                "retrieved_document": clean_string(item.get("retrieved_document")),
            }
        )

    return normalized, ok


def count_retrieval_mentions(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    counts = {}

    for label in CHEXPERT_LABELS:
        counts[label] = {
            "positive_count": 0,
            "negative_count": 0,
            "positive_studies": [],
            "negative_studies": [],
        }

    for case in cases:
        study_key = case.get("retrieved_study_key", "")
        document = case.get("retrieved_document", "")

        for label in CHEXPERT_LABELS:
            if contains_unnegated_label(document, label):
                counts[label]["positive_count"] += 1
                counts[label]["positive_studies"].append(study_key)

            if contains_negated_label(document, label):
                counts[label]["negative_count"] += 1
                counts[label]["negative_studies"].append(study_key)

    return counts


def expected_status_from_classifier(
    label: str,
    classifier_item: dict[str, Any] | None,
    retrieval_counts: dict[str, Any],
) -> str:
    if label == "No Finding":
        return "absent"

    if classifier_item is None:
        return "unavailable"

    probability = classifier_item.get("probability")
    classifier_status = classifier_item.get("status")

    if classifier_status == "unavailable":
        if retrieval_counts.get("positive_count", 0) >= 2:
            return "uncertain"
        return "unavailable"

    if probability is None:
        return classifier_status or "uncertain"

    positive_count = int(retrieval_counts.get("positive_count", 0))
    negative_count = int(retrieval_counts.get("negative_count", 0))

    if probability >= 0.75:
        return "present"

    if probability >= 0.60:
        return "present"

    if probability >= 0.50:
        if positive_count >= 1 and positive_count >= negative_count:
            return "present"
        return "uncertain"

    if probability > 0.20:
        return "uncertain"

    return "absent"


def eval_schema(df: pd.DataFrame) -> tuple[bool, list[str]]:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        return False, [f"Missing required columns: {missing}"]
    return True, []


def eval_json_parse(row: pd.Series) -> tuple[bool, list[str]]:
    failures = []

    for col in JSON_COLUMNS:
        if col not in row.index:
            continue
        _, ok = parse_json_cell(row.get(col), None)
        if not ok:
            failures.append(f"Could not parse JSON column: {col}")

    return len(failures) == 0, failures


def eval_label_completeness(predictions: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    labels = [item["label"] for item in predictions]
    failures = []

    missing = [label for label in CHEXPERT_LABELS if label not in labels]
    duplicate = sorted({label for label in labels if labels.count(label) > 1})
    unknown = [label for label in labels if label not in CHEXPERT_LABELS]

    if len(predictions) != len(CHEXPERT_LABELS):
        failures.append(f"Expected 14 predictions, found {len(predictions)}")
    if missing:
        failures.append(f"Missing labels: {missing}")
    if duplicate:
        failures.append(f"Duplicate labels: {duplicate}")
    if unknown:
        failures.append(f"Unknown labels: {unknown}")

    return len(failures) == 0, failures


def eval_primary_consistency(
    primary_findings: list[str],
    predictions: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    present_labels = sorted(
        item["label"]
        for item in predictions
        if item.get("status") == "present"
    )
    primary_sorted = sorted(primary_findings)

    if primary_sorted != present_labels:
        return False, [
            f"primary_predicted_findings={primary_sorted} but present structured labels={present_labels}"
        ]

    return True, []


def eval_report_text_consistency(
    row: pd.Series,
    predictions: list[dict[str, Any]],
) -> tuple[bool, list[str], list[str], list[str]]:
    report_text = " ".join(
        [
            clean_string(row.get("predicted_findings_section")),
            clean_string(row.get("predicted_impression_section")),
        ]
    )

    unexpected_mentions = []
    missing_present_mentions = []

    for item in predictions:
        label = item["label"]
        status = item["status"]

        if label == "No Finding":
            continue

        if status == "present":
            if not contains_unnegated_label(report_text, label):
                missing_present_mentions.append(label)
        else:
            if contains_unnegated_label(report_text, label):
                unexpected_mentions.append(label)

    failures = []
    if unexpected_mentions:
        failures.append(f"Report text mentions non-present labels: {sorted(set(unexpected_mentions))}")
    if missing_present_mentions:
        failures.append(f"Report text omits present labels: {sorted(set(missing_present_mentions))}")

    return len(failures) == 0, failures, sorted(set(unexpected_mentions)), sorted(set(missing_present_mentions))


def eval_contradictions(
    row: pd.Series,
    predictions: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    report_text = " ".join(
        [
            clean_string(row.get("predicted_findings_section")),
            clean_string(row.get("predicted_impression_section")),
        ]
    ).lower()

    present_labels = {
        item["label"]
        for item in predictions
        if item.get("status") == "present"
    }

    pulmonary_abnormalities = {
        "Edema",
        "Lung Opacity",
        "Pneumonia",
        "Consolidation",
        "Atelectasis",
        "Pleural Effusion",
    }

    failures = []

    if present_labels.intersection(pulmonary_abnormalities):
        if any(phrase in report_text for phrase in CLEAR_LUNGS_PHRASES):
            failures.append("Report says lungs are clear while pulmonary abnormality is present.")

    for item in predictions:
        label = item["label"]
        status = item["status"]

        if status == "absent" and contains_unnegated_label(report_text, label):
            failures.append(f"Report positively mentions absent label: {label}")

    return len(failures) == 0, failures


def eval_classifier_adherence(
    predictions: list[dict[str, Any]],
    classifier_labels: dict[str, dict[str, Any]],
    retrieval_counts: dict[str, dict[str, Any]],
) -> tuple[bool, list[str]]:
    failures = []
    by_label = predictions_by_label(predictions)

    for label in CHEXPERT_LABELS:
        predicted = by_label.get(label)
        if not predicted:
            failures.append(f"No prediction found for {label}")
            continue

        expected = expected_status_from_classifier(
            label=label,
            classifier_item=classifier_labels.get(label),
            retrieval_counts=retrieval_counts.get(label, {}),
        )

        predicted_status = predicted.get("status")

        if expected == "absent" and predicted_status != "absent":
            failures.append(f"{label}: expected absent from classifier/retrieval rules, got {predicted_status}")

        if expected == "present" and predicted_status not in {"present", "uncertain"}:
            failures.append(f"{label}: expected present or uncertain from classifier/retrieval rules, got {predicted_status}")

        if expected == "unavailable" and predicted_status == "present":
            failures.append(f"{label}: classifier unavailable but final prediction is present")

    return len(failures) == 0, failures


def extract_study_keys(text: str) -> list[str]:
    return re.findall(r"patient\d+/study\d+", clean_string(text))


def eval_retrieval_faithfulness(
    row: pd.Series,
    predictions: list[dict[str, Any]],
    retrieval_cases: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    failures = []
    docs_by_study = {
        case["retrieved_study_key"]: case["retrieved_document"]
        for case in retrieval_cases
        if case.get("retrieved_study_key")
    }

    texts_to_check = [
        clean_string(row.get("evidence_summary")),
    ]

    conflicts, _ = parse_json_cell(row.get("conflicting_evidence_json"), [])
    limitations, _ = parse_json_cell(row.get("limitations_json"), [])

    if isinstance(conflicts, list):
        texts_to_check.extend(clean_string(item) for item in conflicts)

    if isinstance(limitations, list):
        texts_to_check.extend(clean_string(item) for item in limitations)

    for item in predictions:
        texts_to_check.append(clean_string(item.get("evidence")))

    for text in texts_to_check:
        referenced_studies = extract_study_keys(text)
        if not referenced_studies:
            continue

        for label in CHEXPERT_LABELS:
            if not contains_unnegated_label(text, label):
                continue

            for study_key in referenced_studies:
                retrieved_doc = docs_by_study.get(study_key)
                if not retrieved_doc:
                    failures.append(f"Claim references {study_key}, but that study is not in retrieval_evidence_json.")
                    continue

                if not contains_unnegated_label(retrieved_doc, label):
                    failures.append(
                        f"Claim says {study_key} supports {label}, but retrieved document does not contain an unnegated {label} mention."
                    )

    return len(failures) == 0, sorted(set(failures))


def evaluate_row(row: pd.Series, schema_pass: bool, schema_failures: list[str]) -> dict[str, Any]:
    failure_reasons = list(schema_failures)

    json_parse_pass, json_failures = eval_json_parse(row)
    failure_reasons.extend(json_failures)

    predictions, predictions_json_ok = parse_predictions(row)
    primary_findings, primary_json_ok = parse_primary_findings(row)
    classifier_labels, classifier_json_ok = parse_classifier_evidence(row)
    retrieval_cases, retrieval_json_ok = parse_retrieval_cases(row)

    retrieval_counts = count_retrieval_mentions(retrieval_cases)

    label_completeness_pass, label_failures = eval_label_completeness(predictions)
    primary_consistency_pass, primary_failures = eval_primary_consistency(primary_findings, predictions)

    (
        report_text_consistency_pass,
        report_failures,
        unexpected_mentions,
        missing_present_mentions,
    ) = eval_report_text_consistency(row, predictions)

    contradiction_pass, contradiction_failures = eval_contradictions(row, predictions)

    classifier_adherence_pass, classifier_failures = eval_classifier_adherence(
        predictions=predictions,
        classifier_labels=classifier_labels,
        retrieval_counts=retrieval_counts,
    )

    retrieval_faithfulness_pass, retrieval_failures = eval_retrieval_faithfulness(
        row=row,
        predictions=predictions,
        retrieval_cases=retrieval_cases,
    )

    for failures in [
        label_failures,
        primary_failures,
        report_failures,
        contradiction_failures,
        classifier_failures,
        retrieval_failures,
    ]:
        failure_reasons.extend(failures)

    present_labels = [
        item["label"]
        for item in predictions
        if item.get("status") == "present"
    ]

    overall_pass = all(
        [
            schema_pass,
            json_parse_pass,
            predictions_json_ok,
            primary_json_ok,
            classifier_json_ok,
            retrieval_json_ok,
            label_completeness_pass,
            primary_consistency_pass,
            report_text_consistency_pass,
            contradiction_pass,
            classifier_adherence_pass,
            retrieval_faithfulness_pass,
        ]
    )

    return {
        "study_key": clean_string(row.get("study_key")),
        "dicom_path": clean_string(row.get("dicom_path")),
        "schema_pass": schema_pass,
        "json_parse_pass": json_parse_pass,
        "label_completeness_pass": label_completeness_pass,
        "primary_consistency_pass": primary_consistency_pass,
        "report_text_consistency_pass": report_text_consistency_pass,
        "contradiction_pass": contradiction_pass,
        "classifier_adherence_pass": classifier_adherence_pass,
        "retrieval_faithfulness_pass": retrieval_faithfulness_pass,
        "overall_pass": overall_pass,
        "present_labels_json": json.dumps(sorted(present_labels)),
        "unexpected_report_mentions_json": json.dumps(unexpected_mentions),
        "missing_present_mentions_json": json.dumps(missing_present_mentions),
        "classifier_adherence_failures_json": json.dumps(classifier_failures),
        "retrieval_faithfulness_failures_json": json.dumps(retrieval_failures),
        "failure_reasons_json": json.dumps(failure_reasons),
    }


def evaluate_disease_reasoning_results(input_path: str, output_path: str) -> pd.DataFrame:
    input_path_obj = Path(input_path)
    output_path_obj = Path(output_path)

    df = pd.read_csv(input_path_obj)

    schema_pass, schema_failures = eval_schema(df)

    eval_rows = []
    for _, row in df.iterrows():
        eval_rows.append(evaluate_row(row, schema_pass, schema_failures))

    eval_df = pd.DataFrame(eval_rows)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    eval_df.to_csv(output_path_obj, index=False)

    total = len(eval_df)
    passed = int(eval_df["overall_pass"].sum()) if total else 0
    failed = total - passed

    print(f"[Disease Reasoning Evals] Input: {input_path_obj}")
    print(f"[Disease Reasoning Evals] Output: {output_path_obj}")
    print(f"[Disease Reasoning Evals] Cases: {total}")
    print(f"[Disease Reasoning Evals] Passed: {passed}")
    print(f"[Disease Reasoning Evals] Failed: {failed}")

    if failed:
        print("[Disease Reasoning Evals] Failed case summaries:")
        failed_rows = eval_df[~eval_df["overall_pass"]]
        for _, row in failed_rows.iterrows():
            reasons = json.loads(row["failure_reasons_json"])
            print(f"- {row['study_key']} | {row['dicom_path']}")
            for reason in reasons[:8]:
                print(f"  - {reason}")

    return eval_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate MEDAGENT-X disease reasoning outputs."
    )
    parser.add_argument(
        "--input",
        default=str(CHEXPERT_OUTPUT_DIR / "disease_reasoning_results.csv"),
        help="Path to disease_reasoning_results.csv",
    )
    parser.add_argument(
        "--output",
        default=str(CHEXPERT_OUTPUT_DIR / "disease_reasoning_eval_results.csv"),
        help="Path to write disease reasoning eval results.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    evaluate_disease_reasoning_results(
        input_path=args.input,
        output_path=args.output,
    )