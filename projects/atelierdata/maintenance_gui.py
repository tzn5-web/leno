"""Native Tkinter maintenance plan and service history dialog for AtelierData."""
from __future__ import annotations
from datetime import date

from maintenance_plans import (
    add_plan, delete_plan, get_plan, update_plan, list_plans,
    log_service, list_services, delete_service, due_status
)


def open_maintenance_window(app, editor_class):
    from tkinter import ttk, messagebox
    tk=app.tk
    vehicle_id=app.vid
    if vehicle_id is None:
        messagebox.showinfo("Vehicul necesar","Alege vehiculul și motorizarea.")
        return None

    win=tk.Toplevel(app.root)
    win.title("AtelierData — întreținere și istoric")
    win.geometry("1250x720")
    win.minsize(940,580)
    win.transient(app.root)
    frame=ttk.Frame(win,padding=14)
    frame.pack(fill="both",expand=True)
    ttk.Label(frame,text="PLAN DE ÎNTREȚINERE — VALORI DOCUMENTATE",
              font=("Segoe UI Semibold",16)).pack(anchor="w")
    ttk.Label(frame,text="Intervalele trebuie introduse dintr-o sursă autorizată. "
                         "Scadența este orientativă; fără istoric nu se calculează."
             ).pack(anchor="w",pady=(5,8))

    current=ttk.Frame(frame);current.pack(fill="x",pady=(0,8))
    ttk.Label(current,text="Kilometraj actual (opțional):").pack(side="left")
    odometer=tk.StringVar()
    ttk.Entry(current,textvariable=odometer,width=16).pack(side="left",padx=8)
    ttk.Label(current,text="Dată evaluare (YYYY-MM-DD):").pack(side="left",padx=(18,0))
    today=tk.StringVar(value=date.today().isoformat())
    ttk.Entry(current,textvariable=today,width=14).pack(side="left",padx=8)

    cols=("title","system","intervals","status","due_km","due_date")
    plans=ttk.Treeview(frame,columns=cols,show="headings",height=12)
    for key,name,width in zip(cols,
             ("Operație","Sistem","Interval","Stare","Următorul km","Următoarea dată"),
             (260,160,170,200,140,140)):
        plans.heading(key,text=name)
        plans.column(key,width=width,stretch=True,minwidth=70)
    plans.pack(fill="both",expand=True,pady=(0,10))
    win.maintenance_tree=plans
    ttk.Label(frame,text="ISTORIC INTERVENȚII — SURSA ȘI CONDIȚIILE SUNT PĂSTRATE ÎN PLAN"
              ).pack(anchor="w",pady=(5,4))
    logcols=("date","km","notes")
    events=ttk.Treeview(frame,columns=logcols,show="headings",height=5)
    for key,name,width in zip(logcols,("Dată","Kilometraj","Note intervenție"),(120,140,630)):
        events.heading(key,text=name)
        events.column(key,width=width,stretch=True)
    events.pack(fill="both",expand=True)
    win.service_events_tree=events

    state={"id":None}
    summary=tk.StringVar()
    ttk.Label(frame,textvariable=summary).pack(anchor="w",pady=(7,3))
    details=tk.StringVar()
    ttk.Label(frame,textvariable=details).pack(anchor="w",pady=(0,5))

    def chosen():
        selection=plans.selection()
        return int(selection[0]) if selection else None

    def update_events(event=None):
        pid=chosen()
        state["id"]=pid
        events.delete(*events.get_children())
        if pid is None:
            details.set("Selectează un plan.")
            return
        plan=get_plan(app.db,pid)
        if plan is None:
            return
        details.set("Condiții: "+(plan["conditions"] or "neprecizate")
                    +" | Sursă: "+plan["source"])
        for row in list_services(app.db,pid):
            events.insert("","end",iid=str(row["id"]),values=(
                row["performed_on"],row["odometer_km"] if row["odometer_km"] is not None else "—",
                row["notes"]))
    plans.bind("<<TreeviewSelect>>",update_events)

    def refresh(prefer=None):
        try:
            km=odometer.get().strip() or None
            when=today.get().strip()
            # Validation also occurs within due_status (never assume a current odo).
            rows=list_plans(app.db,vehicle_id)
            plans.delete(*plans.get_children())
            for row in rows:
                interval=(" / ".join(v for v in
                    (f"{row['interval_km']} km" if row["interval_km"] is not None else "",
                     f"{row['interval_months']} luni" if row["interval_months"] is not None else "")
                     if v))
                try:
                    due=due_status(app.db,row["id"],km,when)
                    status=due["status"]
                    target_km=due["due_km"] if due["due_km"] is not None else "—"
                    target_date=due["due_date"] or "—"
                except ValueError as exc:
                    status="Date evaluare invalide"
                    target_km=target_date="—"
                    summary.set(str(exc))
                plans.insert("","end",iid=str(row["id"]),
                    values=(row["title"],row["system"],interval,status,target_km,target_date))
            selected=prefer if prefer is not None else state["id"]
            if selected is not None and plans.exists(str(selected)):
                plans.selection_set(str(selected))
                update_events()
            else:
                state["id"]=None
                events.delete(*events.get_children())
                details.set("")
            if not rows:summary.set("Nu există planuri. Adaugă un interval verificat și sursa lui.")
            elif not summary.get():summary.set(f"{len(rows)} planuri; fără baseline nu estimăm scadența.")
        except Exception as exc:
            messagebox.showerror("Evaluare invalidă",str(exc),parent=win)

    def plan_form(edit=False):
        selected=chosen()
        previous=get_plan(app.db,selected) if edit and selected else None
        if edit and previous is None:
            return messagebox.showinfo("Selectare","Alege planul de editat.",parent=win)
        def val(key):
            return str(previous[key]) if previous and previous[key] is not None else ""
        fields=[
            ("title","Operația de întreținere *",val("title")),
            ("system","Sistem *",val("system")),
            ("interval_km","Interval kilometri (opțional)",val("interval_km")),
            ("interval_months","Interval luni (opțional)",val("interval_months")),
            ("conditions","Condiții speciale / regim sever",val("conditions")),
            ("source","Sursa exactă a intervalului *",val("source"))
        ]
        data=editor_class(win,"Editare plan" if edit else "Plan de întreținere nou",fields).value
        if data is None:return
        try:
            if edit:
                update_plan(app.db,selected,**data)
                pid=selected
            else:
                pid=add_plan(app.db,vehicle_id,**data)
            summary.set("")
            refresh(pid)
        except Exception as exc:messagebox.showerror("Plan invalid",str(exc),parent=win)

    def service_form():
        pid=chosen()
        if pid is None:
            return messagebox.showinfo("Selectare","Selectează planul.",parent=win)
        data=editor_class(win,"Înregistrează intervenția",[
            ("performed_on","Dată executare YYYY-MM-DD",date.today().isoformat()),
            ("odometer_km","Kilometraj la intervenție (când este aplicabil)",odometer.get()),
            ("notes","Observații / documente și proveniență","")
        ]).value
        if data is None:return
        try:
            log_service(app.db,pid,**data)
            summary.set("")
            refresh(pid)
        except Exception as exc:
            messagebox.showerror("Intervenție invalidă",str(exc),parent=win)

    def remove_plan():
        pid=chosen()
        if pid is not None and messagebox.askyesno(
                "Ștergere","Ștergi planul și istoricul tuturor intervențiilor lui?",
                parent=win):
            delete_plan(app.db,pid)
            summary.set("")
            refresh()

    def remove_service():
        selected=events.selection()
        if not selected:return
        if messagebox.askyesno("Ștergere","Ștergi această intervenție?",parent=win):
            delete_service(app.db,int(selected[0]))
            summary.set("")
            refresh(chosen())

    actions=ttk.Frame(frame);actions.pack(fill="x",pady=(8,0))
    for label,callback in [
        ("Actualizează scadența",refresh),
        ("+ Plan",lambda:plan_form(False)),
        ("Editează plan",lambda:plan_form(True)),
        ("Șterge plan",remove_plan),
        ("+ Intervenție",service_form),
        ("Șterge intervenție",remove_service)
    ]:
        ttk.Button(actions,text=label,command=callback).pack(side="left",padx=(0,7))
    refresh()
    return win
