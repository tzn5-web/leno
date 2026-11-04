"""Native Windows/Tkinter procedure navigator for user-owned, sourced workshop data."""
from __future__ import annotations

from procedure_step_navigation import adjacent_step_id
from procedure_step_context import step_context_text
from procedure_warning_overview import warning_overview_text
from procedure_warning_reference import warning_step_reference_id
from repair_export import export_procedure_html,export_procedures_json
from procedure_audit import (audit_procedure, get_step_reference,
                             get_step_reference_snapshot, resolve_step_attachment)
from procedure_audit_export import export_procedure_audit_json
from procedure_audit_html import export_procedure_audit_html
from procedure_search_hits import (DEFAULT_LIMIT, PROCEDURE_FIELDS, STEP_FIELDS,
                                   filter_hit_indices, list_procedure_hits, next_hit_index)
from procedure_search_live import validate_live_hit
from procedure_search_navigation import require_live_navigation_target
from procedure_audit_navigation import require_live_audit_step
from repair_procedures import (
    add_step, create_procedure, delete_procedure, delete_step, get_procedure,
    list_procedures, list_steps, list_reference_articles, move_step, procedure_text, update_procedure, update_step
)


def _safe_search_preview(value, limit=420):
    """Keep untrusted SQLite search snippets on one visible Tkinter row."""
    if not isinstance(value, str):
        return ""
    if type(limit) is not int or limit <= 0:
        raise ValueError("Invalid preview limit")
    forbidden = "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
    return "".join(" " if ord(ch) < 32 or 127 <= ord(ch) <= 159 or ch in forbidden or ch in "\u2028\u2029" else ch
                   for ch in value).strip()[:limit]


def _step_tree_values(step):
    """Build a safe, single-line Tk tree preview from possibly incomplete SQLite rows."""
    def preview(value, limit):
        return _safe_search_preview(value, limit)

    number = step["step_number"]
    if type(number) is not int or number <= 0:
        number = ""
    return (number, preview(step["instruction"], 130),
            preview(step["safety_note"], 95),
            preview(step["reference_title"], 130))


def _validate_navigation_id(value, label):
    """Require exact positive SQLite IDs before resolving GUI navigation."""
    if type(value) is not int or value <= 0:
        raise ValueError(f"Invalid {label} ID")
    return value


