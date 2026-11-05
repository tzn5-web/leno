"""Regression guard for the packaged Windows invalid-reference GUI smoke path."""
from pathlib import Path
import unittest


class InvalidReferenceSmokeTests(unittest.TestCase):
    def test_smoke_restores_parent_and_child_before_asserting_warning(self):
        source = Path(__file__).with_name("atelierdata.py").read_text(encoding="utf-8")
        start = source.index("foreign_vehicle=ui.db.add_vehicle('FOREIGN SYNTHETIC','GUI TEST')")
        end = source.index("PROCEDURES_GUI_INVALID_REFERENCE_WARNING_MISSING", start)
        block = source[start:end]
        self.assertIn("window.refresh_steps(step_id, procedure_id=pid)", block)
        self.assertIn("window.steps_tree.selection_set(str(step_id))", block)
        self.assertIn("window.render_selected_step()", block)
        self.assertLess(block.index("window.render_selected_step()"),
                        block.index("shown=window.procedure_detail_text.get"))
        self.assertIn("UPDATE articles SET vehicle_id=?", block)


if __name__ == "__main__":
    unittest.main()
