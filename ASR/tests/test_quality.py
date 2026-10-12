from __future__ import annotations

import unittest

from ASR.quality import character_error_rate, normalize_for_scoring, word_error_rate


class QualityMetricTests(unittest.TestCase):
    def test_russian_case_punctuation_and_yo_are_normalized(self) -> None:
        reference = "Ёжик, шёл по дорожке!"
        hypothesis = "ежик шел по дорожке"

        self.assertEqual(normalize_for_scoring(reference), ["ежик", "шел", "по", "дорожке"])
        self.assertEqual(word_error_rate(reference, hypothesis), 0.0)
        self.assertEqual(character_error_rate(reference, hypothesis), 0.0)

    def test_word_error_rate_counts_deletions(self) -> None:
        self.assertAlmostEqual(word_error_rate("один два три", "один три") or 0, 1 / 3)

    def test_word_error_rate_counts_insertions_and_substitutions(self) -> None:
        self.assertAlmostEqual(word_error_rate("синий кот", "большой синий кит") or 0, 1.0)

    def test_empty_reference_has_undefined_error_rate(self) -> None:
        self.assertIsNone(word_error_rate("...", "слова есть"))
        self.assertIsNone(character_error_rate("", "слова есть"))


if __name__ == "__main__":
    unittest.main()
