"""Regression tests: original AtelierData features only, synthetic data."""
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atelierdata import Store, import_records
from atelierdata_extensions import (
    attach_document, export_records, integrity_check, list_documents, resolve_document
)


class ExtensionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / 'data.sqlite3')
        self.addCleanup(self.store.close)
        self.vid = self.store.add_vehicle('Mitsubishi', 'Lancer', '4A91', '2008', 'Benzină')
        self.aid = self.store.add_article(
            self.vid, 'Note atelier', 'Test document', 'Exemplu creat în test', 'manual')

    def test_export_import_integrity_and_indexes(self):
        destination = self.root / 'export.json'
        self.assertEqual(export_records(self.store, destination), 1)
        payload = json.loads(destination.read_text(encoding='utf-8'))
        self.assertEqual(payload['schema'], 'atelierdata-records-v1')
        self.assertEqual(payload['records'][0]['engine'], '4A91')
        copy = Store(self.root / 'copy.sqlite3')
        try:
            self.assertEqual(import_records(copy, destination)['inserted'], 1)
            self.assertEqual(copy.stats(), [1, 1])
            self.assertTrue(integrity_check(copy)['ok'])
            indexes = {row[1] for row in copy.db.execute("PRAGMA index_list('articles')")}
            self.assertIn('idx_articles_vehicle_category', indexes)
        finally:
            copy.close()
        with self.assertRaises(ValueError):
            export_records(self.store, self.store.path)

    def test_managed_attachment_and_integrity(self):
        source = self.root / 'sample.pdf'
        source.write_bytes(b'%PDF-1.4\n%%EOF\n')
        attachment_id = attach_document(self.store, self.aid, source)
        self.assertEqual(attach_document(self.store, self.aid, source), attachment_id)
        self.assertEqual(len(list_documents(self.store, self.aid)), 1)
        managed = resolve_document(self.store, attachment_id)
        self.assertEqual(managed.read_bytes(), source.read_bytes())
        managed.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            resolve_document(self.store, attachment_id)

    def test_attachment_rejects_unsafe_input(self):
        executable = self.root / 'unsafe.exe'
        executable.write_bytes(b'MZ')
        with self.assertRaises(ValueError):
            attach_document(self.store, self.aid, executable)
        pdf = self.root / 'safe.pdf'
        pdf.write_bytes(b'%PDF-1.4')
        with self.assertRaises(ValueError):
            attach_document(self.store, 999999, pdf)
        self.store.db.execute(
            "INSERT INTO attachments(article_id,path) VALUES(?,?)",
            (self.aid, '../../escape.pdf'))
        self.store.db.commit()
        bad = self.store.db.execute(
            "SELECT id FROM attachments WHERE path='../../escape.pdf'").fetchone()[0]
        with self.assertRaises(ValueError):
            resolve_document(self.store, bad)

    def test_cli_export_import_and_check(self):
        script = str(Path(__file__).with_name('atelierdata.py'))
        export = self.root / 'cli.json'
        run = subprocess.run([sys.executable, script, '--db-path', str(self.store.path),
                              '--export-json', str(export)],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('EXPORT_JSON=PASS', run.stdout)
        dest = self.root / 'cli_import.sqlite3'
        run = subprocess.run([sys.executable, script, '--db-path', str(dest),
                              '--import-records', str(export)],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        run = subprocess.run([sys.executable, script, '--db-path', str(dest),
                              '--check-db'],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('"ok": true', run.stdout)


if __name__ == '__main__':
    unittest.main()
