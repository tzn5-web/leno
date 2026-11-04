"""SQLite regression: blank and malformed optional step metadata never leaks into GUI text."""
import sqlite3
import unittest
from types import SimpleNamespace

from procedure_step_context import step_context_text


class StepContextOptionalMetadataTests(unittest.TestCase):
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
            INSERT INTO procedures VALUES(1,10,'   ','   ');
            INSERT INTO procedure_steps VALUES(1,1,1,'Licensed synthetic instruction','  ',1);
            INSERT INTO articles VALUES(1,10,'Licensed synthetic diagram','   ');
        """)
        self.store = SimpleNamespace(db=self.db)

    def tearDown(self):
        self.db.close()

    def test_whitespace_optional_fields_not_rendered(self):
        before = self.db.total_changes
        result = step_context_text(self.store, 10, 1, 1)
        self.assertIn("Licensed synthetic instruction", result)
        self.assertIn("DOCUMENT ASOCIAT: Licensed synthetic diagram", result)
        for label in ("SURSĂ PROCEDURĂ:", "AVERTISMENT GENERAL:",
                      "ATENȚIE LA ACEST PAS:", "SURSĂ DOCUMENT:"):
            self.assertNotIn(label, result)
        self.assertEqual(before, self.db.total_changes)

    def test_corrupt_nontext_optional_fields_not_rendered(self):
        self.db.execute("UPDATE procedures SET source=x'00ff', precautions=x'ff' WHERE id=1")
        self.db.execute("UPDATE procedure_steps SET safety_note=x'ff' WHERE id=1")
        self.db.execute("UPDATE articles SET source=x'ff' WHERE id=1")
        before = self.db.total_changes
        result = step_context_text(self.store, 10, 1, 1)
        self.assertIn("Licensed synthetic instruction", result)
        self.assertNotIn("SURSĂ PROCEDURĂ:", result)
        self.assertNotIn("AVERTISMENT GENERAL:", result)
        self.assertNotIn("ATENȚIE LA ACEST PAS:", result)
        self.assertNotIn("SURSĂ DOCUMENT:", result)
        self.assertEqual(before, self.db.total_changes)


if __name__ == "__main__":
    unittest.main()
