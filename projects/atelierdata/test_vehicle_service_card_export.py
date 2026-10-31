"""Print/export regression: values are sourced, alternative rows distinct, HTML escaped."""
import tempfile
import unittest
from pathlib import Path
from atelierdata import Store
from vehicle_service_card import FIELD_DATA,add_value
from vehicle_service_card_export import export_vehicle_card_html

class ServiceCardExportTests(unittest.TestCase):
    def test_complete_missing_and_html_escaping(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            store=Store(root/"data.sqlite3")
            try:
                car=store.add_vehicle("Opel","Astra","Z16XER","2009","Benzină")
                i=next(i for i,f in enumerate(FIELD_DATA)
                       if f[0]=="Antigel" and f[1]=="Tip / omologare antigel")
                add_value(store,car,i,"TEST <COOLANT>", "Source & test page <1>",
                          conditions="Synthetic only")
                path=root/"sheet.html"
                report=export_vehicle_card_html(store,car,path)
                text=path.read_text("utf-8")
                self.assertIn("NECONFIRMAT",text)
                self.assertIn("Z16XER",text)
                self.assertIn("TEST &lt;COOLANT&gt;",text)
                self.assertIn("Source &amp; test page &lt;1&gt;",text)
                self.assertNotIn("TEST <COOLANT>",text)
                self.assertEqual(report["sourced"],1)
                self.assertEqual(report["fields"],len(FIELD_DATA))
                with self.assertRaises(ValueError):
                    export_vehicle_card_html(store,car,root/"raw.exe")
            finally:store.close()

if __name__=="__main__":unittest.main()
