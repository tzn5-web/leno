"""Synthetic tests for source attribution of vehicle-scoped procedure references.

No actual repair specifications or proprietary diagrams are included.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from atelierdata import Store
from repair_export import export_procedures_json, procedure_html
from repair_procedures import (
    add_step, create_procedure, ensure_schema, list_steps, procedure_text,
)


class ProcedureReferenceProvenanceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = Store(self.root / "synthetic.sqlite3")
        self.addCleanup(self.store.close)
        ensure_schema(self.store)
        self.car = self.store.add_vehicle("TEST", "VEHICLE", "DEMO")
        self.other = self.store.add_vehicle("OTHER", "VEHICLE", "DEMO")
        self.procedure = create_procedure(
            self.store, self.car, "SYNTHETIC SYSTEM", "Synthetic steps",
            source="AUTHOR-OWNED PROCEDURE")
        self.article = self.store.add_article(
            self.car, "Scheme electrice", "Drawing <test>",
            "Synthetic content only", "Licensed & authored <source>")
        self.foreign = self.store.add_article(
            self.other, "Scheme electrice", "Foreign drawing",
            "Unrelated synthetic content", "PRIVATE FOREIGN SOURCE")
        self.step = add_step(
            self.store, self.procedure, "Synthetic instruction",
            safety_note="Synthetic warning", article_id=self.article)

    def test_source_visible_in_steps_and_gui_detail_model(self):
        before = self.store.db.total_changes
        step = list_steps(self.store, self.procedure)[0]
        self.assertEqual(step["reference_source"], "Licensed & authored <source>")
        self.assertEqual(step["reference_title"], "Drawing <test>")
        detail = procedure_text(self.store, self.procedure)
        self.assertIn("SURSĂ DOCUMENT: Licensed & authored <source>", detail)
        self.assertIn("SURSĂ: AUTHOR-OWNED PROCEDURE", detail)
        self.assertIn("ATENȚIE: Synthetic warning", detail)
        self.assertEqual(self.store.db.total_changes, before)

    def test_json_and_printable_html_preserve_escaped_source(self):
        before = self.store.db.total_changes
        output = self.root / "procedures.json"
        self.assertEqual(export_procedures_json(self.store, output, self.car), 1)
        payload = json.loads(output.read_text(encoding="utf-8"))
        step = payload["procedures"][0]["steps"][0]
        self.assertEqual(step["reference_source"], "Licensed & authored <source>")
        self.assertFalse(payload["attachment_bytes_included"])
        html = procedure_html(self.store, self.procedure)
        self.assertIn("Sursă document: Licensed &amp; authored &lt;source&gt;", html)
        self.assertNotIn("Licensed & authored <source>", html)
        self.assertIn("default-src 'none'", html)
        self.assertEqual(self.store.db.total_changes, before)

    def test_corrupted_foreign_link_never_exposes_other_vehicle_source(self):
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (self.foreign, self.step))
        self.store.db.commit()
        before = self.store.db.total_changes
        row = list_steps(self.store, self.procedure)[0]
        self.assertIsNone(row["reference_title"])
        self.assertIsNone(row["reference_source"])
        self.assertNotIn("PRIVATE FOREIGN SOURCE",
                         procedure_text(self.store, self.procedure))
        self.assertNotIn("PRIVATE FOREIGN SOURCE",
                         procedure_html(self.store, self.procedure))
        output = self.root / "filtered.json"
        export_procedures_json(self.store, output, self.car)
        payload = json.loads(output.read_text(encoding="utf-8"))
        exported = payload["procedures"][0]["steps"][0]
        self.assertIsNone(exported["reference_source"])
        self.assertIsNone(exported["reference_title"])
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_tkinter_procedure_detail_and_live_reference_revocation(self):
        import tkinter as tk
        from repair_procedures_gui import open_procedures_window

        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("No graphical Tk display available: " + str(exc))
        self.addCleanup(root.destroy)
        root.withdraw()
        app = SimpleNamespace(root=root, tk=tk, db=self.store, vid=self.car)
        window = open_procedures_window(
            app, object, selected_procedure_id=self.procedure)
        self.addCleanup(window.destroy)
        window.update_idletasks()
        detail = window.procedure_detail_text.get("1.0", "end")
        self.assertIn("SURSĂ DOCUMENT: Licensed & authored <source>", detail)
        self.assertIn("Synthetic warning", detail)

        # Imported/corrupt cross-vehicle links must not remain visible after refresh.
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (self.foreign, self.step))
        self.store.db.commit()
        window.refresh_steps()
        window.update_idletasks()
        detail = window.procedure_detail_text.get("1.0", "end")
        self.assertNotIn("PRIVATE FOREIGN SOURCE", detail)
        self.assertNotIn("Licensed & authored <source>", detail)


if __name__ == "__main__":
    unittest.main()
