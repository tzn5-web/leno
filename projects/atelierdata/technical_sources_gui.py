"""Windows GUI for an offline, curated catalogue of external automotive sources.

Only the user-activated 'Open' button launches a browser. Search/filter remains
offline, and no VIN, vehicle data, article content, or query is transmitted.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

from technical_sources import SOURCES, search_sources, makes, categories, ACCESS, normalize

ACCESS_NAMES={
    "gratis":"Gratuit",
    "cont_gratuit":"Gratuit cu cont",
    "aplicatie_gratuita":"Aplicație gratuită",
    "mixt":"Gratuit + opțiuni plătite",
    "cu_plata":"Cu plată / abonament",
    "public_neoficial":"Public, neoficial",
}

def make_for_selected_vehicle(app):
    if getattr(app,"vid",None) is None:
        return ""
    row=app.db.db.execute("SELECT make FROM vehicles WHERE id=?",(app.vid,)).fetchone()
    if not row:
        return ""
    name=normalize(row["make"])
    alias={"vauxhall":"opel","škoda":"skoda","mercedes":"mercedes-benz",
           "vw":"volkswagen","citroën":"citroen","mini cooper":"mini"}
    return alias.get(name,name)

def open_sources_window(app):
    win=tk.Toplevel(app.root)
    win.title("AtelierData — surse tehnice pe mărci")
    win.geometry("1160x700")
    win.minsize(820,490)
    win.transient(app.root)
    frame=ttk.Frame(win,padding=15)
    frame.pack(fill="both",expand=True)

    ttk.Label(frame,text="SURSE TEHNICE — MANUALE, SCHEME, DIAGNOZĂ",
              font=("Segoe UI Semibold",16)).pack(anchor="w",pady=(0,7))
    ttk.Label(frame,text=(
        "Catalog de LINKURI, nu o bază de manuale importată. "
        "Unele servicii cer cont sau abonament. Verifică motorizarea, anul și piața. "
        "Datele vehiculului și căutările NU sunt trimise automat pe internet."
    ),wraplength=1040).pack(anchor="w",pady=(0,10))

    controls=ttk.Frame(frame)
    controls.pack(fill="x",pady=(0,8))
    search=tk.StringVar()
    make=tk.StringVar(value=make_for_selected_vehicle(app) or "Toate")
    category=tk.StringVar(value="Toate")
    access=tk.StringVar(value="Toate")
    ttk.Label(controls,text="Caută:").grid(row=0,column=0,sticky="w")
    ttk.Entry(controls,textvariable=search,width=26).grid(row=1,column=0,padx=(0,8),sticky="ew")
    ttk.Label(controls,text="Marcă:").grid(row=0,column=1,sticky="w")
    make_combo=ttk.Combobox(controls,textvariable=make,
                            values=["Toate"]+makes(),state="readonly",width=19)
    make_combo.grid(row=1,column=1,padx=(0,8),sticky="ew")
    ttk.Label(controls,text="Tip informație:").grid(row=0,column=2,sticky="w")
    category_combo=ttk.Combobox(controls,textvariable=category,
                               values=["Toate"]+categories(),state="readonly",width=20)
    category_combo.grid(row=1,column=2,padx=(0,8),sticky="ew")
    ttk.Label(controls,text="Acces:").grid(row=0,column=3,sticky="w")
    access_options=["Toate"]+sorted(set(ACCESS_NAMES.values()))
    access_combo=ttk.Combobox(controls,textvariable=access,
                             values=access_options,state="readonly",width=26)
    access_combo.grid(row=1,column=3,sticky="ew")
    for i in range(4):controls.columnconfigure(i,weight=1)

    layout=ttk.PanedWindow(frame,orient="vertical")
    layout.pack(fill="both",expand=True,pady=(4,5))
    top=ttk.Frame(layout)
    bottom=ttk.Frame(layout)
    layout.add(top,weight=5)
    layout.add(bottom,weight=3)

    cols=("source","brands","topic","access")
    tree=ttk.Treeview(top,columns=cols,show="headings",selectmode="browse")
    for key,label,width in zip(cols,("Sursă","Mărci","Domeniu","Acces"),
                                (280,310,250,190)):
        tree.heading(key,text=label)
        tree.column(key,width=width,minwidth=80,stretch=True)
    scroll=ttk.Scrollbar(top,orient="vertical",command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left",fill="both",expand=True)
    scroll.pack(side="right",fill="y")
    detail=tk.Text(bottom,height=9,wrap="word",state="disabled",
                   bg="#1a2a42",fg="#eef5ff",font=("Segoe UI",10),relief="flat",
                   padx=11,pady=10)
    detail.pack(fill="both",expand=True)
    status=tk.StringVar()
    ttk.Label(frame,textvariable=status).pack(anchor="w",pady=(2,7))
    picked={}
    def selected():
        keys=tree.selection()
        return picked.get(keys[0]) if keys else None
    def show_detail(event=None):
        item=selected()
        if not item:
            text="Selectează o sursă pentru detalii și proveniență."
        else:
            brands=", ".join(item.makes) if "*" not in item.makes else "OBD/RMI — mai multe mărci"
            text=(f"{item.title}\n\nMărci: {brands}\n"
                  f"Tip: {', '.join(item.categories)}\nAcces: {ACCESS_NAMES[item.access]}\n"
                  f"Piață: {item.market}\n\n{item.notes}\n\n"
                  f"Link: {item.url}\nDovadă: {item.provenance}\n\n"
                  "Un link public nu acordă automat dreptul de a descărca sau redistribui manualul.")
        detail.configure(state="normal")
        detail.delete("1.0","end")
        detail.insert("1.0",text)
        detail.configure(state="disabled")

    def refresh(*_):
        access_key=next((k for k,v in ACCESS_NAMES.items() if v==access.get()),"")
        results=search_sources(search.get(),
                               "" if make.get()=="Toate" else make.get(),
                               "" if category.get()=="Toate" else category.get(),
                               access_key)
        tree.delete(*tree.get_children())
        picked.clear()
        for item in results:
            picked[item.key]=item
            brands="mai multe mărci" if "*" in item.makes else ", ".join(item.makes[:4]) + (
                " …" if len(item.makes)>4 else "")
            tree.insert("","end",iid=item.key,values=(item.title,brands,
                       ", ".join(item.categories[:2]),ACCESS_NAMES[item.access]))
        status.set(f"{len(results)} surse găsite din {len(SOURCES)}. "
                   "Linkurile se deschid numai la cerere, în browserul extern.")
        show_detail()

    def open_browser():
        item=selected()
        if item is None:
            return messagebox.showinfo("Selectare","Selectează o sursă.",parent=win)
        if item.access=="cu_plata":
            confirmed=messagebox.askyesno("Acces condiționat",
                "Sursa aleasă poate necesita cont și abonament. "
                "Continuăm către site-ul furnizorului, fără a cumpăra automat?",
                parent=win)
            if not confirmed:return
        try:
            webbrowser.open_new_tab(item.url)
        except Exception as exc:
            messagebox.showerror("Browser",str(exc),parent=win)

    controls_frame=ttk.Frame(frame)
    controls_frame.pack(fill="x",pady=(3,0))
    ttk.Button(controls_frame,text="Deschide sursa în browser",
               command=open_browser).pack(side="left",padx=(0,8))
    ttk.Button(controls_frame,text="Toate mărcile",
               command=lambda:make.set("Toate")).pack(side="left",padx=(0,8))
    ttk.Button(controls_frame,text="Închide",command=win.destroy).pack(side="right")
    for var in (search,make,category,access):var.trace_add("write",refresh)
    tree.bind("<<TreeviewSelect>>",show_detail)
    tree.bind("<Double-1>",lambda event:open_browser())
    refresh()
    win.sources_tree=tree
    win.sources_status=status
    win.sources_search=search
    win.sources_make=make
    return win
