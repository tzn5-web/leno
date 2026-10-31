"""AtelierData workshop atlas: vehicle-scoped specifications and in-app diagram/PDF viewer.

Manual entry only. No provider scraping, guessed vehicle information or file execution.
PDF rendering uses pypdfium2, images use Pillow. Document integrity verified before
opening by the existing SHA256-gated storage module.
"""
from __future__ import annotations
import sys
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog
from workshop_atlas import (KINDS,ensure_schema,list_facts,record_fact,delete_fact,
                            add_marker,list_markers,delete_marker)
from document_library import verified_library_file,list_library
from pdf_text_index import index_pdf,search_pdf_text

FIELDS=(
 ("system","Sistem (ex.: Frâne)"),
 ("component","Componentă / reper"),
 ("operation","Operație (ex.: montare)"),
 ("value","Valoare exactă (nu ghici)"),
 ("unit","Unitate (Nm, °, litri etc.)"),
 ("stages","Etape / unghi / secvență"),
 ("conditions","Condiții / model piesă / stare"),
 ("component_location","Locație fizică"),
 ("notes","Notă tehnică"),
 ("source_name","Sursa originală exactă"),
 ("source_url","URL HTTPS al sursei (opțional)"),
 ("market","Piața (UE/UK/SUA etc.)"),
 ("applicability","Aplicabilitate / cod motor / revizie"),
)

def _render_document(path,page_number=1,max_pixels=8_000_000):
    """Return (PIL image copy, total pages) from verified attached PDF or image."""
    from PIL import Image,ImageOps
    suffix=Path(path).suffix.lower()
    if suffix==".pdf":
        try:import pypdfium2 as pdfium
        except ImportError as exc:raise RuntimeError(
            "Instalează pypdfium2 pentru vizualizarea PDF în aplicație") from exc
        document=pdfium.PdfDocument(str(path))
        try:
            n=len(document)
            if n<1 or n>10000:raise ValueError("Număr de pagini neacceptat")
            if page_number<1 or page_number>n:raise ValueError("Pagina PDF nu există")
            page=document[page_number-1]
            try:
                width,height=page.get_size()
                if width<=0 or height<=0:raise ValueError("Dimensiune PDF invalidă")
                scale=min(1.7,(max_pixels/(width*height))**.5)
                bitmap=page.render(scale=scale)
                try:
                    image=bitmap.to_pil().convert("RGB").copy()
                finally:bitmap.close()
                return image,n
            finally:page.close()
        finally:document.close()
    if suffix in (".png",".jpg",".jpeg"):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS=max_pixels
        with Image.open(path) as image:
            if image.width*image.height>max_pixels:
                raise ValueError("Imaginea depășește limita de 8 megapixeli")
            image.verify()
        with Image.open(path) as image:
            return ImageOps.exif_transpose(image).convert("RGB").copy(),1
    raise ValueError("Previzualizare doar pentru PDF/PNG/JPG")

