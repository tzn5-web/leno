"""Regression tests for sourced procedure search; synthetic data only."""
import tempfile
import unittest
from pathlib import Path

from atelierdata import Store
from repair_procedures import create_procedure, add_step, list_procedures


class ProcedureSearchIsolationTests(unittest.TestCase):
    def test_foreign_document_text_is_not_searchable_through_corrupt_link(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 'isolation.sqlite3')
            try:
                owned = store.add_vehicle('TEST', 'OWNED')
                foreign = store.add_vehicle('TEST', 'FOREIGN')
                pid = create_procedure(store, owned, 'Synthetic', 'Owned procedure', source='TEST')
                step = add_step(store, pid, 'Neutral synthetic instruction')
                foreign_doc = store.add_article(foreign, 'Scheme electrice',
                    'FOREIGN_SECRET_TOKEN', 'PRIVATE_BODY_TOKEN', 'FOREIGN_SOURCE_TOKEN')
                store.db.execute('UPDATE procedure_steps SET article_id=? WHERE id=?',
                                 (foreign_doc, step))
                store.db.commit()
                for term in ('FOREIGN_SECRET_TOKEN', 'PRIVATE_BODY_TOKEN',
                             'FOREIGN_SOURCE_TOKEN'):
                    with self.subTest(term=term):
                        self.assertEqual(list_procedures(store, owned, term), [])
                self.assertEqual([r['id'] for r in list_procedures(
                    store, owned, 'owned procedure')], [pid])
                self.assertEqual(store.db.execute('PRAGMA quick_check').fetchone()[0], 'ok')
            finally:
                store.close()

    def test_unicode_casefold_and_literal_wildcards_in_step_search(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 'unicode.sqlite3')
            try:
                vid = store.add_vehicle('TEST', 'MODEL')
                pid = create_procedure(store, vid, 'Synthetic', 'Procedure', source='TEST')
                add_step(store, pid, 'Große %_ SAFETY TOKEN')
                for term in ('GROSSE', '%_', 'safety token'):
                    with self.subTest(term=term):
                        self.assertEqual([r['id'] for r in list_procedures(
                            store, vid, term)], [pid])
                self.assertEqual(list_procedures(store, vid, '%X'), [])
            finally:
                store.close()


if __name__ == '__main__':
    unittest.main()
