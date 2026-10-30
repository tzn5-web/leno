"""Regression tests for inert, authorized repair-procedure exports."""
import json
import tempfile
import unittest
from pathlib import Path
from atelierdata import Store
from repair_procedures import ensure_schema,create_procedure,add_step
from repair_export import export_procedures_json,export_procedure_html,procedure_html

class RepairExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.store=Store(self.root/"data.sqlite3")
        self.addCleanup(self.store.close)
        ensure_schema(self.store)
        self.vehicle=self.store.add_vehicle("SYNTHETIC","MODEL","TEST ENGINE")
        self.procedure=create_procedure(
            self.store,self.vehicle,"Test system","<script>alert(1)</script>",
            "Test & description","Warning <b>not real</b>","Source & TEST")
        self.article=self.store.add_article(
            self.vehicle,"Scheme electrice","Reference <img src=x onerror=alert(1)>",
            "Synthetic drawing","TEST")
        add_step(self.store,self.procedure,"First <iframe src=x></iframe>",
                 "Warning & test",article_id=self.article)
        add_step(self.store,self.procedure,"Second step")

    def test_html_is_escaped_offline_and_ordered(self):
        rendered=procedure_html(self.store,self.procedure)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;",rendered)
        self.assertNotIn("<script>",rendered)
        self.assertNotIn("<iframe",rendered)
        self.assertNotIn("<img",rendered)
        self.assertIn("default-src 'none'",rendered)
        self.assertIn("Source &amp; TEST",rendered)
        self.assertIn("Warning &amp; test",rendered)
        self.assertIn("Document asociat",rendered)
        self.assertLess(rendered.index("First &lt;iframe"),rendered.index("Second step"))
        target=self.root/"print.html"
        self.assertEqual(export_procedure_html(self.store,self.procedure,target),target)
        self.assertEqual(target.read_text(encoding="utf-8"),rendered)

    def test_json_export_preserves_provenance_and_link_metadata(self):
        target=self.root/"procedures.json"
        self.assertEqual(export_procedures_json(self.store,target),1)
        payload=json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"],"atelierdata-repair-procedures-v1")
        self.assertFalse(payload["attachment_bytes_included"])
        row=payload["procedures"][0]
        self.assertEqual(row["source"],"Source & TEST")
        self.assertEqual(row["vehicle"]["engine"],"TEST ENGINE")
        self.assertEqual([s["step_number"] for s in row["steps"]],[1,2])
        self.assertEqual(row["steps"][0]["reference_title"],
                         "Reference <img src=x onerror=alert(1)>")
        self.assertEqual(row["steps"][0]["safety_note"],"Warning & test")

    def test_rejects_db_overwrite_missing_procedure_and_invalid_suffix(self):
        with self.assertRaises(ValueError):
            export_procedures_json(self.store,self.store.path)
        with self.assertRaises(ValueError):
            export_procedure_html(self.store,self.procedure,self.store.path)
        with self.assertRaises(ValueError):
            procedure_html(self.store,999999)
        with self.assertRaises(ValueError):
            export_procedure_html(self.store,self.procedure,self.root/"wrong.txt")
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0],"ok")

    def test_filter_by_vehicle(self):
        other=self.store.add_vehicle("SECOND","TEST")
        create_procedure(self.store,other,"Test","Other procedure",source="Synthetic")
        target=self.root/"filtered.json"
        self.assertEqual(export_procedures_json(self.store,target,self.vehicle),1)
        self.assertEqual(export_procedures_json(self.store,target),2)

if __name__=="__main__":
    unittest.main()