def open_workshop_atlas(app):
    from tkinter import filedialog
    tk=app.tk
    vid=app.vid
    if vid is None:
        messagebox.showinfo("Vehicul necesar","Selectează mai întâi marca, modelul și motorul.")
        return None
    ensure_schema(app.db)
    vehicle=app.db.db.execute("SELECT * FROM vehicles WHERE id=?",(vid,)).fetchone()
    top=tk.Toplevel(app.root)
    top.title("AtelierData — Atlas tehnic")
    top.geometry("1320x830")
    top.minsize(960,650)
    top.transient(app.root)
    wrapper=ttk.Frame(top,padding=11)
    wrapper.pack(fill="both",expand=True)
    ttk.Label(wrapper,text="ATLAS TEHNIC — CUPLURI / LOCAȚII / SCHEME / DOCUMENTE",
              font=("Segoe UI Semibold",16)).pack(anchor="w")
    ttk.Label(wrapper,text=(
        f"{vehicle['make']} {vehicle['model']} | Motor: {vehicle['engine'] or 'neconfirmat'} "
        f"| Ani: {vehicle['years'] or '-'} | Variantă: {vehicle['variant'] or '-'}\n"
        "Nu există valori tehnice implicite. Fiecare informație necesită o sursă și verificarea motorizării."
    )).pack(anchor="w",pady=(3,8))
    notebook=ttk.Notebook(wrapper)
    notebook.pack(fill="both",expand=True)
    facts_tab=ttk.Frame(notebook,padding=8)
    diagrams_tab=ttk.Frame(notebook,padding=8)
    notebook.add(facts_tab,text="Cupluri, locații și date")
    notebook.add(diagrams_tab,text="PDF / imagini / poziții pe diagramă")

    fact_tools=ttk.Frame(facts_tab);fact_tools.pack(fill="x",pady=(0,6))
    query=tk.StringVar()
    kind=tk.StringVar(value="Toate")
    ttk.Label(fact_tools,text="Caută:").pack(side="left")
    ttk.Entry(fact_tools,textvariable=query,width=27).pack(side="left",padx=6)
    ttk.Label(fact_tools,text="Tip:").pack(side="left")
    ttk.Combobox(fact_tools,textvariable=kind,state="readonly",
                 values=("Toate",)+KINDS,width=25).pack(side="left",padx=6)
    cols=("kind","system","component","value","location","source")
    tree=ttk.Treeview(facts_tab,show="headings",columns=cols,selectmode="browse")
    for col,label,size in zip(cols,("Tip","Sistem","Componentă","Valoare","Locație","Sursă"),
                              (175,135,190,115,260,180)):
        tree.heading(col,text=label);tree.column(col,width=size,minwidth=75,stretch=True)
    tree.pack(fill="both",expand=True)
    fact_details=tk.Text(facts_tab,height=8,wrap="word",bg="#1a2a42",
        fg="#eef5ff",font=("Segoe UI",10),relief="flat")
    fact_details.pack(fill="x",pady=(6,6))
    facts={}
    def selected_fact():
        choices=tree.selection()
        return facts.get(choices[0]) if choices else None
    def show_fact(event=None):
        row=selected_fact()
        if row:
            text=(f"{row['kind']} / {row['system']} / {row['component']}\n"
                  f"Operație: {row['operation']}\nValoare: {row['value']} {row['unit']}\n"
                  f"Etape: {row['stages']}\nCondiții: {row['conditions']}\n"
                  f"Amplasare: {row['component_location']}\nNotă: {row['notes']}\n"
                  f"Sursă: {row['source_name']} {row['source_url']}\n"
                  f"Piață/aplicabilitate: {row['market']} / {row['applicability']}\n"
                  f"Document legat: {row['attachment_id'] or '—'} / pagina {row['page_number'] or '—'}")
        else:text="Selectează o înregistrare pentru proveniență și condiții."
        fact_details.configure(state="normal")
        fact_details.delete("1.0","end");fact_details.insert("1.0",text)
        fact_details.configure(state="disabled")
    def refresh_facts(*_):
        try:rows=list_facts(app.db,vid,"" if kind.get()=="Toate" else kind.get(),query.get())
        except ValueError as exc:
            messagebox.showerror("Filtru",str(exc),parent=top);return
        tree.delete(*tree.get_children());facts.clear()
        for row in rows:
            key=str(row["id"]);facts[key]=row
            tree.insert("","end",iid=key,values=(row["kind"],row["system"],
                row["component"],(row["value"]+" "+row["unit"]).strip(),
                row["component_location"][:100],row["source_name"]))
        show_fact()
    query.trace_add("write",refresh_facts);kind.trace_add("write",refresh_facts)
    tree.bind("<<TreeviewSelect>>",show_fact)

    def fact_form(old=None):
        dialog=tk.Toplevel(top)
        dialog.title("Date tehnice cu sursă")
        dialog.geometry("680x780");dialog.transient(top)
        dialog.grab_set()
        frame=ttk.Frame(dialog,padding=11);frame.pack(fill="both",expand=True)
        canvas=tk.Canvas(frame,highlightthickness=0)
        scroll=ttk.Scrollbar(frame,command=canvas.yview,orient="vertical")
        content=ttk.Frame(canvas)
        content.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0),window=content,anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left",fill="both",expand=True)
        scroll.pack(side="right",fill="y")
        chosen=tk.StringVar(value=old["kind"] if old else "Cuplu de strângere")
        ttk.Label(content,text="Tip de informație").pack(anchor="w")
        ttk.Combobox(content,textvariable=chosen,state="readonly",values=KINDS).pack(fill="x")
        vars={}
        for key,label in FIELDS:
            ttk.Label(content,text=label).pack(anchor="w",pady=(6,0))
            current=(old[key] if old is not None else "") or ""
            var=tk.StringVar(value=current);vars[key]=var
            ttk.Entry(content,textvariable=var,width=65).pack(fill="x",padx=(0,14))
        docs=[r for r in list_library(app.db) if r["vehicle_id"]==vid]
        docnames={"Fără document":" "}
        for row in docs:
            docnames[f"{row['attachment_id']}: {row['display_title'] or row['article_title']}"]=row["attachment_id"]
        selected_doc=tk.StringVar(value="Fără document")
        if old and old["attachment_id"]:
            selected_doc.set(next((k for k,v in docnames.items()
                                   if v==old["attachment_id"]),"Fără document"))
        ttk.Label(content,text="Document din biblioteca vehiculului").pack(anchor="w",pady=(6,0))
        ttk.Combobox(content,textvariable=selected_doc,values=list(docnames),
                     state="readonly",width=58).pack(fill="x")
        page=tk.StringVar(value=str(old["page_number"] or "") if old else "")
        ttk.Label(content,text="Pagina documentului (opțional)").pack(anchor="w",pady=(6,0))
        ttk.Entry(content,textvariable=page).pack(fill="x")
        def submit():
            try:
                result=record_fact(app.db,vehicle_id=vid,kind=chosen.get(),
                    attachment_id=docnames[selected_doc.get()] or None,
                    page_number=page.get() or None,
                    fact_id=old["id"] if old else None,
                    **{key:var.get() for key,var in vars.items()})
                dialog.destroy()
                refresh_facts()
                tree.selection_set(str(result));tree.see(str(result));show_fact()
            except Exception as exc:
                messagebox.showerror("Date invalide",str(exc),parent=dialog)
        ttk.Button(content,text="Salvează",command=submit).pack(pady=16)
        ttk.Label(content,text="Valorile trebuie verificate în documentul sursă, nu extrapolate.").pack()
    def delete_selected():
        old=selected_fact()
        if old is None:return
        if messagebox.askyesno("Ștergere","Ștergi informația selectată?",parent=top):
            delete_fact(app.db,vid,old["id"]);refresh_facts()
    actions=ttk.Frame(facts_tab);actions.pack(fill="x")
    ttk.Button(actions,text="Adaugă informație",command=fact_form).pack(side="left")
    ttk.Button(actions,text="Editează",command=lambda:fact_form(selected_fact()) if selected_fact() else None).pack(side="left",padx=6)
    ttk.Button(actions,text="Șterge",command=delete_selected).pack(side="left")

    docrows={}
    rowbar=ttk.Frame(diagrams_tab);rowbar.pack(fill="x")
    ttk.Label(rowbar,text="Document:").pack(side="left")
    docchoice=tk.StringVar()
    doccombo=ttk.Combobox(rowbar,textvariable=docchoice,values=[],state="readonly",width=53)
    doccombo.pack(side="left",padx=7)
    page=tk.IntVar(value=1)
    page_label=tk.StringVar(value="Pagina 1/1")
    ttk.Label(rowbar,textvariable=page_label).pack(side="left",padx=8)
    image=tk.Canvas(diagrams_tab,bg="#172336",highlightthickness=0)
    image.pack(fill="both",expand=True,pady=(8,5))
    panel=tk.StringVar(value="Alege un PDF sau o schemă asociată vehiculului.")
    ttk.Label(diagrams_tab,textvariable=panel).pack(anchor="w")
    state={"photo":None,"geometry":None,"page_count":1,"attachment_id":None,
           "mark_mode":False,"markers":{}}

    def reload_docs():
        docs=list_library(app.db)
        docrows.clear()
        for row in docs:
            if row["vehicle_id"]!=vid:continue
            if Path(row["path"]).suffix.lower() not in (".pdf",".jpg",".jpeg",".png"):
                continue
            docrows[f"{row['attachment_id']}: {row['display_title'] or row['article_title']}"]=row
        doccombo.configure(values=list(docrows))
        if docchoice.get() not in docrows:
            docchoice.set(next(iter(docrows),""))

    def show_page():
        row=docrows.get(docchoice.get())
        if not row:
            image.delete("all");panel.set("Nu există documente PDF/PNG/JPG atașate acestui vehicul.")
            return
        try:
            from PIL import ImageTk
            path=verified_library_file(app.db,row["attachment_id"],vid)
            picture,npages=_render_document(path,page.get())
            if picture.width*picture.height>8_000_000:
                raise ValueError("Imagine prea mare pentru previzualizare")
            # Fit to currently available canvas, preserving aspect ratio.
            w=max(500,image.winfo_width()-15);h=max(300,image.winfo_height()-20)
            scale=min(1.0,w/picture.width,h/picture.height)
            target=(max(1,int(picture.width*scale)),max(1,int(picture.height*scale)))
            if picture.size!=target:
                from PIL import Image
                picture=picture.resize(target,Image.Resampling.LANCZOS)
            photo=ImageTk.PhotoImage(picture,master=top)
            image.delete("all")
            ox=max(0,(image.winfo_width()-target[0])//2)
            oy=max(0,(image.winfo_height()-target[1])//2)
            image.create_image(ox,oy,image=photo,anchor="nw",tags="document")
            state.update(photo=photo,geometry=(ox,oy,*target),
                         page_count=npages,attachment_id=row["attachment_id"])
            page_label.set(f"Pagina {page.get()}/{npages}")
            markermap={}
            for marker in list_markers(app.db,vid,row["attachment_id"],page.get()):
                cx=ox+marker["x"]*target[0];cy=oy+marker["y"]*target[1]
                point=image.create_oval(cx-7,cy-7,cx+7,cy+7,fill="#f6a43a",
                                        outline="#fff",width=1,tags="mark")
                image.create_text(cx+10,cy-8,text=marker["label"][:30],
                    fill="#f6dfb1",anchor="w",tags="mark")
                markermap[point]=marker["id"]
            state["markers"]=markermap
            panel.set(f"Fișier local verificat SHA256: {path.name}. "
                      "Clic „Adaugă punct” apoi clic pe schema afișată.")
        except Exception as exc:
            image.delete("all")
            state["geometry"]=None
            panel.set("Previzualizare indisponibilă: "+str(exc))
    def change_page(n):
        target=page.get()+n
        if 1<=target<=state["page_count"]:
            page.set(target);show_page()
    def doc_changed(event=None):
        page.set(1);show_page()
    doccombo.bind("<<ComboboxSelected>>",doc_changed)
    def mark_mode():
        state["mark_mode"]=True
        panel.set("Clic pe poziția componentei, în interiorul paginii.")
    def canvas_click(event):
        geometry=state["geometry"]
        if not geometry:return
        if state["mark_mode"]:
            state["mark_mode"]=False
            ox,oy,w,h=geometry
            x=(event.x-ox)/w;y=(event.y-oy)/h
            if not 0<=x<=1 or not 0<=y<=1:
                panel.set("Clic în afara diagramei. Marcajul nu a fost salvat.")
                return
            label=simpledialog.askstring("Locație pe schemă","Nume componentă / identificator:",
                                         parent=top)
            if not label:return
            note=simpledialog.askstring("Notă","Observații (opțional):",parent=top)
            try:
                selected=selected_fact()
                add_marker(app.db,vid,state["attachment_id"],page.get(),x,y,label,
                           note or "",selected["id"] if selected else None)
                show_page()
            except Exception as exc:messagebox.showerror("Marcaj",str(exc),parent=top)
        else:
            hit=image.find_closest(event.x,event.y)
            if hit and hit[0] in state["markers"]:
                mid=state["markers"][hit[0]]
                marker=app.db.db.execute("SELECT label,note,fact_id FROM diagram_markers WHERE id=?",
                                         (mid,)).fetchone()
                messagebox.showinfo("Marcaj",f"{marker['label']}\n{marker['note']}\n"
                    f"Date legate: {marker['fact_id'] or '—'}",parent=top)
    image.bind("<Button-1>",canvas_click)
    def delete_last_marker():
        if not state["attachment_id"]:return
        rows=list_markers(app.db,vid,state["attachment_id"],page.get())
        if rows and messagebox.askyesno("Ștergere marcaj",
                 f"Ștergi ultimul marcaj: {rows[-1]['label']}?",parent=top):
            delete_marker(app.db,vid,rows[-1]["id"]);show_page()
    def index_current_pdf():
        row=docrows.get(docchoice.get())
        if not row or Path(row["path"]).suffix.lower()!=".pdf":
            return messagebox.showinfo("PDF necesar","Selectează un document PDF.",parent=top)
        try:
            result=index_pdf(app.db,vid,row["attachment_id"])
            panel.set(f"Indexat local: {result['pages_with_text']}/{result['pages_total']} pagini "
                      f"cu text, {result['characters']} caractere. PDF-urile scanate necesită OCR separat.")
        except Exception as exc:
            messagebox.showerror("Index PDF",str(exc),parent=top)

    def search_pdf_index():
        term=simpledialog.askstring("Caută în PDF-uri",
                "Cuvinte din PDF-urile indexate ale vehiculului selectat:",parent=top)
        if not term:return
        try:hits=search_pdf_text(app.db,vid,term)
        except Exception as exc:
            return messagebox.showerror("Căutare PDF",str(exc),parent=top)
        if not hits:
            return messagebox.showinfo("Căutare PDF","Nu există rezultate în PDF-urile indexate.",parent=top)
        result_window=tk.Toplevel(top)
        result_window.title(f"Rezultate PDF: {term}")
        result_window.geometry("990x540")
        result_window.transient(top)
        frame=ttk.Frame(result_window,padding=11);frame.pack(fill="both",expand=True)
        cols=("doc","page","excerpt")
        result_tree=ttk.Treeview(frame,columns=cols,show="headings",selectmode="browse")
        for key,label,width in (("doc","Document",260),("page","Pagina",80),
                                ("excerpt","Text găsit (scurt)",580)):
            result_tree.heading(key,text=label)
            result_tree.column(key,width=width,stretch=True)
        result_tree.pack(fill="both",expand=True)
        for i,row in enumerate(hits):
            result_tree.insert("","end",iid=str(i),values=(
                row["article_title"],row["page_number"],row["excerpt"].replace("\n"," ")[:170]))
        def goto():
            selection=result_tree.selection()
            if not selection:return
            hit=hits[int(selection[0])]
            key=next((name for name,item in docrows.items()
                      if item["attachment_id"]==hit["attachment_id"]),None)
            if key is None:
                reload_docs()
                key=next((name for name,item in docrows.items()
                          if item["attachment_id"]==hit["attachment_id"]),None)
            if key is None:
                return messagebox.showerror("Document lipsă",
                    "Documentul indexat nu este în biblioteca vehiculului.",parent=result_window)
            docchoice.set(key)
            page.set(hit["page_number"])
            show_page()
            notebook.select(diagrams_tab)
            result_window.destroy()
        ttk.Button(frame,text="Deschide pagina în atlas",command=goto).pack(pady=6)
        result_tree.bind("<Double-1>",lambda event:goto())

    nav=ttk.Frame(diagrams_tab);nav.pack(fill="x",pady=(3,1))
    ttk.Button(nav,text="Documente actualizate",command=lambda:(reload_docs(),show_page())).pack(side="left")
    ttk.Button(nav,text="◀ Pagina",command=lambda:change_page(-1)).pack(side="left",padx=6)
    ttk.Button(nav,text="Pagina ▶",command=lambda:change_page(1)).pack(side="left")
    ttk.Button(nav,text="Adaugă punct / locație",command=mark_mode).pack(side="left",padx=8)
    ttk.Button(nav,text="Șterge ultimul punct",command=delete_last_marker).pack(side="left")
    ttk.Button(nav,text="Indexează textul PDF",command=index_current_pdf).pack(side="left",padx=(8,3))
    ttk.Button(nav,text="Caută în PDF-uri",command=search_pdf_index).pack(side="left",padx=(3,8))
    ttk.Button(nav,text="Închide",command=top.destroy).pack(side="right")

    refresh_facts();reload_docs()
    if docrows:show_page()
    top.atlas_facts_tree=tree
    top.atlas_image_canvas=image
    top.atlas_document_choice=docchoice
    return top
