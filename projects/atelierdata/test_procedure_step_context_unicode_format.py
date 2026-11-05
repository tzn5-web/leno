"""Regression tests for Unicode format-control spoofing in step context.

Synthetic display text only; no repair specifications or licensed documents.
"""
import unittest
from procedure_step_context import _safe_display_text, _has_unsafe_display_controls, step_context_text


class _FakeCursor:
    def __init__(self, row):
        self.row = row
    def fetchone(self):
        return self.row


class _FakeDb:
    def __init__(self, row):
        self.row = row
        self.calls = []
    def execute(self, query, params):
        self.calls.append((query, params))
        return _FakeCursor(self.row)


class _FakeStore:
    def __init__(self, row):
        self.db = _FakeDb(row)


def _row(**changes):
    base = dict(step_number=1, instruction="Inspect synthetic item",
                safety_note="Use approved precautions",
                article_id=7, precautions="Follow source guidance",
                procedure_source="USER DOCUMENT", reference_title="Synthetic diagram",
                reference_source="LICENSED SOURCE")
    base.update(changes)
    return base


class StepContextUnicodeSafetyTests(unittest.TestCase):
    def test_format_controls_not_accepted_as_provenance(self):
        for control in ("\u202e", "\u202a", "\u2066", "\u200b", "\ufeff"):
            with self.subTest(control=repr(control)):
                self.assertTrue(_has_unsafe_display_controls("A" + control + "B"))
                self.assertIsNone(_safe_display_text("SOURCE " + control + " altered"))

    def test_instruction_rejects_bidi_spoof_without_write(self):
        store = _FakeStore(_row(instruction="Inspect \u202e altered"))
        with self.assertRaisesRegex(ValueError, "forbidden control"):
            step_context_text(store, 1, 2, 3)
        self.assertEqual(len(store.db.calls), 1)
        self.assertEqual(store.db.calls[0][1], (2, 1, 3))

    def test_invalid_document_title_does_not_disclose_source(self):
        store = _FakeStore(_row(reference_title="Synthetic\u2067diagram",
                                reference_source="FOREIGN SECRET"))
        output = step_context_text(store, 1, 2, 3)
        self.assertIn("AVERTISMENT REFERINȚĂ", output)
        self.assertNotIn("FOREIGN SECRET", output)
        self.assertNotIn("DOCUMENT ASOCIAT:", output)

    def test_normal_unicode_text_remains_visible(self):
        store = _FakeStore(_row(instruction="Verifică piesa sintetică",
                                reference_title="Schemă autorizată"))
        output = step_context_text(store, 1, 2, 3)
        self.assertIn("Verifică piesa sintetică", output)
        self.assertIn("Schemă autorizată", output)


if __name__ == "__main__":
    unittest.main()
