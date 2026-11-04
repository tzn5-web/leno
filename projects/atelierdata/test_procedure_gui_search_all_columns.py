"""Regression: every text column in search hits is safe for Tkinter."""
import ast
from pathlib import Path
import unittest


class SearchHitColumnSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).with_name("repair_procedures_gui.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                      and node.name == "_safe_search_preview")
        scope = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[])),
                     "<search-preview>", "exec"), scope)
        cls.preview = staticmethod(scope["_safe_search_preview"])
        cls.source = source

    def test_untrusted_text_is_one_line_and_bounded(self):
        for value in ("Procedura\\nINJECTAT", "Titlu\\u202eINJECTAT", "Câmp\\x00fals"):
            result = self.preview(value, 190)
            self.assertNotIn("\\n", result)
            self.assertNotIn("\\x00", result)
            self.assertNotIn("\\u202e", result)
            self.assertLessEqual(len(result), 190)

    def test_valid_romanian_is_preserved(self):
        self.assertEqual(self.preview("Întreținere și reparații"), "Întreținere și reparații")

    def test_search_table_sanitizes_title_field_and_source(self):
        self.assertIn('_safe_search_preview(hit["procedure_title"],190)', self.source)
        self.assertIn('_safe_search_preview(hit["field"],160)', self.source)
        self.assertIn('_safe_search_preview(hit["excerpt"])', self.source)
        self.assertIn('_safe_search_preview(hit["source"],190)', self.source)
        self.assertIn('type(hit["step_number"]) is int', self.source)


if __name__ == "__main__":
    unittest.main()
