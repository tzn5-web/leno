"""Read-only cross-module search over user-owned AtelierData SQLite records.

No remote calls, technical values, original Autodata data, or IDF decoding.
Search treats SQL LIKE metacharacters as literal text.
"""
from __future__ import annotations

MAX_TERM = 200
MAX_LIMIT = 200

# Static SQL fragments only. Search text is always bound, never interpolated.
_SOURCES = (
    ('vehicle', 'vehicles', 'v', 'v.id',
     "trim(v.make || ' ' || v.model || ' ' || v.engine)",
     "substr(v.years || ' ' || v.fuel || ' ' || v.variant,1,240)",
     "''", ('v.make','v.model','v.engine','v.years','v.fuel','v.variant'), None),
    ('document', 'articles', 'r', 'r.id', 'r.title',
     "substr(r.category || ' — ' || r.content,1,240)",
     'r.source', ('r.title','r.category','r.content','r.source'), None),
    ('procedure', 'procedures', 'r', 'r.id', 'r.title',
     "substr(r.system || ' — ' || r.summary,1,240)",
     'r.source', ('r.title','r.system','r.summary','r.precautions','r.source'),
     "EXISTS (SELECT 1 FROM procedure_steps s WHERE s.procedure_id=r.id "
     "AND (s.instruction LIKE ? ESCAPE '\\' OR s.safety_note LIKE ? ESCAPE '\\'))"),
    ('specification', 'technical_specs', 'r', 'r.id',
     "r.system || ' / ' || r.parameter",
     "substr(r.value || ' ' || r.unit || ' — ' || r.conditions,1,240)",
     'r.source', ('r.system','r.parameter','r.value','r.unit','r.conditions','r.source'), None),
    ('dtc', 'dtc_entries', 'r', 'r.id', "r.code || ' — ' || r.title",
     "substr(r.system || ' — ' || r.symptoms,1,240)",
     'r.source', ('r.code','r.system','r.title','r.symptoms','r.possible_causes',
                  'r.checks','r.notes','r.source'), None),
    ('maintenance', 'maintenance_plans', 'r', 'r.id', 'r.title',
     "substr(r.system || ' — ' || r.conditions,1,240)",
     'r.source', ('r.title','r.system','r.conditions','r.source'), None),
)


def _validated(term, vehicle_id, limit, offset):
    if not isinstance(term, str) or not term.strip() or len(term) > MAX_TERM or '\0' in term:
        raise ValueError('Căutarea trebuie să conțină 1–200 caractere')
    if vehicle_id is not None and (type(vehicle_id) is not int or vehicle_id <= 0):
        raise ValueError('ID vehicul invalid')
    if type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
        raise ValueError('Limita trebuie să fie între 1 și 200')
    if type(offset) is not int or not 0 <= offset <= 100000:
        raise ValueError('Offset invalid')
    return '%' + term.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%'


def search_catalog(store, term, vehicle_id=None, limit=100, offset=0):
    """Return a stable page of provenance-bearing, cross-module results.

    The query is read-only, does not modify SQLite schema, and scopes every
    result (including matching procedure steps) to its owning vehicle.
    """
    pattern = _validated(term, vehicle_id, limit, offset)
    selects, parameters = [], []
    for kind, table, alias, ident, title, excerpt, source, fields, extra in _SOURCES:
        join = '' if kind == 'vehicle' else f' JOIN vehicles v ON v.id={alias}.vehicle_id'
        clauses = [f"{field} LIKE ? ESCAPE '\\'" for field in fields]
        parameters.extend([pattern] * len(fields))
        if extra:
            clauses.append(extra)
            parameters.extend([pattern, pattern])
        where = ' OR '.join(clauses)
        if vehicle_id is not None:
            where = f'v.id=? AND ({where})'
            # Vehicle filter placeholder occurs before LIKE placeholders.
            parameters[-(len(fields) + (2 if extra else 0)):] = (
                [vehicle_id] + parameters[-(len(fields) + (2 if extra else 0)):])
        selects.append(
            f"SELECT '{kind}' AS kind,{ident} AS record_id,v.id AS vehicle_id,"
            f"v.make AS make,v.model AS model,v.engine AS engine,"
            f"{title} AS title,{excerpt} AS excerpt,{source} AS source "
            f'FROM {table} {alias}{join} WHERE ({where})'
        )
    sql = ('SELECT kind,record_id,vehicle_id,make,model,engine,title,excerpt,source '
           'FROM (' + ' UNION ALL '.join(selects) + ') '
           'ORDER BY make COLLATE NOCASE,model COLLATE NOCASE,kind,'
           'title COLLATE NOCASE,record_id LIMIT ? OFFSET ?')
    parameters.extend((limit, offset))
    return [dict(row) for row in store.db.execute(sql, parameters)]


