"""Regression coverage for repair text provenance and cross-vehicle references.

Only synthetic fixtures; no proprietary technical specifications.
"""
import sqlite3
import unittest
from types import SimpleNamespace

from repair_procedures import procedure_text, list_steps


class RepairTextReferenceSafety(unittest.TestCase):
    def setUp(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        self.addCleanup(db.close)
        db.executescript("""
            CREATE TABLE procedures(
                id INTEGER PRIMARY KEY, vehicle_id INTEGER, system TEXT,
                title TEXT, summary TEXT, precautions TEXT, source TEXT);
            CREATE TABLE procedure_steps(
                id INTEGER PRIMARY KEY, procedure_id INTEGER, step_number INTEGER,
                instruction TEXT, safety_note TEXT, article_id INTEGER);
            CREATE TABLE articles(
                id INTEGER PRIMARY KEY, vehicle_id INTEGER, category TEXT,
                title TEXT, source TEXT, content TEXT);
            INSERT INTO procedures VALUES
                (10,1,'Synthetic system','Synthetic repair','','General caution','Own notes');
            INSERT INTO articles VALUES
                (20,1,'Diagram','Authorized diagram','Licensed reference','Own text'),
                (21,2,'Other','FOREIGN SECRET','FOREIGN SOURCE','FOREIGN CONTENT');
            INSERT INTO procedure_steps VALUES
                (30,10,1,'Check synthetic item','Step caution',20),
                (31,10,2,'Inspect synthetic item','',21);
        """)
        self.store = SimpleNamespace(db=db)

    def test_valid_reference_and_warnings_visible(self):
        output = procedure_text(self.store, 10)
        for expected in ('Own notes', 'General caution', 'Step caution',
                         'Authorized diagram', 'Licensed reference'):
            self.assertIn(expected, output)

    def test_foreign_reference_metadata_not_disclosed(self):
        output = procedure_text(self.store, 10)
        self.assertIn('AVERTISMENT REFERINȚĂ', output)
        for secret in ('FOREIGN SECRET', 'FOREIGN SOURCE', 'FOREIGN CONTENT'):
            self.assertNotIn(secret, output)
        rows = list_steps(self.store, 10)
        self.assertIsNone(rows[1]['reference_title'])
        self.assertIsNone(rows[1]['reference_source'])

    def test_deleted_reference_warns_without_disclosing_metadata(self):
        self.store.db.execute('DELETE FROM articles WHERE id=20')
        output = procedure_text(self.store, 10)
        self.assertIn('AVERTISMENT REFERINȚĂ', output)
        self.assertNotIn('Authorized diagram', output)

    def test_missing_procedure_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Procedure does not exist'):
            procedure_text(self.store, 999)


if __name__ == '__main__':
    unittest.main()
