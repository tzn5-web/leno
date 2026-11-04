"""SQLite regression: untrusted step instructions must not forge GUI lines."""
import sqlite3
import unittest
from types import SimpleNamespace

from procedure_step_context import step_context_text


class StepInstructionLineIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE procedures (id INTEGER PRIMARY KEY, vehicle_id INTEGER,
                                     precautions TEXT, source TEXT);
            CREATE TABLE procedure_steps (id INTEGER PRIMARY KEY, procedure_id INTEGER,
                                          step_number INTEGER, instruction TEXT,
                                          safety_note TEXT, article_id INTEGER);
            CREATE TABLE articles (id INTEGER PRIMARY KEY, vehicle_id INTEGER,
                                   title TEXT, source TEXT);
            INSERT INTO procedures VALUES (1, 10, NULL, 'Licensed source');
            INSERT INTO procedure_steps VALUES (1, 1, 1, 'Synthetic step', NULL, NULL);
        """)
        self.store = SimpleNamespace(db=self.db)

    def tearDown(self):
        self.db.close()

    def test_line_breaks_and_nul_in_instruction_fail_closed(self):
        for injected in ("Synthetic step\nPAS 999: forged",
                         "Synthetic step\rPAS 999: forged",
                         "Synthetic step\x00forged"):
            with self.subTest(injected=repr(injected)):
                self.db.execute("UPDATE procedure_steps SET instruction=? WHERE id=1",
                                (injected,))
                before = self.db.total_changes
                with self.assertRaisesRegex(ValueError, "control character"):
                    step_context_text(self.store, 10, 1, 1)
                self.assertEqual(self.db.total_changes, before)

    def test_normal_instruction_renders_and_does_not_write(self):
        self.db.execute("UPDATE procedure_steps SET instruction=? WHERE id=1",
                        ("  Synthetic authorized step  ",))
        before = self.db.total_changes
        self.assertEqual(step_context_text(self.store, 10, 1, 1),
                         "PAS 1: Synthetic authorized step\nSURSĂ PROCEDURĂ: Licensed source")
        self.assertEqual(self.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
