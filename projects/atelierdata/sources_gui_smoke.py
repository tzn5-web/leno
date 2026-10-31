"""Windows Tkinter GUI smoke test for external sources. No browser or network usage."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import tkinter as tk
import webbrowser
from technical_sources_gui import open_sources_window
from technical_sources import SOURCES

class DummyApp:
    vid=None
    def __init__(self,root):
        self.root=root
        self.db=None

def main():
    opened=[]
    real=webbrowser.open_new_tab
    webbrowser.open_new_tab=lambda uri:opened.append(uri)
    root=tk.Tk()
    root.withdraw()
    try:
        ui=open_sources_window(DummyApp(root))
        root.update_idletasks()
        assert len(ui.sources_tree.get_children())==len(SOURCES)
        assert ui.sources_make.get()=="Toate"
        ui.sources_make.set("Opel")
        root.update_idletasks()
        opel_ids=ui.sources_tree.get_children()
        assert "autodoc" in opel_ids
        assert "stellantis_servicebox" in opel_ids
        assert "charm" not in opel_ids
        ui.sources_search.set("Mitsubishi")
        assert len(ui.sources_tree.get_children())==0
        ui.sources_search.set("")
        ui.sources_make.set("Mitsubishi")
        assert "mmc_lancer" in ui.sources_tree.get_children()
        assert opened==[], "Catalog must never open URLs automatically"
        ui.destroy()
        print("SOURCES_GUI_SMOKE=PASS")
    finally:
        root.destroy()
        webbrowser.open_new_tab=real

if __name__=="__main__":
    main()
