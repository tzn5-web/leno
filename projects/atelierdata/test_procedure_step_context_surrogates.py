"""SQLite GUI-context regression: lone Unicode surrogates must not render.

Uses only synthetic data and a minimal read-only SQLite store.
"""
import sqlite3
import unittest
from types import SimpleNamespace

from procedure_step_context import step_context_text


class LoneSurrogateContextTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE procedures(id INTEGER PRIMARY KEY, vehicle_id INTEGER,
                                    precautions TEXT, source TEXT);
            CREATE TABLE procedure_steps(id INTEGER PRIMARY KEY, procedure_id INTEGER,
                                         step_number INTEGER, instruction TEXT,
                                         safety_note TEXT, article_id INTEGER);
            CREATE TABLE articles(id INTEGER PRIMARY KEY, vehicle_id INTEGER,
                                  title TEXT, source TEXT);
            INSERT INTO procedures VALUES(1, 10, 'General warning', 'Own source');
            INSERT INTO procedure_steps VALUES(2, 1, 1, 'Synthetic instruction',
                                               'Step warning', 3);
            INSERT INTO articles VALUES(3, 10, 'Own diagram', 'Own document');
        """)
        self.store = SimpleNamespace(db=self.db)

    def tearDown(self):
        self.db.close()

    def test_surrogate_instruction_is_rejected(self):
        # SQLite's Python adapter rejects unpaired surrogates in TEXT. Simulate
        # corrupted imported rows through the display validator directly.
        from procedure_step_context import _safe_display_text, _has_unsafe_display_controls
        for surrogate in ("\\ud800", "\\udfff"):
            with self.subTest(surrogate=repr(surrogate)):
                self.assertTrue(_has_unsafe_display_controls(surrogate))
                self.assertIsNone(_safe_display_text("Title " + surrogate))

    def test_valid_unicode_and_read_only_sqlite_context(self):
        self.db.execute("UPDATE procedures SET precautions=? WHERE id=1",
                        ("Atenție: verifică documentația autorizată",))
        before = self.db.total_changes
        result = step_context_text(self.store, 10, 1, 2)
        self.assertIn("Atenție: verifică documentația autorizată", result)
        self.assertIn("DOCUMENT ASOCIAT: Own diagram", result)
        self.assertEqual(before, self.db.total_changes)
        self.assertEqual(self.db.execute("PRAGMA integrity_check").fetchone()[0], "ok")


if __name__ == "__main__":
    unittest.main()
