"""Synthetic regression tests: invalid safety/provenance is explicitly flagged.

No OEM data, repair values, or proprietary documentation.
"""
import unittest
from procedure_step_context import step_context_text


class _Cursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _Db:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, sql, args):
        self.calls.append((sql, args))
        return _Cursor(self.row)


class _Store:
    def __init__(self, **changes):
        row = dict(step_number=1, instruction="Synthetic instruction",
                   safety_note="", article_id=None, precautions="",
                   procedure_source="USER SOURCE", reference_title=None,
                   reference_source=None)
        row.update(changes)
        self.db = _Db(row)


class InvalidContextMetadataTests(unittest.TestCase):
    def test_invalid_safety_warning_is_not_silently_hidden(self):
        for value in ("Check\\u202e forged", "Line\\u2028 forged", 123):
            value = value.replace("\\u202e", "\u202e").replace("\\u2028", "\u2028") if isinstance(value, str) else value
            with self.subTest(value=repr(value)):
                store = _Store(safety_note=value)
                result = step_context_text(store, 1, 2, 3)
                self.assertIn("AVERTISMENT DATE: ATENȚIE LA ACEST PAS", result)
                self.assertNotIn("forged", result)
                self.assertEqual(len(store.db.calls), 1)
                self.assertEqual(store.db.calls[0][1], (2, 1, 3))

    def test_invalid_general_precautions_and_provenance_are_flagged(self):
        store = _Store(precautions="Unsafe\u2066content",
                       procedure_source="Source\u2029spoof")
        result = step_context_text(store, 1, 2, 3)
        self.assertIn("AVERTISMENT DATE: AVERTISMENT GENERAL", result)
        self.assertIn("AVERTISMENT DATE: SURSĂ PROCEDURĂ", result)
        self.assertNotIn("Unsafe", result)
        self.assertNotIn("spoof", result)

    def test_optional_empty_warning_is_not_flagged(self):
        store = _Store(safety_note="  ", precautions="", procedure_source="OWN")
        result = step_context_text(store, 1, 2, 3)
        self.assertNotIn("AVERTISMENT DATE:", result)
        self.assertIn("SURSĂ PROCEDURĂ: OWN", result)


if __name__ == "__main__":
    unittest.main()
