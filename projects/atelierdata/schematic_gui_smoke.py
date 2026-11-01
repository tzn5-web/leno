"""Windows GUI smoke: schematic search, image preview, and stale-attachment denial.

Uses synthetic, user-owned test data only.
"""
from __future__ import annotations

import tempfile
import struct
import zlib
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
            # A checksum-valid PNG may advertise bomb-sized dimensions.
            oversized_path = folder / "oversized.png"
            payload = bytearray(image_path.read_bytes())
            payload[16:24] = struct.pack(">II", 12000, 12000)
            payload[29:33] = struct.pack(">I", zlib.crc32(payload[12:29]) & 0xffffffff)
            oversized_path.write_bytes(payload)
            oversized = attach_document(store, article, oversized_path)
            app = SimpleNamespace(tk=tk, root=root, db=store, vid=vehicle,
                                  refresh=lambda: None)
            # A stale/untyped vehicle ID must fail before Tk creates a popup.
            with patch("tkinter.Toplevel") as popup:
                for bad in (True, float(vehicle), str(vehicle), 0):
                    try:
                        open_schematics_window(
                            app, lambda *_: None, vehicle_id=bad)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError("Invalid vehicle ID accepted")
                popup.assert_not_called()
            viewer = open_schematics_window(
                app, lambda *_: None, selected_article_id=article)
            root.update()
            assert viewer.schematics_tree.selection() == (str(article),)
            assert len(viewer.diagram_canvas.find_all()) == 1
            viewer.schematic_search_var.set("STRASSE")
            root.update()
            assert viewer.schematics_tree.selection() == (str(article),)
            assert viewer.attachments_tree.get_children() == (str(attachment), str(oversized))
            assert len(viewer.diagram_canvas.find_all()) == 1
            with patch("tkinter.messagebox.showerror") as error:
                viewer.attachments_tree.selection_set(str(oversized))
                root.update()
                assert error.called, "Oversized PNG must show a GUI error"
            assert not viewer.diagram_canvas.find_all(), "Rejected image left a preview"
            # Force a tiny preview budget to exercise the actual Tk resize
            # path, not merely the pure dimension calculation.
            with patch("schematic_viewer.MAX_RENDER_PIXELS", 512):
                viewer.attachments_tree.selection_set(str(attachment))
                root.update()
                items = viewer.diagram_canvas.find_all()
                assert len(items) == 1
                photo_name = viewer.diagram_canvas.itemcget(items[0], "image")
                displayed_width = int(root.tk.call("image", "width", photo_name))
                displayed_height = int(root.tk.call("image", "height", photo_name))
                assert displayed_width * displayed_height <= 512, (
                    "Tk preview exceeded the configured pixel budget")
            viewer.schematic_search_var.set("100%X")
            root.update()
            assert not viewer.schematics_tree.get_children()
            assert not viewer.attachments_tree.get_children(), "Stale attachments after filter"
            assert not viewer.diagram_canvas.find_all(), "Stale image after filter"
            assert viewer.schematic_title_var.get() == "Selectează o schemă"
            assert not viewer.schematic_details_text.get("1.0", "end").strip()
            viewer.schematic_search_var.set("")
            root.update()
            assert viewer.schematics_tree.exists(str(article))
            assert not viewer.attachments_tree.get_children()
            viewer.schematics_tree.selection_set(str(article))
            root.update()
            assert viewer.attachments_tree.get_children() == (str(attachment), str(oversized))
            assert len(viewer.diagram_canvas.find_all()) == 1
            viewer.schematic_search_var.set("x" * 201)
            root.update()
            assert not viewer.attachments_tree.get_children(), "Invalid search retained attachment"
            assert not viewer.diagram_canvas.find_all(), "Invalid search retained preview"
            assert "invalidă" in viewer.schematic_title_var.get()
            assert not viewer.schematic_details_text.get("1.0", "end").strip()
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
