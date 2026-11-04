"""Regression for queued Tk selection events after step reordering."""
import ast
from pathlib import Path
import unittest


class SelectionStabilityTests(unittest.TestCase):
    def test_selection_callback_does_not_rebuild_for_same_procedure(self):
        source = Path(__file__).with_name('repair_procedures_gui.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        outer = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                     and node.name == 'open_procedures_window')
        callback = next(node for node in outer.body if isinstance(node, ast.FunctionDef)
                        and node.name == 'selection')
        # Exercise the real callback body with minimal Tk/SQLite-free stand-ins.
        module = ast.Module(body=[callback], type_ignores=[])
        namespace = {'state': {'pid': 7}, 'selected_step_id': None,
                     'selected_procedure_id': None}
        class Tree:
            def __init__(self):
                self.selected = ('7',)
            def selection(self):
                return self.selected
            def exists(self, iid):
                return iid == '7'
        namespace['procedures'] = Tree()
        refreshes = []
        namespace['refresh_steps'] = lambda prefer=None: refreshes.append(prefer)
        exec(compile(ast.fix_missing_locations(module), '<selection>', 'exec'), namespace)
        namespace['selection']()
        self.assertEqual(refreshes, [])
        self.assertEqual(namespace['state']['pid'], 7)
        namespace['procedures'].selected = ('8',)
        namespace['selection']()
        self.assertEqual(namespace['state']['pid'], 8)
        self.assertEqual(refreshes, [None])


if __name__ == '__main__':
    unittest.main()
