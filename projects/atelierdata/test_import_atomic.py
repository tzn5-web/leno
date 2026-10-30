import csv
import tempfile
import unittest
from pathlib import Path
from atelierdata import Store, import_records


class AtomicImportTests(unittest.TestCase):
    def test_invalid_row_does_not_commit_valid_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            store=Store(root/'catalog.sqlite3')
            file=root/'batch.csv'
            with file.open('w',encoding='utf-8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=['make','model','category','title'])
                writer.writeheader()
                writer.writerow({'make':'A','model':'B','category':'Motor','title':'Valid'})
                writer.writerow({'make':'A','model':'','category':'Motor','title':'Invalid'})
            result=import_records(store,file)
            self.assertEqual(result['inserted'],0)
            self.assertEqual(len(result['rejected']),1)
            self.assertEqual(store.stats(),[0,0])
            store.close()

    def test_valid_rows_commit_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            store=Store(root/'catalog.sqlite3')
            file=root/'batch.csv'
            file.write_text('make,model,category,title\nA,B,Motor,One\nA,B,Motor,Two\n',encoding='utf-8')
            result=import_records(store,file)
            self.assertEqual(result['inserted'],2)
            self.assertEqual(store.stats(),[1,2])
            store.close()


if __name__=='__main__':
    unittest.main()
