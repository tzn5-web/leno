"""Native Windows/Tkinter procedure navigator for user-owned, sourced workshop data."""
from __future__ import annotations

from repair_export import export_procedure_html,export_procedures_json
from repair_procedures import (
    add_step, create_procedure, delete_procedure, delete_step, get_procedure,
    list_procedures, list_steps, list_reference_articles, move_step, procedure_text, update_procedure, update_step
)


def open_procedures_window(app, editor_class):
    from tkinter import filedialog, messagebox, simpledialog, ttk
    tk=app.tk
    if app.vid is None:
        messagebox.showinfo("Vehicul necesar", "Selectează un vehicul și motorizarea sa.")
        return None
    vehicle_id=app.vid
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
    field.pack(fill="x",padx=(0,12),pady=(0,8))
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
        candidates=list_procedures(app.db,vehicle_id,search.get())
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
        refresh_steps()

    procedures.bind("<<TreeviewSelect>>",selection)
    search.trace_add("write",lambda *_:refresh_proc())

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
        row=app.db.db.execute("SELECT article_id FROM procedure_steps WHERE id=?",
                              (int(selected[0]),)).fetchone()
        if row is None or row["article_id"] is None:
            return messagebox.showinfo("Referință","Pasul nu are document asociat.",parent=top)
        article=app.db.get_article(row["article_id"])
        if article is None:
            return messagebox.showinfo("Referință","Documentul asociat nu mai există.",parent=top)
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
              ("Export HTML",export_html),("Export JSON",export_json)]
    for start in range(0,len(commands),6):
        row=ttk.Frame(controls)
        row.pack(fill="x",pady=(0,5))
        for label,callback in commands[start:start+6]:
            ttk.Button(row,text=label,command=callback).pack(side="left",padx=(0,5))

    # Expose read-only widget handles for the packaged Windows GUI smoke test.
    top.procedures_tree=procedures
    top.steps_tree=steps
    top.open_reference_picker=choose_reference
    top.open_schematic_reference=open_schematic_reference
    refresh_proc()
    return top
