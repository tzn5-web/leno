"""Windows/Tk smoke test for the real offline document library widget."""
import tempfile
import tkinter as tk
from pathlib import Path
from atelierdata import Store
from document_library import import_local_file
from document_library_gui import open_document_library

class TestApp:
    def __init__(self,root,store,vid):
        self.root=root
        self.db=store
        self.vid=vid

def main():
    with tempfile.TemporaryDirectory() as directory:
        root=tk.Tk()
        root.withdraw()
        store=Store(Path(directory)/"atelierdata.sqlite3")
        try:
            vid=store.add_vehicle("Mitsubishi","Lancer","4A91","2008","Benzina")
            doc=Path(directory)/"example.pdf"
            doc.write_bytes(b"%PDF-1.4\n%%EOF\n")
            import_local_file(store,vid,doc,"Manual de atelier","Straße %_ 4A91",
                              "Local synthetic fixture",rights_basis="document_propriu",
                              source_url="https://example.org/synthetic%_source",
                              revision="EDITION-ß-42")
            app=TestApp(root,store,vid)
            win=open_document_library(app)
            root.update_idletasks()
            assert len(win.library_tree.get_children())==1
            item=win.library_tree.item(win.library_tree.get_children()[0])
            assert item["values"][1]=="4A91",item
            assert win.library_status.get().startswith("1 documente"),win.library_status.get()
            win.library_search.set("Not found fixture")
            root.update_idletasks()
            assert len(win.library_tree.get_children())==0
            win.library_search.set("STRASSE")
            root.update_idletasks()
            assert len(win.library_tree.get_children())==1, "Unicode search must find Straße"
            win.library_search.set("%_")
            root.update_idletasks()
            assert len(win.library_tree.get_children())==1, "Percent/underscore are literal"
            win.library_search.set("STRASSE%")
            root.update_idletasks()
            assert len(win.library_tree.get_children())==0, "Search must not expand SQL wildcards"
            for provenance_query in ("synthetic%_source", "EDITION-SS-42"):
                win.library_search.set(provenance_query)
                root.update_idletasks()
                assert len(win.library_tree.get_children())==1, (
                    "GUI must find source URL and Unicode revision: "+provenance_query)
            win.library_search.set("synthetic%_missing")
            root.update_idletasks()
            assert len(win.library_tree.get_children())==0, "GUI search must remain literal"
            win.library_search.set("4A91")
            root.update_idletasks()
            assert len(win.library_tree.get_children())==1
            win.destroy()
            print("DOCUMENT_LIBRARY_GUI_SMOKE=PASS")
        finally:
            store.close()
            root.destroy()

if __name__=="__main__":
    main()
