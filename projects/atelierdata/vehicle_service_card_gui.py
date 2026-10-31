"""Autodata-style read-only-by-default vehicle technical overview for AtelierData.

Displays only sourced service specifications saved in the existing SQLite
database. User-entered engine code is explicitly marked as unverified.
"""
from __future__ import annotations
from tkinter import ttk,messagebox,simpledialog
import tkinter as tk
from vehicle_service_card import FIELD_DATA,SECTIONS,card,add_value,edit_value,delete_value
from vehicle_service_card_export import export_vehicle_card_html

def open_vehicle_service_card(app):
    vid=app.vid
    if vid is None:
        return messagebox.showinfo("Vehicul necesar",
            "Alege întâi marca, modelul, motorizarea și anul.",parent=app.root)
    sheet=card(app.db,vid)
    vehicle=sheet["vehicle"]
    win=tk.Toplevel(app.root)
    win.title("AtelierData — Fișa tehnică vehicul")
    win.geometry("1200x810");win.minsize(890,630);win.transient(app.root)
    root=ttk.Frame(win,padding=14);root.pack(fill="both",expand=True)
    ttk.Label(root,text="FIȘĂ TEHNICĂ VEHICUL — DATE DE ÎNTREȚINERE",
              font=("Segoe UI Semibold",18)).pack(anchor="w")
    identity=f"{vehicle['make']}  {vehicle['model']}  |  {vehicle['years'] or 'an neprecizat'}  |  {vehicle['fuel'] or 'combustibil neprecizat'}"
    ttk.Label(root,text=identity,font=("Segoe UI Semibold",12)).pack(anchor="w",pady=(4,2))
    ttk.Label(root,text=f"Cod motor (din fișa utilizatorului): {vehicle['engine'] or 'necunoscut'}  "
               f"|  Variantă: {vehicle['variant'] or 'neprecizată'}").pack(anchor="w",pady=(0,8))
    ttk.Label(root,text=("Valorile lipsă apar ca «NECONFIRMAT». Nu folosi cupluri, "
             "presiuni sau specificații fără manualul corespunzător motorizării și pieței."),
             wraplength=1120).pack(anchor="w",pady=(0,9))
    search=tk.StringVar()
    bar=ttk.Frame(root);bar.pack(fill="x")
    ttk.Label(bar,text="Caută parametru:").pack(side="left")
    ttk.Entry(bar,textvariable=search,width=32).pack(side="left",padx=(6,12))
    ttk.Label(bar,text="Cod motor, ulei, antigel, anvelope, frâne, transmisie…").pack(side="left")
    cols=("parameter","value","unit","conditions","source")
    tree=ttk.Treeview(root,columns=cols,show="tree headings",selectmode="browse")
    tree.heading("#0",text="Sistem")
    tree.column("#0",width=170,minwidth=125,stretch=False)
    for key,label,size in zip(cols,("Parametru","Valoare","Unitate","Condiții / variantă","Sursă"),
                              (215,175,75,260,260)):
        tree.heading(key,text=label)
        tree.column(key,width=size,minwidth=60,stretch=True)
    scrollbar=ttk.Scrollbar(root,orient="vertical",command=tree.yview)
    view=ttk.Frame(root);view.pack(fill="both",expand=True,pady=(8,4))
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(in_=view,side="left",fill="both",expand=True)
    scrollbar.pack(in_=view,side="right",fill="y")
    detail=tk.Text(root,height=8,wrap="word",bg="#1a2a42",fg="#eef5ff",
                   font=("Segoe UI",10),padx=11,pady=10,relief="flat")
    detail.pack(fill="x",pady=(4,6))
    summary=tk.StringVar()
    ttk.Label(root,textvariable=summary).pack(anchor="w")
    mapping={}

    def selected():
        ids=tree.selection()
        return mapping.get(ids[0]) if ids else None
    def view_selected(_event=None):
        chosen=selected()
        if not chosen:
            content="Selectează un parametru. «NECONFIRMAT» = nu există valoare cu sursă."
        else:
            index,entry=chosen
            section,label,_,_,_=FIELD_DATA[index]
            content=(f"SECȚIUNE: {section}\nPARAMETRU: {label}\n"
                     f"VALOARE: {entry['value'] if entry else 'NECONFIRMAT'} "
                     f"{entry['unit'] if entry else ''}\n"
                     f"CONDIȚII/VARIANTĂ: {entry['conditions'] if entry else 'Nu există'}\n"
                     f"SURSĂ: {entry['source'] if entry else 'Nu există'}\n\n"
                     "Sursa indicată de utilizator nu garantează compatibilitatea cu vehiculul.")
        detail.config(state="normal")
        detail.delete("1.0","end");detail.insert("1.0",content)
        detail.config(state="disabled")
    def refresh():
        result=card(app.db,vid)
        tree.delete(*tree.get_children());mapping.clear()
        folders={}
        term=search.get().casefold().strip()
        for i,(section,label,system,parameter,hint) in enumerate(FIELD_DATA):
            entries=result["values"][i]
            displayed=entries if entries else [None]
            for j,entry in enumerate(displayed):
                content=f"{section} {label} "+(f"{entry['value']} {entry['conditions']} {entry['source']}" if entry else "")
                if term and term not in content.casefold():continue
                if section not in folders:
                    folders[section]=tree.insert("","end",text=section,open=True,
                                                 values=("","","","",""))
                ident=f"f{i}_{j}"
                mapping[ident]=(i,entry)
                tree.insert(folders[section],"end",iid=ident,text="",
                            values=(label,entry["value"] if entry else "NECONFIRMAT",
                            entry["unit"] if entry else hint,
                            entry["conditions"] if entry else "—",
                            entry["source"] if entry else "—"))
        summary.set(f"{result['sourced_count']} / {result['total_count']} câmpuri cu valori și surse "
                    "înregistrate. Pot exista mai multe variante pentru același parametru.")
        view_selected()
    def edit_dialog():
        chosen=selected()
        if not chosen:
            return messagebox.showinfo("Selectare","Selectează un parametru.",parent=win)
        index,entry=chosen
        _,label,_,_,hint=FIELD_DATA[index]
        dialog=tk.Toplevel(win);dialog.title(label)
        dialog.geometry("630x430");dialog.transient(win);dialog.grab_set()
        frame=ttk.Frame(dialog,padding=16);frame.pack(fill="both",expand=True)
        ttk.Label(frame,text=label,font=("Segoe UI Semibold",14)).pack(anchor="w")
        ttk.Label(frame,text="Completează exclusiv valori din documentația exactă a vehiculului.",
                  wraplength=580).pack(anchor="w",pady=(7,12))
        variables={}
        for key,caption,default in (
            ("value","Valoare *",entry["value"] if entry else ""),
            ("unit","Unitate",entry["unit"] if entry else hint),
            ("conditions","Condiții: dimensiune roată, sarcină, temperatură, piață etc.",
             entry["conditions"] if entry else ""),
            ("source","Sursa exactă: document, pagină, anul/ediția *",
             entry["source"] if entry and entry["id"] is not None else "")
        ):
            ttk.Label(frame,text=caption).pack(anchor="w",pady=(4,1))
            variable=tk.StringVar(value=default);variables[key]=variable
            ttk.Entry(frame,textvariable=variable,width=77).pack(fill="x")
        def save():
            try:
                kw={key:v.get() for key,v in variables.items()}
                if entry and entry["id"] is not None:
                    edit_value(app.db,vid,entry["id"],index,**kw)
                else:
                    add_value(app.db,vid,index,**kw)
                dialog.destroy();refresh()
            except Exception as exc:
                messagebox.showerror("Valoare respinsă",str(exc),parent=dialog)
        ttk.Button(frame,text="Salvează valoarea documentată",command=save).pack(pady=15)
    def add_alternative():
        chosen=selected()
        if not chosen:return
        index,old=chosen
        if old is None:return edit_dialog()
        # New alternatives must be clearly separated from the old entry.
        dialog=tk.Toplevel(win);dialog.title("Variantă alternativă")
        dialog.geometry("600x320");dialog.transient(win);dialog.grab_set()
        p=ttk.Frame(dialog,padding=14);p.pack(fill="both",expand=True)
        values={}
        for key,label,hint in (("value","Valoare *",""),
                               ("unit","Unitate",FIELD_DATA[index][4]),
                               ("conditions","Condiții exacte / variantă *",""),
                               ("source","Sursa documentului, pagina *","")):
            ttk.Label(p,text=label).pack(anchor="w")
            v=tk.StringVar(value=hint);values[key]=v
            ttk.Entry(p,textvariable=v).pack(fill="x")
        def save():
            try:
                if not values["conditions"].get().strip():
                    raise ValueError("Varianta alternativă necesită condiții")
                add_value(app.db,vid,index,**{k:v.get() for k,v in values.items()})
                dialog.destroy();refresh()
            except Exception as exc:messagebox.showerror("Variantă invalidă",str(exc),parent=dialog)
        ttk.Button(p,text="Salvează varianta",command=save).pack(pady=10)
    def delete_selected():
        chosen=selected()
        if not chosen or not chosen[1] or chosen[1]["id"] is None:return
        if messagebox.askyesno("Ștergere","Ștergi numai această valoare cu sursă?",
                               parent=win):
            try:delete_value(app.db,vid,chosen[1]["id"]);refresh()
            except Exception as exc:messagebox.showerror("Ștergere",str(exc),parent=win)
    def save_printable():
        from tkinter import filedialog
        path=filedialog.asksaveasfilename(parent=win,defaultextension=".html",
              filetypes=[("HTML pentru imprimare","*.html")],
              initialfile="AtelierData_fisa_vehicul.html")
        if not path:return
        try:
            summary=export_vehicle_card_html(app.db,vid,path)
            messagebox.showinfo("Fișă exportată",
                f"Fișă salvată: {summary['path']}\n"
                f"Câmpuri cu date documentate: {summary['sourced']}/{summary['fields']}",
                parent=win)
        except Exception as exc:
            messagebox.showerror("Export",str(exc),parent=win)

    buttons=ttk.Frame(root);buttons.pack(fill="x",pady=(6,0))
    ttk.Button(buttons,text="Adaugă / editează valoare",command=edit_dialog).pack(side="left")
    ttk.Button(buttons,text="+ Variantă alternativă",command=add_alternative).pack(side="left",padx=8)
    ttk.Button(buttons,text="Șterge valoare",command=delete_selected).pack(side="left")
    ttk.Button(buttons,text="Reîncarcă",command=refresh).pack(side="left",padx=8)
    ttk.Button(buttons,text="Exportă fișa HTML",command=save_printable).pack(side="left")
    ttk.Button(buttons,text="Închide",command=win.destroy).pack(side="right")
    tree.bind("<<TreeviewSelect>>",view_selected)
    search.trace_add("write",lambda *_:refresh())
    refresh()
    win.vehicle_card_tree=tree
    win.vehicle_card_summary=summary
    return win
