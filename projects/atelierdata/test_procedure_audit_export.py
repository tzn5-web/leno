"""Synthetic audit export tests: no network or proprietary vehicle content."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from procedure_audit_export import export_procedure_audit_json
from repair_procedures import add_step, create_procedure


class ProcedureAuditExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "workshop.sqlite3")
        self.addCleanup(self.store.close)
        self.vehicle = self.store.add_vehicle("DEMO", "SYNTHETIC", "NOT REAL")
        self.other = self.store.add_vehicle("OTHER", "SYNTHETIC")
        self.proc = create_procedure(
            self.store, self.vehicle, "Sistem test", "Test fără valori",
            precautions="Avertisment fictiv", source="USER-OWNED TEST"
        )
        self.step = add_step(self.store, self.proc, "Pas fictiv", "Avertisment test")

    def test_json_schema_provenance_and_read_only(self):
        dest = self.root / "reports" / "audit.json"
        before = self.store.db.total_changes
        payload = export_procedure_audit_json(
            self.store, self.proc, dest, vehicle_id=self.vehicle)
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(json.loads(dest.read_text(encoding="utf-8")), payload)
        self.assertEqual(payload["schema"], "atelierdata-procedure-audit-v1")
        self.assertFalse(payload["attachment_bytes_included"])
        self.assertEqual(payload["vehicle"]["make"], "DEMO")
        self.assertEqual(payload["audit"]["source"], "USER-OWNED TEST")
        self.assertEqual(payload["audit"]["steps"], 1)
        self.assertEqual(payload["audit"]["errors"], 0)
        self.assertEqual(payload["audit"]["warnings"], 0)
        self.assertIn("not technical accuracy", payload["limitations"])

    def test_export_reflects_fresh_findings_not_stale_gui_snapshot(self):
        dest = self.root / "report.json"
        first = export_procedure_audit_json(
            self.store, self.proc, dest, self.vehicle)
        self.assertTrue(first["audit"]["ok"])
        self.store.db.execute(
            "UPDATE procedure_steps SET instruction='' WHERE id=?", (self.step,))
        self.store.db.commit()
        second = export_procedure_audit_json(
            self.store, self.proc, dest, self.vehicle)
        self.assertFalse(second["audit"]["ok"])
        self.assertIn("STEP_INSTRUCTION_MISSING",
                      {issue["code"] for issue in second["audit"]["issues"]})
        self.assertNotEqual(dest.read_text(encoding="utf-8"), "")

    def test_cross_vehicle_and_unknown_procedure_rejected_without_output(self):
        dest = self.root / "report.json"
        with self.assertRaisesRegex(ValueError, "altui vehicul"):
            export_procedure_audit_json(self.store, self.proc, dest, self.other)
        self.assertFalse(dest.exists())
        with self.assertRaisesRegex(ValueError, "nu există"):
            export_procedure_audit_json(self.store, 999999, dest, self.vehicle)
        self.assertFalse(dest.exists())

    def test_refuse_wrong_extension_and_managed_documents(self):
        with self.assertRaisesRegex(ValueError, "json"):
            export_procedure_audit_json(
                self.store, self.proc, self.root / "notes.txt", self.vehicle)
        folder = self.root / "documents"
        folder.mkdir()
        path = folder / "keep.json"
        path.write_text("untouched", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "atașamente"):
            export_procedure_audit_json(self.store, self.proc, path, self.vehicle)
        self.assertEqual(path.read_text(encoding="utf-8"), "untouched")
        self.assertFalse(list(self.root.glob(".atelierdata-export-*")))

    def test_existing_report_not_destroyed_on_validation_failure(self):
        dest = self.root / "audit.json"
        dest.write_text("KEEP", encoding="utf-8")
        with self.assertRaises(ValueError):
            export_procedure_audit_json(self.store, self.proc, dest, self.other)
        self.assertEqual(dest.read_text(encoding="utf-8"), "KEEP")


if __name__ == "__main__":
    unittest.main()
