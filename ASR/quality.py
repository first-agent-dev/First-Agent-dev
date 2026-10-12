"""Reference-normalized WER/CER helpers for the local ASR experiment."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence


def normalize_for_scoring(text: str) -> list[str]:
    """Lowercase Russian text, fold ё→е, and discard punctuation for scoring."""
    normalized = text.casefold().replace("ё", "е")
    words: list[str] = []
    current: list[str] = []
    for character in normalized:
        if unicodedata.category(character)[0] in {"L", "N"}:
            current.append(character)
        elif current:
            words.append("".join(current))
            current.clear()
    if current:
        words.append("".join(current))
    return words


def edit_distance(reference: Sequence[str], hypothesis: Sequence[str]) -> int:
    """Return Levenshtein distance using memory linear in the shorter input."""
    if len(hypothesis) > len(reference):
        reference, hypothesis = hypothesis, reference
    previous = list(range(len(hypothesis) + 1))
    for reference_index, reference_token in enumerate(reference, start=1):
        current = [reference_index]
        for hypothesis_index, hypothesis_token in enumerate(hypothesis, start=1):
            substitution_cost = 0 if reference_token == hypothesis_token else 1
            current.append(
                min(
                    previous[hypothesis_index] + 1,
                    current[hypothesis_index - 1] + 1,
                    previous[hypothesis_index - 1] + substitution_cost,
                )
            )
        previous = current
    return previous[-1]


def word_error_rate(reference: str, hypothesis: str) -> float | None:
    """Compute WER after Russian-friendly case/punctuation normalization."""
    reference_words = normalize_for_scoring(reference)
    if not reference_words:
        return None
    hypothesis_words = normalize_for_scoring(hypothesis)
    return edit_distance(reference_words, hypothesis_words) / len(reference_words)


def character_error_rate(reference: str, hypothesis: str) -> float | None:
    """Compute CER over normalized text, including spaces between words."""
    reference_words = normalize_for_scoring(reference)
    if not reference_words:
        return None
    hypothesis_words = normalize_for_scoring(hypothesis)
    reference_chars = list(" ".join(reference_words))
    hypothesis_chars = list(" ".join(hypothesis_words))
    return edit_distance(reference_chars, hypothesis_chars) / len(reference_chars)
