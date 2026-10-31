"""Windows Tk smoke: service-card displays 36 fields, without invented values."""
import tempfile
import tkinter as tk
from pathlib import Path
from atelierdata import Store
from vehicle_service_card_gui import open_vehicle_service_card
from vehicle_service_card import FIELD_DATA,add_value

class App:
    def __init__(self,root,db,vid):
        self.root=root
        self.db=db
        self.vid=vid

def main():
    with tempfile.TemporaryDirectory() as d:
        root=tk.Tk();root.withdraw()
        db=Store(Path(d)/"db.sqlite3")
        try:
            vid=db.add_vehicle("Mitsubishi","Lancer","4A91","2008","Benzină")
            i=next(i for i,field in enumerate(FIELD_DATA)
                   if field[0]=="Ulei motor" and field[1]=="Vâscozitate SAE")
            add_value(db,vid,i,"TEST-5W-30","SYNTHETIC SOURCE ONLY")
            window=open_vehicle_service_card(App(root,db,vid))
            root.update_idletasks()
            all_fields=[]
            for section in window.vehicle_card_tree.get_children():
                all_fields.extend(window.vehicle_card_tree.get_children(section))
            assert len(all_fields)==len(FIELD_DATA),(len(all_fields),len(FIELD_DATA))
            values=[window.vehicle_card_tree.item(item,"values") for item in all_fields]
            assert any("TEST-5W-30" in row for row in values)
            assert any("NECONFIRMAT" in row for row in values)
            assert "1 /" in window.vehicle_card_summary.get()
            window.destroy()
            print("VEHICLE_SERVICE_CARD_GUI_SMOKE=PASS")
        finally:
            db.close()
            root.destroy()

if __name__=="__main__":
    main()
