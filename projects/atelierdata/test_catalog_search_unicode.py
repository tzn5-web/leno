"""Unicode and literal search regressions using synthetic, user-owned SQLite rows."""
import unittest

from catalog_search import search_catalog
from test_catalog_search import StoreFixture


class UnicodeCatalogTests(unittest.TestCase):
    def setUp(self):
        self.store = StoreFixture()
        db = self.store.db
        db.execute("UPDATE vehicles SET make='ȘKODA',model='Fábia' WHERE id=1")
        db.execute("UPDATE articles SET title='Schemă ÎNCĂRCARE' WHERE id=10")
        db.execute("UPDATE procedure_steps SET instruction='Verifică ÎNTREȚINEREA' WHERE id=30")
        db.execute("UPDATE technical_specs SET parameter='TURAȚIE' WHERE id=40")
        db.execute("UPDATE dtc_entries SET title='Diagnoză' WHERE id=50")
        db.execute("UPDATE maintenance_plans SET title='Revizie periodică' WHERE id=60")
        db.commit()

    def tearDown(self):
        self.store.db.close()

    def test_vehicle_and_document_casefold(self):
        self.assertEqual([(r['kind'], r['record_id']) for r in
                          search_catalog(self.store, 'șkoda')], [('vehicle', 1)])
        self.assertEqual([(r['kind'], r['record_id']) for r in
                          search_catalog(self.store, 'încărcare')], [('document', 10)])

    def test_procedure_steps_are_unicode_and_vehicle_scoped(self):
        self.assertEqual([(r['kind'], r['record_id']) for r in
                          search_catalog(self.store, 'întreținerea', vehicle_id=1)],
                         [('procedure', 20)])
        self.assertEqual(search_catalog(self.store, 'întreținerea', vehicle_id=2), [])

    def test_other_modules_casefold(self):
        for term, kind in [('turație', 'specification'),
                           ('diagnoză', 'dtc'), ('revizie', 'maintenance')]:
            with self.subTest(term=term):
                self.assertEqual([r['kind'] for r in search_catalog(self.store, term)],
                                 [kind])

    def test_metacharacters_remain_literal(self):
        self.assertEqual(search_catalog(self.store, '%not present'), [])
        self.assertEqual(search_catalog(self.store, '_not present'), [])
        self.store.db.execute("UPDATE articles SET title='100%_literal' WHERE id=10")
        self.assertEqual([(r['kind'], r['record_id']) for r in
                          search_catalog(self.store, '%_')], [('document', 10)])

    def test_pagination_and_read_only(self):
        all_rows = search_catalog(self.store, 'a', limit=200)
        pages = (search_catalog(self.store, 'a', limit=2, offset=0) +
                 search_catalog(self.store, 'a', limit=2, offset=2))
        self.assertEqual(pages, all_rows[:4])
        before = self.store.db.total_changes
        search_catalog(self.store, 'încărcare')
        self.assertEqual(self.store.db.total_changes, before)

    def test_rejects_invalid_scopes(self):
        for kwargs in ({'vehicle_id': True}, {'vehicle_id': 1.0},
                       {'limit': 0}, {'offset': -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                search_catalog(self.store, 'x', **kwargs)


if __name__ == '__main__':
    unittest.main()
