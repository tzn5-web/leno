"""Regression: a detail-render error must not erase a live SQLite step."""
import ast
from pathlib import Path
import unittest


class DetailFailureTests(unittest.TestCase):
    def _run(self, live, foreign_reference=False):
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
            def __init__(self):
                self.last_query = None
            def execute(self, sql, params):
                assert "procedure_steps" in sql
                if "authorized_article_id" in sql:
                    assert params == (11, 7, 1)
                    self.last_query = "reference"
                else:
                    assert params == (11, 7)
                    self.last_query = "live"
                return self
            def fetchone(self):
                if self.last_query == "reference":
                    return {"article_id": 42, "authorized_article_id": None} if foreign_reference else {"article_id": None, "authorized_article_id": None}
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

    def test_foreign_reference_warns_without_leaking_document_metadata(self):
        rows, messages = self._run(True, foreign_reference=True)
        self.assertEqual(rows, ["11"])
        self.assertIn("AVERTISMENT REFERINȚĂ", messages[0])
        self.assertNotIn("42", messages[0])

    def test_deleted_row_is_removed(self):
        rows, messages = self._run(False)
        self.assertEqual(rows, [])
        self.assertIn("Pasul nu mai aparține procedurii", messages[0])


if __name__ == "__main__":
    unittest.main()
