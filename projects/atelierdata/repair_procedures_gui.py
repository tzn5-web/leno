"""Native Windows/Tkinter procedure navigator for user-owned, sourced workshop data."""
from __future__ import annotations

from repair_export import export_procedure_html,export_procedures_json
from procedure_audit import audit_procedure, get_step_reference
from procedure_search_hits import list_procedure_hits
from repair_procedures import (
    add_step, create_procedure, delete_procedure, delete_step, get_procedure,
    list_procedures, list_steps, list_reference_articles, move_step, procedure_text, update_procedure, update_step
)


def open_procedures_window(app, editor_class, selected_procedure_id=None,
                           selected_step_id=None, vehicle_id=None):
    from tkinter import filedialog, messagebox, simpledialog, ttk
    tk=app.tk
    vehicle_id=app.vid if vehicle_id is None else vehicle_id
    if vehicle_id is None:
        messagebox.showinfo("Vehicul necesar", "Selectează un vehicul și motorizarea sa.")
        return None
    if selected_procedure_id is not None:
        target=get_procedure(app.db,selected_procedure_id)
        if target is None or target["vehicle_id"]!=vehicle_id:
            raise ValueError("Procedura nu aparține vehiculului selectat")
        if selected_step_id is not None:
            linked=app.db.db.execute(
                "SELECT 1 FROM procedure_steps WHERE id=? AND procedure_id=?",
                (selected_step_id,selected_procedure_id)).fetchone()
            if linked is None:
                raise ValueError("Pasul nu aparține procedurii selectate")
    elif selected_step_id is not None:
        raise ValueError("Selectarea pasului necesită procedura asociată")
    top=tk.Toplevel(app.root)
    top.title("AtelierData — proceduri de atelier")
    top.geometry("1180x720")
    top.minsize(920,540)
    top.transient(app.root)
    body=ttk.Frame(top,padding=12)
    body.pack(fill="both",expand=True)

    ttk.Label(body,text="PROCEDURI DE REPARAȚIE — PAȘI, AVERTISMENTE ȘI REFERINȚE",
              font=("Segoe UI Semibold",14)).pack(anchor="w",pady=(0,10))
    ttk.Label(body,text="Introduceți numai proceduri verificate, cu sursă și drept de utilizare. "
                         "Programul nu furnizează valori tehnice implicit.").pack(anchor="w",pady=(0,10))

    pane=ttk.PanedWindow(body,orient="horizontal")
    pane.pack(fill="both",expand=True)
    left=ttk.Frame(pane)
    right=ttk.Frame(pane)
    pane.add(left,weight=3)
    pane.add(right,weight=7)

    ttk.Label(left,text="PROCEDURI").pack(anchor="w",pady=(0,5))
    search=tk.StringVar()
    field=ttk.Entry(left,textvariable=search)
    field.pack(fill="x",padx=(0,12),pady=(0,4))
    ttk.Label(left,text="Căutare literală: proceduri, pași, avertismente și documente.",
              wraplength=290).pack(anchor="w",pady=(0,8))
    search_notice=tk.StringVar(value="")
    ttk.Label(left,textvariable=search_notice,wraplength=290).pack(anchor="w")
    ttk.Button(left,text="Rezultate detaliate → pas",command=lambda:open_search_hits()
               ).pack(anchor="w",pady=(4,7))
    procedures=ttk.Treeview(left,show="tree")
    procedures.pack(fill="both",expand=True,padx=(0,12))
    ttk.Label(right,text="PAȘI ÎN ORDINEA EXECUȚIEI").pack(anchor="w",pady=(0,5))
    columns=("number","instruction","warning","reference")
    steps=ttk.Treeview(right,columns=columns,show="headings",selectmode="browse")
    for col,title,width in zip(columns,("Nr.","Instrucțiune","Avertisment","Document"),
                                (45,310,190,180)):
        steps.heading(col,text=title)
        steps.column(col,width=width,stretch=True,minwidth=35)
    steps.pack(fill="both",expand=True)
    ttk.Label(right,text="DETALII PROCEDURĂ").pack(anchor="w",pady=(10,5))
    detail=tk.Text(right,height=10,wrap="word",state="disabled",
                   font=("Segoe UI",10),bg="#1a2a42",fg="#eef5ff",relief="flat")
    detail.pack(fill="both",expand=False)

    state={"pid":None}
    def render(text):
        detail.configure(state="normal")
        detail.delete("1.0","end")
        detail.insert("1.0",text)
        detail.configure(state="disabled")

    def refresh_proc(prefer=None):
        try:
            candidates=list_procedures(app.db,vehicle_id,search.get())
        except ValueError as exc:
            candidates=[]
            search_notice.set("Căutare invalidă: "+str(exc))
        else:
            search_notice.set(f"{len(candidates)} proceduri găsite")
        procedures.delete(*procedures.get_children())
        for row in candidates:
            procedures.insert("","end",iid=str(row["id"]),
                              text=f"{row['system']} / {row['title']}")
        chosen=prefer if prefer is not None else state["pid"]
        if chosen is not None and procedures.exists(str(chosen)):
            procedures.selection_set(str(chosen))
            procedures.see(str(chosen))
            state["pid"]=chosen
        else:
            state["pid"]=None
        refresh_steps()

    def refresh_steps(prefer=None):
        steps.delete(*steps.get_children())
        pid=state["pid"]
        if pid is None:
            render("Selectează o procedură sau adaugă una nouă.")
            return
        for step in list_steps(app.db,pid):
            steps.insert("","end",iid=str(step["id"]),values=(
                step["step_number"],step["instruction"][:130],
                step["safety_note"][:95],step["reference_title"] or ""))
        if prefer is not None and steps.exists(str(prefer)):
            steps.selection_set(str(prefer))
        render(procedure_text(app.db,pid))

    def selection(event=None):
        items=procedures.selection()
        state["pid"]=int(items[0]) if items else None
        selected=(selected_step_id if state["pid"]==selected_procedure_id else None)
        refresh_steps(selected)

    procedures.bind("<<TreeviewSelect>>",selection)
    search.trace_add("write",lambda *_:refresh_proc())

    def open_search_hits():
        """List exact match locations and jump to a verified same-vehicle step."""
        try:
            hits=list_procedure_hits(app.db,vehicle_id,search.get())
        except ValueError as exc:
            messagebox.showinfo("Căutare detaliată",str(exc),parent=top)
            return None
        popup=tk.Toplevel(top)
        popup.title("Rezultate căutare — proceduri și pași")
        popup.geometry("1080x540")
        popup.minsize(740,360)
        popup.transient(top)
        box=ttk.Frame(popup,padding=12)
        box.pack(fill="both",expand=True)
        ttk.Label(box,text=f"{len(hits)} potriviri pentru «{search.get()}»",
                  font=("Segoe UI Semibold",12)).pack(anchor="w",pady=(0,7))
        ttk.Label(box,text="Rezultatele sunt din documentația locală, cu proveniență și vehicul verificate."
                  ).pack(anchor="w",pady=(0,7))
        columns=("procedure","step","field","excerpt","source")
        table=ttk.Treeview(box,columns=columns,show="headings",selectmode="browse")
        for key,title,width in zip(columns,
                ("Procedură","Pas","Câmp","Fragment găsit","Proveniență"),
                (190,45,160,420,190)):
            table.heading(key,text=title)
            table.column(key,width=width,minwidth=40,stretch=True)
        table.pack(fill="both",expand=True)
        for index,hit in enumerate(hits):
            table.insert("","end",iid=str(index),values=(
                hit["procedure_title"],
                hit["step_number"] if hit["step_number"] is not None else "—",
                hit["field"],hit["excerpt"],hit["source"]))
        def go_to_hit(event=None):
            selected=table.selection()
            if not selected:return None
            hit=hits[int(selected[0])]
            procedure=get_procedure(app.db,hit["procedure_id"])
            if procedure is None or procedure["vehicle_id"]!=vehicle_id:
                messagebox.showerror("Referință invalidă",
                    "Procedura nu mai aparține vehiculului selectat.",parent=popup)
                return None
            sid=hit["step_id"]
            if sid is not None:
                exists=app.db.db.execute(
                    "SELECT 1 FROM procedure_steps WHERE id=? AND procedure_id=?",
                    (sid,hit["procedure_id"])).fetchone()
                if exists is None:
                    messagebox.showerror("Referință invalidă",
                        "Pasul nu mai aparține procedurii.",parent=popup)
                    return None
            refresh_proc(hit["procedure_id"])
            if not procedures.exists(str(hit["procedure_id"])):
                messagebox.showinfo("Căutare modificată",
                    "Procedura nu mai corespunde filtrului curent.",parent=popup)
                return None
            procedures.selection_set(str(hit["procedure_id"]))
            procedures.see(str(hit["procedure_id"]))
            state["pid"]=hit["procedure_id"]
            refresh_steps(sid)
            if sid is not None and steps.exists(str(sid)):
                steps.selection_set(str(sid))
                steps.see(str(sid))
            top.lift()
            return hit
        table.bind("<Double-1>",go_to_hit)
        ttk.Button(box,text="Deschide potrivirea selectată",command=go_to_hit
                   ).pack(anchor="w",pady=(9,0))
        popup.hits_tree=table
        popup.go_to_hit=go_to_hit
        popup.hits=hits
        return popup

    def procedure_form(edit):
        current=get_procedure(app.db,state["pid"]) if edit and state["pid"] else None
        if edit and current is None:
            return messagebox.showinfo("Selectare","Alege mai întâi o procedură.",parent=top)
        fields=[("system","Sistem *",current["system"] if current else ""),
                ("title","Titlu *",current["title"] if current else ""),
                ("summary","Rezumat",current["summary"] if current else ""),
                ("precautions","Avertisment general",current["precautions"] if current else ""),
                ("source","Sursă verificată *",current["source"] if current else "")]
        data=editor_class(top,"Editare procedură" if edit else "Procedură nouă",fields).value
        if data is None:return
        try:
            if edit:
                update_procedure(app.db,current["id"],**data)
                chosen=current["id"]
            else:
                chosen=create_procedure(app.db,vehicle_id,**data)
            refresh_proc(chosen)
        except Exception as exc:messagebox.showerror("Date invalide",str(exc),parent=top)

    def step_form(edit):
        pid=state["pid"]
        if pid is None:
            return messagebox.showinfo("Selectare","Selectează o procedură.",parent=top)
        selected=steps.selection()
        current=None
        if edit:
            if not selected:
                return messagebox.showinfo("Selectare","Selectează un pas.",parent=top)
            current=app.db.db.execute("SELECT * FROM procedure_steps WHERE id=?",
                                      (int(selected[0]),)).fetchone()
        fields=[("safety_note","Avertisment la acest pas",
                 current["safety_note"] if current else ""),
                ("article_id","ID document asociat din același vehicul (opțional)",
                 str(current["article_id"]) if current and current["article_id"] else "")]
        data=editor_class(top,"Editare pas" if edit else "Adaugă pas",
                          fields,body=("instruction",current["instruction"] if current else "")).value
        if data is None:return
        try:
            ref=int(data["article_id"]) if data["article_id"] else None
            if edit:
                update_step(app.db,current["id"],data["instruction"],data["safety_note"],ref)
                chosen=current["id"]
            else:
                chosen=add_step(app.db,pid,data["instruction"],data["safety_note"],ref)
            refresh_steps(chosen)
        except Exception as exc:messagebox.showerror("Pas invalid",str(exc),parent=top)

    def step_move(direction):
        selected=steps.selection()
        if not selected:return
        try:
            move_step(app.db,int(selected[0]),direction)
            refresh_steps(int(selected[0]))
        except Exception as exc:messagebox.showerror("Ordonare",str(exc),parent=top)

    def procedure_remove():
        pid=state["pid"]
        if pid is not None and messagebox.askyesno("Ștergere",
                                      "Ștergi procedura și toți pașii?",parent=top):
            delete_procedure(app.db,pid)
            refresh_proc()

    def step_remove():
        selected=steps.selection()
        if selected and messagebox.askyesno("Ștergere","Ștergi pasul selectat?",parent=top):
            delete_step(app.db,int(selected[0]))
            refresh_steps()

    def choose_reference():
        """Select a verified same-vehicle article by title, not by opaque numeric ID."""
        selected=steps.selection()
        if not selected or state["pid"] is None:
            messagebox.showinfo("Selectare","Selectează un pas pentru a lega un document.",parent=top)
            return None
        sid=int(selected[0])
        original=app.db.db.execute("SELECT * FROM procedure_steps WHERE id=?",(sid,)).fetchone()
        if original is None or original["procedure_id"]!=state["pid"]:
            messagebox.showerror("Referință","Pasul nu mai aparține procedurii.",parent=top)
            return None
        pid=state["pid"]
        picker=tk.Toplevel(top)
        picker.title("Alege documentul asociat pasului")
        picker.geometry("790x500")
        picker.minsize(580,340)
        picker.transient(top)
        picker.grab_set()
        box=ttk.Frame(picker,padding=12)
        box.pack(fill="both",expand=True)
        ttk.Label(box,text="DOCUMENTE ALE ACELUIAȘI VEHICUL",
                  font=("Segoe UI Semibold",12)).pack(anchor="w",pady=(0,5))
        ttk.Label(box,text="Selectează un document propriu/licențiat; alte vehicule sunt excluse."
                 ).pack(anchor="w",pady=(0,8))
        search_ref=tk.StringVar()
        ttk.Entry(box,textvariable=search_ref).pack(fill="x",pady=(0,8))
        columns=("category","title","source")
        references=ttk.Treeview(box,columns=columns,show="headings",selectmode="browse")
        for key,label,width in zip(columns,("Categorie","Document","Proveniență"),(170,280,250)):
            references.heading(key,text=label)
            references.column(key,width=width,stretch=True,minwidth=75)
        references.pack(fill="both",expand=True)
        notice=tk.StringVar()
        ttk.Label(box,textvariable=notice).pack(anchor="w",pady=(7,5))

        def populate(*_):
            references.delete(*references.get_children())
            try:
                docs=list_reference_articles(app.db,pid,search_ref.get())
                for article in docs:
                    references.insert("","end",iid=str(article["id"]),
                                      values=(article["category"],article["title"],article["source"]))
                if original["article_id"] is not None and references.exists(str(original["article_id"])):
                    references.selection_set(str(original["article_id"]))
                notice.set(f"{len(docs)} documente; sursa este afișată pentru verificare.")
            except Exception as exc:
                notice.set("Eroare de căutare: "+str(exc))
        search_ref.trace_add("write",populate)
        populate()

        def change_link(article_id):
            try:
                current=app.db.db.execute("SELECT * FROM procedure_steps WHERE id=?",(sid,)).fetchone()
                if current is None or current["procedure_id"]!=pid:
                    raise ValueError("Pasul a fost șters sau mutat")
                update_step(app.db,sid,current["instruction"],current["safety_note"],article_id)
                picker.destroy()
                refresh_steps(sid)
            except Exception as exc:
                messagebox.showerror("Referință invalidă",str(exc),parent=picker)

        def apply():
            picked=references.selection()
            if not picked:
                messagebox.showinfo("Selectare","Alege un document din listă.",parent=picker)
                return
            change_link(int(picked[0]))

        actions=ttk.Frame(box)
        actions.pack(fill="x",pady=(7,0))
        ttk.Button(actions,text="Leagă documentul selectat",command=apply).pack(side="left",padx=(0,8))
        ttk.Button(actions,text="Elimină legătura",command=lambda:change_link(None)).pack(side="left")
        ttk.Button(actions,text="Anulează",command=picker.destroy).pack(side="right")
        references.bind("<Double-1>",lambda _event:apply())
        picker.reference_tree=references
        picker.apply_reference=apply
        picker.clear_reference=lambda:change_link(None)
        top.reference_picker=picker
        return picker

    def open_schematic_reference():
        """Navigate to a linked diagram, keeping the procedure's vehicle scope."""
        selected=steps.selection()
        if not selected or state["pid"] is None:
            messagebox.showinfo("Schemă", "Selectează un pas.", parent=top)
            return None
        row=app.db.db.execute(
            "SELECT s.article_id FROM procedure_steps s "
            "JOIN procedures p ON p.id=s.procedure_id "
            "WHERE s.id=? AND p.id=? AND p.vehicle_id=?",
            (int(selected[0]),state["pid"],vehicle_id)).fetchone()
        if row is None or row["article_id"] is None:
            messagebox.showinfo("Schemă", "Pasul nu are schemă asociată.", parent=top)
            return None
        try:
            from schematic_viewer import get_schematic_reference, open_schematics_window
            get_schematic_reference(app.db,vehicle_id,row["article_id"])
            return open_schematics_window(
                app,editor_class,selected_article_id=row["article_id"],
                vehicle_id=vehicle_id)
        except ValueError as exc:
            messagebox.showinfo("Schemă indisponibilă",str(exc),parent=top)
            return None
        except Exception as exc:
            messagebox.showerror("Eroare schemă",str(exc),parent=top)
            return None

    def open_reference():
        selected=steps.selection()
        if not selected:return
        try:
            article=get_step_reference(
                app.db,int(selected[0]),vehicle_id,state["pid"])
        except ValueError as exc:
            return messagebox.showerror("Referință invalidă",str(exc),parent=top)
        if article is None:
            return messagebox.showinfo("Referință","Pasul nu are document asociat.",parent=top)
        from atelierdata_extensions import list_documents
        linked=list_documents(app.db,article["id"])
        display=tk.Toplevel(top)
        display.title("Document asociat: "+article["title"])
        display.geometry("700x500")
        area=tk.Text(display,wrap="word",font=("Segoe UI",11))
        area.pack(fill="both",expand=True)
        attachments="\n".join(row["path"] for row in linked)
        area.insert("1.0",f"SURSĂ: {article['source']}\n\n{article['content']}\n\n"
                  f"ATAȘAMENTE ({len(linked)}):\n{attachments}")
        area.configure(state="disabled")
        if linked:
            def open_attachment():
                import os,sys,subprocess
                choice=1 if len(linked)==1 else simpledialog.askinteger(
                    "Atașamente","Alege numărul atașamentului (1–"+str(len(linked))+"):",
                    minvalue=1,maxvalue=len(linked),parent=display)
                if choice is None:return
                try:
                    from atelierdata_extensions import resolve_document
                    path=resolve_document(app.db,linked[choice-1]["id"])
                    if sys.platform=="win32":os.startfile(str(path))
                    else:subprocess.Popen(["xdg-open",str(path)])
                except Exception as exc:
                    messagebox.showerror("Atașament invalid",str(exc),parent=display)
            ttk.Button(display,text="Deschide atașament verificat SHA256",
                       command=open_attachment).pack(pady=8)

    def open_procedure_audit():
        """Read-only, vehicle-scoped verification of steps and managed files."""
        pid=state["pid"]
        if pid is None:
            messagebox.showinfo("Audit", "Selectează o procedură.", parent=top)
            return None
        try:
            report=audit_procedure(app.db,pid)
            if report["vehicle_id"]!=vehicle_id:
                raise ValueError("Procedura aparține altui vehicul")
        except Exception as exc:
            messagebox.showerror("Audit indisponibil",str(exc),parent=top)
            return None
        audit=tk.Toplevel(top)
        audit.title("Audit integritate — procedură și referințe")
        audit.geometry("1040x560")
        audit.minsize(720,380)
        audit.transient(top)
        pane=ttk.Frame(audit,padding=12)
        pane.pack(fill="both",expand=True)
        ttk.Label(pane,text="AUDIT DOCUMENTAȚIE — DOAR CITIRE",
                  font=("Segoe UI Semibold",13)).pack(anchor="w",pady=(0,8))
        summary=(f"Pași: {report['steps']} | Fișiere SHA256 verificate: "
                 f"{report['verified_attachments']} | Erori: {report['errors']} "
                 f"| Avertismente: {report['warnings']}")
        ttk.Label(pane,text=summary).pack(anchor="w",pady=(0,5))
        ttk.Label(pane,text="Sursă procedură: "+report["source"],
                  wraplength=950).pack(anchor="w",pady=(0,6))
        ttk.Label(pane,text=("SHA256 verifică integritatea fișierelor, nu corectitudinea "
                             "tehnică sau dreptul de utilizare."),
                  wraplength=950).pack(anchor="w",pady=(0,9))
        columns=("severity","step","code","detail")
        table=ttk.Treeview(pane,columns=columns,show="headings",selectmode="browse")
        for key,label,width in zip(columns,
                ("Nivel","Pas","Cod verificare","Detalii"),(95,65,260,540)):
            table.heading(key,text=label)
            table.column(key,width=width,minwidth=55,stretch=True)
        table.pack(fill="both",expand=True)
        for index,issue in enumerate(report["issues"]):
            table.insert("","end",iid=str(index),values=(
                issue["severity"],
                issue["step_number"] if issue["step_number"] is not None else "—",
                issue["code"],issue["detail"]))
        if not report["issues"]:
            ttk.Label(pane,text="Nu au fost detectate probleme în verificările efectuate."
                      ).pack(anchor="w",pady=(7,0))
        def go_to_step(event=None):
            picked=table.selection()
            if not picked:
                return
            issue=report["issues"][int(picked[0])]
            sid=issue["step_id"]
            if sid is not None and steps.exists(str(sid)):
                steps.selection_set(str(sid))
                steps.see(str(sid))
                top.lift()
        table.bind("<Double-1>",go_to_step)
        ttk.Button(pane,text="Mergi la pasul selectat",command=go_to_step
                   ).pack(anchor="w",pady=(8,0))
        audit.audit_report=report
        audit.issues_tree=table
        audit.go_to_step=go_to_step
        return audit

    def export_html():
        pid=state["pid"]
        if pid is None:
            return messagebox.showinfo("Selectare","Selectează o procedură.",parent=top)
        destination=filedialog.asksaveasfilename(
            parent=top,defaultextension=".html",
            filetypes=[("Procedură HTML imprimabilă","*.html")])
        if not destination:return
        try:
            export_procedure_html(app.db,pid,destination)
            messagebox.showinfo("Export","Procedura a fost exportată ca HTML offline.",
                                parent=top)
        except Exception as exc:
            messagebox.showerror("Export eșuat",str(exc),parent=top)

    def export_json():
        destination=filedialog.asksaveasfilename(
            parent=top,defaultextension=".json",
            filetypes=[("Proceduri JSON","*.json")])
        if not destination:return
        try:
            count=export_procedures_json(app.db,destination,vehicle_id)
            messagebox.showinfo("Export",f"Exportate {count} proceduri ale vehiculului.",
                                parent=top)
        except Exception as exc:
            messagebox.showerror("Export eșuat",str(exc),parent=top)

    controls=ttk.Frame(body)
    controls.pack(fill="x",pady=(12,0))
    commands=[("+ Procedură",lambda:procedure_form(False)),
              ("Editează procedură",lambda:procedure_form(True)),
              ("Șterge procedură",procedure_remove),
              ("+ Pas",lambda:step_form(False)),
              ("Editează pas",lambda:step_form(True)),
              ("↑",lambda:step_move(-1)),("↓",lambda:step_move(1)),
              ("Șterge pas",step_remove),("Alege document",choose_reference),
              ("Document asociat",open_reference),
              ("Vezi schema",open_schematic_reference),
              ("Audit documente",open_procedure_audit),
              ("Export HTML",export_html),("Export JSON",export_json)]
    for start in range(0,len(commands),6):
        row=ttk.Frame(controls)
        row.pack(fill="x",pady=(0,5))
        for label,callback in commands[start:start+6]:
            ttk.Button(row,text=label,command=callback).pack(side="left",padx=(0,5))

    # Expose read-only widget handles for the packaged Windows GUI smoke test.
    top.procedures_tree=procedures
    top.procedure_search_var=search
    top.procedure_search_notice=search_notice
    top.open_search_hits=open_search_hits
    top.steps_tree=steps
    top.open_reference_picker=choose_reference
    top.open_schematic_reference=open_schematic_reference
    top.open_procedure_audit=open_procedure_audit
    refresh_proc(selected_procedure_id)
    if selected_procedure_id is not None and selected_step_id is not None:
        refresh_steps(selected_step_id)
    return top
