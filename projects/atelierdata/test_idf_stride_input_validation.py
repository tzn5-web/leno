"""Input-validation regression tests; synthetic-only, no private IDF bytes."""
import unittest
from idf_stride_hypotheses import compare_stride_hypotheses


class StrideInputValidationTests(unittest.TestCase):
    def test_rejects_mutable_and_nonbinary_inputs(self):
        for value in (bytearray(b"ABC"), memoryview(b"ABC"), "ABC", None):
            with self.subTest(type=type(value).__name__):
                with self.assertRaises(TypeError):
                    compare_stride_hypotheses(value)

    def test_rejects_duplicate_strides(self):
        with self.assertRaises(ValueError):
            compare_stride_hypotheses(b"ABC" * 100, (19, 19))

    def test_invalid_types_remain_value_errors(self):
        for strides in ((19, 19.0), (19, False), (19, "19")):
            with self.subTest(strides=strides):
                with self.assertRaises(ValueError):
                    compare_stride_hypotheses(b"ABC" * 100, strides)

    def test_valid_sample_preserves_no_decoder_claim(self):
        report = compare_stride_hypotheses(bytes(range(128)), (19, 21))
        self.assertEqual(set(report["hypotheses"]), {"19", "21"})
        self.assertFalse(report["idf_decoder_proven"])


if __name__ == "__main__":
    unittest.main()
