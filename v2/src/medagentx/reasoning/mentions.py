"""Keyword and negation mention parsing for retrieved report evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from medagentx.reasoning.constants import FUSION_LABELS

NEGATION_TERMS: tuple[str, ...] = (
    "no ",
    "without ",
    "no evidence of ",
    "negative for ",
    "absent ",
    "clear of ",
    "free of ",
)

LABEL_TERMS: dict[str, tuple[str, ...]] = {
    "Atelectasis": ("atelectasis", "volume loss"),
    "Cardiomegaly": (
        "cardiomegaly",
        "enlarged cardiac silhouette",
        "cardiac silhouette is enlarged",
    ),
    "Consolidation": ("consolidation", "focal airspace opacity"),
    "Edema": (
        "pulmonary edema",
        "interstitial edema",
        "edema",
        "vascular congestion",
        "pulmonary venous hypertension",
    ),
    "Pleural Effusion": ("pleural effusion", "effusion"),
    "Pneumonia": ("pneumonia", "infectious infiltrate"),
    "Pneumothorax": ("pneumothorax",),
    "Fracture": ("fracture",),
    "Lung Lesion": ("lung lesion", "nodule", "mass"),
    "Lung Opacity": ("lung opacity", "opacity", "airspace opacity", "infiltrate"),
    "Enlarged Cardiomediastinum": (
        "enlarged cardiomediastinum",
        "widened mediastinum",
    ),
    "Pleural Other": ("pleural thickening", "pleural abnormality"),
}

EXAMPLE_SNIPPET_MAX_CHARS = 260
_NEGATION_WINDOW_CHARS = 70


class RetrievedReportCase(Protocol):
    """Minimal retrieval payload consumed by mention counting."""

    document: str


@dataclass(frozen=True)
class MentionCounts:
    """Per-label retrieval mention evidence."""

    positive_count: int = 0
    negative_count: int = 0
    example_positive: str = ""
    example_negative: str = ""


def split_sentences(text: str) -> list[str]:
    """Split report text into lowercase sentence-like fragments."""
    normalized = str(text or "").strip().lower()
    if not normalized:
        return []
    pieces = re.split(r"[\n.;:]+", normalized)
    return [piece.strip() for piece in pieces if piece.strip()]


def sentence_has_negation(sentence: str, term: str) -> bool:
    """Return True when a negation cue appears shortly before the matched term."""
    index = sentence.find(term)
    if index < 0:
        return False
    prefix = sentence[max(0, index - _NEGATION_WINDOW_CHARS) : index]
    return any(neg in prefix for neg in NEGATION_TERMS)


def _document_from_case(case: RetrievedReportCase | Mapping[str, Any]) -> str:
    document = getattr(case, "document", None)
    if document is not None:
        return str(document)
    if "document" in case:
        return str(case["document"] or "")
    return str(case.get("retrieved_document") or "")


def _empty_mention_counts() -> dict[str, MentionCounts]:
    return {label: MentionCounts() for label in FUSION_LABELS}


def count_retrieval_mentions(
    retrieved_cases: Sequence[RetrievedReportCase | Mapping[str, Any]],
) -> dict[str, MentionCounts]:
    """Count positive and negative keyword mentions across retrieved reports."""
    counts = _empty_mention_counts()

    for case in retrieved_cases:
        document = _document_from_case(case)
        for label in FUSION_LABELS:
            terms = LABEL_TERMS[label]
            for sentence in split_sentences(document):
                matched_terms = [term for term in terms if term in sentence]
                if not matched_terms:
                    continue

                is_negative = any(
                    sentence_has_negation(sentence, term) for term in matched_terms
                )
                current = counts[label]
                if is_negative:
                    counts[label] = MentionCounts(
                        positive_count=current.positive_count,
                        negative_count=current.negative_count + 1,
                        example_positive=current.example_positive,
                        example_negative=current.example_negative
                        or sentence[:EXAMPLE_SNIPPET_MAX_CHARS],
                    )
                else:
                    counts[label] = MentionCounts(
                        positive_count=current.positive_count + 1,
                        negative_count=current.negative_count,
                        example_positive=current.example_positive
                        or sentence[:EXAMPLE_SNIPPET_MAX_CHARS],
                        example_negative=current.example_negative,
                    )

    return counts
