"""Only synthetic fixtures; never import proprietary samples."""
import unittest
from idf_stride_hypotheses import compare_stride_hypotheses


class StrideHypothesisTests(unittest.TestCase):
    def test_19_byte_repetition(self):
        sample = (b'ABCDEFGH' + b'x' * 11) * 20
        result = compare_stride_hypotheses(sample)
        self.assertGreaterEqual(result['hypotheses']['19']['longest_run_tokens'], 20)
        self.assertEqual(result['hypotheses']['21']['longest_run_tokens'], 0)
        self.assertFalse(result['idf_decoder_proven'])
        self.assertNotIn('ABCDEFGH', str(result))

    def test_21_byte_repetition(self):
        sample = (b'ABCDEFGH' + b'y' * 13) * 20
        result = compare_stride_hypotheses(sample)
        self.assertGreaterEqual(result['hypotheses']['21']['longest_run_tokens'], 20)
        self.assertEqual(result['hypotheses']['19']['longest_run_tokens'], 0)

    def test_no_false_evidence_on_short_sample(self):
        result = compare_stride_hypotheses(b'abcdefgh')
        self.assertEqual(result['hypotheses']['19']['qualified_runs'], 0)

    def test_constant_data_is_flagged_as_confounder(self):
        result = compare_stride_hypotheses(b'Z' * 1024)
        self.assertEqual(result['distinct_byte_values'], 1)
        for hypothesis in result['hypotheses'].values():
            self.assertTrue(hypothesis['low_diversity_confounder'])
            self.assertGreater(hypothesis['qualified_runs'], 0)
        self.assertFalse(result['idf_decoder_proven'])

    def test_repeated_structured_fixture_is_not_low_diversity(self):
        sample = (b'ABCDEFGH' + b'x' * 11) * 20
        result = compare_stride_hypotheses(sample)
        self.assertFalse(result['hypotheses']['19']['low_diversity_confounder'])

    def test_bounded_and_invalid_inputs(self):
        with self.assertRaises(ValueError):
            compare_stride_hypotheses(b'a' * (256 * 1024 + 1))
        with self.assertRaises(ValueError):
            compare_stride_hypotheses(b'abc', (0,))
        with self.assertRaises(ValueError):
            compare_stride_hypotheses(b'abc', (True,))


if __name__ == '__main__':
    unittest.main()
