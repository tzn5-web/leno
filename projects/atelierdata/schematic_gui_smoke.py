"""Windows GUI smoke: schematic search, image preview, and stale-attachment denial.

Uses synthetic, user-owned test data only.
"""
from __future__ import annotations

import tempfile
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from atelierdata import Store
from atelierdata_extensions import attach_document
from schematic_viewer import open_schematics_window


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        store = Store(folder / "smoke.sqlite3")
        root = tk.Tk()
        root.withdraw()
        try:
            vehicle = store.add_vehicle("TEST", "SYNTHETIC")
            other = store.add_vehicle("OTHER", "SYNTHETIC")
            article = store.add_article(
                vehicle, "Scheme electrice", "Straße 100%_",
                "Synthetic content", "TEST LICENSE")
            foreign = store.add_article(
                other, "Scheme electrice", "Other diagram", "", "TEST LICENSE")
            image_path = folder / "diagram.png"
            Image.new("RGB", (64, 32), (10, 30, 50)).save(image_path)
            attachment = attach_document(store, article, image_path)
            app = SimpleNamespace(tk=tk, root=root, db=store, vid=vehicle,
                                  refresh=lambda: None)
            viewer = open_schematics_window(
                app, lambda *_: None, selected_article_id=article)
            root.update()
            assert viewer.schematics_tree.selection() == (str(article),)
            assert len(viewer.diagram_canvas.find_all()) == 1
            viewer.schematic_search_var.set("STRASSE")
            root.update()
            assert viewer.schematics_tree.exists(str(article))
            viewer.schematic_search_var.set("100%X")
            root.update()
            assert not viewer.schematics_tree.get_children()
            viewer.schematic_search_var.set("")
            root.update()
            viewer.schematics_tree.selection_set(str(article))
            root.update()
            viewer.attachments_tree.selection_set(str(attachment))
            # Simulate a database change after the viewer has listed the file.
            store.db.execute(
                "UPDATE attachments SET article_id=? WHERE id=?",
                (foreign, attachment))
            store.db.commit()
            with patch("tkinter.messagebox.showerror") as error:
                viewer.open_selected_attachment()
                error.assert_called_once()
            assert len(viewer.diagram_canvas.find_all()) == 0
            viewer.destroy()
        finally:
            root.destroy()
            store.close()
    print("SCHEMATIC_GUI_SMOKE=PASS")


if __name__ == "__main__":
    main()
