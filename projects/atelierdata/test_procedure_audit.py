"""Synthetic integration tests: no OEM data, network, or proprietary files."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image
from atelierdata import Store
from atelierdata_extensions import attach_document, resolve_document
from procedure_audit import audit_procedure, get_step_reference
from repair_procedures import add_step, create_procedure, update_step


class ProcedureAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "audit.sqlite3")
        self.addCleanup(self.store.close)
        self.car = self.store.add_vehicle("DEMO", "TEST CAR")
        self.other_car = self.store.add_vehicle("DEMO", "OTHER CAR")
        self.proc = create_procedure(
            self.store, self.car, "Sistem demo", "Procedură fictivă",
            source="WORKSHOP TEST DATA"
        )
        self.diagram = self.store.add_article(
            self.car, "Scheme electrice", "Diagramă sintetică", "TEST", "USER TEST"
        )
        self.step = add_step(
            self.store, self.proc, "Instrucțiune fictivă",
            safety_note="Avertisment de test", article_id=self.diagram
        )

    def _image(self):
        path = self.root / "fake-diagram.png"
        Image.new("RGB", (20, 12), (20, 30, 40)).save(path)
        return path

    def test_verified_schematic_and_reference_are_read_only(self):
        attachment_id = attach_document(self.store, self.diagram, self._image())
        before = self.store.db.total_changes
        report = audit_procedure(self.store, self.proc)
        self.assertTrue(report["ok"])
        self.assertEqual(report["errors"], 0)
        self.assertEqual(report["warnings"], 0)
        self.assertEqual(report["steps"], 1)
        self.assertEqual(report["verified_attachments"], 1)
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(get_step_reference(
            self.store, self.step, self.car, self.proc)["id"], self.diagram
        )
        self.assertEqual(resolve_document(self.store, attachment_id).suffix, ".png")

    def test_missing_image_warning_and_source_provenance(self):
        report = audit_procedure(self.store, self.proc)
        self.assertTrue(report["ok"])
        self.assertEqual(report["warnings"], 1)
        self.assertEqual(report["issues"][0]["code"], "SCHEMATIC_IMAGE_UNAVAILABLE")
        self.store.db.execute(
            "UPDATE articles SET source='' WHERE id=?", (self.diagram,)
        )
        self.store.db.commit()
        codes = {i["code"] for i in audit_procedure(self.store, self.proc)["issues"]}
        self.assertEqual(codes, {
            "SCHEMATIC_IMAGE_UNAVAILABLE", "REFERENCE_SOURCE_MISSING"
        })

    def test_sha256_valid_but_invalid_png_is_not_previewable(self):
        fake = self.root / "invalid.png"
        fake.write_bytes(b"synthetic non-image bytes")
        attach_document(self.store, self.diagram, fake)
        report = audit_procedure(self.store, self.proc)
        self.assertFalse(report["ok"])
        self.assertEqual(report["verified_attachments"], 1)
        codes = {issue["code"] for issue in report["issues"]}
        self.assertIn("SCHEMATIC_IMAGE_INVALID", codes)
        self.assertIn("SCHEMATIC_IMAGE_UNAVAILABLE", codes)

    def test_tamper_detected_without_modifying_original_file(self):
        attachment_id = attach_document(self.store, self.diagram, self._image())
        path = resolve_document(self.store, attachment_id)
        path.write_bytes(b"tampered")
        before = path.read_bytes()
        report = audit_procedure(self.store, self.proc)
        self.assertFalse(report["ok"])
        self.assertEqual(report["errors"], 1)
        self.assertEqual(report["verified_attachments"], 0)
        self.assertIn("ATTACHMENT_INTEGRITY_FAILED",
                      {i["code"] for i in report["issues"]})
        self.assertEqual(path.read_bytes(), before)

    def test_other_vehicle_reference_rejected_even_if_db_was_modified(self):
        foreign = self.store.add_article(
            self.other_car, "Scheme electrice", "Foreign", "TEST", "OTHER"
        )
        # Foreign keys alone do not enforce that an article belongs to the
        # same vehicle as its referencing procedure.
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",
            (foreign, self.step)
        )
        self.store.db.commit()
        with self.assertRaisesRegex(ValueError, "altui vehicul"):
            get_step_reference(self.store, self.step, self.car, self.proc)
        report = audit_procedure(self.store, self.proc)
        self.assertFalse(report["ok"])
        self.assertIn("REFERENCE_OTHER_VEHICLE",
                      {i["code"] for i in report["issues"]})
        self.assertEqual(report["verified_attachments"], 0)

    def test_deleted_reference_and_missing_step(self):
        self.store.delete_article(self.diagram)
        self.assertIsNone(get_step_reference(
            self.store, self.step, self.car, self.proc))
        self.assertTrue(audit_procedure(self.store, self.proc)["ok"])
        with self.assertRaises(ValueError):
            get_step_reference(self.store, self.step, self.other_car, self.proc)
        with self.assertRaises(ValueError):
            get_step_reference(self.store, 987654, self.car, self.proc)
        with self.assertRaises(ValueError):
            audit_procedure(self.store, 987654)

    def test_empty_procedure_warning_and_step_order_gap(self):
        empty = create_procedure(
            self.store, self.car, "DEMO", "Empty", source="OWNED TEST"
        )
        report = audit_procedure(self.store, empty)
        self.assertTrue(report["ok"])
        self.assertEqual(report["issues"][0]["code"], "PROCEDURE_EMPTY")
        add_step(self.store, self.proc, "Second synthetic step")
        self.store.db.execute(
            "UPDATE procedure_steps SET step_number=4 WHERE id=?", (self.step,)
        )
        self.store.db.commit()
        codes = [i["code"] for i in audit_procedure(self.store, self.proc)["issues"]]
        self.assertIn("STEP_ORDER_INVALID", codes)


if __name__ == "__main__":
    unittest.main()
