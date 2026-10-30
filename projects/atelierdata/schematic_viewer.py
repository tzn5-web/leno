"""Read-only verified local schematic viewer for user-owned PNG/JPEG documents.

No Autodata content is bundled; files must be explicitly attached to vehicle articles.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from atelierdata_extensions import attach_document, list_documents, resolve_document

IMAGE_EXT = {".png", ".jpg", ".jpeg"}
SCHEME_CATEGORIES = ("Scheme electrice", "Siguranțe și relee")
MAX_IMAGE_PIXELS = 24_000_000
MIN_ZOOM = 0.15
MAX_ZOOM = 4.0


def clamp_zoom(value):
    return min(MAX_ZOOM, max(MIN_ZOOM, float(value)))


def image_metadata(path):
    """Check both the file signature and decoded dimensions before displaying."""
    from PIL import Image, UnidentifiedImageError
    source = Path(path)
    if source.suffix.lower() not in IMAGE_EXT or not source.is_file() or source.is_symlink():
        raise ValueError("Numai imagini PNG/JPEG verificate")
    if source.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Imaginea depășește 32 MiB")
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(source) as picture:
            expected="PNG" if source.suffix.lower()==".png" else "JPEG"
            if picture.format != expected:
                raise ValueError("Formatul imaginii nu corespunde extensiei")
            w, h = picture.size
            if w <= 0 or h <= 0 or w * h > MAX_IMAGE_PIXELS:
                raise ValueError("Imagine prea mare sau invalidă")
            picture.verify()
        return {"width": w, "height": h, "format": source.suffix.lower()}
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Imagine invalidă sau deteriorată") from exc


def fit_zoom(width, height, viewport_width, viewport_height):
    if min(width, height) <= 0:
        raise ValueError("Dimensiuni imagine invalide")
    if min(viewport_width, viewport_height) <= 0:
        return 1.0
    return clamp_zoom(min(viewport_width / width, viewport_height / height, 1.0))


def list_schematic_articles(store, vehicle_id, search=""):
    query = ("SELECT id,vehicle_id,category,title,content,source FROM articles WHERE "
             "vehicle_id=? AND category IN (?,?)")
    params = [vehicle_id, *SCHEME_CATEGORIES]
    if search:
        query += " AND (title LIKE ? OR content LIKE ? OR source LIKE ?)"
        params += ["%" + search + "%"] * 3
    return store.db.execute(query + " ORDER BY category,title,id", params).fetchall()


def open_schematics_window(app, editor_class):
    """Show the original AtelierData vehicle schematics browser (no bundled drawings)."""
    from tkinter import ttk, messagebox, filedialog
    from PIL import Image, ImageTk
    tk = app.tk
    vehicle_id = app.vid
    if vehicle_id is None:
        messagebox.showinfo("Vehicul necesar", "Selectează un vehicul.")
        return None

    window = tk.Toplevel(app.root)
    window.title("AtelierData — scheme și documentație")
    window.geometry("1250x780")
    window.minsize(970,600)
    window.transient(app.root)
    header = ttk.Frame(window,padding=(14,12))
    header.pack(fill="x")
    ttk.Label(header,text="SCHEME ȘI DOCUMENTE TEHNICE",
              font=("Segoe UI Semibold",16)).pack(anchor="w")
    ttk.Label(header,text="Doar documente proprii sau licențiate. Verificare SHA256 la deschidere."
             ).pack(anchor="w",pady=(5,0))
    panel = ttk.PanedWindow(window,orient="horizontal")
    panel.pack(fill="both",expand=True,padx=14,pady=8)
    sidebar = ttk.Frame(panel)
    body = ttk.Frame(panel)
    panel.add(sidebar,weight=3)
    panel.add(body,weight=7)

    q = tk.StringVar()
    ttk.Label(sidebar,text="Caută scheme, titlu sau sursă").pack(anchor="w")
    entry=ttk.Entry(sidebar,textvariable=q)
    entry.pack(fill="x",pady=7,padx=(0,7))
    schematics=ttk.Treeview(sidebar,show="tree",height=14,selectmode="browse")
    schematics.pack(fill="both",expand=True,padx=(0,7))
    ttk.Label(sidebar,text="Fișiere asociate schemei").pack(anchor="w",pady=(9,3))
    attachments=ttk.Treeview(sidebar,show="tree",height=8,selectmode="browse")
    attachments.pack(fill="both",expand=False,padx=(0,7))
    state={"article_id":None, "image":None, "image_path":None, "zoom":1.0,
           "photo":None}
    window.schematics_tree=schematics
    window.attachments_tree=attachments

    title = tk.StringVar(value="Selectează o schemă")
    ttk.Label(body,textvariable=title,font=("Segoe UI Semibold",13)).pack(anchor="w",pady=(0,6))
    details = tk.Text(body,height=4,wrap="word",state="disabled",
                      font=("Segoe UI",10),bg="#1a2a42",fg="#eef5ff",relief="flat")
    details.pack(fill="x",pady=(0,8))
    frame=ttk.Frame(body)
    frame.pack(fill="both",expand=True)
    canvas=tk.Canvas(frame,bg="#0e1624",highlightthickness=0)
    vscroll=ttk.Scrollbar(frame,orient="vertical",command=canvas.yview)
    hscroll=ttk.Scrollbar(frame,orient="horizontal",command=canvas.xview)
    canvas.configure(xscrollcommand=hscroll.set,yscrollcommand=vscroll.set)
    frame.rowconfigure(0,weight=1)
    frame.columnconfigure(0,weight=1)
    canvas.grid(row=0,column=0,sticky="nsew")
    vscroll.grid(row=0,column=1,sticky="ns")
    hscroll.grid(row=1,column=0,sticky="ew")
    window.diagram_canvas=canvas
    zoom_label = tk.StringVar(value="Fără imagine selectată")
    ttk.Label(body,textvariable=zoom_label).pack(anchor="w",pady=(5,4))

    def set_details(value):
        details.config(state="normal")
        details.delete("1.0","end")
        details.insert("1.0",value)
        details.config(state="disabled")

    def refresh_schematics(prefer=None):
        schematics.delete(*schematics.get_children())
        for row in list_schematic_articles(app.db,vehicle_id,q.get()):
            schematics.insert("","end",iid=str(row["id"]),
                              text=f"[{row['category']}] {row['title']}")
        if prefer is not None and schematics.exists(str(prefer)):
            schematics.selection_set(str(prefer))
            schematics.see(str(prefer))
            select_article()

    def clear_image():
        state["image"]=None
        state["image_path"]=None
        state["photo"]=None
        canvas.delete("all")
        canvas.configure(scrollregion=(0,0,0,0))
        zoom_label.set("Fără imagine selectată")

    def select_article(event=None):
        selected=schematics.selection()
        clear_image()
        attachments.delete(*attachments.get_children())
        state["article_id"]=int(selected[0]) if selected else None
        if state["article_id"] is None:
            title.set("Selectează o schemă")
            set_details("")
            return
        article=app.db.get_article(state["article_id"])
        if article is None or article["vehicle_id"]!=vehicle_id:
            state["article_id"]=None
            return
        title.set(article["title"])
        set_details(f"Categorie: {article['category']}\nSursă: {article['source'] or 'neprecizată'}"
                    f"\n{article['content']}")
        for item in list_documents(app.db,article["id"]):
            ext=Path(item["path"]).suffix.lower()
            label="Imagine" if ext in IMAGE_EXT else "Document"
            attachments.insert("","end",iid=str(item["id"]),text=f"{label}: {item['path'][:20]}")
    schematics.bind("<<TreeviewSelect>>",select_article)
    q.trace_add("write",lambda *_:refresh_schematics())

    def render():
        image=state["image"]
        if image is None:return
        w=max(1,round(image.width*state["zoom"]))
        h=max(1,round(image.height*state["zoom"]))
        if w*h>MAX_IMAGE_PIXELS*MAX_ZOOM*MAX_ZOOM:
            raise ValueError("Zoom prea mare")
        resized=image.resize((w,h),Image.Resampling.LANCZOS)
        photo=ImageTk.PhotoImage(resized,master=window)
        state["photo"]=photo
        canvas.delete("all")
        canvas.create_image(0,0,anchor="nw",image=photo)
        canvas.config(scrollregion=(0,0,w,h))
        zoom_label.set(f"{image.width} × {image.height} px  •  {round(state['zoom']*100)}%")

    def open_selected(event=None):
        items=attachments.selection()
        if not items:
            return
        try:
            path=resolve_document(app.db,int(items[0]))
            if path.suffix.lower() not in IMAGE_EXT:
                if sys.platform=="win32":
                    os.startfile(str(path))
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open",str(path)])
                return
            image_metadata(path)
            Image.MAX_IMAGE_PIXELS=MAX_IMAGE_PIXELS
            with Image.open(path) as picture:
                picture.load()
                state["image"]=picture.convert("RGB")
            state["image_path"]=path
            state["zoom"]=fit_zoom(state["image"].width,state["image"].height,
                                   max(1,canvas.winfo_width()-15),max(1,canvas.winfo_height()-15))
            render()
        except Exception as exc:
            messagebox.showerror("Fișier invalid",str(exc),parent=window)
    def preview_selection(event=None):
        selection=attachments.selection()
        if not selection:return
        row=app.db.db.execute("SELECT path FROM attachments WHERE id=?",
                              (int(selection[0]),)).fetchone()
        if row is None:return
        if Path(row["path"]).suffix.lower() in IMAGE_EXT:
            open_selected()
        else:
            clear_image()
            zoom_label.set("PDF / text — apasă Deschide pentru aplicația Windows")

    attachments.bind("<Double-1>",open_selected)
    attachments.bind("<<TreeviewSelect>>",preview_selection)

    def change_zoom(factor):
        if state["image"] is None:return
        state["zoom"]=clamp_zoom(state["zoom"]*factor)
        render()

    def fit():
        if state["image"] is None:return
        state["zoom"]=fit_zoom(state["image"].width,state["image"].height,
                               max(1,canvas.winfo_width()-15),max(1,canvas.winfo_height()-15))
        render()

    def add_schematic():
        fields=[("category","Categorie (Scheme electrice / Siguranțe și relee)","Scheme electrice"),
                ("title","Titlu document *",""),
                ("source","Sursa documentului / licență *","")]
        data=editor_class(window,"Document schemă nou",fields,body=("content","")).value
        if data is None:return
        if data["category"] not in SCHEME_CATEGORIES or not data["source"]:
            return messagebox.showerror("Sursă necesară","Alege o categorie permisă și o sursă.",
                                        parent=window)
        try:
            aid=app.db.add_article(vehicle_id,**data)
            refresh_schematics(aid)
            app.refresh()
        except Exception as exc:
            messagebox.showerror("Eroare",str(exc),parent=window)

    def attach_image():
        aid=state["article_id"]
        if aid is None:
            return messagebox.showinfo("Selectează schema","Alege o schemă din stânga.",parent=window)
        filename=filedialog.askopenfilename(parent=window,filetypes=[
                    ("Scheme PNG/JPEG/PDF","*.png *.jpg *.jpeg *.pdf")])
        if not filename:return
        try:
            ext=Path(filename).suffix.lower()
            if ext in IMAGE_EXT:image_metadata(filename)
            attach_document(app.db,aid,filename)
            select_article()
        except Exception as exc:
            messagebox.showerror("Atașament invalid",str(exc),parent=window)

    toolbar=ttk.Frame(body)
    toolbar.pack(fill="x",pady=(7,0))
    for label,callback in [("+ Schemă",add_schematic),
                           ("Atașează fișier",attach_image),
                           ("Deschide",open_selected),
                           ("Potrivește",fit),
                           ("−",lambda:change_zoom(0.8)),
                           ("+",lambda:change_zoom(1.25))]:
        ttk.Button(toolbar,text=label,command=callback).pack(side="left",padx=(0,7))

    def scroll_zoom(event):
        if state["image"] is None:return
        change_zoom(1.15 if event.delta>0 else 1/1.15)
    canvas.bind("<Control-MouseWheel>",scroll_zoom)
    refresh_schematics()
    return window
