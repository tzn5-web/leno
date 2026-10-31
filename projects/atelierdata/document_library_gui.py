"""Tkinter library browser for local authorized technical PDFs/images/text.

No website crawling. Documents are attached to exact vehicle records and remain
inside the existing SQLite+documents backup system. Browser does not launch
anything without user interaction; local file opens are hash checked.
"""
from __future__ import annotations
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from document_library import (
    DOCUMENT_TYPES,ACCESS_RIGHTS,ensure_schema,import_local_file,
    list_library,set_metadata,verified_library_file)
from technical_sources import normalize
from document_bulk_import import bulk_import_folder

RIGHTS_LABEL={
    "neconfirmat":"Drepturi neconfirmate — numai inventar",
    "document_propriu":"Document propriu",
    "licenta_expresa":"Copie cu licență",
    "domeniu_public":"Domeniu public verificat",
    "permisiune_scrisa":"Permisiune scrisă",
}

def open_document_library(app):
    ensure_schema(app.db)
    win=tk.Toplevel(app.root)
    win.title("AtelierData — bibliotecă tehnică locală")
    win.geometry("1220x735")
    win.minsize(910,570)
    win.transient(app.root)
    outer=ttk.Frame(win,padding=14)
    outer.pack(fill="both",expand=True)
    ttk.Label(outer,text="BIBLIOTECĂ TEHNICĂ OFFLINE — DOCUMENTE VERIFICATE",
              font=("Segoe UI Semibold",15)).pack(anchor="w")
    ttk.Label(outer,text=("Documentele sunt salvate local, cu SHA256. "
              "Marca, modelul, codul motor și anul provin din vehiculul selectat, nu sunt presupuse. "
              "Adaugă numai materiale asupra cărora ai drepturi de păstrare."),
              wraplength=1100).pack(anchor="w",pady=(7,10))

    filters=ttk.Frame(outer)
    filters.pack(fill="x")
    search=tk.StringVar()
    make=tk.StringVar()
    category=tk.StringVar(value="Toate")
    year=tk.StringVar()
    selection=app.db.db.execute("SELECT * FROM vehicles WHERE id=?",(app.vid,)).fetchone() if app.vid else None
    if selection:
        make.set(selection["make"])
        year.set(selection["years"] if len(selection["years"] or "")==4 else "")
    ttk.Label(filters,text="Caută titlu / sursă / vehicul").grid(row=0,column=0,sticky="w")
    ttk.Entry(filters,textvariable=search).grid(row=1,column=0,sticky="ew",padx=(0,8))
    ttk.Label(filters,text="Marcă").grid(row=0,column=1,sticky="w")
    ttk.Entry(filters,textvariable=make).grid(row=1,column=1,sticky="ew",padx=(0,8))
    ttk.Label(filters,text="Categorie").grid(row=0,column=2,sticky="w")
    ttk.Combobox(filters,textvariable=category,
                 values=("Toate",)+DOCUMENT_TYPES,state="readonly").grid(
                 row=1,column=2,sticky="ew",padx=(0,8))
    ttk.Label(filters,text="An (YYYY)").grid(row=0,column=3,sticky="w")
    ttk.Entry(filters,textvariable=year,width=12).grid(row=1,column=3,sticky="ew")
    for i in (0,1,2):filters.columnconfigure(i,weight=1)

    split=ttk.PanedWindow(outer,orient="vertical")
    split.pack(fill="both",expand=True,pady=(10,5))
    upper=ttk.Frame(split)
    lower=ttk.Frame(split)
    split.add(upper,weight=6)
    split.add(lower,weight=3)

    columns=("vehicle","engine","year","title","kind","rights")
    tree=ttk.Treeview(upper,columns=columns,show="headings",selectmode="browse")
    captions=("Marcă / model","Motor","An","Document","Tip","Proveniență / drepturi")
    widths=(225,115,95,285,165,240)
    for key,label,width in zip(columns,captions,widths):
        tree.heading(key,text=label)
        tree.column(key,width=width,minwidth=65,stretch=True)
    scroll=ttk.Scrollbar(upper,orient="vertical",command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left",fill="both",expand=True)
    scroll.pack(side="right",fill="y")

    details=tk.Text(lower,height=9,state="disabled",wrap="word",
                    bg="#1a2a42",fg="#eef5ff",font=("Segoe UI",10),
                    padx=10,pady=10,relief="flat")
    details.pack(fill="both",expand=True)
    status=tk.StringVar()
    ttk.Label(outer,textvariable=status).pack(anchor="w",pady=(0,6))
    indexed={}

    def selected():
        keys=tree.selection()
        return indexed.get(keys[0]) if keys else None

    def show_detail(_event=None):
        row=selected()
        if row:
            text=(f"{row['display_title'] or row['article_title']}\n"
                  f"Vehicul: {row['make']} {row['model']} / {row['engine'] or 'motor necunoscut'} / {row['years'] or 'an neprecizat'}\n"
                  f"Fișier stocat: {row['path']}\n"
                  f"Tip: {row['document_type'] or row['article_category']}\n"
                  f"Proveniență: {row['source_name'] or row['article_source'] or 'neprecizată'}\n"
                  f"Link sursă: {row['source_url'] or 'nespecificat'}\n"
                  f"Limbă: {row['language'] or '-'} / Piață: {row['market'] or '-'} / Revizie: {row['revision'] or '-'}\n"
                  f"Drepturi declarate: {RIGHTS_LABEL[row['rights_basis'] or 'neconfirmat']}\n"
                  f"Notă aplicabilitate: {row['applicability_note'] or 'Nu a fost verificată aplicabilitatea'}\n"
                  "SHA256 este reverificat la deschidere. Metadatele nu constituie certificare independentă.")
        else:
            text="Selectează un document. Materialele vechi pot exista fără metadate de proveniență."
        details.configure(state="normal")
        details.delete("1.0","end")
        details.insert("1.0",text)
        details.configure(state="disabled")

    def refresh(*_):
        try:
            rows=list_library(
                app.db,make=make.get(),category="" if category.get()=="Toate" else category.get(),
                year=year.get(),query=search.get())
        except ValueError as exc:
            status.set("Filtru invalid: "+str(exc))
            return
        indexed.clear()
        tree.delete(*tree.get_children())
        for row in rows:
            key=str(row["attachment_id"])
            indexed[key]=row
            rights=row["rights_basis"] or "neconfirmat"
            tree.insert("","end",iid=key,values=(
                row["make"]+" / "+row["model"],row["engine"],row["years"],
                row["display_title"] or row["article_title"],
                row["document_type"] or row["article_category"],
                RIGHTS_LABEL[rights]))
        status.set(f"{len(rows)} documente / fișiere atașate. "
                   "Sunt afișate și atașamentele vechi fără metadate.")
        show_detail()

    def details_form(record=None,importing=False):
        dialog=tk.Toplevel(win)
        dialog.title("Importă document local" if importing else "Metadate și proveniență document")
        dialog.geometry("650x685")
        dialog.minsize(550,620)
        dialog.transient(win)
        dialog.grab_set()
        body=ttk.Frame(dialog,padding=15)
        body.pack(fill="both",expand=True)
        saved={"value":None}
        fields=[
            ("title","Titlu document *",record.get("display_title") or record.get("article_title") if record else ""),
            ("source_name","Proveniență (autor/furnizor) *",record.get("source_name") or record.get("article_source") if record else ""),
            ("source_url","Link către sursă (opțional)",record.get("source_url") or "" if record else ""),
            ("language","Limbă",record.get("language") or "" if record else ""),
            ("market","Piață / regiune",record.get("market") or "" if record else ""),
            ("revision","Ediție / revizie",record.get("revision") or "" if record else ""),
            ("applicability_note","Nota de aplicabilitate",record.get("applicability_note") or "" if record else ""),
        ]
        variables={}
        for key,label,value in fields:
            ttk.Label(body,text=label).pack(anchor="w",pady=(6,1))
            var=tk.StringVar(value=value)
            ttk.Entry(body,textvariable=var).pack(fill="x")
            variables[key]=var
        ttk.Label(body,text="Tip document").pack(anchor="w",pady=(8,1))
        initial=(record.get("document_type") or record.get("article_category")) if record else ""
        kind=tk.StringVar(value=initial if initial in DOCUMENT_TYPES else DOCUMENT_TYPES[0])
        ttk.Combobox(body,textvariable=kind,values=DOCUMENT_TYPES,
                     state="readonly").pack(fill="x")
        ttk.Label(body,text="Drept de păstrare (declarația utilizatorului)").pack(anchor="w",pady=(8,1))
        rights=tk.StringVar(value=record.get("rights_basis") or "neconfirmat" if record else "neconfirmat")
        ttk.Combobox(body,textvariable=rights,values=ACCESS_RIGHTS,
                     state="readonly").pack(fill="x")
        ttk.Label(body,text=("Nu bifa drepturi pe care nu le deții. "
                  "Sursele gratuite online nu dau automat drept de copiere."),
                  wraplength=610).pack(anchor="w",pady=(7,5))
        def save():
            values={k:v.get() for k,v in variables.items()}
            values["category"]=kind.get()
            values["rights_basis"]=rights.get()
            saved["value"]=values
            dialog.destroy()
        line=ttk.Frame(body)
        line.pack(fill="x",pady=14)
        ttk.Button(line,text="Salvează",command=save).pack(side="right")
        ttk.Button(line,text="Anulează",command=dialog.destroy).pack(side="right",padx=10)
        win.wait_window(dialog)
        return saved["value"]

    def import_file():
        # Vehicle must be selected with exact make/model/engine stored by user.
        if app.vid is None:
            return messagebox.showinfo("Vehicul necesar",
                "Selectează mai întâi un vehicul și motorizarea din fereastra principală.",parent=win)
        path=filedialog.askopenfilename(parent=win,filetypes=[
            ("Documente permise","*.pdf *.txt *.jpg *.jpeg *.png")])
        if not path:return
        data=details_form(importing=True)
        if data is None:return
        try:
            aid=import_local_file(
                app.db,app.vid,path,category=data["category"],
                title=data["title"],source_name=data["source_name"],
                source_url=data["source_url"],language=data["language"],
                market=data["market"],revision=data["revision"],
                rights_basis=data["rights_basis"],
                applicability_note=data["applicability_note"])
            refresh()
            tree.selection_set(str(aid))
            tree.see(str(aid))
            show_detail()
            app.refresh()
            messagebox.showinfo("Import", "Document indexat și verificat SHA256.",parent=win)
        except Exception as exc:
            messagebox.showerror("Import respins",str(exc),parent=win)

    def import_folder():
        if app.vid is None:
            return messagebox.showinfo("Vehicul necesar",
                "Selectează vehiculul și motorul înainte de importul unui director.",parent=win)
        folder=filedialog.askdirectory(parent=win,title="Alege un dosar cu PDF, imagini și TXT")
        if not folder:return
        dialog=tk.Toplevel(win)
        dialog.title("Import privat de documente — confirmare sursă")
        dialog.geometry("550x430");dialog.transient(win);dialog.grab_set()
        frame=ttk.Frame(dialog,padding=17);frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="Importul asociază TOATE fișierele vehiculului selectat.",
                  wraplength=490).pack(anchor="w")
        ttk.Label(frame,text="Furnizorul / proveniența documentelor (obligatoriu):").pack(anchor="w",pady=(10,1))
        provider=tk.StringVar()
        ttk.Entry(frame,textvariable=provider).pack(fill="x")
        ttk.Label(frame,text="Tip inițial (poate fi modificat ulterior):").pack(anchor="w",pady=(10,1))
        kind=tk.StringVar(value="Alt document")
        ttk.Combobox(frame,textvariable=kind,values=DOCUMENT_TYPES,state="readonly").pack(fill="x")
        ttk.Label(frame,text="Drept de păstrare declarat:").pack(anchor="w",pady=(10,1))
        rights=tk.StringVar(value="document_propriu")
        ttk.Combobox(frame,textvariable=rights,
                     values=[r for r in ACCESS_RIGHTS if r!="neconfirmat"],
                     state="readonly").pack(fill="x")
        ttk.Label(frame,text=("Nu selecta un drept fără bază reală. "
                  "Manualele online nu se descarcă automat. Se importă doar fișierele deja "
                  "aflate în folderul tău; maximum 500 fișiere, 32 MiB fiecare."),
                  wraplength=485).pack(anchor="w",pady=(12,8))
        def proceed():
            if not provider.get().strip():
                return messagebox.showerror("Sursă lipsă","Completează proveniența.",parent=dialog)
            if not messagebox.askyesno("Confirmă importul",
                    "Confirmi că ai dreptul să păstrezi local fișierele selectate și că "
                    "se aplică vehiculului/motorului selectat?",parent=dialog):
                return
            try:
                result=bulk_import_folder(app.db,app.vid,folder,provider.get(),
                                          rights.get(),category=kind.get())
                dialog.destroy()
                refresh();app.refresh()
                messagebox.showinfo("Import dosar",
                    f"Importate: {result['imported']}\nDuplicate: {result['duplicates']}\n"
                    f"Respingeri: {len(result['failed'])}\n"
                    "Fișierele respinse rămân în folderul inițial.",parent=win)
            except Exception as exc:
                messagebox.showerror("Import dosar eșuat",str(exc),parent=dialog)
        ttk.Button(frame,text="Importă fișierele autorizate",command=proceed).pack(pady=12)

    def edit_metadata():
        row=selected()
        if not row:
            return messagebox.showinfo("Selectare","Selectează un atașament.",parent=win)
        data=details_form(row)
        if data is None:return
        try:
            set_metadata(app.db,row["attachment_id"],document_type=data["category"],
                display_title=data["title"],source_name=data["source_name"],
                source_url=data["source_url"],language=data["language"],
                market=data["market"],revision=data["revision"],
                rights_basis=data["rights_basis"],
                applicability_note=data["applicability_note"])
            refresh()
            if tree.exists(str(row["attachment_id"])):
                tree.selection_set(str(row["attachment_id"]))
                show_detail()
        except Exception as exc:
            messagebox.showerror("Metadate invalide",str(exc),parent=win)

    def open_verified():
        row=selected()
        if not row:return messagebox.showinfo("Selectare","Selectează un fișier.",parent=win)
        try:
            path=verified_library_file(app.db,row["attachment_id"])
            if sys.platform=="win32":
                os.startfile(str(path))
            else:
                import subprocess
                subprocess.Popen(["xdg-open",str(path)])
        except Exception as exc:
            messagebox.showerror("Integritate fișier",str(exc),parent=win)

    actions=ttk.Frame(outer)
    actions.pack(fill="x",pady=(4,1))
    ttk.Button(actions,text="Importă fișier local",command=import_file).pack(side="left",padx=(0,7))
    ttk.Button(actions,text="Importă dosar local",command=import_folder).pack(side="left",padx=(0,7))
    ttk.Button(actions,text="Editează proveniența",command=edit_metadata).pack(side="left",padx=(0,7))
    ttk.Button(actions,text="Deschide verificat",command=open_verified).pack(side="left",padx=(0,7))
    ttk.Button(actions,text="Închide",command=win.destroy).pack(side="right")
    for var in (search,make,year,category):var.trace_add("write",refresh)
    tree.bind("<<TreeviewSelect>>",show_detail)
    refresh()
    win.library_tree=tree
    win.library_status=status
    win.library_search=search
    return win
