"""Synthetic-only variable-payload regression tests; no original data."""
import unittest
from idf_stride_variability import has_variable_payload_streak


class StrideVariabilityTests(unittest.TestCase):
    def test_variable_payload_all_candidate_strides(self):
        token = b"ABCD1234"
        for stride in (17, 19, 21):
            with self.subTest(stride=stride):
                sample = b"".join(
                    token + bytes([i % 251, (i * 7) % 251])
                    + b"X" * (stride - 10)
                    for i in range(64)
                )
                self.assertTrue(has_variable_payload_streak(sample, stride))

    def test_repeated_identical_records_not_promoted(self):
        for stride in (17, 19, 21):
            sample = (b"ABCD1234" + b"X" * (stride - 8)) * 64
            self.assertFalse(has_variable_payload_streak(sample, stride))

    def test_all_zero_not_promoted(self):
        self.assertFalse(has_variable_payload_streak(b"\x00" * 4096, 19))

    def test_single_varying_column_not_promoted(self):
        sample = b"".join(
            b"ABCD1234" + bytes([i]) + b"X" * 10 for i in range(64)
        )
        self.assertFalse(has_variable_payload_streak(sample, 19))

    def test_short_sample_not_promoted(self):
        self.assertFalse(has_variable_payload_streak(b"ABCD1234" + b"X" * 11, 19))

    def test_partial_final_row_not_promoted(self):
        sample = b"".join(
            b"ABCD1234" + bytes([i, i * 3]) + b"X" * 9
            for i in range(31)
        ) + b"ABCD1234"
        self.assertFalse(has_variable_payload_streak(sample, 19))


if __name__ == "__main__":
    unittest.main()
