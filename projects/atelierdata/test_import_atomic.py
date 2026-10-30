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


    def test_backup_roundtrip_and_tamper_rejection(self):
        import zipfile
        from atelierdata_backup import backup_bundle, restore_bundle
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            store=Store(root/'source'/'catalog.sqlite3')
            vid=store.add_vehicle('Example','Model')
            store.add_article(vid,'Motor','User document','Authorized text')
            backup=root/'backup.zip'
            backup_bundle(store,backup)
            store.close()
            restored=restore_bundle(backup,root/'restored')
            check=Store(restored)
            self.assertEqual(check.stats(),[1,1])
            check.close()
            tampered=root/'tampered.zip'
            with zipfile.ZipFile(backup) as src, zipfile.ZipFile(tampered,'w') as dst:
                for info in src.infolist():
                    data=src.read(info.filename)
                    if info.filename=='database.sqlite3':
                        data=b'corrupt'+data
                    dst.writestr(info.filename,data)
            with self.assertRaises(ValueError):
                restore_bundle(tampered,root/'rejected')
            self.assertFalse((root/'rejected').exists())



if __name__=='__main__':
    unittest.main()
