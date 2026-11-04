"""Guard explicit procedure context during Windows GUI reorder restoration."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class ExplicitProcedureRestoreTests(unittest.TestCase):
    def test_refresh_steps_accepts_verified_procedure_context(self):
        tree = ast.parse((ROOT / "repair_procedures_gui.py").read_text(encoding="utf-8"))
        functions = [node for node in ast.walk(tree)
                     if isinstance(node, ast.FunctionDef) and node.name == "refresh_steps"]
        self.assertEqual(len(functions), 1)
        function = functions[0]
        self.assertIn("procedure_id", [arg.arg for arg in function.args.args])
        body = ast.get_source_segment(
            (ROOT / "repair_procedures_gui.py").read_text(encoding="utf-8"), function
        )
        self.assertIn("require_live_procedure(procedure_id)", body)
        self.assertIn('procedures.exists(str(procedure_id))', body)

    def test_windows_smoke_restores_using_procedure_id(self):
        source = (ROOT / "atelierdata.py").read_text(encoding="utf-8")
        self.assertIn("window.refresh_steps(step_id, procedure_id=pid)", source)


if __name__ == "__main__":
    unittest.main()
