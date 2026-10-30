"""AtelierData vehicle make/model browser powered by the public NHTSA vPIC API.

Searches are user-initiated. Results are cached and never become personal vehicles
until explicitly chosen. No VIN or vehicle documents are transmitted.
"""
from __future__ import annotations
import datetime as dt
from tkinter import ttk, messagebox
import tkinter as tk
from vpic_catalog import (valid_query,fetch_models,cache_models,
                          cached_models,ensure_schema,SOURCE)


def open_vehicle_catalog(app):
    win=tk.Toplevel(app.root)
    win.title("AtelierData — catalog public mărci / modele NHTSA")
    win.geometry("1020x650")
    win.minsize(760,480)
    win.transient(app.root)
    body=ttk.Frame(win,padding=15)
    body.pack(fill="both",expand=True)
    ttk.Label(body,text="CATALOG VEHICULE — NHTSA vPIC",
              font=("Segoe UI Semibold",16)).pack(anchor="w")
    ttk.Label(body,text=("Informații publice pentru identificarea modelelor (în principal SUA). "
       "Nu sunt incluse motoare, cupluri de strângere sau proceduri de reparație.")
    ).pack(anchor="w",pady=(6,10))
    row=ttk.Frame(body)
    row.pack(fill="x",pady=(0,12))
    ttk.Label(row,text="Marcă:").pack(side="left")
    make_var=tk.StringVar(value="MITSUBISHI")
    ttk.Entry(row,textvariable=make_var,width=25).pack(side="left",padx=(7,16))
    ttk.Label(row,text="An model:").pack(side="left")
    year_var=tk.StringVar(value=str(dt.datetime.now(dt.timezone.utc).year))
    ttk.Entry(row,textvariable=year_var,width=8).pack(side="left",padx=(7,16))
    status=tk.StringVar(value="Alege Online pentru o singură interogare NHTSA sau Cache pentru date salvate.")
    fields=("make_name","model_name","model_year","source")
    tree=ttk.Treeview(body,columns=fields,show="headings",selectmode="browse")
    for key,label,width in zip(fields,("Marcă","Model","An model","Sursa datelor"),(220,310,100,320)):
        tree.heading(key,text=label)
        tree.column(key,width=width,minwidth=80,stretch=True)
    tree.pack(fill="both",expand=True,pady=(0,6))
    ttk.Label(body,textvariable=status).pack(anchor="w",pady=(2,8))
    win.models_tree=tree
    win.make_var=make_var
    win.year_var=year_var
    win.catalog_status=status
    selected={}

    def render(models):
        selected.clear()
        tree.delete(*tree.get_children())
        for index,record in enumerate(models):
            data=dict(record)
            key=f"m{index}"
            selected[key]=data
            tree.insert("","end",iid=key,values=(data["make_name"],data["model_name"],
                       data["model_year"],data.get("source",SOURCE)))
        status.set(f"{len(selected)} modele disponibile; motorul trebuie completat manual.")

    def offline():
        try:
            make,year=valid_query(make_var.get(),year_var.get())
            rows=cached_models(app.db,make,year)
            render(rows)
        except Exception as exc:messagebox.showerror("Catalog local",str(exc),parent=win)

    def online():
        # The user explicitly clicks to send only make+year to the government endpoint.
        try:
            make,year=valid_query(make_var.get(),year_var.get())
            status.set("Interogare vPIC în curs (numai marca și anul sunt transmise)...")
            win.update_idletasks()
            models=fetch_models(make,year)
            cache_models(app.db,models)
            render(cached_models(app.db,make,year))
            if not models:
                status.set("Niciun model exact găsit pentru marca/anul ales. Încearcă altă scriere.")
        except Exception as exc:
            status.set("Interogarea online nu a reușit; cache-ul rămâne disponibil.")
            messagebox.showerror("NHTSA vPIC",str(exc),parent=win)

    def add_selected(event=None):
        picked=tree.selection()
        if not picked:return messagebox.showinfo("Selectare","Selectează un model.",parent=win)
        model=selected[picked[0]]
        form=tk.Toplevel(win)
        form.title("Adaugă vehicul în atelier")
        form.geometry("470x370")
        form.transient(win)
        form.grab_set()
        inner=ttk.Frame(form,padding=16);inner.pack(fill="both",expand=True)
        ttk.Label(inner,text=f"{model['make_name']} — {model['model_name']} "
                             f"({model['model_year']})",
                  font=("Segoe UI Semibold",12)).pack(anchor="w",pady=(0,10))
        ttk.Label(inner,text=("Motorul și varianta nu provin din vPIC: introdu datele reale "
                              "din identificarea vehiculului."),wraplength=410).pack(anchor="w",pady=(0,9))
        values={}
        for key,label in (("engine","Cod motor"),("fuel","Combustibil"),("variant","Variantă")):
            ttk.Label(inner,text=label).pack(anchor="w",pady=(5,2))
            var=tk.StringVar()
            ttk.Entry(inner,textvariable=var).pack(fill="x")
            values[key]=var
        def save():
            try:
                engine=values["engine"].get().strip()
                fuel=values["fuel"].get().strip()
                variant=values["variant"].get().strip()
                if any(len(item)>120 for item in (engine,fuel,variant)):
                    raise ValueError("Câmp prea lung")
                years=str(model["model_year"])
                exists=app.db.db.execute(
                    "SELECT id FROM vehicles WHERE make=? AND model=? AND engine=? "
                    "AND years=? AND fuel=? AND variant=?",
                    (model["make_name"],model["model_name"],engine,years,fuel,variant)).fetchone()
                if exists:
                    vid=exists["id"]
                else:
                    vid=app.db.add_vehicle(model["make_name"],model["model_name"],
                                           engine,years,fuel,variant)
                app.vid=vid
                app.refresh()
                status.set("Vehiculul selectat a fost adăugat în catalogul atelierului.")
                form.destroy()
            except Exception as exc:
                messagebox.showerror("Vehicul invalid",str(exc),parent=form)
        ttk.Button(inner,text="Adaugă în AtelierData",command=save).pack(pady=12)
        return form

    actions=ttk.Frame(body)
    actions.pack(fill="x")
    ttk.Button(actions,text="Caută ONLINE vPIC",command=online).pack(side="left",padx=(0,7))
    ttk.Button(actions,text="Caută în cache OFFLINE",command=offline).pack(side="left",padx=(0,7))
    ttk.Button(actions,text="Adaugă modelul selectat",command=add_selected).pack(side="left")
    tree.bind("<Double-1>",add_selected)
    win.load_offline_models=offline
    win.load_online_models=online
    return win
