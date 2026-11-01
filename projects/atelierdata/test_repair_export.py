"""Regression tests for inert, authorized repair-procedure exports."""
import json
import subprocess
import sys
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

    def test_offline_checklist_tracks_steps_without_persisting_or_running_scripts(self):
        before = self.store.db.total_changes
        rendered = procedure_html(self.store, self.procedure)
        self.assertEqual(rendered.count("type='checkbox'"), 2)
        self.assertIn("id='parcurs-1'", rendered)
        self.assertIn("id='parcurs-2'", rendered)
        self.assertIn("Pasul 1 parcurs", rendered)
        self.assertIn("Pasul 2 parcurs", rendered)
        self.assertIn("Nu se salvează și nu confirmă siguranța lucrării.", rendered)
        self.assertNotIn("type='checkbox' checked", rendered)
        self.assertNotIn("<script", rendered)
        self.assertEqual(self.store.db.total_changes, before)
        self.store.db.execute(
            "DELETE FROM procedure_steps WHERE procedure_id=? AND step_number=2",
            (self.procedure,))
        self.store.db.commit()
        one_step = procedure_html(self.store, self.procedure)
        self.assertEqual(one_step.count("type='checkbox'"), 1)
        self.assertNotIn("id='parcurs-2'", one_step)
        self.store.db.execute(
            "DELETE FROM procedure_steps WHERE procedure_id=?", (self.procedure,))
        self.store.db.commit()
        empty = procedure_html(self.store, self.procedure)
        self.assertNotIn("type='checkbox'", empty)
        self.assertNotIn("Bifele marchează", empty)

    def test_document_index_groups_steps_and_redacts_foreign_references(self):
        """Offline document index links every use without exposing other vehicles."""
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? "
            "WHERE procedure_id=? AND step_number=2",
            (self.article, self.procedure))
        self.store.db.commit()
        before = self.store.db.total_changes
        rendered = procedure_html(self.store, self.procedure)
        self.assertIn("aria-label='Index documente asociate'", rendered)
        index = rendered.split("aria-label='Index documente asociate'", 1)[1].split("</aside>", 1)[0]
        self.assertEqual(index.count("<strong>Reference &lt;img"), 1)
        self.assertIn("Tip: Scheme electrice", index)
        self.assertIn("Sursă: TEST", index)
        self.assertIn("href='#pas-1'", index)
        self.assertIn("href='#pas-2'", index)
        self.assertNotIn("<img", index)
        self.assertNotIn("href='http", index)
        self.assertEqual(self.store.db.total_changes, before)

        other = self.store.add_vehicle("FOREIGN", "TEST")
        foreign = self.store.add_article(
            other, "Scheme electrice", "PRIVATE FOREIGN TITLE",
            "PRIVATE FOREIGN BODY", "PRIVATE FOREIGN SOURCE")
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? "
            "WHERE procedure_id=? AND step_number=2",
            (foreign, self.procedure))
        self.store.db.commit()
        before = self.store.db.total_changes
        rendered = procedure_html(self.store, self.procedure)
        index = rendered.split("aria-label='Index documente asociate'", 1)[1].split("</aside>", 1)[0]
        self.assertIn("href='#pas-1'", index)
        self.assertNotIn("href='#pas-2'", index)
        self.assertNotIn("PRIVATE FOREIGN", rendered)
        self.assertIn("AVERTISMENT REFERINȚĂ", rendered)
        self.assertEqual(self.store.db.total_changes, before)
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=NULL WHERE procedure_id=?",
            (self.procedure,))
        self.store.db.commit()
        self.assertNotIn("Index documente asociate",
                         procedure_html(self.store, self.procedure))
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_document_index_backlinks_are_stable_and_vehicle_scoped(self):
        """Each verified document has one anchor and every linked step returns to it."""
        second = self.store.add_article(
            self.vehicle, "Note atelier", "<svg onload=alert(1)>",
            "Synthetic content", "AUTHORIZED TEST")
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? "
            "WHERE procedure_id=? AND step_number=2",
            (self.article, self.procedure))
        self.store.db.commit()
        add_step(self.store, self.procedure, "Third synthetic step", article_id=second)
        before = self.store.db.total_changes
        rendered = procedure_html(self.store, self.procedure)
        self.assertEqual(rendered.count("id='document-1'"), 1)
        self.assertEqual(rendered.count("id='document-2'"), 1)
        self.assertEqual(rendered.count("href='#document-1'"), 2)
        self.assertEqual(rendered.count("href='#document-2'"), 1)
        self.assertIn("id='document-1'", rendered.split("Index documente asociate", 1)[1])
        self.assertIn("&lt;svg onload=alert(1)&gt;", rendered)
        self.assertNotIn("<svg", rendered)
        self.assertNotIn("href='http", rendered)
        self.assertEqual(self.store.db.total_changes, before)

        foreign = self.store.add_vehicle("OTHER", "SYNTHETIC")
        self.store.db.execute(
            "UPDATE articles SET vehicle_id=? WHERE id=?", (foreign, second))
        self.store.db.commit()
        before = self.store.db.total_changes
        redacted = procedure_html(self.store, self.procedure)
        self.assertEqual(redacted.count("id='document-1'"), 1)
        self.assertEqual(redacted.count("href='#document-1'"), 2)
        self.assertNotIn("id='document-2'", redacted)
        self.assertNotIn("href='#document-2'", redacted)
        self.assertNotIn("AUTHORIZED TEST", redacted)
        self.assertNotIn("&lt;svg onload", redacted)
        self.assertIn("AVERTISMENT REFERINȚĂ", redacted)
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_step_navigation_is_offline_ordered_and_read_only(self):
        """Each step links only to existing adjacent anchors and the contents."""
        before = self.store.db.total_changes
        rendered = procedure_html(self.store, self.procedure)
        self.assertIn("<h2 id='cuprins-pasi'>Cuprins</h2>", rendered)
        self.assertEqual(rendered.count("class='step-navigation'"), 2)
        first = rendered.split("aria-label='Navigare pas 1'", 1)[1].split("</nav>", 1)[0]
        second = rendered.split("aria-label='Navigare pas 2'", 1)[1].split("</nav>", 1)[0]
        self.assertIn("href='#pas-2'>Pasul următor", first)
        self.assertNotIn("Pasul anterior", first)
        self.assertIn("href='#pas-1'>← Pasul anterior", second)
        self.assertNotIn("Pasul următor", second)
        self.assertEqual(rendered.count("href='#cuprins-pasi'"), 2)
        self.assertIn("@media print{nav{display:none}", rendered)
        self.assertNotIn("href='http", rendered)
        self.assertEqual(self.store.db.total_changes, before)

        self.store.db.execute("DELETE FROM procedure_steps WHERE procedure_id=? AND step_number=2",
                              (self.procedure,))
        self.store.db.commit()
        one = procedure_html(self.store, self.procedure)
        self.assertEqual(one.count("class='step-navigation'"), 1)
        self.assertIn("href='#cuprins-pasi'", one)
        self.assertNotIn("Pasul următor", one)
        self.assertNotIn("Pasul anterior", one)
        self.store.db.execute("DELETE FROM procedure_steps WHERE procedure_id=?",
                              (self.procedure,))
        self.store.db.commit()
        empty = procedure_html(self.store, self.procedure)
        self.assertNotIn("step-navigation", empty.split("</style>", 1)[1])
        self.assertNotIn("cuprins-pasi", empty)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_html_step_contents_links_are_offline_and_print_friendly(self):
        rendered=procedure_html(self.store,self.procedure)
        self.assertIn("<nav aria-label='Cuprinsul pașilor'>",rendered)
        self.assertIn("href='#pas-1'",rendered)
        self.assertIn("id='pas-1'",rendered)
        self.assertIn("href='#pas-2'",rendered)
        self.assertIn("id='pas-2'",rendered)
        self.assertIn("Pasul 1</a> — Atenție",rendered)
        self.assertIn("nav{display:none}",rendered)
        self.assertLess(rendered.index("href='#pas-1'"),rendered.index("id='pas-1'"))
        self.assertNotIn("href='http",rendered)
        self.store.db.execute("DELETE FROM procedure_steps WHERE procedure_id=?",
                              (self.procedure,))
        self.store.db.commit()
        self.assertNotIn("<nav ",procedure_html(self.store,self.procedure))

    def test_multiline_steps_and_safety_notes_remain_readable_and_inert(self):
        """Line breaks must survive browser layout without allowing HTML injection."""
        instruction="Prima linie\nA doua linie <script>alert(1)</script>"
        safety="Avertisment 1\nAvertisment 2 & control"
        self.store.db.execute(
            "UPDATE procedure_steps SET instruction=?,safety_note=? "
            "WHERE procedure_id=? AND step_number=1",
            (instruction,safety,self.procedure))
        self.store.db.commit()
        rendered=procedure_html(self.store,self.procedure)
        self.assertIn("class='instruction'",rendered)
        self.assertIn(".instruction{white-space:pre-wrap;overflow-wrap:anywhere}",rendered)
        self.assertIn(".warning{border-left:5px solid #b3312a;background:#fff1ee;"
                      "padding:1rem;white-space:pre-wrap;overflow-wrap:anywhere}",rendered)
        self.assertIn("Prima linie\nA doua linie &lt;script&gt;alert(1)&lt;/script&gt;",rendered)
        self.assertIn("Avertisment 1\nAvertisment 2 &amp; control",rendered)
        self.assertNotIn("<script>",rendered)
        self.assertIn("Pasul 1</a> — Atenție — Document asociat",rendered)
        self.assertIn("href='#pas-1'",rendered)

    def test_printable_safety_index_links_only_flagged_steps(self):
        """Warnings and damaged links must be visible before the instructions."""
        foreign_vehicle = self.store.add_vehicle("FOREIGN", "SYNTHETIC")
        foreign_article = self.store.add_article(
            foreign_vehicle, "Scheme electrice", "PRIVATE FOREIGN TITLE",
            "PRIVATE FOREIGN CONTENT", "PRIVATE FOREIGN SOURCE")
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? "
            "WHERE procedure_id=? AND step_number=1",
            (foreign_article, self.procedure))
        self.store.db.commit()
        before = self.store.db.total_changes
        rendered = procedure_html(self.store, self.procedure)
        self.assertIn("aria-label='Avertismente și referințe'", rendered)
        self.assertIn("Verificări înainte de lucru", rendered)
        self.assertIn("href='#avertismente-generale'", rendered)
        self.assertIn("id='avertismente-generale'", rendered)
        self.assertLess(rendered.index("href='#avertismente-generale'"),
                        rendered.index("href='#pas-1'"))
        self.assertIn("Pasul 1</a>: Avertisment de siguranță / Referință indisponibilă",
                      rendered)
        self.assertNotIn("Pasul 2</a>:", rendered)
        self.assertLess(rendered.index("Verificări înainte de lucru"),
                        rendered.index("<h2>Pași de lucru</h2>"))
        self.assertIn(".safety-index{", rendered)
        self.assertNotIn("PRIVATE FOREIGN", rendered)
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0], "ok")
        self.store.db.execute(
            "UPDATE procedure_steps SET safety_note='', article_id=NULL "
            "WHERE procedure_id=?", (self.procedure,))
        self.store.db.commit()
        # The procedure-level precaution must remain indexed even when no
        # individual step has a warning or an invalid document.
        general_only = procedure_html(self.store, self.procedure)
        self.assertIn("Verificări înainte de lucru", general_only)
        self.assertIn("href='#avertismente-generale'", general_only)
        self.assertNotIn("Pasul 1</a>:", general_only)
        self.store.db.execute("UPDATE procedures SET precautions='' WHERE id=?",
                              (self.procedure,))
        self.store.db.commit()
        self.assertNotIn("Verificări înainte de lucru",
                         procedure_html(self.store, self.procedure))

    def test_general_precaution_is_indexed_without_step_warnings(self):
        self.store.db.execute(
            "UPDATE procedure_steps SET safety_note='', article_id=NULL "
            "WHERE procedure_id=?", (self.procedure,))
        self.store.db.commit()
        before = self.store.db.total_changes
        rendered = procedure_html(self.store, self.procedure)
        self.assertIn("href='#avertismente-generale'", rendered)
        self.assertIn("id='avertismente-generale'", rendered)
        self.assertIn("Warning &lt;b&gt;not real&lt;/b&gt;", rendered)
        self.assertNotIn("Pasul 1</a>:", rendered)
        self.assertNotIn("href='http", rendered)
        self.assertEqual(self.store.db.total_changes, before)

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

    def test_corrupt_foreign_reference_is_redacted_and_warned_in_exports(self):
        """An imported cross-vehicle link must not leak IDs or disappear silently."""
        foreign_vehicle=self.store.add_vehicle("OTHER","SYNTHETIC")
        foreign=self.store.add_article(
            foreign_vehicle,"Scheme electrice","PRIVATE FOREIGN TITLE",
            "PRIVATE FOREIGN CONTENT","PRIVATE FOREIGN SOURCE")
        step_id=self.store.db.execute(
            "SELECT id FROM procedure_steps WHERE procedure_id=? ORDER BY step_number",
            (self.procedure,)).fetchone()[0]
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE id=?",(foreign,step_id))
        self.store.db.commit()
        before=self.store.db.total_changes
        target=self.root/"redacted.json"
        self.assertEqual(export_procedures_json(self.store,target,self.vehicle),1)
        exported=json.loads(target.read_text(encoding="utf-8"))["procedures"][0]["steps"][0]
        self.assertEqual(exported["reference_status"],"invalid_or_unavailable")
        self.assertIsNone(exported["reference_article_id"])
        self.assertIsNone(exported["reference_title"])
        self.assertIsNone(exported["reference_source"])
        self.assertNotIn("PRIVATE FOREIGN",target.read_text(encoding="utf-8"))
        rendered=procedure_html(self.store,self.procedure)
        self.assertIn("AVERTISMENT REFERINȚĂ",rendered)
        self.assertIn("Referință indisponibilă",rendered)
        self.assertIn("href='#pas-1'",rendered)
        self.assertIn("verifică auditul",rendered)
        self.assertNotIn("PRIVATE FOREIGN",rendered)
        self.assertNotIn("Document asociat:",rendered)
        self.assertEqual(self.store.db.total_changes,before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0],"ok")

    def test_export_rejects_managed_attachment_destination(self):
        """A save dialog must not overwrite documents managed by SHA256."""
        managed=self.root/"documents"
        managed.mkdir()
        html_target=managed/"protected.html"
        json_target=managed/"protected.json"
        html_target.write_text("KEEP HTML",encoding="utf-8")
        json_target.write_text("KEEP JSON",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"atașamente"):
            export_procedure_html(self.store,self.procedure,html_target)
        with self.assertRaisesRegex(ValueError,"atașamente"):
            export_procedures_json(self.store,json_target)
        self.assertEqual(html_target.read_text(encoding="utf-8"),"KEEP HTML")
        self.assertEqual(json_target.read_text(encoding="utf-8"),"KEEP JSON")


    def test_verified_document_category_in_exports_and_foreign_redaction(self):
        """Expose only the category of a same-vehicle document, never a foreign one."""
        before=self.store.db.total_changes
        output=self.root/"category.json"
        export_procedures_json(self.store,output,self.vehicle)
        valid=json.loads(output.read_text(encoding="utf-8"))["procedures"][0]["steps"][0]
        self.assertEqual(valid["reference_category"],"Scheme electrice")
        self.assertIn("Tip document: Scheme electrice",procedure_html(self.store,self.procedure))
        self.assertEqual(self.store.db.total_changes,before)

        # Even hostile category text is inert in the printable HTML.
        self.store.db.execute(
            "UPDATE articles SET category=? WHERE id=?",
            ("<svg onload=alert(1)>",self.article))
        self.store.db.commit()
        escaped=procedure_html(self.store,self.procedure)
        self.assertIn("Tip document: &lt;svg onload=alert(1)&gt;",escaped)
        self.assertNotIn("<svg",escaped)

        foreign_vehicle=self.store.add_vehicle("OTHER","CATEGORY TEST")
        foreign=self.store.add_article(
            foreign_vehicle,"PRIVATE FOREIGN CATEGORY","PRIVATE FOREIGN TITLE",
            "PRIVATE FOREIGN CONTENT","PRIVATE FOREIGN SOURCE")
        self.store.db.execute(
            "UPDATE procedure_steps SET article_id=? WHERE procedure_id=? AND step_number=1",
            (foreign,self.procedure))
        self.store.db.commit()
        before=self.store.db.total_changes
        export_procedures_json(self.store,output,self.vehicle)
        redacted=json.loads(output.read_text(encoding="utf-8"))["procedures"][0]["steps"][0]
        self.assertEqual(redacted["reference_status"],"invalid_or_unavailable")
        self.assertIsNone(redacted["reference_category"])
        self.assertIsNone(redacted["reference_title"])
        self.assertIsNone(redacted["reference_source"])
        rendered=procedure_html(self.store,self.procedure)
        self.assertIn("AVERTISMENT REFERINȚĂ",rendered)
        self.assertNotIn("PRIVATE FOREIGN",rendered)
        self.assertNotIn("PRIVATE FOREIGN",output.read_text(encoding="utf-8"))
        self.assertEqual(self.store.db.total_changes,before)
        self.assertEqual(self.store.db.execute("PRAGMA quick_check").fetchone()[0],"ok")

    def test_cli_exports(self):
        script=str(Path(__file__).with_name("atelierdata.py"))
        target=self.root/"cli-procedures.json"
        run=subprocess.run([sys.executable,script,"--db-path",str(self.store.path),
                            "--export-procedures-json",str(target)],
                           capture_output=True,text=True,timeout=30)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn("EXPORT_PROCEDURES_JSON=PASS",run.stdout)
        self.assertEqual(len(json.loads(target.read_text(encoding="utf-8"))["procedures"]),1)
        html=self.root/"cli-procedure.html"
        run=subprocess.run([sys.executable,script,"--db-path",str(self.store.path),
                            "--procedure-id",str(self.procedure),
                            "--export-procedure-html",str(html)],
                           capture_output=True,text=True,timeout=30)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn("EXPORT_PROCEDURE_HTML=PASS",run.stdout)
        self.assertIn("&lt;script&gt;",html.read_text(encoding="utf-8"))

    def test_filter_by_vehicle(self):
        other=self.store.add_vehicle("SECOND","TEST")
        create_procedure(self.store,other,"Test","Other procedure",source="Synthetic")
        target=self.root/"filtered.json"
        self.assertEqual(export_procedures_json(self.store,target,self.vehicle),1)
        self.assertEqual(export_procedures_json(self.store,target),2)

if __name__=="__main__":
    unittest.main()
