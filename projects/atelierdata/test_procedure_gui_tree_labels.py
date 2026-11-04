"""Regression tests for safe procedure labels in the Windows tree."""
import inspect
import unittest

from repair_procedures_gui import _safe_search_preview, open_procedures_window


class ProcedureTreeLabelTests(unittest.TestCase):
    def test_control_characters_and_bidi_are_not_rendered(self):
        system = "Motor\nINJECTED\u202e"
        title = "Schimb\u2028ulei\u2066"
        label = f"{_safe_search_preview(system, 100)} / {_safe_search_preview(title, 180)}"
        self.assertEqual(label, "Motor INJECTED / Schimb ulei")
        self.assertNotIn("\n", label)

    def test_long_labels_are_bounded(self):
        label = f"{_safe_search_preview('S' * 500, 100)} / {_safe_search_preview('T' * 500, 180)}"
        self.assertEqual(len(label), 100 + 3 + 180)

    def test_gui_tree_uses_sanitizer_for_both_fields(self):
        source = inspect.getsource(open_procedures_window)
        self.assertIn("_safe_search_preview(row['system'], 100)", source)
        self.assertIn("_safe_search_preview(row['title'], 180)", source)


if __name__ == "__main__":
    unittest.main()
