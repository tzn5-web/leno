"""Synthetic HTML audit export tests; no proprietary documentation or network."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from procedure_audit_html import audit_html, export_procedure_audit_html
from repair_procedures import add_step, create_procedure


class ProcedureAuditHtmlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "workshop.sqlite3")
        self.addCleanup(self.store.close)
        self.car = self.store.add_vehicle("DEMO", "CAR <img src=x onerror=alert(1)>")
        self.other = self.store.add_vehicle("OTHER", "CAR")
        self.proc = create_procedure(
            self.store, self.car, "Test <script>bad()</script>",
            "Procedure <iframe src='https://invalid.test'></iframe>",
            source='TEST <script>alert("source")</script>')
        self.step = add_step(self.store, self.proc, "Synthetic instruction")

    def test_offline_escaped_html_provenance_and_read_only(self):
        before = self.store.db.total_changes
        target = self.root / "reports" / "audit.html"
        output = export_procedure_audit_html(
            self.store, self.proc, target, self.car)
        html = target.read_text(encoding="utf-8")
        self.assertEqual(output, target)
        self.assertEqual(self.store.db.total_changes, before)
        self.assertIn("default-src 'none'", html)
        self.assertIn("form-action 'none'", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;iframe", html)
        self.assertIn("&lt;img", html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<iframe", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("http-equiv='refresh'", html)
        self.assertIn("Atașamente verificate SHA256", html)
        self.assertIn("nu include fișierele", html.lower())
        self.assertIn("Test &lt;script&gt;", html)
        self.assertIn("Erori: 0", html)

    def test_current_findings_are_reaudited(self):
        target = self.root / "report.htm"
        first = audit_html(self.store, self.proc, self.car)
        self.assertIn("Nu au fost detectate probleme", first)
        self.store.db.execute(
            "UPDATE procedure_steps SET instruction='' WHERE id=?",
            (self.step,))
        self.store.db.commit()
        export_procedure_audit_html(self.store, self.proc, target, self.car)
        updated = target.read_text(encoding="utf-8")
        self.assertIn("STEP_INSTRUCTION_MISSING", updated)
        self.assertIn("Erori: 1", updated)
        self.assertNotIn("Nu au fost detectate probleme", updated)

    def test_reject_other_vehicle_and_unknown_procedure(self):
        target = self.root / "report.html"
        with self.assertRaisesRegex(ValueError, "altui vehicul"):
            export_procedure_audit_html(self.store, self.proc, target, self.other)
        self.assertFalse(target.exists())
        with self.assertRaises(ValueError):
            export_procedure_audit_html(self.store, 999999, target, self.car)
        self.assertFalse(target.exists())

    def test_reject_extension_and_managed_storage_without_overwrite(self):
        folder = self.root / "documents"
        folder.mkdir()
        target = folder / "keep.html"
        target.write_text("KEEP", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "atașamente"):
            export_procedure_audit_html(self.store, self.proc, target, self.car)
        self.assertEqual(target.read_text(encoding="utf-8"), "KEEP")
        with self.assertRaisesRegex(ValueError, "HTML"):
            export_procedure_audit_html(
                self.store, self.proc, self.root / "not-html.txt", self.car)
        self.assertFalse((self.root / "not-html.txt").exists())

    def test_cross_vehicle_reference_not_leaked_in_report(self):
        foreign = self.store.add_article(
            self.other, "Scheme electrice", "SECRET_FOREIGN_TITLE", "SECRET_FOREIGN_BODY",
            "FOREIGN_TEST")
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (foreign, self.step))
        self.store.db.commit()
        before = self.store.db.total_changes
        html = audit_html(self.store, self.proc, self.car)
        self.assertIn("REFERENCE_OTHER_VEHICLE", html)
        self.assertNotIn("SECRET_FOREIGN_TITLE", html)
        self.assertNotIn("SECRET_FOREIGN_BODY", html)
        self.assertEqual(self.store.db.total_changes, before)

    def test_existing_file_preserved_on_failed_scope_check(self):
        target = self.root / "report.html"
        target.write_text("KEEP", encoding="utf-8")
        with self.assertRaises(ValueError):
            export_procedure_audit_html(self.store, self.proc, target, self.other)
        self.assertEqual(target.read_text(encoding="utf-8"), "KEEP")


if __name__ == "__main__":
    unittest.main()
