"""Synthetic regression tests for reverse procedure/document references."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from procedure_usage import list_document_usage
from repair_procedures import ensure_schema, create_procedure, add_step, move_step, delete_step


class ReverseDocumentUsageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Store(Path(temp.name) / "reverse_usage.sqlite3")
        self.addCleanup(self.store.close)
        ensure_schema(self.store)
        self.v1 = self.store.add_vehicle("TEST", "A", "FAKE")
        self.v2 = self.store.add_vehicle("TEST", "B", "FAKE")
        self.doc1 = self.store.add_article(
            self.v1, "Scheme electrice", "Schema sintetică",
            "Numai test", "Document propriu fictiv"
        )
        self.doc2 = self.store.add_article(
            self.v2, "Scheme electrice", "Schema izolată",
            "Numai test", "Document propriu fictiv"
        )
        self.p1 = create_procedure(
            self.store, self.v1, "Sistem A", "Test A",
            precautions="Avertisment fictiv", source="Autor test"
        )
        self.p2 = create_procedure(
            self.store, self.v2, "Sistem B", "Test B", source="Autor B"
        )

    def test_reverse_lookup_preserves_provenance_warning_and_step(self):
        sid = add_step(
            self.store, self.p1, "Operație fictivă",
            safety_note="Atenție fictivă", article_id=self.doc1
        )
        before = self.store.db.total_changes
        rows = list_document_usage(self.store, self.v1, self.doc1)
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["step_id"], sid)
        self.assertEqual(rows[0]["step_number"], 1)
        self.assertEqual(rows[0]["source"], "Autor test")
        self.assertEqual(rows[0]["precautions"], "Avertisment fictiv")
        self.assertEqual(rows[0]["safety_note"], "Atenție fictivă")

    def test_multiple_steps_sorted_after_reorder(self):
        a = add_step(self.store, self.p1, "Pas A", article_id=self.doc1)
        b = add_step(self.store, self.p1, "Pas B", article_id=self.doc1)
        add_step(self.store, self.p1, "Pas fără schemă")
        self.assertEqual([r["step_id"] for r in
                          list_document_usage(self.store, self.v1, self.doc1)], [a, b])
        self.assertTrue(move_step(self.store, b, -1))
        self.assertEqual([r["step_id"] for r in
                          list_document_usage(self.store, self.v1, self.doc1)], [b, a])
        delete_step(self.store, b)
        self.assertEqual([r["step_id"] for r in
                          list_document_usage(self.store, self.v1, self.doc1)], [a])

    def test_other_vehicle_document_never_visible(self):
        add_step(self.store, self.p2, "Alt vehicul", article_id=self.doc2)
        with self.assertRaises(ValueError):
            list_document_usage(self.store, self.v1, self.doc2)
        with self.assertRaises(ValueError):
            list_document_usage(self.store, self.v2, self.doc1)
        self.assertEqual(list_document_usage(self.store, self.v1, self.doc1), [])
        # Even an externally corrupted cross-vehicle step is never returned.
        sid = add_step(self.store, self.p1, "Test corupere")
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?", (self.doc2, sid)
        )
        self.store.db.commit()
        self.assertEqual(list_document_usage(self.store, self.v2, self.doc2)[0]["procedure_id"],
                         self.p2)

    def test_invalid_ids_and_missing_article(self):
        for value in (None, True, 0, -2, "1", 1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                list_document_usage(self.store, self.v1, value)
        with self.assertRaises(ValueError):
            list_document_usage(self.store, self.v1, 999999)
        with self.assertRaises(ValueError):
            list_document_usage(self.store, True, self.doc1)

    def test_deletion_and_reopen(self):
        add_step(self.store, self.p1, "Pas test", article_id=self.doc1)
        self.assertEqual(len(list_document_usage(self.store, self.v1, self.doc1)), 1)
        self.store.db.execute("DELETE FROM procedures WHERE id=?", (self.p1,))
        self.store.db.commit()
        self.assertEqual(list_document_usage(self.store, self.v1, self.doc1), [])
        self.assertEqual(self.store.db.execute("PRAGMA foreign_key_check").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
