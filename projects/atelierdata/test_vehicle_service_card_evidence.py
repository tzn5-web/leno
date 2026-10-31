"""Ensure PDF evidence is vehicle-scoped and never auto-committed as a specification."""
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from atelierdata import Store
from atelierdata_extensions import attach_document
from pdf_text_index import ensure_schema as ensure_pdf_schema
from vehicle_service_card import FIELD_DATA,card
from vehicle_service_card_evidence import search_evidence

class EvidenceTests(unittest.TestCase):
    def test_sources_only_and_no_invented_values(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            db=Store(base/"db.sqlite3")
            try:
                m=db.add_vehicle("Mitsubishi","Lancer","4A91","2008","Benzina")
                other=db.add_vehicle("Opel","Corsa","Z12XEP","2007","Benzina")
                path=base/"synthetic.pdf"
                path.write_bytes(b"%PDF-1.4\nSynthetic fixture only")
                a=db.add_article(m,"Date tehnice","Manual synthetic","","TEST DOCUMENT")
                att=attach_document(db,a,path)
                ensure_pdf_schema(db)
                with db.db:
                    db.db.execute("""INSERT INTO pdf_page_text(
                        attachment_id,page_number,file_sha256,content,extracted_utc)
                        VALUES(?,?,?,?,?)""",
                        (att,4,"0"*64,"Coolant synthetic SOURCE SPEC-XYZ; for test only.",
                         datetime.now(timezone.utc).isoformat()))
                index=next(i for i,f in enumerate(FIELD_DATA)
                           if f[0]=="Antigel" and f[1]=="Tip / omologare antigel")
                hits=search_evidence(db,m,index)
                self.assertEqual(len(hits),1)
                self.assertEqual(hits[0]["page_number"],4)
                self.assertEqual(hits[0]["attachment_id"],att)
                self.assertEqual(search_evidence(db,other,index),[])
                self.assertEqual(card(db,m)["values"][index],[])
                with self.assertRaises(ValueError):
                    search_evidence(db,m,999)
            finally:db.close()
if __name__=="__main__":unittest.main()
