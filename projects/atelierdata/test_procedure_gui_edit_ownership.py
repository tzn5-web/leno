"""Regression for editing a step that was moved/deleted after GUI selection."""
import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).with_name("repair_procedures_gui.py")


class StepEditOwnershipTests(unittest.TestCase):
    def test_edit_query_scoped_to_active_procedure(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name == "open_procedures_window")
        form = next(n for n in outer.body if isinstance(n, ast.FunctionDef)
                    and n.name == "step_form")
        statements = ast.get_source_segment(SOURCE.read_text(encoding="utf-8"), form)
        self.assertIn("WHERE id=? AND procedure_id=?", statements)
        self.assertIn("(int(selected[0]),pid)", statements)
        self.assertIn("if current is None:", statements)
        self.assertIn("refresh_steps()", statements)
        self.assertIn("Pasul nu mai aparține procedurii selectate.", statements)


if __name__ == "__main__":
    unittest.main()