def open_procedures_window(app, editor_class, selected_procedure_id=None,
                           selected_step_id=None, vehicle_id=None):
    from tkinter import filedialog, messagebox, simpledialog, ttk
    tk=app.tk
    vehicle_id=app.vid if vehicle_id is None else vehicle_id
    if vehicle_id is None:
        messagebox.showinfo("Vehicul necesar", "Selectează un vehicul și motorizarea sa.")
        return None
    _validate_navigation_id(vehicle_id, "vehicle")
    if selected_procedure_id is not None:
        _validate_navigation_id(selected_procedure_id, "procedure")
    if selected_step_id is not None:
        _validate_navigation_id(selected_step_id, "step")
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
    ttk.Label(right,text="DETALII PAS SELECTAT / PROCEDURĂ").pack(anchor="w",pady=(10,5))
    detail=tk.Text(right,height=10,wrap="word",state="disabled",
                   font=("Segoe UI",10),bg="#1a2a42",fg="#eef5ff",relief="flat")
    detail.pack(fill="both",expand=False)

    state={"pid":None}

    def require_live_procedure(pid):
        """Reject a deleted or reassigned procedure before exposing GUI data."""
        _validate_navigation_id(pid, "procedure")
        if app.db.db.execute(
                "SELECT 1 FROM procedures WHERE id=? AND vehicle_id=?",
                (pid, vehicle_id)).fetchone() is None:
            raise ValueError("Procedura nu mai aparține vehiculului selectat")
        return pid

    def invalidate_stale_procedure(pid):
        """Remove stale rows as well as details; never retain foreign step text."""
        state["pid"]=None
        old_steps=steps.get_children()
        if old_steps:
            steps.delete(*old_steps)
        if procedures.exists(str(pid)):
            procedures.delete(str(pid))
        render("Procedura nu mai aparține vehiculului selectat. Actualizează lista.")

    def ensure_live_for_edit(pid):
        try:
            require_live_procedure(pid)
        except ValueError as exc:
            invalidate_stale_procedure(pid)
            messagebox.showerror("Procedură indisponibilă",str(exc),parent=top)
            return False
        return True

    def render(text):
        detail.configure(state="normal")
        detail.delete("1.0","end")
        detail.insert("1.0",text)
        detail.configure(state="disabled")

    def render_selected_step(event=None):
        """Show live selected-step warnings, references and source; never stale text."""
        pid=state["pid"]
        if pid is None:
            render("Selectează o procedură sau adaugă una nouă.")
            return None
        try:
            require_live_procedure(pid)
        except ValueError:
            invalidate_stale_procedure(pid)
            return None
        chosen=steps.selection()
        if not chosen:
            render(procedure_text(app.db,pid))
            return None
        try:
            context=step_context_text(app.db,vehicle_id,pid,int(chosen[0]))
        except ValueError:
            # A deleted or reassigned step must not remain selectable in the GUI.
            # Keep other live rows intact; this is a read-only view update.
            if steps.exists(chosen[0]):
                steps.delete(chosen[0])
            render("Pasul selectat nu mai aparține procedurii sau vehiculului. "
                   "Actualizează lista înainte de a continua.")
            return None
        render(context)
        return context

    def refresh_proc(prefer=None):
        try:
            candidates=list_procedures(app.db,vehicle_id,search.get())
        except ValueError as exc:
            candidates=[]
            search_notice.set("Căutare invalidă: "+str(exc))
        else:
            search_notice.set(f"{len(candidates)} proceduri găsite")
        procedures.delete(*procedures.get_children())
        visible_count=0
        for row in candidates:
            # The list query is a snapshot. A procedure may be reassigned
            # before the GUI consumes its cached title and system.
            if app.db.db.execute(
                    "SELECT 1 FROM procedures WHERE id=? AND vehicle_id=?",
                    (row["id"],vehicle_id)).fetchone() is None:
                continue
            procedures.insert("","end",iid=str(row["id"]),
                              text=f"{row['system']} / {row['title']}")
            visible_count+=1
        if candidates:
            search_notice.set(f"{visible_count} proceduri găsite")
        chosen=prefer if prefer is not None else state["pid"]
        if chosen is not None and procedures.exists(str(chosen)):
            procedures.selection_set(str(chosen))
            procedures.see(str(chosen))
            state["pid"]=chosen
        else:
            state["pid"]=None
        refresh_steps()

    def refresh_steps(prefer=None):
        # Validate and fetch before mutating the visible tree. A transient
        # empty selection must not erase otherwise valid SQLite-backed rows.
        pid=state["pid"]
        if pid is None:
            selected_parent=procedures.selection()
            if len(selected_parent)==1 and procedures.exists(selected_parent[0]):
                try:
                    candidate=int(selected_parent[0])
                    require_live_procedure(candidate)
                except (ValueError, TypeError):
                    pass
                else:
                    state["pid"]=pid=candidate
        if pid is None:
            steps.delete(*steps.get_children())
            render("Selectează o procedură sau adaugă una nouă.")
            return
        try:
            require_live_procedure(pid)
        except ValueError:
            invalidate_stale_procedure(pid)
            return
        live_rows=list_steps(app.db,pid)
        try:
            require_live_procedure(pid)
        except ValueError:
            invalidate_stale_procedure(pid)
            return
        # Tk queues <<TreeviewSelect>> when the selected child is deleted.
        # Rebuild only after obtaining a valid snapshot; restore the parent
        # and the requested child independently of queued selection events.
        if procedures.exists(str(pid)):
            procedures.selection_set(str(pid))
        state["pid"]=pid
        steps.delete(*steps.get_children())
        for step in live_rows:
            steps.insert("","end",iid=str(step["id"]),
                         values=_step_tree_values(step))
        if prefer is not None and steps.exists(str(prefer)):
            steps.selection_set(str(prefer))
        render_selected_step()

    def selection(event=None):
        previous_pid=state["pid"]
        items=procedures.selection()
        if not items:
            # TreeviewSelect with an empty selection is also queued when
            # refresh_proc deletes/reinserts filtered rows. refresh_proc owns
            # clearing state["pid"] when the chosen row is no longer visible;
            # processing the queued event here can clear a newer selection and
            # empty the step list after a successful SQLite reorder.
            return
        state["pid"]=int(items[0])
        # Ignore queued Tk selection events that do not change the procedure.
        # Rebuilding the tree here discards a newer step selection after reorder.
        if state["pid"] is not None and state["pid"]==previous_pid:
            return
        selected=(selected_step_id if state["pid"]==selected_procedure_id else None)
        refresh_steps(selected)

    procedures.bind("<<TreeviewSelect>>",selection)
    steps.bind("<<TreeviewSelect>>",render_selected_step)
    search.trace_add("write",lambda *_:refresh_proc())

    def open_search_hits():
        """List exact match locations and jump to a verified same-vehicle step."""
        term=search.get()
        page_state={"offset":0,"has_more":False}
        field_filter=tk.StringVar(value="Toate câmpurile")

        def fetch_page():
            batch=list_procedure_hits(
                app.db,vehicle_id,term,limit=DEFAULT_LIMIT+1,
                offset=page_state["offset"],
                field=None if field_filter.get()=="Toate câmpurile" else field_filter.get())
            page_state["has_more"]=len(batch)>DEFAULT_LIMIT
            return batch[:DEFAULT_LIMIT]

        try:
            hits=fetch_page()
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
        count_notice=tk.StringVar()
        ttk.Label(box,textvariable=count_notice,
                  font=("Segoe UI Semibold",12)).pack(anchor="w",pady=(0,7))
        ttk.Label(box,text="Rezultatele sunt din documentația locală, cu proveniență și vehicul verificate."
                  ).pack(anchor="w",pady=(0,7))
        filter_row=ttk.Frame(box)
        filter_row.pack(fill="x",pady=(0,7))
        ttk.Label(filter_row,text="Câmp:").pack(side="left",padx=(0,7))
        # A field may first occur after page 1; expose the complete schema.
        available_fields=[label for _,label in (*PROCEDURE_FIELDS,*STEP_FIELDS)]
        field_choice=ttk.Combobox(filter_row,textvariable=field_filter,
                                  values=("Toate câmpurile",*available_fields),
                                  state="readonly",width=29)
        field_choice.pack(side="left")
        ttk.Button(filter_row,text="◀ Pagina precedentă",
                   command=lambda:change_hits_page(-1)).pack(side="left",padx=(12,4))
        ttk.Button(filter_row,text="Pagina următoare ▶",
                   command=lambda:change_hits_page(1)).pack(side="left")
        columns=("procedure","step","field","excerpt","source")
        table=ttk.Treeview(box,columns=columns,show="headings",selectmode="browse")
        for key,title,width in zip(columns,
                ("Procedură","Pas","Câmp","Fragment găsit","Proveniență"),
                (190,45,160,420,190)):
            table.heading(key,text=title)
            table.column(key,width=width,minwidth=40,stretch=True)
        table.pack(fill="both",expand=True)
        visible_indices=[]
        def refresh_hit_filter(event=None):
            """Rebuild displayed rows using stable original hit IDs."""
            nonlocal visible_indices
            selected=field_filter.get()
            visible_indices=filter_hit_indices(
                hits,None if selected=="Toate câmpurile" else selected)
            existing=table.get_children()
            if existing:
                table.delete(*existing)
            for index in visible_indices:
                hit=hits[index]
                table.insert("","end",iid=str(index),values=(
                    _safe_search_preview(hit["procedure_title"],190),
                    hit["step_number"] if type(hit["step_number"]) is int and hit["step_number"] > 0 else "—",
                    _safe_search_preview(hit["field"],160),_safe_search_preview(hit["excerpt"]),
                    _safe_search_preview(hit["source"],190)))
            first=page_state["offset"]+1 if hits else 0
            last=page_state["offset"]+len(hits)
            more="; există rezultate pe pagina următoare" if page_state["has_more"] else ""
            count_notice.set(
                f"Pagina {page_state['offset']//DEFAULT_LIMIT+1}: "
                f"{len(visible_indices)} din {len(hits)} potriviri afișate "
                f"(pozițiile {first}–{last}{more}) pentru «{term}»")
            return tuple(visible_indices)
        def apply_field_filter(event=None):
            old_offset=page_state["offset"]
            old_more=page_state["has_more"]
            page_state["offset"]=0
            try:
                new_hits=fetch_page()
            except ValueError as exc:
                page_state["offset"]=old_offset
                page_state["has_more"]=old_more
                messagebox.showerror("Căutare detaliată",str(exc),parent=popup)
                return False
            hits[:]=new_hits
            refresh_hit_filter()
            return True
        field_choice.bind("<<ComboboxSelected>>",apply_field_filter)
        refresh_hit_filter()

        def change_hits_page(direction):
            """Load another bounded result page without changing SQLite."""
            if type(direction) is not int or direction not in (-1,1):
                raise ValueError("Invalid page direction")
            if direction<0 and page_state["offset"]==0:
                return False
            if direction>0 and not page_state["has_more"]:
                return False
            old_offset=page_state["offset"]
            old_more=page_state["has_more"]
            page_state["offset"]=old_offset+direction*DEFAULT_LIMIT
            try:
                new_hits=fetch_page()
            except ValueError as exc:
                page_state["offset"]=old_offset
                page_state["has_more"]=old_more
                messagebox.showerror("Căutare detaliată",str(exc),parent=popup)
                return False
            hits[:]=new_hits
            field_choice.configure(values=("Toate câmpurile",*available_fields))
            # Preserve a selected field across pages, even when this page
            # contains no matches in that field. Reset only by user choice.
            refresh_hit_filter()
            return True

        def move_hit_selection(direction):
            """Navigate only the visible subset, preserving original hit IDs."""
            chosen=table.selection()
            current=(visible_indices.index(int(chosen[0]))
                     if chosen and int(chosen[0]) in visible_indices else None)
            position=next_hit_index(len(visible_indices),current,direction)
            if position is None:
                return None
            index=visible_indices[position]
            iid=str(index)
            table.selection_set(iid)
            table.focus(iid)
            table.see(iid)
            return hits[index]

        def go_to_hit(event=None):
            selected=table.selection()
            if not selected:return None
            hit=hits[int(selected[0])]
            try:
                validate_live_hit(app.db,vehicle_id,hit,term)
            except ValueError as exc:
                messagebox.showerror("Rezultat învechit",
                    "Rezultatul căutării s-a schimbat: "+str(exc),parent=popup)
                return None
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
            # A document search result is a snapshot of a particular linked
            # article. A changed step link must not silently open another
            # document when the user follows an older result row.
            if hit["field"] in {label for key, label in STEP_FIELDS
                                if key.startswith("article_")}:
                live=app.db.db.execute(
                    "SELECT s.article_id FROM procedure_steps s "
                    "JOIN procedures p ON p.id=s.procedure_id "
                    "JOIN articles a ON a.id=s.article_id AND a.vehicle_id=p.vehicle_id "
                    "WHERE s.id=? AND p.id=? AND p.vehicle_id=?",
                    (sid,hit["procedure_id"],vehicle_id)).fetchone()
                if live is None or live["article_id"]!=hit.get("article_id"):
                    messagebox.showerror("Referință modificată",
                        "Documentul asociat acestui rezultat a fost schimbat sau eliminat.",
                        parent=popup)
                    return None
            refresh_proc(hit["procedure_id"])
            try:
                validate_live_hit(app.db,vehicle_id,hit,term)
            except ValueError as exc:
                messagebox.showerror("Rezultat învechit",
                    "Rezultatul căutării s-a schimbat: "+str(exc),parent=popup)
                return None
            if not procedures.exists(str(hit["procedure_id"])):
                messagebox.showinfo("Căutare modificată",
                    "Procedura nu mai corespunde filtrului curent.",parent=popup)
                return None
            procedures.selection_set(str(hit["procedure_id"]))
            procedures.see(str(hit["procedure_id"]))
            state["pid"]=hit["procedure_id"]
            refresh_steps(sid)
            # A row can disappear or change ownership while refresh_steps
            # reads SQLite and Tkinter redraws. Never report a successful
            # jump unless the live match and final GUI selection still agree.
            selected_steps=steps.selection()
            selected_sid=int(selected_steps[0]) if selected_steps else None
            try:
                require_live_navigation_target(
                    app.db,vehicle_id,hit,term,state["pid"],selected_sid)
            except ValueError as exc:
                if sid is not None and steps.exists(str(sid)):
                    steps.delete(str(sid))
                render("Rezultatul căutării s-a schimbat. Actualizează lista.")
                messagebox.showerror("Rezultat învechit",
                    "Navigarea a fost anulată: "+str(exc),parent=popup)
                return None
            if sid is not None:
                steps.see(str(sid))
            top.lift()
            return hit
        def open_hit_reference():
            """Open the selected hit's linked document after fresh scope checks."""
            chosen=table.selection()
            if not chosen:
                return None
            hit=hits[int(chosen[0])]
            if hit["step_id"] is None:
                messagebox.showinfo("Document asociat",
                    "Rezultatul descrie procedura, nu un pas cu document.",
                    parent=popup)
                return None
            # go_to_hit revalidates the procedure and step against current SQLite.
            # open_reference separately revalidates the article's vehicle.
            if go_to_hit() is None:
                return None
            # A document-field hit identifies a specific article snapshot.
            # Do not open a different document if the link changes after jump.
            return open_reference(expected_article_id=hit["article_id"]) if (
                hit["article_id"] is not None) else open_reference()

        table.bind("<Double-1>",go_to_hit)
        actions=ttk.Frame(box)
        actions.pack(anchor="w",pady=(9,0))
        ttk.Button(actions,text="Deschide potrivirea selectată",command=go_to_hit
                   ).pack(side="left",padx=(0,8))
        ttk.Button(actions,text="Documentul pasului găsit",command=open_hit_reference
                   ).pack(side="left",padx=(0,8))
        ttk.Button(actions,text="◀ Anterior",command=lambda:move_hit_selection(-1)
                   ).pack(side="left",padx=(0,8))
        ttk.Button(actions,text="Următor ▶",command=lambda:move_hit_selection(1)
                   ).pack(side="left")
        popup.bind("<Alt-Left>",lambda _event:move_hit_selection(-1))
        popup.bind("<Alt-Right>",lambda _event:move_hit_selection(1))
        popup.move_hit_selection=move_hit_selection
        popup.change_hits_page=change_hits_page
        popup.search_page_state=page_state
        popup.search_field_filter=field_filter
        popup.refresh_hit_filter=refresh_hit_filter
        popup.apply_field_filter=apply_field_filter
        popup.visible_hit_indices=lambda:tuple(visible_indices)
        popup.hits_tree=table
        popup.go_to_hit=go_to_hit
        popup.open_hit_reference=open_hit_reference
        popup.hits=hits
        return popup

    def procedure_form(edit):
        if edit and state["pid"] is not None and not ensure_live_for_edit(state["pid"]):
            return None
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
        if not ensure_live_for_edit(pid):
            return None
        selected=steps.selection()
        current=None
        if edit:
            if not selected:
                return messagebox.showinfo("Selectare","Selectează un pas.",parent=top)
            current=app.db.db.execute(
                "SELECT * FROM procedure_steps WHERE id=? AND procedure_id=?",
                (int(selected[0]),pid)).fetchone()
            if current is None:
                refresh_steps()
                return messagebox.showerror("Pas indisponibil",
                    "Pasul nu mai aparține procedurii selectate.",parent=top)
        fields=[("safety_note","Avertisment la acest pas",
                 current["safety_note"] if current else ""),
                ("article_id","ID document asociat din același vehicul (opțional)",
                 str(current["article_id"]) if current and current["article_id"] else "")]
        data=editor_class(top,"Editare pas" if edit else "Adaugă pas",
                          fields,body=("instruction",current["instruction"] if current else "")).value
        if data is None:return
        try:
            # Keep the raw form value: int() silently accepts +1 and Unicode
            # digits, bypassing the canonical ASCII-decimal reference policy.
            # add_step/update_step validate the value and its vehicle scope.
            ref=data["article_id"] if data["article_id"] else None
            if edit:
                update_step(app.db,current["id"],data["instruction"],data["safety_note"],ref)
                chosen=current["id"]
            else:
                chosen=add_step(app.db,pid,data["instruction"],data["safety_note"],ref)
            refresh_steps(chosen)
        except Exception as exc:messagebox.showerror("Pas invalid",str(exc),parent=top)

    def navigate_step(direction):
        """Select the adjacent live SQLite step, never a stale or foreign row."""
        pid=state["pid"]
        if pid is None:
            messagebox.showinfo("Navigare", "Selectează o procedură.", parent=top)
            return None
        selected=steps.selection()
        current=int(selected[0]) if selected else None
        try:
            target=adjacent_step_id(app.db,vehicle_id,pid,current,direction)
            if target is None:
                return None
            refresh_steps(target)
            if not steps.exists(str(target)):
                raise ValueError("Pasul selectat nu mai există")
            steps.see(str(target))
            return target
        except ValueError as exc:
            # Do not leave stale rows visible when ownership changed or a
            # selected step was deleted between navigation and GUI refresh.
            try:
                require_live_procedure(pid)
            except ValueError:
                invalidate_stale_procedure(pid)
            else:
                refresh_steps()
            messagebox.showerror("Navigare indisponibilă",str(exc),parent=top)
            return None

    def step_move(direction):
        if state["pid"] is None or not ensure_live_for_edit(state["pid"]):
            return None
        selected=steps.selection()
        if not selected:return
        try:
            move_step(app.db,int(selected[0]),direction)
            refresh_steps(int(selected[0]))
        except Exception as exc:messagebox.showerror("Ordonare",str(exc),parent=top)

    def procedure_remove():
        pid=state["pid"]
        if pid is None or not ensure_live_for_edit(pid):
            return None
        if messagebox.askyesno("Ștergere",
                              "Ștergi procedura și toți pașii?",parent=top):
            if not ensure_live_for_edit(pid):
                return None
            delete_procedure(app.db,pid)
            refresh_proc()

    def step_remove():
        if state["pid"] is None or not ensure_live_for_edit(state["pid"]):
            return None
        selected=steps.selection()
        if selected and messagebox.askyesno("Ștergere","Ștergi pasul selectat?",parent=top):
            if not ensure_live_for_edit(state["pid"]):
                return None
            pid=state["pid"]
            delete_step(app.db,int(selected[0]))
            # Restore the still-live parent selection before rebuilding its steps.
            # Tk can queue selection events while deleting the selected child.
            if procedures.exists(str(pid)):
                procedures.selection_set(str(pid))
                state["pid"]=pid
            refresh_steps()

    def choose_reference():
        """Select a verified same-vehicle article by title, not by opaque numeric ID."""
        selected=steps.selection()
        if not selected or state["pid"] is None:
            messagebox.showinfo("Selectare","Selectează un pas pentru a lega un document.",parent=top)
            return None
        if not ensure_live_for_edit(state["pid"]):
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
                require_live_procedure(pid)
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
        picker.reference_search_var=search_ref
        picker.apply_reference=apply
        picker.clear_reference=lambda:change_link(None)
        top.reference_picker=picker
        return picker

    def open_warning_overview():
        """Display recorded warnings with source and live vehicle ownership checks."""
        pid=state["pid"]
        if pid is None:
            messagebox.showinfo("Avertismente", "Selectează o procedură.", parent=top)
            return None
        try:
            require_live_procedure(pid)
            initial=warning_overview_text(app.db,vehicle_id,pid)
            from procedure_warning_navigation import warning_step_targets
            initial_targets=warning_step_targets(app.db,vehicle_id,pid)
            # Do not show a cached snapshot if ownership changed during the read.
            require_live_procedure(pid)
        except ValueError as exc:
            invalidate_stale_procedure(pid)
            messagebox.showerror("Avertismente indisponibile",str(exc),parent=top)
            return None
        popup=tk.Toplevel(top)
        popup.title("AtelierData — avertismente înregistrate")
        popup.geometry("760x510")
        area=tk.Text(popup,wrap="word",font=("Segoe UI",11))
        area.pack(fill="both",expand=True,padx=12,pady=(12,6))
        ttk.Label(popup,text="PAȘI CU AVERTISMENT — selectează pentru navigare").pack(
            anchor="w",padx=12)
        warning_tree=ttk.Treeview(
            popup,columns=("number","warning"),show="headings",
            selectmode="browse",height=5)
        warning_tree.heading("number",text="Pas")
        warning_tree.heading("warning",text="Avertisment înregistrat")
        warning_tree.column("number",width=65,stretch=False)
        warning_tree.column("warning",width=590,stretch=True)
        warning_tree.pack(fill="x",padx=12,pady=(4,8))

        def show_targets(targets):
            old=warning_tree.get_children()
            if old:
                warning_tree.delete(*old)
            for step_id,number,note in targets:
                warning_tree.insert("", "end", iid=str(step_id),
                                    values=(number,note))

        def show(text):
            area.configure(state="normal")
            area.delete("1.0","end")
            area.insert("1.0",text)
            area.configure(state="disabled")

        def refresh_overview():
            try:
                require_live_procedure(pid)
                current=warning_overview_text(app.db,vehicle_id,pid)
                targets=warning_step_targets(app.db,vehicle_id,pid)
                require_live_procedure(pid)
            except ValueError:
                show_targets(())
                show("Procedura nu mai aparține vehiculului selectat. "
                     "Închide fereastra și actualizează lista.")
                invalidate_stale_procedure(pid)
                return None
            show_targets(targets)
            show(current)
            return current

        def goto_warning_step():
            """Navigate only to a warning still linked to this vehicle/procedure."""
            chosen=warning_tree.selection()
            if not chosen:
                messagebox.showinfo("Avertismente","Selectează un pas cu avertisment.",
                                    parent=popup)
                return None
            step_id=int(chosen[0])
            try:
                require_live_procedure(pid)
                targets=warning_step_targets(app.db,vehicle_id,pid)
                if step_id not in {row[0] for row in targets}:
                    refresh_overview()
                    messagebox.showinfo("Avertisment actualizat",
                                        "Avertismentul nu mai este asociat acestui pas.",
                                        parent=popup)
                    return None
                require_live_procedure(pid)
                if state["pid"]!=pid:
                    raise ValueError("Procedura selectată s-a schimbat")
                refresh_steps(step_id)
                if not steps.exists(str(step_id)):
                    raise ValueError("Pasul nu mai este disponibil")
                steps.selection_set(str(step_id))
                steps.see(str(step_id))
                render_selected_step()
                top.lift()
                return step_id
            except ValueError as exc:
                refresh_overview()
                messagebox.showinfo("Navigare indisponibilă",str(exc),parent=popup)
                return None

        def open_warning_reference():
            """Open the selected warning's current, same-vehicle linked document."""
            chosen=warning_tree.selection()
            if not chosen:
                messagebox.showinfo("Document avertisment",
                                    "Selectează un pas cu avertisment.",parent=popup)
                return None
            step_id=int(chosen[0])
            shown_warning=warning_tree.item(chosen[0],"values")[1]
            try:
                require_live_procedure(pid)
                article_id,warning=warning_step_reference_id(
                    app.db,vehicle_id,pid,step_id)
                if warning!=shown_warning:
                    raise ValueError("Avertismentul s-a schimbat; actualizează lista")
                if state["pid"]!=pid:
                    raise ValueError("Procedura selectată s-a schimbat")
                if goto_warning_step()!=step_id:
                    return None
                # Recheck after GUI navigation, then compare against the
                # document returned by the final snapshot in open_reference.
                if warning_step_reference_id(
                        app.db,vehicle_id,pid,step_id)!=(article_id,warning):
                    raise ValueError("Avertismentul sau documentul s-a schimbat")
                return open_reference(expected_article_id=article_id,
                                      expected_warning=warning,
                                      expected_step_id=step_id)
            except ValueError as exc:
                refresh_overview()
                messagebox.showinfo("Document indisponibil",str(exc),parent=popup)
                return None

        show(initial)
        show_targets(initial_targets)
        controls=ttk.Frame(popup)
        controls.pack(fill="x",padx=12,pady=(0,12))
        ttk.Button(controls,text="Mergi la pasul selectat",
                   command=goto_warning_step).pack(side="left")
        ttk.Button(controls,text="Documentul avertismentului",
                   command=open_warning_reference).pack(side="left",padx=8)
        ttk.Button(controls,text="Actualizează avertismente",
                   command=refresh_overview).pack(side="right")
        popup.overview_text=area
        popup.warning_steps=warning_tree
        popup.goto_warning_step=goto_warning_step
        popup.open_warning_reference=open_warning_reference
        popup.refresh_overview=refresh_overview
        return popup

    def open_schematic_reference():
        """Navigate to a linked diagram, keeping the procedure's vehicle scope."""
        selected=steps.selection()
        if not selected or state["pid"] is None:
            messagebox.showinfo("Schemă", "Selectează un pas.", parent=top)
            return None
        try:
            from procedure_schematic_link import linked_step_schematic_id
            from schematic_viewer import get_schematic_reference, open_schematics_window
            step_id=int(selected[0])
            pid=state["pid"]
            article_id=linked_step_schematic_id(app.db,vehicle_id,pid,step_id)
            get_schematic_reference(app.db,vehicle_id,article_id)
            # The link may have changed while the article was being validated.
            # Never open an unrelated/stale diagram from an older selection.
            if linked_step_schematic_id(app.db,vehicle_id,pid,step_id)!=article_id:
                raise ValueError("Schematic link changed; refresh the selected step")
            return open_schematics_window(
                app,editor_class,selected_article_id=article_id,
                vehicle_id=vehicle_id)
        except ValueError as exc:
            messagebox.showinfo("Schemă indisponibilă",str(exc),parent=top)
            return None
        except Exception as exc:
            messagebox.showerror("Eroare schemă",str(exc),parent=top)
            return None

    def open_reference(expected_article_id=None, expected_warning=None,
                       expected_step_id=None):
        selected=steps.selection()
        if not selected:return
        selected_step_id=int(selected[0])
        selected_procedure_id=state["pid"]
        try:
            article,linked=get_step_reference_snapshot(
                app.db,selected_step_id,vehicle_id,selected_procedure_id)
        except ValueError as exc:
            return messagebox.showerror("Referință invalidă",str(exc),parent=top)
        if expected_article_id is not None and (
                article is None or article["id"]!=expected_article_id):
            messagebox.showerror(
                "Referință schimbată",
                "Documentul asociat s-a schimbat în timpul navigării; actualizează lista.",
                parent=top)
            return None
        # Warning-driven navigation must validate the warning again AFTER
        # loading the document snapshot. A concurrent edit may revoke the
        # warning without changing its article_id during that read.
        if expected_warning is not None:
            try:
                if (type(expected_step_id) is not int
                        or selected_step_id != expected_step_id
                        or state["pid"] != selected_procedure_id
                        or steps.selection() != (str(expected_step_id),)):
                    raise ValueError("Selecția pasului s-a schimbat")
                current_reference=warning_step_reference_id(
                    app.db,vehicle_id,selected_procedure_id,expected_step_id)
                if current_reference != (expected_article_id,expected_warning):
                    raise ValueError("Avertismentul sau documentul s-a schimbat")
            except ValueError as exc:
                messagebox.showerror("Avertisment schimbat",str(exc),parent=top)
                return None
        if article is None:
            return messagebox.showinfo("Referință","Pasul nu are document asociat.",parent=top)
        display=tk.Toplevel(top)
        display.title("Document asociat: "+article["title"])
        display.geometry("700x500")
        area=tk.Text(display,wrap="word",font=("Segoe UI",11))
        area.pack(fill="both",expand=True)
        attachments="\n".join(row["path"] for row in linked)
        area.insert("1.0",f"SURSĂ: {article['source']}\n\n{article['content']}\n\n"
                  f"ATAȘAMENTE ({len(linked)}):\n{attachments}")
        area.configure(state="disabled")
        def resolve_attachment(attachment_id):
            return resolve_step_attachment(
                app.db,selected_step_id,vehicle_id,selected_procedure_id,
                attachment_id)
        display.resolve_attachment=resolve_attachment
        if linked:
            def open_attachment():
                import os,sys,subprocess
                choice=1 if len(linked)==1 else simpledialog.askinteger(
                    "Atașamente","Alege numărul atașamentului (1–"+str(len(linked))+"):",
                    minvalue=1,maxvalue=len(linked),parent=display)
                if choice is None:return
                try:
                    path=resolve_attachment(linked[choice-1]["id"])
                    if sys.platform=="win32":os.startfile(str(path))
                    else:subprocess.Popen(["xdg-open",str(path)])
                except Exception as exc:
                    messagebox.showerror("Atașament invalid",str(exc),parent=display)
            ttk.Button(display,text="Deschide atașament verificat SHA256",
                       command=open_attachment).pack(pady=8)
            def preview_attachment(attachment_id=None):
                """Preview the selected authorized TXT without external launch."""
                if attachment_id is None:
                    choice=1 if len(linked)==1 else simpledialog.askinteger(
                        "Atașamente TXT",
                        "Alege numărul atașamentului (1–"+str(len(linked))+"):",
                        minvalue=1,maxvalue=len(linked),parent=display)
                    if choice is None:
                        return None
                    attachment_id=linked[choice-1]["id"]
                try:
                    if type(attachment_id) is not int or attachment_id not in {
                            row["id"] for row in linked}:
                        raise ValueError("Atașamentul nu este în lista acestui pas")
                    from procedure_audit import read_step_text_preview
                    content=read_step_text_preview(
                        app.db,selected_step_id,vehicle_id,selected_procedure_id,
                        attachment_id)
                    preview=tk.Toplevel(display)
                    preview.title("AtelierData — TXT verificat din pas")
                    preview.geometry("850x590")
                    preview.transient(display)
                    ttk.Label(preview,text=(
                        "Previzualizare locală numai pentru citire; drepturile "
                        "sunt declarate, nu certificate independent."),
                        wraplength=800).pack(anchor="w",padx=12,pady=9)
                    frame=ttk.Frame(preview,padding=10)
                    frame.pack(fill="both",expand=True)
                    scrollbar=ttk.Scrollbar(frame,orient="vertical")
                    viewer=tk.Text(frame,wrap="word",yscrollcommand=scrollbar.set)
                    scrollbar.configure(command=viewer.yview)
                    scrollbar.pack(side="right",fill="y")
                    viewer.pack(side="left",fill="both",expand=True)
                    viewer.insert("1.0",content)
                    viewer.configure(state="disabled")
                    preview.preview_text_widget=viewer
                    return preview
                except (ValueError,FileNotFoundError,OSError) as exc:
                    messagebox.showerror("Previzualizare indisponibilă",str(exc),
                                         parent=display)
                    return None
            ttk.Button(display,text="Previzualizează TXT verificat",
                       command=preview_attachment).pack(pady=5)
            display.preview_attachment=preview_attachment
            def preview_image_attachment(attachment_id=None):
                """Show a current, authorized PNG/JPEG linked to this exact step."""
                if attachment_id is None:
                    choice=1 if len(linked)==1 else simpledialog.askinteger(
                        "Atașamente imagine",
                        "Alege numărul atașamentului (1–"+str(len(linked))+"):",
                        minvalue=1,maxvalue=len(linked),parent=display)
                    if choice is None:
                        return None
                    attachment_id=linked[choice-1]["id"]
                try:
                    if type(attachment_id) is not int or attachment_id not in {
                            row["id"] for row in linked}:
                        raise ValueError("Atașamentul nu este în lista acestui pas")
                    from step_image_preview import read_step_image_preview
                    from PIL import Image, ImageTk
                    image=read_step_image_preview(
                        app.db,selected_step_id,vehicle_id,selected_procedure_id,
                        attachment_id)
                    image.thumbnail((1000,700),Image.Resampling.LANCZOS)
                    preview=tk.Toplevel(display)
                    preview.title("AtelierData — imagine verificată din pas")
                    preview.geometry("1050x780")
                    preview.transient(display)
                    frame=ttk.Frame(preview,padding=12)
                    frame.pack(fill="both",expand=True)
                    ttk.Label(frame,text=(
                        "Imagine locală verificată SHA256; drepturile sunt declarate, "
                        "nu certificate independent. Conținutul nu este validat tehnic."),
                        wraplength=1000).pack(anchor="w",pady=(0,8))
                    photo=ImageTk.PhotoImage(image,master=preview)
                    ttk.Label(frame,image=photo).pack(expand=True)
                    preview.image_photo=photo
                    return preview
                except (ValueError,FileNotFoundError,OSError,RuntimeError,tk.TclError) as exc:
                    messagebox.showerror("Previzualizare indisponibilă",str(exc),
                                         parent=display)
                    return None
            ttk.Button(display,text="Previzualizează imagine verificată",
                       command=preview_image_attachment).pack(pady=5)
            display.preview_image_attachment=preview_image_attachment
            def preview_pdf_attachment(attachment_id=None):
                """Navigate a step's PDF, revalidating its current link per page."""
                if attachment_id is None:
                    choice=1 if len(linked)==1 else simpledialog.askinteger(
                        "Atașamente PDF",
                        "Alege numărul atașamentului (1–"+str(len(linked))+"):",
                        minvalue=1,maxvalue=len(linked),parent=display)
                    if choice is None:
                        return None
                    attachment_id=linked[choice-1]["id"]
                try:
                    if type(attachment_id) is not int or attachment_id not in {
                            row["id"] for row in linked}:
                        raise ValueError("Atașamentul nu este în lista acestui pas")
                    from step_pdf_preview import read_step_pdf_page
                    from PIL import Image, ImageTk
                    def read_page(number):
                        return read_step_pdf_page(
                            app.db,selected_step_id,vehicle_id,selected_procedure_id,
                            attachment_id,page_number=number)
                    picture,count=read_page(1)
                    preview=tk.Toplevel(display)
                    preview.title("AtelierData — PDF verificat din pas")
                    preview.geometry("1050x780")
                    preview.transient(display)
                    frame=ttk.Frame(preview,padding=12)
                    frame.pack(fill="both",expand=True)
                    ttk.Label(frame,text=(
                        "PDF local verificat la fiecare pagină; drepturile sunt "
                        "declarate, nu certificate independent. Numai citire."),
                        wraplength=1000).pack(anchor="w",pady=(0,8))
                    controls=ttk.Frame(frame)
                    controls.pack(fill="x")
                    page=tk.IntVar(value=1)
                    label=tk.StringVar(value=f"Pagina 1/{count}")
                    previous=ttk.Button(controls,text="Pagina anterioară")
                    previous.pack(side="left")
                    ttk.Label(controls,textvariable=label).pack(side="left",padx=12)
                    following=ttk.Button(controls,text="Pagina următoare")
                    following.pack(side="left")
                    canvas=ttk.Label(frame)
                    canvas.pack(fill="both",expand=True)
                    def display_page(image):
                        image.thumbnail((1000,690),Image.Resampling.LANCZOS)
                        photo=ImageTk.PhotoImage(image,master=preview)
                        canvas.configure(image=photo)
                        preview.pdf_photo=photo
                    def invalidate():
                        canvas.configure(image="")
                        preview.pdf_photo=None
                        preview.pdf_invalidated=True
                        label.set("Previzualizare invalidată")
                        previous.configure(state="disabled")
                        following.configure(state="disabled")
                    def show_page(number):
                        if preview.pdf_invalidated or number<1 or number>count:
                            return False
                        try:
                            image,new_count=read_page(number)
                            if new_count!=count:
                                raise ValueError("Numărul paginilor PDF s-a schimbat")
                            display_page(image)
                        except (ValueError,FileNotFoundError,OSError,RuntimeError,tk.TclError) as exc:
                            invalidate()
                            messagebox.showerror("Previzualizare indisponibilă",str(exc),
                                                 parent=preview)
                            return False
                        page.set(number)
                        label.set(f"Pagina {number}/{count}")
                        previous.configure(state="normal" if number>1 else "disabled")
                        following.configure(state="normal" if number<count else "disabled")
                        return True
                    previous.configure(command=lambda:show_page(page.get()-1))
                    following.configure(command=lambda:show_page(page.get()+1))
                    preview.pdf_invalidated=False
                    display_page(picture)
                    previous.configure(state="disabled")
                    following.configure(state="normal" if count>1 else "disabled")
                    preview.pdf_page_number=page
                    preview.pdf_page_count=count
                    preview.pdf_page_label=label
                    preview.pdf_next=lambda:show_page(page.get()+1)
                    preview.pdf_previous=lambda:show_page(page.get()-1)
                    return preview
                except (ValueError,FileNotFoundError,OSError,RuntimeError,tk.TclError) as exc:
                    messagebox.showerror("Previzualizare indisponibilă",str(exc),
                                         parent=display)
                    return None
            ttk.Button(display,text="Previzualizează PDF verificat",
                       command=preview_pdf_attachment).pack(pady=5)
            display.preview_pdf_attachment=preview_pdf_attachment
        display.reference_article_id=article["id"]
        display.reference_text_widget=area
        return display

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
            """Navigate only while the exact audit finding remains current."""
            picked=table.selection()
            if not picked:
                return None
            issue=report["issues"][int(picked[0])]
            if issue["step_id"] is None:
                return None
            sid=issue["step_id"]
            try:
                if state["pid"]!=pid:
                    raise ValueError("Procedura selectată s-a schimbat")
                require_live_audit_step(app.db,vehicle_id,pid,issue)
                refresh_steps(sid)
                if state["pid"]!=pid or not steps.exists(str(sid)):
                    raise ValueError("Pasul nu mai este disponibil")
                # A redraw can race a SQLite edit. Re-audit before accepting
                # the final selection, rather than trusting the old report.
                require_live_audit_step(app.db,vehicle_id,pid,issue)
                if steps.selection()!=(str(sid),):
                    raise ValueError("Selecția pasului s-a schimbat")
                steps.see(str(sid))
                top.lift()
                return sid
            except ValueError as exc:
                if steps.selection()==(str(sid),):
                    steps.selection_remove(str(sid))
                messagebox.showerror("Audit învechit",
                    "Actualizează auditul înainte de navigare: "+str(exc),
                    parent=audit)
                return None
        table.bind("<Double-1>",go_to_step)
        ttk.Button(pane,text="Mergi la pasul selectat",command=go_to_step
                   ).pack(anchor="w",pady=(8,0))
        def export_audit_report(destination=None, notify=True):
            """Re-check current SQLite/attachments before exporting the audit."""
            if destination is None:
                destination=filedialog.asksaveasfilename(
                    parent=audit,defaultextension=".json",
                    filetypes=[("Raport audit JSON","*.json")])
            if not destination:
                return None
            try:
                payload=export_procedure_audit_json(
                    app.db,pid,destination,vehicle_id=vehicle_id)
                if notify:
                    messagebox.showinfo("Audit exportat",
                                        "Raportul JSON a fost salvat.",parent=audit)
                return payload
            except Exception as exc:
                if not notify:
                    raise
                messagebox.showerror("Export audit eșuat",str(exc),parent=audit)
                return None

        ttk.Button(pane,text="Exportă raport audit JSON",
                   command=export_audit_report).pack(anchor="w",pady=(7,0))
        def export_audit_printable(destination=None, notify=True):
            """Re-audit on demand and write inert, printable HTML offline."""
            if destination is None:
                destination=filedialog.asksaveasfilename(
                    parent=audit,defaultextension=".html",
                    filetypes=[("Raport audit HTML imprimabil","*.html")])
            if not destination:
                return None
            try:
                target=export_procedure_audit_html(
                    app.db,pid,destination,vehicle_id=vehicle_id)
                if notify:
                    messagebox.showinfo("Audit exportat",
                                        "Raportul HTML a fost salvat.",parent=audit)
                return target
            except Exception as exc:
                if not notify:
                    raise
                messagebox.showerror("Export HTML eșuat",str(exc),parent=audit)
                return None

        ttk.Button(pane,text="Exportă raport audit HTML",
                   command=export_audit_printable).pack(anchor="w",pady=(7,0))
        audit.audit_report=report
        audit.issues_tree=table
        audit.go_to_step=go_to_step
        audit.export_audit_report=export_audit_report
        audit.export_audit_printable=export_audit_printable
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
              ("◀ Pas anterior",lambda:navigate_step(-1)),
              ("Pas următor ▶",lambda:navigate_step(1)),
              ("Șterge pas",step_remove),("Alege document",choose_reference),
              ("Document asociat",open_reference),
              ("Vezi schema",open_schematic_reference),
               ("Avertismente",open_warning_overview),
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
    top.procedure_detail_text=detail
    top.refresh_steps=refresh_steps
    top.render_selected_step=render_selected_step
    top.move_selected_step=step_move
    top.navigate_step=navigate_step
    top.edit_selected_step=lambda:step_form(True)
    top.open_reference_picker=choose_reference
    top.open_schematic_reference=open_schematic_reference
    top.open_warning_overview=open_warning_overview
    top.open_step_reference=open_reference
    top.open_procedure_audit=open_procedure_audit
    refresh_proc(selected_procedure_id)
    if selected_procedure_id is not None and selected_step_id is not None:
        refresh_steps(selected_step_id)
    return top
