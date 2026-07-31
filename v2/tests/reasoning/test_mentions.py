"""Tests for retrieval mention parsing."""

from __future__ import annotations

from dataclasses import dataclass

from medagentx.reasoning.mentions import (
    count_retrieval_mentions,
    sentence_has_negation,
    split_sentences,
)


@dataclass(frozen=True)
class _Case:
    document: str


def _retrieved(document: str) -> _Case:
    return _Case(document=document)


def test_split_sentences_splits_on_punctuation() -> None:
    sentences = split_sentences("Findings: pneumonia. No effusion.")
    assert sentences == ["findings", "pneumonia", "no effusion"]


def test_sentence_has_negation_detects_prefix_cue() -> None:
    sentence = "no pleural effusion identified"
    assert sentence_has_negation(sentence, "pleural effusion")
    assert not sentence_has_negation(sentence, "pneumonia")


def test_count_retrieval_mentions_positive_and_negative() -> None:
    cases = [
        _retrieved("Findings: small left pleural effusion."),
        _retrieved("Impression: no pleural effusion."),
        _retrieved("Consolidation in the right lower lobe."),
    ]
    counts = count_retrieval_mentions(cases)

    effusion = counts["Pleural Effusion"]
    assert effusion.positive_count == 1
    assert effusion.negative_count == 1
    assert "pleural effusion" in effusion.example_positive
    assert "no pleural effusion" in effusion.example_negative

    consolidation = counts["Consolidation"]
    assert consolidation.positive_count == 1
    assert consolidation.negative_count == 0


def test_count_retrieval_mentions_empty_documents() -> None:
    counts = count_retrieval_mentions([_retrieved("")])
    assert all(
        item.positive_count == 0 and item.negative_count == 0
        for item in counts.values()
    )
