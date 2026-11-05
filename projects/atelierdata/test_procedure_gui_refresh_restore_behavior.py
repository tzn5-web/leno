"""Behavioral regression for restoring a step after Tk parent selection disappears."""
import ast
from pathlib import Path
import unittest


class FakeTree:
    def __init__(self, children=()):
        self.rows = list(children)
        self.selected = ()
    def get_children(self):
        return tuple(self.rows)
    def delete(self, *ids):
        for iid in ids:
            self.rows.remove(iid)
        self.selected = ()
    def exists(self, iid):
        return iid in self.rows
    def selection(self):
        return self.selected
    def selection_set(self, iid):
        self.selected = (str(iid),)
    def insert(self, parent, index, iid, values):
        self.rows.append(iid)


class RefreshRestoreTests(unittest.TestCase):
    def test_explicit_live_parent_restores_child_despite_empty_selection(self):
        source = Path(__file__).with_name("repair_procedures_gui.py").read_text(encoding="utf-8")
        outer = next(node for node in ast.walk(ast.parse(source))
                     if isinstance(node, ast.FunctionDef) and node.name == "open_procedures_window")
        callback = next(node for node in outer.body
                        if isinstance(node, ast.FunctionDef) and node.name == "refresh_steps")
        procedures = FakeTree(("7",))
        steps = FakeTree()
        state = {"pid": None}
        renders = []
        class Row(dict):
            pass
        rows = [Row(id=11, step_number=1, instruction="Synthetic only",
                    safety_note="", reference_title="")]
        def require_live(pid):
            if pid != 7:
                raise ValueError("wrong parent")
        ns = dict(procedures=procedures, steps=steps, state=state,
                  require_live_procedure=require_live,
                  list_steps=lambda db, pid: rows if pid == 7 else [],
                  app=type("App", (), {"db": object()})(),
                  render=lambda value: renders.append(value),
                  render_selected_step=lambda: renders.append("step"),
                  _step_tree_values=lambda row: (row["step_number"], row["instruction"], "", ""),
                  _validate_navigation_id=lambda value, label: value,
                  vehicle_id=1, invalidate_stale_procedure=lambda pid: self.fail("stale"))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[callback], type_ignores=[])),
                     "<refresh_steps>", "exec"), ns)
        ns["refresh_steps"](prefer=11, procedure_id=7)
        self.assertEqual(steps.get_children(), ("11",))
        self.assertEqual(steps.selection(), ("11",))
        self.assertEqual(procedures.selection(), ("7",))
        self.assertEqual(state["pid"], 7)
        self.assertEqual(renders, ["step"])

    def test_hidden_parent_is_rejected_without_clearing_existing_steps(self):
        source = Path(__file__).with_name("repair_procedures_gui.py").read_text(encoding="utf-8")
        outer = next(node for node in ast.walk(ast.parse(source))
                     if isinstance(node, ast.FunctionDef) and node.name == "open_procedures_window")
        callback = next(node for node in outer.body
                        if isinstance(node, ast.FunctionDef) and node.name == "refresh_steps")
        procedures = FakeTree(("8",))
        steps = FakeTree(("existing",))
        state = {"pid": 8}
        ns = dict(procedures=procedures, steps=steps, state=state,
                  require_live_procedure=lambda pid: None,
                  list_steps=lambda *args: self.fail("must not read hidden parent"),
                  app=type("App", (), {"db": object()})(),
                  _validate_navigation_id=lambda value, label: value,
                  vehicle_id=1)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[callback], type_ignores=[])),
                     "<refresh_steps>", "exec"), ns)
        with self.assertRaisesRegex(ValueError, "vizibil"):
            ns["refresh_steps"](procedure_id=7)
        self.assertEqual(steps.get_children(), ("existing",))
        self.assertEqual(state["pid"], 8)


if __name__ == "__main__":
    unittest.main()
