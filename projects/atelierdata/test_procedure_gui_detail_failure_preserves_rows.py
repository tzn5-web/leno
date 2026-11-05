"""Regression: a detail-render error must not erase a live SQLite step."""
import ast
from pathlib import Path
import unittest


class DetailFailureTests(unittest.TestCase):
    def _run(self, live):
        source = Path(__file__).with_name("repair_procedures_gui.py").read_text(encoding="utf-8")
        outer = next(n for n in ast.walk(ast.parse(source))
                     if isinstance(n, ast.FunctionDef) and n.name == "open_procedures_window")
        callback = next(n for n in outer.body
                        if isinstance(n, ast.FunctionDef) and n.name == "render_selected_step")
        class Tree:
            rows = ["11"]
            def selection(self):
                return ("11",)
            def exists(self, key):
                return key in self.rows
            def delete(self, key):
                self.rows.remove(key)
        class DB:
            def execute(self, sql, params):
                assert "procedure_steps" in sql
                assert params == (11, 7)
                return self
            def fetchone(self):
                return (1,) if live else None
        tree = Tree()
        messages = []
        ns = dict(state={"pid": 7}, steps=tree, require_live_procedure=lambda pid: None,
                  step_context_text=lambda *args: (_ for _ in ()).throw(ValueError("invalid context")),
                  app=type("App", (), {"db": type("Store", (), {"db": DB()})()})(),
                  vehicle_id=1, render=messages.append,
                  invalidate_stale_procedure=lambda pid: self.fail("unexpected stale parent"))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[callback], type_ignores=[])),
                     "<detail>", "exec"), ns)
        ns["render_selected_step"]()
        return tree.rows, messages

    def test_live_row_survives_invalid_detail(self):
        rows, messages = self._run(True)
        self.assertEqual(rows, ["11"])
        self.assertIn("Detaliile", messages[0])

    def test_deleted_row_is_removed(self):
        rows, messages = self._run(False)
        self.assertEqual(rows, [])
        self.assertIn("Pasul nu mai aparține procedurii", messages[0])


if __name__ == "__main__":
    unittest.main()
