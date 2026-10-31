"""Synthetic-only regression tests for unified catalog search."""
import sqlite3
import unittest
from catalog_search import search_catalog


class StoreFixture:
    def __init__(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE vehicles(id INTEGER PRIMARY KEY,make TEXT,model TEXT,engine TEXT,years TEXT,fuel TEXT,variant TEXT);
            CREATE TABLE articles(id INTEGER PRIMARY KEY,vehicle_id INTEGER,category TEXT,title TEXT,content TEXT,source TEXT);
            CREATE TABLE procedures(id INTEGER PRIMARY KEY,vehicle_id INTEGER,system TEXT,title TEXT,summary TEXT,precautions TEXT,source TEXT);
            CREATE TABLE procedure_steps(id INTEGER PRIMARY KEY,procedure_id INTEGER,instruction TEXT,safety_note TEXT);
            CREATE TABLE technical_specs(id INTEGER PRIMARY KEY,vehicle_id INTEGER,system TEXT,parameter TEXT,value TEXT,unit TEXT,conditions TEXT,source TEXT);
            CREATE TABLE dtc_entries(id INTEGER PRIMARY KEY,vehicle_id INTEGER,code TEXT,system TEXT,title TEXT,symptoms TEXT,possible_causes TEXT,checks TEXT,notes TEXT,source TEXT);
            CREATE TABLE maintenance_plans(id INTEGER PRIMARY KEY,vehicle_id INTEGER,title TEXT,system TEXT,conditions TEXT,source TEXT);
            INSERT INTO vehicles VALUES(1,'Mitsubishi','Lancer','4A91','2008','Petrol','1.5');
            INSERT INTO vehicles VALUES(2,'Mitsubishi','Colt','4A90','2007','Petrol','1.3');
            INSERT INTO articles VALUES(10,1,'Scheme','Circuit %_','Test & wiring','user');
            INSERT INTO articles VALUES(11,2,'Scheme','Other','Unrelated','user');
            INSERT INTO procedures VALUES(20,1,'Brake','Replace part','Authorized text','Stop engine','manual');
            INSERT INTO procedure_steps VALUES(30,20,'Check %_ pressure','Use PPE');
            INSERT INTO technical_specs VALUES(40,1,'Engine','Voltage','12.5','V','Engine off','manual');
            INSERT INTO dtc_entries VALUES(50,1,'P0123','Engine','Sensor circuit','Diagnostic','Fault','Check wiring','Note','manual');
            INSERT INTO maintenance_plans VALUES(60,1,'Inspect filter','Engine','Yearly','manual');
        ''')


class CatalogSearchTests(unittest.TestCase):
    def setUp(self):
        self.store = StoreFixture()

    def tearDown(self):
        self.store.db.close()

    def test_all_modules_and_vehicles(self):
        cases = [('Lancer', 'vehicle'), ('Circuit', 'document'),
                 ('pressure', 'procedure'), ('Voltage', 'specification'),
                 ('P0123', 'dtc'), ('filter', 'maintenance')]
        for term, kind in cases:
            with self.subTest(term=term):
                rows = search_catalog(self.store, term)
                self.assertIn(kind, {row['kind'] for row in rows})
                self.assertTrue(all('vehicle_id' in row and 'source' in row for row in rows))

    def test_literal_wildcards_and_escape(self):
        self.assertEqual([(r['kind'],r['record_id']) for r in search_catalog(self.store,'%_')],
                         [('document',10),('procedure',20)])
        self.assertEqual(search_catalog(self.store,'\\'),[])
        self.assertEqual(search_catalog(self.store,'%not present'),[])

    def test_vehicle_scope_and_no_writes(self):
        before = self.store.db.total_changes
        self.assertEqual(search_catalog(self.store,'Other',vehicle_id=1),[])
        self.assertEqual([(r['kind'],r['vehicle_id']) for r in search_catalog(self.store,'Other',vehicle_id=2)],
                         [('document',2)])
        self.assertEqual(self.store.db.total_changes,before)

    def test_pagination_is_stable(self):
        rows = search_catalog(self.store,'Mitsubishi',limit=2)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows + search_catalog(self.store,'Mitsubishi',limit=2,offset=2),
                         search_catalog(self.store,'Mitsubishi',limit=4))

    def test_rejects_invalid_inputs(self):
        for value in ('', '   ', 'x'*201, '\x00', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                search_catalog(self.store,value)
        for kwargs in ({'vehicle_id':True},{'vehicle_id':-1},{'limit':0},
                       {'limit':201},{'offset':-1},{'offset':True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                search_catalog(self.store,'x',**kwargs)


if __name__ == '__main__':
    unittest.main()
