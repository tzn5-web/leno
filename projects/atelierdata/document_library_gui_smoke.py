"""Windows/Tk smoke test for the real offline document library widget."""
import tempfile
import tkinter as tk
from unittest.mock import patch
from pathlib import Path
from atelierdata import Store
from document_library import import_local_file, set_metadata
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
            win.library_year.set("invalid")
            root.update_idletasks()
            assert not win.library_tree.get_children(), "Invalid year must clear stale results"
            assert "Filtru invalid" in win.library_status.get()
            assert "Selectează un document" in win.library_details.get("1.0","end")
            win.library_year.set("2008")
            root.update_idletasks()
            assert len(win.library_tree.get_children())==1
            attachment_id=int(win.library_tree.get_children()[0])
            win.library_tree.selection_set(str(attachment_id))
            root.update_idletasks()
            # Preflight is explicit, read-only and must never launch a viewer.
            before=store.db.total_changes
            with patch("document_library_gui.os.startfile") as launch:
                result=win.library_verify_selected()
                assert result["ok"], result
                assert not launch.called, "Preflight must not open a file"
            assert store.db.total_changes==before, "Preflight must not write SQLite"
            assert "SHA256 valid" in win.library_status.get()
            # The real Windows launch must be blocked if the current rights
            # declaration is revoked after the search result was selected.
            with patch("document_library_gui.os.startfile") as launch, \
                 patch("document_library_gui.messagebox.showerror") as error:
                win.library_open_verified()
                assert launch.called and not error.called
            set_metadata(store,attachment_id,"Manual de atelier",
                         "Straße %_ 4A91","Local synthetic fixture",
                         rights_basis="neconfirmat")
            with patch("document_library_gui.os.startfile") as launch, \
                 patch("document_library_gui.messagebox.showerror") as error:
                result=win.library_verify_selected()
                assert not result["ok"] and error.called
                assert not launch.called
                assert "eșuată" in win.library_status.get()
            with patch("document_library_gui.os.startfile") as launch, \
                 patch("document_library_gui.messagebox.showerror") as error:
                win.library_open_verified()
                assert not launch.called, "Unconfirmed rights must block launch"
                assert error.called, "Unconfirmed rights must show a GUI error"
            set_metadata(store,attachment_id,"Manual de atelier",
                         "Straße %_ 4A91","Local synthetic fixture",
                         rights_basis="document_propriu")
            foreign_vehicle=store.add_vehicle("SYNTHETIC","OTHER")
            foreign_article=store.add_article(
                foreign_vehicle,"Manual de atelier","Foreign synthetic fixture",
                "","OWNED")
            store.db.execute("UPDATE attachments SET article_id=? WHERE id=?",
                                (foreign_article,attachment_id))
            store.db.commit()
            with patch("document_library_gui.os.startfile") as launch, \
                 patch("document_library_gui.messagebox.showerror") as error:
                result=win.library_verify_selected()
                assert not result["ok"] and error.called
                assert not launch.called, "Stale selection must fail preflight"
            with patch("document_library_gui.os.startfile") as launch, \
                 patch("document_library_gui.messagebox.showerror") as error:
                win.library_open_verified()
                assert not launch.called, "Stale attachment must not open"
                assert error.called, "Stale selection must report an error"
            # A file named .pdf but containing executable-like bytes must not
            # be launched even when its stored SHA256 and declared rights match.
            masquerade=Path(directory)/"masquerade.pdf"
            masquerade.write_bytes(b"MZ" + bytes([0x90, 0]) + b"synthetic")
            forged_id=import_local_file(
                store,vid,masquerade,"Manual de atelier",
                "masquerade synthetic fixture","Local synthetic fixture",
                rights_basis="document_propriu")
            win.library_search.set("masquerade")
            root.update_idletasks()
            assert len(win.library_tree.get_children())==1
            assert int(win.library_tree.get_children()[0])==forged_id
            win.library_tree.selection_set(str(forged_id))
            root.update_idletasks()
            before=store.db.total_changes
            with patch("document_library_gui.os.startfile") as launch, \
                 patch("document_library_gui.messagebox.showerror") as error:
                result=win.library_verify_selected()
                assert not result["ok"] and "Semnătură" in result["message"]
                assert error.called and not launch.called
                win.library_open_verified()
                assert not launch.called, "Disguised PDF must not launch"
            assert store.db.total_changes==before, "Signature checks must be read-only"
            # The single-file importer accepts TXT bytes for inventory, but
            # the GUI must refuse an executable header disguised as .txt.
            disguised_txt = Path(directory)/"masquerade_txt.txt"
            disguised_txt.write_bytes(b"MZ" + bytes([0x90, 0]) + b"synthetic")
            txt_id = import_local_file(
                store, vid, disguised_txt, "Manual de atelier",
                "binary TXT synthetic fixture", "Local synthetic fixture",
                rights_basis="document_propriu")
            win.library_search.set("binary TXT synthetic fixture")
            root.update_idletasks()
            assert len(win.library_tree.get_children()) == 1
            assert int(win.library_tree.get_children()[0]) == txt_id
            win.library_tree.selection_set(str(txt_id))
            root.update_idletasks()
            before = store.db.total_changes
            with patch("document_library_gui.os.startfile") as launch, \
                 patch("document_library_gui.messagebox.showerror") as error:
                result = win.library_verify_selected()
                assert not result["ok"] and "TXT nu pare text" in result["message"]
                assert error.called and not launch.called
                win.library_open_verified()
                assert not launch.called, "Binary TXT must not launch"
            assert store.db.total_changes == before, "TXT preflight must be read-only"
            # Authorized TXT is previewed inside Tk without invoking the OS
            # viewer; the same selected row must fail after rights revocation.
            preview_source=Path(directory)/"preview_valid.txt"
            preview_source.write_text("Pași sintetici — numai test\\n",encoding="utf-8")
            preview_id=import_local_file(
                store,vid,preview_source,"Manual de atelier",
                "preview authorized fixture","Local synthetic fixture",
                rights_basis="document_propriu")
            win.library_search.set("preview authorized fixture")
            root.update_idletasks()
            assert len(win.library_tree.get_children())==1
            win.library_tree.selection_set(str(preview_id))
            root.update_idletasks()
            before=store.db.total_changes
            with patch("document_library_gui.os.startfile") as launch:
                preview=win.library_preview_text()
                assert preview is not None, "Authorized TXT preview must open"
                assert "Pași sintetici" in preview.preview_text_widget.get("1.0","end")
                assert not launch.called, "Internal preview must not start an OS viewer"
                preview.destroy()
            assert store.db.total_changes==before, "Preview must be read-only"
            set_metadata(store,preview_id,"Manual de atelier",
                         "preview authorized fixture","Local synthetic fixture",
                         rights_basis="neconfirmat")
            with patch("document_library_gui.messagebox.showerror") as error, \
                 patch("document_library_gui.os.startfile") as launch:
                assert win.library_preview_text() is None
                assert error.called and not launch.called
            assert store.db.total_changes>=before
            # A generated, user-owned PNG must preview in Tk without launching
            # an OS viewer. Revocation after selection must block preview.
            from PIL import Image
            image_source=Path(directory)/"preview_owned.png"
            Image.new("RGB",(4,3),(15,40,80)).save(image_source)
            image_id=import_local_file(
                store,vid,image_source,"Manual de atelier",
                "preview image fixture","Local synthetic fixture",
                rights_basis="document_propriu")
            win.library_search.set("preview image fixture")
            root.update_idletasks()
            assert len(win.library_tree.get_children())==1
            win.library_tree.selection_set(str(image_id))
            root.update_idletasks()
            before_image=store.db.total_changes
            with patch("document_library_gui.os.startfile") as launch:
                image_window=win.library_preview_image()
                assert image_window is not None, "Authorized image must preview"
                assert image_window.preview_image.width()==4
                assert image_window.preview_image.height()==3
                assert not launch.called, "Image preview must remain internal"
                image_window.destroy()
            assert store.db.total_changes==before_image
            set_metadata(store,image_id,"Manual de atelier",
                         "preview image fixture","Local synthetic fixture",
                         rights_basis="neconfirmat")
            after_revocation=store.db.total_changes
            with patch("document_library_gui.messagebox.showerror") as error, \
                 patch("document_library_gui.os.startfile") as launch:
                assert win.library_preview_image() is None
                assert error.called and not launch.called
            assert store.db.total_changes==after_revocation
            win.destroy()
            print("DOCUMENT_LIBRARY_GUI_SMOKE=PASS")
        finally:
            store.close()
            root.destroy()

if __name__=="__main__":
    main()
