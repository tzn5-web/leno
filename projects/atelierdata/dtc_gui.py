"""Tkinter diagnostics/DTC viewer for original, user-provided workshop references."""
from __future__ import annotations

from dtc_catalog import add_dtc, update_dtc, delete_dtc, get_dtc, list_dtc, dtc_text, import_dtc, export_dtc


def open_dtc_window(app, editor_class):
    from tkinter import ttk, filedialog, messagebox
    tk=app.tk
    vehicle_id=app.vid
    if vehicle_id is None:
        messagebox.showinfo("Vehicul necesar","Selectează mai întâi vehiculul și motorizarea.")
        return None
    win=tk.Toplevel(app.root)
    win.title("AtelierData — diagnosticare DTC")
    win.geometry("1160x720")
    win.minsize(960,570)
    win.transient(app.root)

    base=ttk.Frame(win,padding=14);base.pack(fill="both",expand=True)
    ttk.Label(base,text="DIAGNOSTICARE DTC — REFERINȚE CU SURSĂ",
              font=("Segoe UI Semibold",16)).pack(anchor="w")
    ttk.Label(base,text="Catalog documentar offline. Nu comunică prin OBD și nu șterge coduri din ECU."
              ).pack(anchor="w",pady=(5,12))

    search=tk.StringVar()
    ttk.Label(base,text="Caută cod, sistem, simptom, cauză sau sursă").pack(anchor="w")
    filter_box=ttk.Entry(base,textvariable=search)
    filter_box.pack(fill="x",pady=(5,8))

    columns=("code","system","title","source")
    tree=ttk.Treeview(base,columns=columns,show="headings",height=12)
    for key,name,width in zip(columns,("Cod","Sistem","Descriere verificată","Sursă"),(100,200,450,260)):
        tree.heading(key,text=name);tree.column(key,width=width,stretch=True,minwidth=70)
    tree.pack(fill="both",expand=True)
    win.dtc_tree=tree

    ttk.Label(base,text="DETALII DE DIAGNOSTICARE").pack(anchor="w",pady=(10,5))
    body=tk.Text(base,height=12,wrap="word",font=("Segoe UI",10),
                 bg="#1a2a42",fg="#eef5ff",relief="flat")
    body.pack(fill="both",expand=True)
    def show(text):
        body.config(state="normal")
        body.delete("1.0","end")
        body.insert("1.0",text)
        body.config(state="disabled")

    def refresh(prefer=None):
        tree.delete(*tree.get_children())
        for item in list_dtc(app.db,vehicle_id,search.get()):
            tree.insert("","end",iid=str(item["id"]),
                        values=(item["code"],item["system"],item["title"],item["source"]))
        if prefer is not None and tree.exists(str(prefer)):
            tree.selection_set(str(prefer))
            tree.see(str(prefer))
        else:
            show("Selectează un cod DTC. Codurile nu au definiții automate inventate.")

    def selected_id():
        selection=tree.selection()
        return int(selection[0]) if selection else None

    def choose(event=None):
        entry=selected_id()
        if entry is not None:
            show(dtc_text(app.db,entry))
    tree.bind("<<TreeviewSelect>>",choose)
    search.trace_add("write",lambda *_:refresh())

    def edit(create):
        entry=get_dtc(app.db,selected_id()) if not create and selected_id() else None
        if not create and entry is None:
            return messagebox.showinfo("Selectare","Selectează o înregistrare DTC.",parent=win)
        fields=[
            ("code","Cod DTC P/B/C/U + 4 caractere *",entry["code"] if entry else ""),
            ("system","Sistem *",entry["system"] if entry else ""),
            ("title","Descriere *",entry["title"] if entry else ""),
            ("symptoms","Simptome",entry["symptoms"] if entry else ""),
            ("possible_causes","Cauze posibile",entry["possible_causes"] if entry else ""),
            ("checks","Verificări documentate",entry["checks"] if entry else ""),
            ("notes","Note",entry["notes"] if entry else ""),
            ("source","Sursă exactă / licență *",entry["source"] if entry else ""),
            ("procedure_id","ID procedură asociată (opțional)",str(entry["procedure_id"]) if entry and entry["procedure_id"] else ""),
            ("article_id","ID document asociat (opțional)",str(entry["article_id"]) if entry and entry["article_id"] else "")
        ]
        data=editor_class(win,"Cod DTC" if create else "Editare DTC",fields).value
        if data is None:return
        try:
            proc=int(data.pop("procedure_id")) if data["procedure_id"] else None
            article=int(data.pop("article_id")) if data["article_id"] else None
            if create:
                ident=add_dtc(app.db,vehicle_id,procedure_id=proc,article_id=article,**data)
            else:
                ident=entry["id"]
                update_dtc(app.db,ident,procedure_id=proc,article_id=article,**data)
            refresh(ident)
            show(dtc_text(app.db,ident))
        except Exception as exc:messagebox.showerror("DTC invalid",str(exc),parent=win)

    def remove():
        ident=selected_id()
        if ident is None:return
        if messagebox.askyesno("Confirmare","Ștergi această înregistrare DTC?",parent=win):
            delete_dtc(app.db,ident);refresh()

    def import_file():
        path=filedialog.askopenfilename(parent=win,filetypes=[("Date JSON/CSV","*.json *.csv")])
        if not path:return
        try:
            count=import_dtc(app.db,path)
            refresh()
            messagebox.showinfo("Import DTC",
                f"Importate: {count['inserted']}, duplicate: {count['duplicates']}",parent=win)
        except Exception as exc:
            messagebox.showerror("Import respins",str(exc),parent=win)

    def export_file():
        path=filedialog.asksaveasfilename(parent=win,defaultextension=".json",
                                          filetypes=[("JSON","*.json")])
        if not path:return
        try:
            count=export_dtc(app.db,path)
            messagebox.showinfo("Export DTC",f"Exportate {count} înregistrări cu sursă.",parent=win)
        except Exception as exc:
            messagebox.showerror("Export eșuat",str(exc),parent=win)

    actions=ttk.Frame(base);actions.pack(fill="x",pady=(10,0))
    for caption,action in [
        ("+ Cod DTC",lambda:edit(True)),
        ("Editează",lambda:edit(False)),
        ("Șterge",remove),
        ("Import CSV/JSON",import_file),
        ("Export JSON",export_file)
    ]:
        ttk.Button(actions,text=caption,command=action).pack(side="left",padx=(0,7))
    refresh()
    return win
