import unittest
from metrics import score_cds, score_labels


class CodonAccuracyTests(unittest.TestCase):
    def setUp(self):
        self.record = {"protein": "MG", "reference_cds": "ATGGGATAA", "reference_labels": "jqw"}

    def test_stop_codon_equivalence(self):
        for stop in ("TAA", "TAG", "TGA"):
            self.assertEqual(score_cds("ATGGGA" + stop, self.record), (3, 3, 2, 2, 1))

    def test_missing_and_partial_codons_count_wrong(self):
        self.assertEqual(score_cds("ATGGG", self.record), (1, 3, 1, 2, 0))
        self.assertEqual(score_cds("", self.record), (0, 3, 0, 2, 0))

    def test_extra_codons_ignored_without_alignment(self):
        self.assertEqual(score_cds("ATGGGATAATTT", self.record), (3, 3, 2, 2, 1))
        self.assertEqual(score_cds("TTTATGGGATAA", self.record), (0, 3, 0, 2, 0))

    def test_synonymous_codon_difference_is_incorrect(self):
        self.assertEqual(score_cds("ATGGGTTGA", self.record), (2, 3, 1, 2, 1))

    def test_label_accuracy_including_dummy_stop(self):
        self.assertEqual(score_labels("jqw", self.record), (3, 3, 2, 2, 1))
        self.assertEqual(score_labels("jkw", self.record), (2, 3, 1, 2, 1))
        self.assertEqual(score_labels("?qw", self.record), (2, 3, 1, 2, 1))


if __name__ == "__main__":
    unittest.main()