def open_search_window(app):
    """Search across all modules and navigate to the owning vehicle/module."""
    from tkinter import messagebox, ttk
    tk = app.tk
    window = tk.Toplevel(app.root)
    window.title('AtelierData — căutare globală în catalogul local')
    window.geometry('1080x640')
    window.transient(app.root)
    panel = ttk.Frame(window, padding=12)
    panel.pack(fill='both', expand=True)
    ttk.Label(panel, text='Căutare globală: vehicule, documente, proceduri, specificații, DTC și întreținere').pack(anchor='w')
    bar = ttk.Frame(panel)
    bar.pack(fill='x', pady=8)
    query = tk.StringVar()
    field = ttk.Entry(bar, textvariable=query)
    field.pack(side='left', fill='x', expand=True)
    scoped = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text='Doar vehiculul selectat', variable=scoped).pack(side='left', padx=8)
    status = tk.StringVar(value='Introdu un termen pentru căutare literală.')
    cols = ('kind', 'vehicle', 'title', 'source')
    tree = ttk.Treeview(panel, columns=cols, show='headings', selectmode='browse')
    for key, label, width in zip(cols, ('Tip', 'Vehicul', 'Rezultat', 'Sursă'), (110, 220, 440, 180)):
        tree.heading(key, text=label)
        tree.column(key, width=width, minwidth=65, stretch=True)
    tree.pack(fill='both', expand=True)
    detail = tk.Text(panel, height=6, wrap='word', state='disabled')
    detail.pack(fill='x', pady=(8, 4))
    ttk.Label(panel, textvariable=status).pack(anchor='w')
    records = {}

    def set_detail(value):
        detail.configure(state='normal')
        detail.delete('1.0', 'end')
        detail.insert('1.0', value)
        detail.configure(state='disabled')

    def selected():
        keys = tree.selection()
        return records.get(keys[0]) if keys else None

    def preview(_event=None):
        row = selected()
        if row:
            set_detail(f"{row['title']}\nVehicul: {row['make']} {row['model']} {row['engine']}\n"
                       f"Sursă: {row['source'] or 'nespecificată'}\n{row['excerpt']}")

    def run_search(_event=None):
        try:
            rows = search_catalog(app.db, query.get(), app.vid if scoped.get() else None)
        except ValueError as exc:
            messagebox.showerror('Căutare invalidă', str(exc), parent=window)
            return
        tree.delete(*tree.get_children())
        records.clear()
        set_detail('')
        for row in rows:
            item = tree.insert('', 'end', values=(row['kind'],
                  f"{row['make']} {row['model']} {row['engine']}", row['title'], row['source']))
            records[item] = row
        status.set(f'{len(rows)} rezultate afișate (maximum 100); fără acces la internet.')

    def navigate(_event=None):
        row = selected()
        if row is None:
            return
        app.vid = row['vehicle_id']
        app.aid = None
        app.vsearch.set('')
        app.asearch.set('')
        app.cat.set('Toate')
        app.refresh()
        kind, record_id = row['kind'], row['record_id']
        if kind == 'document':
            for item, aid in app.amap.items():
                if aid == record_id:
                    app.atree.selection_set(item)
                    app.atree.see(item)
                    app.select_article()
                    break
        elif kind == 'procedure':
            target = app.procedures()
            view = getattr(target, 'procedures_tree', None)
            if view is not None and view.exists(str(record_id)):
                view.selection_set(str(record_id))
                view.see(str(record_id))
                view.event_generate('<<TreeviewSelect>>')
        elif kind == 'dtc':
            target = app.diagnostics()
            view = getattr(target, 'dtc_tree', None)
            if view is not None and view.exists(str(record_id)):
                view.selection_set(str(record_id))
                view.see(str(record_id))
                view.event_generate('<<TreeviewSelect>>')
        elif kind == 'maintenance':
            target = app.maintenance()
            view = getattr(target, 'maintenance_tree', None)
            if view is not None and view.exists(str(record_id)):
                view.selection_set(str(record_id))
                view.see(str(record_id))
                view.event_generate('<<TreeviewSelect>>')
        elif kind == 'specification':
            app.specifications()
        else:
            app.detail.set(row['title'])
        window.lift()

    field.bind('<Return>', run_search)
    tree.bind('<<TreeviewSelect>>', preview)
    tree.bind('<Double-1>', navigate)
    buttons = ttk.Frame(panel)
    buttons.pack(fill='x', pady=(5, 0))
    ttk.Button(buttons, text='Caută', command=run_search).pack(side='left')
    ttk.Button(buttons, text='Deschide rezultatul', command=navigate).pack(side='left', padx=8)
    field.focus_set()
    return window
