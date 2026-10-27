"""Small regression checks for count clipping, overlap and BLEU penalty."""
import math
import unittest
from evaluate import score


class NucleotideMetricsTest(unittest.TestCase):
    def test_identity(self):
        self.assertTrue(all(value == 1 for value in score("ACGTACGT", "ACGTACGT").values()))

    def test_overlapping_clipped_counts(self):
        # AAAA contains three overlapping AA and two overlapping AAA occurrences.
        result = score("AAAA", "AAAAAA")
        self.assertAlmostEqual(result["rouge_2"], 3/5)
        self.assertAlmostEqual(result["rouge_3"], 2/4)
        self.assertAlmostEqual(result["bleu"], math.exp(1-6/4))
        long_prediction = score("AAAAAA", "AAAA")
        self.assertEqual(long_prediction["rouge"], 1)
        self.assertAlmostEqual(long_prediction["bleu_1"], 4/6)

    def test_empty_prediction_and_zero_ngram(self):
        self.assertTrue(all(value == 0 for value in score("", "ACGT").values()))
        result = score("AAAA", "ACGT")
        self.assertEqual(result["bleu_2"], 0)
        self.assertEqual(result["bleu_3"], 0)
        self.assertAlmostEqual(result["bleu"], (1/4)/3)

    def test_reject_invalid_reference(self):
        with self.assertRaises(ValueError):
            score("ACGT", "")
        with self.assertRaises(ValueError):
            score("ACGT", "ACGN")


if __name__ == "__main__":
    unittest.main()
