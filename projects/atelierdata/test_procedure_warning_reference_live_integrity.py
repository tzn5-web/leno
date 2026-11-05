"""Regression tests for live warning/document ownership and SQLite read-only behavior."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from procedure_warning_reference import warning_step_reference_id
from repair_procedures import add_step, create_procedure


class WarningReferenceLiveIntegrityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "warning-integrity.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("SYNTHETIC", "ONE")
        self.other_vehicle = self.store.add_vehicle("SYNTHETIC", "TWO")
        self.article = self.store.add_article(
            self.vehicle, "Document", "Synthetic owned document",
            "No technical values", "USER-OWNED SYNTHETIC")
        self.procedure = create_procedure(
            self.store, self.vehicle, "TEST", "Synthetic procedure",
            source="USER-OWNED SYNTHETIC")
        self.step = add_step(
            self.store, self.procedure, "Synthetic instruction",
            safety_note="Synthetic warning", article_id=self.article)

    def resolve(self):
        return warning_step_reference_id(
            self.store, self.vehicle, self.procedure, self.step)

    def test_deleted_document_is_not_resolved_or_recreated(self):
        self.store.db.execute("UPDATE procedure_steps SET article_id=NULL WHERE id=?", (self.step,))
        self.store.db.execute("DELETE FROM articles WHERE id=?", (self.article,))
        self.store.db.execute("UPDATE procedure_steps SET article_id=? WHERE id=?", (self.article, self.step))
        self.store.db.commit()
        before = self.store.db.total_changes
        with self.assertRaisesRegex(ValueError, "missing or belongs"):
            self.resolve()
        self.assertEqual(self.store.db.total_changes, before)
        self.assertIsNone(self.store.db.execute(
            "SELECT id FROM articles WHERE id=?", (self.article,)).fetchone())

    def test_document_moved_to_other_vehicle_is_rejected(self):
        self.store.db.execute(
            "UPDATE articles SET vehicle_id=? WHERE id=?",
            (self.other_vehicle, self.article))
        self.store.db.commit()
        before = self.store.db.total_changes
        with self.assertRaisesRegex(ValueError, "another vehicle"):
            self.resolve()
        self.assertEqual(self.store.db.total_changes, before)

    def test_whitespace_warning_does_not_authorize_navigation(self):
        self.store.db.execute(
            "UPDATE procedure_steps SET safety_note=? WHERE id=?",
            (" \t\n ", self.step))
        self.store.db.commit()
        before = self.store.db.total_changes
        with self.assertRaisesRegex(ValueError, "no longer has"):
            self.resolve()
        self.assertEqual(self.store.db.total_changes, before)


if __name__ == "__main__":
    unittest.main()
