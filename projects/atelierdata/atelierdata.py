from __future__ import annotations
import argparse,csv,json,os,sqlite3,sys,tempfile,math,collections,zipfile
from pathlib import Path
from atelierdata_extensions import integrity_check,export_records,attach_document,list_documents,resolve_document
from atelierdata_backup import backup_bundle,restore_bundle
from technical_specs import (ensure_schema,add_spec,update_spec,remove_spec,get_spec,
                             list_specs,import_specs,export_specs)
from repair_procedures import (ensure_schema as ensure_procedures_schema,
                               create_procedure,add_step)
from repair_export import export_procedures_json,export_procedure_html
from dtc_catalog import ensure_schema as ensure_dtc_schema, add_dtc
from dtc_gui import open_dtc_window
from maintenance_plans import (ensure_schema as ensure_maintenance_schema,
                               add_plan, log_service)
from maintenance_gui import open_maintenance_window
from vpic_catalog_gui import open_vehicle_catalog
from catalog_search import search_catalog,open_search_window
from technical_sources_gui import open_sources_window
from document_library import ensure_schema as ensure_library_schema
from document_library_gui import open_document_library
from workshop_atlas import ensure_schema as ensure_atlas_schema
from workshop_atlas_gui import open_workshop_atlas
from vehicle_service_card_gui import open_vehicle_service_card

CATEGORIES = ("Date tehnice","Întreținere","Motor","Distribuție","Cupluri de strângere",
              "Diagnosticare / DTC","Scheme electrice","Siguranțe și relee","Frâne / ABS",
              "Direcție / Suspensie","Transmisie","Climatizare","Proceduri de reparație",
              "Timpi de manoperă","Fluide și capacități","Note atelier")

def db_path():
    return Path(os.environ.get("LOCALAPPDATA",str(Path.home()))) / "AtelierData" / "atelierdata.sqlite3"

class Store:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path);self.db.row_factory=sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS vehicles(
            id INTEGER PRIMARY KEY,make TEXT NOT NULL,model TEXT NOT NULL,engine TEXT DEFAULT '',
            years TEXT DEFAULT '',fuel TEXT DEFAULT '',variant TEXT DEFAULT '');
          CREATE TABLE IF NOT EXISTS articles(
            id INTEGER PRIMARY KEY,vehicle_id INTEGER NOT NULL,category TEXT NOT NULL,
            title TEXT NOT NULL,content TEXT NOT NULL DEFAULT '',source TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE);
          CREATE TABLE IF NOT EXISTS attachments(
            id INTEGER PRIMARY KEY,article_id INTEGER NOT NULL,path TEXT NOT NULL,
            FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE);
        """)
        self.db.executescript("""
          CREATE INDEX IF NOT EXISTS idx_articles_vehicle_category ON articles(vehicle_id,category,title);
          CREATE INDEX IF NOT EXISTS idx_attachments_article ON attachments(article_id);
          CREATE INDEX IF NOT EXISTS idx_vehicles_lookup ON vehicles(make,model,engine);
        """)
        self.db.commit()
        ensure_schema(self)
        ensure_procedures_schema(self)
        ensure_dtc_schema(self)
        ensure_maintenance_schema(self)
        ensure_library_schema(self)
        ensure_atlas_schema(self)
    def add_vehicle(self,make,model,engine='',years='',fuel='',variant=''):
        if not make.strip() or not model.strip():raise ValueError("Marca și modelul sunt obligatorii")
        cur=self.db.execute("INSERT INTO vehicles(make,model,engine,years,fuel,variant) VALUES(?,?,?,?,?,?)",
           (make.strip(),model.strip(),engine.strip(),years.strip(),fuel.strip(),variant.strip()))
        self.db.commit();return cur.lastrowid
    def list_vehicles(self,search=''):
        q='%'+search.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        return self.db.execute("SELECT * FROM vehicles WHERE make LIKE ? ESCAPE '\\' OR model LIKE ? ESCAPE '\\' OR engine LIKE ? ESCAPE '\\' ORDER BY make,model,engine", (q,q,q)).fetchall()
    def add_article(self,vehicle_id,category,title,content='',source=''):
        if not title.strip():raise ValueError("Titlu lipsă")
        cur=self.db.execute("INSERT INTO articles(vehicle_id,category,title,content,source) VALUES(?,?,?,?,?)",
               (vehicle_id,category,title.strip(),content,source))
        self.db.commit();return cur.lastrowid
    def list_articles(self,vid=None,category='Toate',search=''):
        query="SELECT articles.*,vehicles.make,vehicles.model FROM articles JOIN vehicles ON vehicles.id=articles.vehicle_id WHERE 1=1"
        values=[]
        if vid is not None:query+=" AND vehicle_id=?";values.append(vid)
        if category!='Toate':query+=" AND category=?";values.append(category)
        if search is not None and not isinstance(search,str):
            raise ValueError("Căutarea trebuie să fie text")
        if search:
            if len(search)>200 or '\0' in search:
                raise ValueError("Căutarea este prea lungă sau invalidă")
            literal='%'+search.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
            query+=" AND (title LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\')"
            values.extend([literal,literal])
        return self.db.execute(query+" ORDER BY category,title",values).fetchall()
    def get_article(self,aid):
        return self.db.execute("SELECT * FROM articles WHERE id=?",(aid,)).fetchone()
    def update_article(self,aid,category,title,content,source):
        if not title.strip():raise ValueError("Titlu lipsă")
        self.db.execute("UPDATE articles SET category=?,title=?,content=?,source=? WHERE id=?",
                        (category,title.strip(),content,source,aid));self.db.commit()
    def delete_article(self,aid):
        self.db.execute("DELETE FROM articles WHERE id=?",(aid,));self.db.commit()
    def delete_vehicle(self,vid):
        self.db.execute("DELETE FROM vehicles WHERE id=?",(vid,));self.db.commit()
    def stats(self):
        return [self.db.execute("SELECT COUNT(*) FROM "+table).fetchone()[0] for table in ('vehicles','articles')]
    def backup(self,path):
        out=sqlite3.connect(path)
        try:
            self.db.backup(out)
        finally:
            out.close()
    def close(self):self.db.close()

def import_records(store,path):
    """Import valid records atomically; reject invalid rows without partial writes."""
    path=Path(path)
    if path.suffix.lower()=='.csv':
        with path.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
    elif path.suffix.lower()=='.json':
        obj=json.loads(path.read_text(encoding='utf-8-sig'))
        rows=obj.get('records',[]) if isinstance(obj,dict) else obj
    else:raise ValueError("Accept doar CSV/JSON")
    if not isinstance(rows,list):raise ValueError("JSON invalid")
    result={'inserted':0,'rejected':[]}
    validated=[]
    for i,row in enumerate(rows,1):
        try:
            if not isinstance(row,dict) or any(not str(row.get(k,'')).strip() for k in ('make','model','category','title')):
                raise ValueError("Câmpurile make, model, category, title sunt obligatorii")
            fields=[str(row.get(k,'')).strip() for k in ('make','model','engine','years','fuel','variant')]
            validated.append((fields,str(row['category']).strip(),str(row['title']).strip(),
                              str(row.get('content',row.get('body',''))),str(row.get('source',''))))
        except (ValueError,KeyError,TypeError) as exc:result['rejected'].append(f"{i}: {exc}")
    # Do not commit an import with rejected records: callers can correct and retry.
    if result['rejected']:
        return result
    vehicles={}
    try:
        with store.db:
            for fields,category,title,content,source in validated:
                key=tuple(fields)
                if key not in vehicles:
                    old=store.db.execute("SELECT id FROM vehicles WHERE make=? AND model=? AND engine=? AND years=? AND fuel=? AND variant=?",fields).fetchone()
                    if old:vehicles[key]=old['id']
                    else:
                        cur=store.db.execute("INSERT INTO vehicles(make,model,engine,years,fuel,variant) VALUES(?,?,?,?,?,?)",fields)
                        vehicles[key]=cur.lastrowid
                store.db.execute("INSERT INTO articles(vehicle_id,category,title,content,source) VALUES(?,?,?,?,?)",
                                 (vehicles[key],category,title,content,source))
                result['inserted']+=1
    except Exception:
        result['inserted']=0
        raise
    return result

def probe_idf(root):
    root=Path(root);items=[]
    def add(name,size,prefix):
        if not prefix:return
        freq=collections.Counter(prefix)
        entropy=-sum((n/len(prefix))*math.log2(n/len(prefix)) for n in freq.values())
        items.append({'name':name,'bytes':size,'sample_entropy':round(entropy,4),
                      'header_hex':prefix[:16].hex(),'decoded':False})
    if root.is_file() and root.suffix.lower()=='.zip':
        with zipfile.ZipFile(root) as z:
            for member in z.infolist():
                if member.filename.lower().endswith('.idf'):
                    with z.open(member) as stream:add(member.filename,member.file_size,stream.read(65536))
    elif root.is_dir():
        for file in root.rglob('*.IDF'):
            if not file.is_symlink():
                with file.open('rb') as stream:add(str(file.relative_to(root)),file.stat().st_size,stream.read(65536))
    else:raise ValueError("Alege director sau ZIP")
    return {'count':len(items),'samples':items,'warning':'Formatul IDF nu este decodat. Entropia mare nu probează criptarea.'}

def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);db=Store(root/'a.sqlite3')
        vid=db.add_vehicle('TEST','VEHICLE','TESTENGINE','2020','test')
        a=db.add_article(vid,'Note atelier','Test','Nicio valoare tehnică reală','test')
        assert len(db.list_articles(vid,search='Test'))==1
        db.update_article(a,'Motor','Actualizat','Test2','manual')
        assert db.get_article(a)['content']=='Test2'
        data=root/'r.csv'
        data.write_text('make,model,engine,category,title,content\nA,B,X,Diagnosticare / DTC,Exemplu,Fictiv\n',encoding='utf8')
        assert import_records(db,data)['inserted']==1
        assert db.stats()==[2,2]
        db.backup(root/'backup.sqlite3');db.close()
        d2=Store(root/'backup.sqlite3');assert d2.stats()==[2,2];d2.close()
    print("ATELIERDATA_SELF_TEST=PASS")
    return 0

class Editor:
    def __init__(self,parent,title,fields,body=None):
        import tkinter as tk
        from tkinter import ttk
        self.value=None
        top=tk.Toplevel(parent);top.title(title);top.geometry('540x610' if body else '520x400')
        top.grab_set();top.transient(parent)
        frame=ttk.Frame(top,padding=17);frame.pack(fill='both',expand=True)
        self.inputs={}
        for name,label,default in fields:
            ttk.Label(frame,text=label).pack(anchor='w',pady=(5,2))
            ent=ttk.Entry(frame);ent.insert(0,default or '');ent.pack(fill='x')
            self.inputs[name]=ent
        if body:
            ttk.Label(frame,text='Conținut document').pack(anchor='w',pady=(8,2))
            field=tk.Text(frame,wrap='word',height=14,font=('Segoe UI',10))
            field.insert('1.0',body[1] or '');field.pack(fill='both',expand=True)
            self.inputs[body[0]]=field
        def save():
            self.value={key: (widget.get('1.0','end-1c') if isinstance(widget,tk.Text) else widget.get().strip()) for key,widget in self.inputs.items()}
            top.destroy()
        ttk.Button(frame,text='Salvează',command=save).pack(side='right',pady=12)
        ttk.Button(frame,text='Anulează',command=top.destroy).pack(side='right',padx=8)
        parent.wait_window(top)

class App:
    def __init__(self,path):
        import tkinter as tk
        from tkinter import ttk
        self.tk=tk;self.ttk=ttk;self.db=Store(path);self.vid=None;self.aid=None
        root=self.root=tk.Tk();root.title('AtelierData — catalog auto offline');root.geometry('1280x800');root.minsize(960,620)
        root.configure(bg='#101a2b')
        sty=ttk.Style();sty.theme_use('clam')
        sty.configure('TFrame',background='#101a2b')
        sty.configure('TLabel',background='#101a2b',foreground='#eef5ff',font=('Segoe UI',10))
        sty.configure('TButton',padding=9,background='#263954',foreground='#ffffff')
        sty.map('TButton',background=[('active','#38688a')])
        sty.configure('Treeview',background='#1a2a42',fieldbackground='#1a2a42',foreground='#ffffff',rowheight=29)
        sty.map('Treeview',background=[('selected','#25647a')])
        title=ttk.Frame(root,padding=(18,14));title.pack(fill='x')
        ttk.Label(title,text='ATELIERDATA  |  CATALOG TEHNIC OFFLINE',font=('Segoe UI Semibold',18)).pack(side='left')
        self.stat=tk.StringVar();ttk.Label(title,textvariable=self.stat).pack(side='right')
        bar=ttk.Frame(root,padding=(18,0,18,12));bar.pack(fill='x')
        actions=[('+ Vehicul',self.new_vehicle),('+ Document',self.new_article),
                 ('Import CSV/JSON',self.load),('Export JSON',self.export),
                 ('Backup SQLite',self.backup),('Backup ZIP',self.backup_full),
                 ('Restaurare ZIP',self.restore_full),('Specificații',self.specifications),
                 ('Proceduri',self.procedures),('Scheme / imagini',self.schematics),
                 ('Diagnosticare DTC',self.diagnostics),('Întreținere',self.maintenance),
                 ('Catalog public NHTSA',self.public_catalog),('Surse tehnice online',self.online_sources),
                 ('Bibliotecă tehnică offline',self.local_library),
                 ('Atlas tehnic',self.workshop_atlas),
                 ('Fișa tehnică vehicul',self.vehicle_service_card),
                 ('Căutare globală',self.global_search),
                 ('Analiză IDF',self.analyze)]
        for col in range(4):
            bar.columnconfigure(col,weight=1)
        for i,(name,cmd) in enumerate(actions):
            ttk.Button(bar,text=name,command=cmd).grid(
                row=i//4,column=i%4,sticky='ew',padx=4,pady=3)
        panes=ttk.PanedWindow(root,orient='horizontal');panes.pack(fill='both',expand=True,padx=17,pady=(0,12))
        left=ttk.Frame(panes);middle=ttk.Frame(panes);right=ttk.Frame(panes)
        panes.add(left,weight=3);panes.add(middle,weight=4);panes.add(right,weight=5)
        ttk.Label(left,text='VEHICULE').pack(anchor='w',pady=(0,6))
        self.vsearch=tk.StringVar()
        e=ttk.Entry(left,textvariable=self.vsearch);e.pack(fill='x');e.bind('<KeyRelease>',lambda ev:self.refresh_vehicles())
        self.vtree=ttk.Treeview(left,show='tree');self.vtree.pack(fill='both',expand=True,pady=9)
        self.vtree.bind('<<TreeviewSelect>>',self.select_vehicle)
        ttk.Button(left,text='Șterge vehicul',command=self.del_vehicle).pack(anchor='w')
        ttk.Label(middle,text='DOCUMENTE ȘI CATEGORII').pack(anchor='w',pady=(0,6))
        self.cat=tk.StringVar(value='Toate')
        picker=ttk.Combobox(middle,textvariable=self.cat,values=('Toate',)+CATEGORIES,state='readonly')
        picker.pack(fill='x');picker.bind('<<ComboboxSelected>>',lambda e:self.refresh_articles())
        self.asearch=tk.StringVar();e=ttk.Entry(middle,textvariable=self.asearch);e.pack(fill='x',pady=7)
        e.bind('<KeyRelease>',lambda ev:self.refresh_articles())
        self.atree=ttk.Treeview(middle,show='tree');self.atree.pack(fill='both',expand=True,pady=(0,7))
        self.atree.bind('<<TreeviewSelect>>',self.select_article)
        self.detail=tk.StringVar(value='Selectează vehiculul și documentul')
        ttk.Label(right,textvariable=self.detail,font=('Segoe UI Semibold',15),wraplength=400).pack(anchor='w',pady=(0,10))
        self.content=tk.Text(right,bg='#1a2a42',fg='#eef5ff',font=('Segoe UI',11),wrap='word',
                             padx=15,pady=15,relief='flat',insertbackground='white')
        self.content.pack(fill='both',expand=True)
        act=ttk.Frame(right);act.pack(fill='x',pady=(10,0))
        ttk.Button(act,text='Editare',command=self.edit_article).pack(side='left',padx=(0,7))
        ttk.Button(act,text='Șterge',command=self.del_article).pack(side='left',padx=(0,7))
        ttk.Button(act,text='Atașează',command=self.attach).pack(side='left',padx=(0,7))
        ttk.Button(act,text='Deschide fișier',command=self.open_attached).pack(side='left')
        self.message=tk.StringVar(value='Datele tehnice nu sunt incluse până la obținerea unui export autorizat.')
        ttk.Label(root,textvariable=self.message).pack(anchor='w',padx=18,pady=(0,12))
        self.refresh();root.protocol('WM_DELETE_WINDOW',self.close)
    def show(self,text):
        self.content.config(state='normal');self.content.delete('1.0','end')
        self.content.insert('1.0',text);self.content.config(state='disabled')
    def refresh(self):
        v,a=self.db.stats();self.stat.set(f"{v} vehicule  •  {a} documente")
        self.refresh_vehicles();self.refresh_articles()
    def refresh_vehicles(self):
        tree=self.vtree;tree.delete(*tree.get_children());self.vmap={}
        groups={}
        for v in self.db.list_vehicles(self.vsearch.get()):
            make=v['make']
            if make not in groups:groups[make]=tree.insert('','end',text=make,open=True)
            item=tree.insert(groups[make],'end',text=f"{v['model']}  {v['engine']}  {v['years']}")
            self.vmap[item]=v['id']
            if v['id']==self.vid:tree.selection_set(item)
    def select_vehicle(self,event=None):
        selection=self.vtree.selection()
        if selection:
            vid=self.vmap.get(selection[0])
            if vid is not None:
                self.vid=vid;self.aid=None
                self.detail.set('Documentație pentru vehiculul selectat')
                self.show('Selectează un document sau adaugă unul nou.\n\nNu sunt completate valori tehnice fictive.')
                self.refresh_articles()
    def refresh_articles(self):
        tree=self.atree;tree.delete(*tree.get_children());self.amap={};groups={}
        for a in self.db.list_articles(self.vid,self.cat.get(),self.asearch.get()):
            cat=a['category']
            if cat not in groups:groups[cat]=tree.insert('','end',text=cat,open=True)
            item=tree.insert(groups[cat],'end',text=a['title']);self.amap[item]=a['id']
    def select_article(self,event=None):
        selection=self.atree.selection()
        if selection:
            aid=self.amap.get(selection[0])
            if aid:
                self.aid=aid;a=self.db.get_article(aid)
                self.detail.set(a['title'])
                files=list_documents(self.db,aid)
                names='\n'.join(f"{i+1}. {item['path']}" for i,item in enumerate(files))
                self.show(f"CATEGORIE: {a['category']}\nSURSĂ: {a['source'] or 'neprecizată'}\n\n{a['content']}" +
                          (f"\n\nFIȘIERE ATAȘATE ({len(files)}):\n{names}" if files else ''))
    def new_vehicle(self):
        from tkinter import messagebox
        fields=[('make','Marca *',''),('model','Model *',''),('engine','Cod motor',''),
                ('years','Ani fabricație',''),('fuel','Combustibil',''),('variant','Variantă','')]
        data=Editor(self.root,'Vehicul nou',fields).value
        if data:
            try:self.vid=self.db.add_vehicle(**data);self.refresh()
            except Exception as e:messagebox.showerror('Vehicul invalid',str(e))
    def del_vehicle(self):
        from tkinter import messagebox
        if self.vid and messagebox.askyesno('Confirmare','Ștergi vehiculul și documentația asociată?'):
            self.db.delete_vehicle(self.vid);self.vid=None;self.aid=None;self.refresh();self.show('')
    def editor(self,article=None):
        from tkinter import messagebox
        if self.vid is None:return messagebox.showinfo('Vehicul necesar','Selectează un vehicul.')
        fields=[('category','Categorie',article['category'] if article else 'Date tehnice'),
                ('title','Titlu *',article['title'] if article else ''),
                ('source','Sursa documentului',article['source'] if article else '')]
        data=Editor(self.root,'Document tehnic',fields,body=('content',article['content'] if article else '')).value
        if data:
            try:
                if article:self.db.update_article(article['id'],**data)
                else:self.db.add_article(self.vid,**data)
                self.refresh();self.message.set('Document salvat în baza locală.')
            except Exception as exc:messagebox.showerror('Eroare',str(exc))
    def new_article(self):self.editor()
    def edit_article(self):
        if self.aid:self.editor(self.db.get_article(self.aid))
    def del_article(self):
        from tkinter import messagebox
        if self.aid and messagebox.askyesno('Ștergere','Ștergi documentul?'):
            self.db.delete_article(self.aid);self.aid=None;self.refresh();self.show('')
    def load(self):
        from tkinter import filedialog,messagebox
        path=filedialog.askopenfilename(filetypes=[('Date CSV/JSON','*.csv *.json')])
        if path:
            try:
                r=import_records(self.db,path);self.refresh()
                messagebox.showinfo('Import',f"Importate: {r['inserted']}, respinse: {len(r['rejected'])}")
            except Exception as exc:messagebox.showerror('Import eșuat',str(exc))

    def export(self):
        from tkinter import filedialog,messagebox
        path=filedialog.asksaveasfilename(defaultextension='.json',
                    filetypes=[('JSON AtelierData','*.json')])
        if path:
            try:
                n=export_records(self.db,path)
                messagebox.showinfo('Export',f'Exportate {n} documente introduse de utilizator.')
            except Exception as exc:messagebox.showerror('Export eșuat',str(exc))

    def attach(self):
        from tkinter import filedialog,messagebox
        if not self.aid:return messagebox.showinfo('Document necesar','Selectează un document.')
        path=filedialog.askopenfilename(filetypes=[('Documente permise','*.pdf *.png *.jpg *.jpeg *.txt')])
        if path:
            try:
                attach_document(self.db,self.aid,path)
                self.select_article()
                self.message.set('Atașament copiat în stocarea locală.')
            except Exception as exc:messagebox.showerror('Atașament respins',str(exc))

    def open_attached(self):
        from tkinter import messagebox,simpledialog
        if not self.aid:return messagebox.showinfo('Document necesar','Selectează un document.')
        files=list_documents(self.db,self.aid)
        if not files:return messagebox.showinfo('Fără atașamente','Nu există fișiere atașate.')
        index=1 if len(files)==1 else simpledialog.askinteger(
            'Atașamente','Numărul fișierului din lista documentului:',
            minvalue=1,maxvalue=len(files),parent=self.root)
        if index is None:return
        try:
            path=resolve_document(self.db,files[index-1]['id'])
            if sys.platform=='win32':os.startfile(str(path))
            else:
                import subprocess
                subprocess.Popen(['xdg-open',str(path)])
        except Exception as exc:messagebox.showerror('Fișier indisponibil',str(exc))


    def public_catalog(self):
        return open_vehicle_catalog(self)

    def online_sources(self):
        return open_sources_window(self)

    def local_library(self):
        return open_document_library(self)

    def workshop_atlas(self):
        return open_workshop_atlas(self)

    def vehicle_service_card(self):
        return open_vehicle_service_card(self)

    def maintenance(self):
        return open_maintenance_window(self,Editor)

    def diagnostics(self):
        return open_dtc_window(self,Editor)

    def schematics(self):
        from schematic_viewer import open_schematics_window
        return open_schematics_window(self,Editor)

    def global_search(self):
        return open_search_window(self)

    def procedures(self):
        from repair_procedures_gui import open_procedures_window
        return open_procedures_window(self,Editor)

    def specifications(self):
        """Structured service values, each with a source and measurement conditions."""
        from tkinter import filedialog,messagebox
        if not self.vid:
            return messagebox.showinfo('Vehicul necesar',
                                       'Selectează o motorizare înainte de specificații.')
        tk=self.tk;ttk=self.ttk
        vehicle_id=self.vid
        window=tk.Toplevel(self.root)
        window.title('AtelierData — specificații tehnice și proveniență')
        window.geometry('1080x580')
        window.transient(self.root)
        root=ttk.Frame(window,padding=14)
        root.pack(fill='both',expand=True)
        ttk.Label(root,text='SPECIFICAȚII TEHNICE — VALORI CU SURSĂ',
                  font=('Segoe UI Semibold',14)).pack(anchor='w',pady=(0,8))
        search=tk.StringVar()
        q=ttk.Entry(root,textvariable=search)
        q.pack(fill='x',pady=(0,7))
        cols=('system','parameter','value','unit','conditions','source')
        view=ttk.Treeview(root,columns=cols,show='headings',selectmode='browse')
        names=('Sistem','Parametru','Valoare','Unitate','Condiții','Sursă')
        widths=(145,185,95,76,260,180)
        for col,title,width in zip(cols,names,widths):
            view.heading(col,text=title);view.column(col,width=width,minwidth=55,stretch=True)
        area=ttk.Frame(root);area.pack(fill='both',expand=True)
        view.pack(in_=area,side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(area,orient='vertical',command=view.yview)
        scroll.pack(side='right',fill='y')
        view.configure(yscrollcommand=scroll.set)
        info=tk.StringVar()
        ttk.Label(root,textvariable=info).pack(anchor='w',pady=(8,6))
        def refresh():
            view.delete(*view.get_children())
            rows=list_specs(self.db,vehicle_id,search.get())
            for item in rows:
                view.insert('','end',iid=str(item['id']),
                            values=tuple(item[key] for key in cols))
            info.set(f'{len(rows)} valori disponibile. Nu sunt introduse date fictive.')
        q.bind('<KeyRelease>',lambda event:refresh())
        def edit(is_new):
            current=None
            if not is_new:
                selected=view.selection()
                if not selected:
                    return messagebox.showinfo('Selectare','Selectează o valoare tehnică.',parent=window)
                current=get_spec(self.db,int(selected[0]))
            fields=[
              ('system','Sistem *',current['system'] if current else ''),
              ('parameter','Parametru *',current['parameter'] if current else ''),
              ('value','Valoare *',current['value'] if current else ''),
              ('unit','Unitate',current['unit'] if current else ''),
              ('conditions','Condiții de măsurare',current['conditions'] if current else ''),
              ('source','Sursa exactă / referința *',current['source'] if current else '')]
            data=Editor(window,'Valoare tehnică',fields).value
            if data is None:return
            try:
                if is_new:add_spec(self.db,vehicle_id,**data)
                else:update_spec(self.db,current['id'],**data)
                refresh()
            except Exception as exc:messagebox.showerror('Valoare respinsă',str(exc),parent=window)
        def delete():
            selected=view.selection()
            if not selected:return
            if messagebox.askyesno('Confirmare','Ștergi această specificație?',parent=window):
                remove_spec(self.db,int(selected[0]));refresh()
        def imp():
            file=filedialog.askopenfilename(parent=window,filetypes=[('CSV/JSON','*.csv *.json')])
            if not file:return
            try:
                report=import_specs(self.db,file)
                refresh();self.refresh()
                messagebox.showinfo('Import',f"Importate: {report['inserted']} / Duplicat: {report['duplicates']}",
                                    parent=window)
            except Exception as exc:messagebox.showerror('Import respins',str(exc),parent=window)
        def exp():
            file=filedialog.asksaveasfilename(parent=window,defaultextension='.json',
                      filetypes=[('JSON','*.json')])
            if not file:return
            try:
                n=export_specs(self.db,file)
                messagebox.showinfo('Export',f'Exportate {n} valori cu sursele asociate.',parent=window)
            except Exception as exc:messagebox.showerror('Export eșuat',str(exc),parent=window)
        buttons=ttk.Frame(root);buttons.pack(fill='x',pady=(6,0))
        for label,action in [('+ Valoare',lambda:edit(True)),('Editează',lambda:edit(False)),
                              ('Șterge',delete),('Import CSV/JSON',imp),('Export JSON',exp)]:
            ttk.Button(buttons,text=label,command=action).pack(side='left',padx=(0,7))
        refresh()

    def backup_full(self):
        from tkinter import filedialog,messagebox
        path=filedialog.asksaveasfilename(defaultextension='.zip',
                    filetypes=[('Backup AtelierData ZIP','*.zip')])
        if path:
            try:
                report=backup_bundle(self.db,path)
                messagebox.showinfo('Backup complet',
                    f"Backup salvat: {report['documents']} atașamente.\n{path}")
            except Exception as exc:messagebox.showerror('Backup eșuat',str(exc))

    def restore_full(self):
        from tkinter import filedialog,messagebox,simpledialog
        archive=filedialog.askopenfilename(filetypes=[('Backup AtelierData ZIP','*.zip')])
        if not archive:return
        parent=filedialog.askdirectory(title='Alege directorul PĂRINTE pentru restaurare')
        if not parent:return
        name=simpledialog.askstring('Restaurare','Numele noului director:',parent=self.root)
        if not name:return
        if name in ('.','..') or '/' in name or chr(92) in name:
            return messagebox.showerror('Destinație invalidă','Folosește un nume simplu de director.')
        try:
            dbfile=restore_bundle(archive,Path(parent)/name)
            messagebox.showinfo('Restaurare verificată',
                'Baza și atașamentele au fost restaurate în director nou.\n'+str(dbfile)+
                '\nPentru a folosi baza restaurată, redeschide aplicația cu --db-path.')
        except Exception as exc:messagebox.showerror('Restaurare eșuată',str(exc))
    def backup(self):
        from tkinter import filedialog,messagebox
        p=filedialog.asksaveasfilename(defaultextension='.sqlite3',filetypes=[('SQLite','*.sqlite3')])
        if p:
            try:self.db.backup(p);messagebox.showinfo('Backup','Salvat.')
            except Exception as e:messagebox.showerror('Backup eșuat',str(e))
    def analyze(self):
        from tkinter import filedialog,messagebox
        p=filedialog.askdirectory(title='Director IDF pentru analiză statică')
        if not p:return
        out=filedialog.asksaveasfilename(defaultextension='.json',initialfile='idf_probe.json')
        if out:
            try:
                r=probe_idf(p);Path(out).write_text(json.dumps(r,indent=2,ensure_ascii=False),encoding='utf8')
                messagebox.showinfo('IDF',f"Fișiere inspectate: {r['count']}. Format nedecodat.")
            except Exception as e:messagebox.showerror('IDF',str(e))
    def close(self):self.db.close();self.root.destroy()
    def run(self):self.root.mainloop()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--self-test',action='store_true')
    ap.add_argument('--ui-smoke',action='store_true')
    ap.add_argument('--probe-idf')
    ap.add_argument('--output',default='idf_probe.json')
    ap.add_argument('--db-path')
    ap.add_argument('--export-json')
    ap.add_argument('--import-records')
    ap.add_argument('--check-db',action='store_true')
    ap.add_argument('--import-specs')
    ap.add_argument('--export-specs')
    ap.add_argument('--list-specs',action='store_true')
    ap.add_argument('--search-specs',default='')
    ap.add_argument('--search-all',default=None,help='Caută literal în toate modulele catalogului local')
    ap.add_argument('--search-vehicle-id',type=int)
    ap.add_argument('--search-limit',type=int,default=100)
    ap.add_argument('--export-procedures-json')
    ap.add_argument('--export-procedure-html')
    ap.add_argument('--procedure-id',type=int)
    ap.add_argument('--backup-zip')
    ap.add_argument('--restore-zip')
    ap.add_argument('--restore-dir')
    args=ap.parse_args()
    if args.self_test:return self_test()
    if args.ui_smoke:
        with tempfile.TemporaryDirectory() as folder:
            ui=App(Path(folder)/'ui-smoke.sqlite3')
            vehicle=ui.db.add_vehicle('SYNTHETIC','GUI TEST')
            ui.vid=vehicle
            article=ui.db.add_article(vehicle,'Scheme electrice',
                                      'Referință sintetică','Doar test','TEST')
            pid=create_procedure(ui.db,vehicle,'Sistem sintetic','Procedură GUI TEST',
                                 source='TEST ONLY')
            step_id=add_step(ui.db,pid,'Pas fictiv 100%_ pentru smoke-test',
                     safety_note='Nu este o instrucțiune reală',article_id=article)
            second_article=ui.db.add_article(vehicle,'Note atelier',
                          'Referință secundară sintetică','Date fictive','TEST OWNED')
            dtc_id=add_dtc(ui.db,vehicle,'P0A01','Sistem demonstrativ',
                          'Descriere inventată',source='DATE SINTETICE',
                          procedure_id=pid,article_id=article)
            maintenance_id=add_plan(ui.db,vehicle,'Întreținere fictivă',
                                    'TEST',interval_km=1000,interval_months=6,
                                    source='SINTETIC — NU FOLOSI')
            log_service(ui.db,maintenance_id,'2026-01-31',1000)
            ui.refresh()
            gui_errors=[]
            # Non-interactive smoke tests must fail instead of waiting forever
            # on an error/info dialog that no CI runner can dismiss.
            from tkinter import messagebox as smoke_messagebox
            previous_showerror=smoke_messagebox.showerror
            previous_showinfo=smoke_messagebox.showinfo
            def unexpected_smoke_dialog(title,message,**kwargs):
                raise RuntimeError('GUI_SMOKE_UNEXPECTED_DIALOG: '+str(title)+': '+str(message))
            smoke_messagebox.showerror=unexpected_smoke_dialog
            smoke_messagebox.showinfo=unexpected_smoke_dialog
            def on_gui_error(exc, value, traceback):
                gui_errors.append(f'{exc.__name__}: {value}')
                ui.root.after(0,ui.close)
            ui.root.report_callback_exception=on_gui_error
            ui.root.after(200,ui.specifications)
            def check_procedures_window():
                window=ui.procedures()
                if window is None or not window.winfo_exists():
                    raise RuntimeError('PROCEDURES_GUI_NOT_OPENED')
                if len(window.procedures_tree.get_children())!=1:
                    raise RuntimeError('PROCEDURES_GUI_ROWS_MISSING')
                window.procedure_search_var.set('%_')
                if window.procedures_tree.get_children()!=(str(pid),):
                    raise RuntimeError('PROCEDURES_GUI_LITERAL_SEARCH_MISSING')
                window.procedure_search_var.set('NOT_PRESENT_%_')
                if window.procedures_tree.get_children():
                    raise RuntimeError('PROCEDURES_GUI_LITERAL_SEARCH_WILDCARD_LEAK')
                window.procedure_search_var.set('x'*201)
                if window.procedures_tree.get_children() or 'invalid' not in window.procedure_search_notice.get().lower():
                    raise RuntimeError('PROCEDURES_GUI_INVALID_SEARCH_NOT_HANDLED')
                window.procedure_search_var.set('')
                if window.procedures_tree.get_children()!=(str(pid),):
                    raise RuntimeError('PROCEDURES_GUI_SEARCH_RESET_FAILED')
                window.procedures_tree.selection_set(str(pid))
                window.procedures_tree.event_generate('<<TreeviewSelect>>')
                def check_steps():
                    if len(window.steps_tree.get_children())!=1:
                        raise RuntimeError('PROCEDURES_GUI_STEPS_MISSING')
                    window.steps_tree.selection_set(str(step_id))
                    picker=window.open_reference_picker()
                    if picker is None or not picker.winfo_exists():
                        raise RuntimeError('PROCEDURES_REFERENCE_PICKER_NOT_OPENED')
                    refs=picker.reference_tree.get_children()
                    if set(refs)!={str(article),str(second_article)}:
                        raise RuntimeError('PROCEDURES_REFERENCE_PICKER_WRONG_VEHICLE_SCOPE')
                    picker.reference_tree.selection_set(str(second_article))
                    picker.apply_reference()
                    linked=ui.db.db.execute(
                        'SELECT article_id,safety_note FROM procedure_steps WHERE id=?',
                        (step_id,)).fetchone()
                    if linked['article_id']!=second_article or not linked['safety_note']:
                        raise RuntimeError('PROCEDURES_REFERENCE_PICKER_UPDATE_FAILED')
                ui.root.after(200,check_steps)
                def check_navigation():
                    window.steps_tree.selection_set(str(step_id))
                    picker=window.open_reference_picker()
                    if picker is None or not picker.winfo_exists():
                        raise RuntimeError('PROCEDURES_SCHEMATIC_PICKER_NOT_OPENED')
                    if not picker.reference_tree.exists(str(article)):
                        raise RuntimeError('PROCEDURES_SCHEMATIC_REFERENCE_NOT_FOUND')
                    picker.reference_tree.selection_set(str(article))
                    picker.apply_reference()
                    linked=ui.db.db.execute(
                        'SELECT article_id,safety_note FROM procedure_steps WHERE id=?',
                        (step_id,)).fetchone()
                    if linked['article_id']!=article or not linked['safety_note']:
                        raise RuntimeError('PROCEDURES_SCHEMATIC_REFERENCE_NOT_LINKED')
                    viewer=window.open_schematic_reference()
                    if viewer is None or not viewer.winfo_exists():
                        raise RuntimeError('PROCEDURES_SCHEMATIC_NAVIGATION_FAILED')
                    if viewer.schematics_tree.selection()!=(str(article),):
                        raise RuntimeError('PROCEDURES_SCHEMATIC_WRONG_ARTICLE')
                    if len(viewer.attachments_tree.get_children())!=1:
                        raise RuntimeError('PROCEDURES_SCHEMATIC_ATTACHMENT_NOT_SELECTED')
                    def check_navigation_image():
                        if len(viewer.diagram_canvas.find_all())!=1:
                            raise RuntimeError('PROCEDURES_SCHEMATIC_IMAGE_NOT_RENDERED')
                    ui.root.after(220,check_navigation_image)
                ui.root.after(950,check_navigation)
                def check_search_hits():
                    # GUI integration: show all fields for one literal query,
                    # not only the first field of a matching procedure/step.
                    window.procedure_search_var.set('TEST')
                    multi=window.open_search_hits()
                    if multi is None or not multi.winfo_exists():
                        raise RuntimeError('PROCEDURES_MULTI_HITS_GUI_NOT_OPENED')
                    fields={hit['field'] for hit in multi.hits}
                    if not {'Titlu procedură', 'Proveniență procedură',
                            'Instrucțiune pas', 'Proveniență document'} <= fields:
                        raise RuntimeError('PROCEDURES_MULTI_HITS_FIELDS_MISSING')
                    if len(multi.hits_tree.get_children()) != len(multi.hits):
                        raise RuntimeError('PROCEDURES_MULTI_HITS_ROWS_MISSING')
                    multi.search_field_filter.set('Instrucțiune pas')
                    if not multi.apply_field_filter():
                        raise RuntimeError('PROCEDURES_HITS_GLOBAL_FILTER_QUERY_FAILED')
                    visible=multi.visible_hit_indices()
                    if not visible or any(multi.hits[i]['field']!='Instrucțiune pas'
                                          for i in visible):
                        raise RuntimeError('PROCEDURES_HITS_FIELD_FILTER_FAILED')
                    if multi.hits_tree.get_children()!=tuple(str(i) for i in visible):
                        raise RuntimeError('PROCEDURES_HITS_FIELD_FILTER_ROWS_FAILED')
                    filtered=multi.move_hit_selection(1)
                    if filtered is None or filtered['field']!='Instrucțiune pas':
                        raise RuntimeError('PROCEDURES_HITS_FIELD_FILTER_NAVIGATION_FAILED')
                    multi.search_field_filter.set('Toate câmpurile')
                    if not multi.apply_field_filter():
                        raise RuntimeError('PROCEDURES_HITS_GLOBAL_FILTER_RESET_FAILED')
                    if len(multi.hits_tree.get_children())!=len(multi.hits):
                        raise RuntimeError('PROCEDURES_HITS_FIELD_FILTER_RESET_FAILED')
                    first=multi.move_hit_selection(1)
                    if first is None or multi.hits_tree.selection()!=('0',):
                        raise RuntimeError('PROCEDURES_MULTI_HITS_NEXT_SELECTION_FAILED')
                    last=multi.move_hit_selection(-1)
                    if last is None or multi.hits_tree.selection()!=(str(len(multi.hits)-1),):
                        raise RuntimeError('PROCEDURES_MULTI_HITS_PREVIOUS_WRAP_FAILED')
                    again=multi.move_hit_selection(1)
                    if again is None or multi.hits_tree.selection()!=('0',):
                        raise RuntimeError('PROCEDURES_MULTI_HITS_FORWARD_WRAP_FAILED')
                    multi.destroy()
                    # Exercise actual GUI paging beyond the 250-result boundary.
                    ui.db.db.executemany(
                        'INSERT INTO procedure_steps'
                        '(procedure_id,step_number,instruction,safety_note)'
                        ' VALUES(?,?,?,?)',
                        [(pid,n,'PAGED-UI synthetic step',
                          'PAGED-UI warning' if n>=252 else '')
                         for n in range(2,263)])
                    ui.db.db.commit()
                    window.procedure_search_var.set('PAGED-UI')
                    pages=window.open_search_hits()
                    if pages is None or len(pages.hits)!=250:
                        raise RuntimeError('PROCEDURES_GUI_FIRST_PAGE_FAILED')
                    if not pages.search_page_state['has_more']:
                        raise RuntimeError('PROCEDURES_GUI_MORE_RESULTS_NOT_DETECTED')
                    # The warning field first appears after the first 250 hits.
                    # Selecting it must query all SQLite hits, not just page one.
                    pages.search_field_filter.set('Avertisment pas')
                    if not pages.apply_field_filter() or len(pages.hits)!=11:
                        raise RuntimeError('PROCEDURES_GUI_GLOBAL_FIELD_FILTER_FAILED')
                    if any(hit['field']!='Avertisment pas' for hit in pages.hits):
                        raise RuntimeError('PROCEDURES_GUI_GLOBAL_FIELD_SCOPE_FAILED')
                    pages.search_field_filter.set('Toate câmpurile')
                    if not pages.apply_field_filter() or len(pages.hits)!=250:
                        raise RuntimeError('PROCEDURES_GUI_GLOBAL_FIELD_RESET_FAILED')
                    if not pages.change_hits_page(1) or len(pages.hits)!=22:
                        raise RuntimeError('PROCEDURES_GUI_NEXT_PAGE_FAILED')
                    if pages.search_page_state['offset']!=250:
                        raise RuntimeError('PROCEDURES_GUI_PAGE_OFFSET_FAILED')
                    if pages.change_hits_page(1):
                        raise RuntimeError('PROCEDURES_GUI_PAST_LAST_PAGE')
                    if not pages.change_hits_page(-1) or len(pages.hits)!=250:
                        raise RuntimeError('PROCEDURES_GUI_PREVIOUS_PAGE_FAILED')
                    if pages.change_hits_page(-1):
                        raise RuntimeError('PROCEDURES_GUI_BEFORE_FIRST_PAGE')
                    pages.destroy()
                    ui.db.db.execute(
                        'DELETE FROM procedure_steps WHERE procedure_id=?'
                        ' AND instruction=?',(pid,'PAGED-UI synthetic step'))
                    ui.db.db.commit()
                    window.procedure_search_var.set('100%_')
                    hits=window.open_search_hits()
                    if hits is None or not hits.winfo_exists():
                        raise RuntimeError('PROCEDURES_SEARCH_HITS_WINDOW_NOT_OPENED')
                    rows=hits.hits_tree.get_children()
                    if len(rows)!=1 or hits.hits[0]['step_id']!=step_id:
                        raise RuntimeError('PROCEDURES_SEARCH_HITS_WRONG_STEP')
                    if hits.hits[0]['source']!='TEST ONLY':
                        raise RuntimeError('PROCEDURES_SEARCH_HITS_PROVENANCE_MISSING')
                    hits.hits_tree.selection_set(rows[0])
                    result=hits.go_to_hit()
                    if result is None or window.procedures_tree.selection()!=(str(pid),):
                        raise RuntimeError('PROCEDURES_SEARCH_HITS_NAVIGATION_FAILED')
                    if window.steps_tree.selection()!=(str(step_id),):
                        raise RuntimeError('PROCEDURES_SEARCH_HITS_STEP_NOT_SELECTED')
                    # The reference picker previously switched this step to
                    # the synthetic second article. Verify direct hit-to-document
                    # navigation opens that exact same-vehicle document.
                    document=hits.open_hit_reference()
                    if document is None or not document.winfo_exists():
                        raise RuntimeError('PROCEDURES_SEARCH_HIT_DOCUMENT_NOT_OPENED')
                    if document.reference_article_id!=second_article:
                        raise RuntimeError('PROCEDURES_SEARCH_HIT_WRONG_DOCUMENT')
                    if 'Date fictive' not in document.reference_text_widget.get('1.0','end'):
                        raise RuntimeError('PROCEDURES_SEARCH_HIT_DOCUMENT_TEXT_MISSING')
                    document.destroy()
                    hits.destroy()
                    window.procedure_search_var.set('')
                ui.root.after(620,check_search_hits)
                def check_procedure_audit():
                    window.procedures_tree.selection_set(str(pid))
                    window.procedures_tree.event_generate('<<TreeviewSelect>>')
                    audit=window.open_procedure_audit()
                    if audit is None or not audit.winfo_exists():
                        raise RuntimeError('PROCEDURES_AUDIT_WINDOW_NOT_OPENED')
                    report=audit.audit_report
                    if report['steps']!=1 or report['errors']!=0:
                        raise RuntimeError('PROCEDURES_AUDIT_INCORRECT_STEP_STATUS')
                    if report['verified_attachments']!=1 or report['warnings']!=0:
                        raise RuntimeError('PROCEDURES_AUDIT_SHA256_CHECK_FAILED')
                    if audit.issues_tree.get_children():
                        raise RuntimeError('PROCEDURES_AUDIT_UNEXPECTED_FINDINGS')
                    import json
                    audit_file=Path(folder)/'gui-audit-report.json'
                    changes_before=ui.db.db.total_changes
                    exported=audit.export_audit_report(audit_file,notify=False)
                    if exported is None or exported['audit']['procedure_id']!=pid:
                        raise RuntimeError('PROCEDURES_AUDIT_JSON_EXPORT_FAILED')
                    if not audit_file.exists():
                        raise RuntimeError('PROCEDURES_AUDIT_JSON_MISSING')
                    stored=json.loads(audit_file.read_text(encoding='utf-8'))
                    if stored!=exported or stored['vehicle']['make']!='SYNTHETIC':
                        raise RuntimeError('PROCEDURES_AUDIT_JSON_WRONG_VEHICLE_OR_CONTENT')
                    if ui.db.db.total_changes!=changes_before:
                        raise RuntimeError('PROCEDURES_AUDIT_JSON_MUTATED_SQLITE')
                    audit_html_file=Path(folder)/'gui-audit-report.html'
                    output=audit.export_audit_printable(audit_html_file,notify=False)
                    if output!=audit_html_file or not audit_html_file.is_file():
                        raise RuntimeError('PROCEDURES_AUDIT_HTML_EXPORT_FAILED')
                    printable=audit_html_file.read_text(encoding='utf-8')
                    if ('default-src \'none\'' not in printable or
                        'SYNTHETIC' not in printable or
                        'Erori: 0' not in printable):
                        raise RuntimeError('PROCEDURES_AUDIT_HTML_WRONG_CONTENT')
                    if ui.db.db.total_changes!=changes_before:
                        raise RuntimeError('PROCEDURES_AUDIT_HTML_MUTATED_SQLITE')

                ui.root.after(1650,check_procedure_audit)
            ui.root.after(520,check_procedures_window)
            def check_schematics_window():
                from PIL import Image
                image_path=Path(folder)/'synthetic_diagram.png'
                Image.new('RGB',(640,320),(10,40,70)).save(image_path)
                attach_document(ui.db,article,image_path)
                schematic=ui.schematics()
                if schematic is None or not schematic.winfo_exists():
                    raise RuntimeError('SCHEMATIC_VIEWER_NOT_OPENED')
                if not schematic.schematics_tree.exists(str(article)):
                    raise RuntimeError('SCHEMATIC_ARTICLE_NOT_LISTED')
                schematic.schematics_tree.selection_set(str(article))
                schematic.schematics_tree.event_generate('<<TreeviewSelect>>')
                def check_image():
                    attachments=schematic.attachments_tree.get_children()
                    if len(attachments)!=1:
                        raise RuntimeError('SCHEMATIC_ATTACHMENT_NOT_LISTED')
                    schematic.attachments_tree.selection_set(attachments[0])
                    schematic.attachments_tree.event_generate('<<TreeviewSelect>>')
                    def image_drawn():
                        if len(schematic.diagram_canvas.find_all())!=1:
                            raise RuntimeError('SCHEMATIC_IMAGE_NOT_DRAWN')
                    ui.root.after(170,image_drawn)
                ui.root.after(220,check_image)
                def check_reverse_usage():
                    usage=schematic.open_usage()
                    if usage is None or not usage.winfo_exists():
                        raise RuntimeError('SCHEMATIC_REVERSE_USAGE_WINDOW_NOT_OPENED')
                    rows=usage.usage_tree.get_children()
                    if len(rows)!=1:
                        raise RuntimeError('SCHEMATIC_REVERSE_USAGE_ROW_MISSING')
                    usage.usage_tree.selection_set(rows[0])
                    editor=usage.open_step()
                    if editor is None or not editor.winfo_exists():
                        raise RuntimeError('SCHEMATIC_REVERSE_NAVIGATION_NOT_OPENED')
                    def check_target():
                        if editor.procedures_tree.selection()!=(str(pid),):
                            raise RuntimeError('SCHEMATIC_REVERSE_WRONG_PROCEDURE')
                        if editor.steps_tree.selection()!=(str(step_id),):
                            raise RuntimeError('SCHEMATIC_REVERSE_WRONG_STEP')
                    ui.root.after(170,check_target)
                ui.root.after(600,check_reverse_usage)
            ui.root.after(950,check_schematics_window)
            def check_dtc_window():
                popup=ui.diagnostics()
                if popup is None or not popup.winfo_exists():
                    raise RuntimeError('DTC_GUI_NOT_OPENED')
                if not popup.dtc_tree.exists(str(dtc_id)):
                    raise RuntimeError('DTC_GUI_ENTRY_NOT_LISTED')
                popup.dtc_tree.selection_set(str(dtc_id))
                popup.dtc_tree.event_generate('<<TreeviewSelect>>')
            ui.root.after(1850,check_dtc_window)
            def check_maintenance_window():
                popup=ui.maintenance()
                if popup is None or not popup.winfo_exists():
                    raise RuntimeError('MAINTENANCE_GUI_NOT_OPENED')
                if not popup.maintenance_tree.exists(str(maintenance_id)):
                    raise RuntimeError('MAINTENANCE_GUI_PLAN_MISSING')
                popup.maintenance_tree.selection_set(str(maintenance_id))
                popup.maintenance_tree.event_generate('<<TreeviewSelect>>')
                def check_history():
                    if len(popup.service_events_tree.get_children())!=1:
                        raise RuntimeError('MAINTENANCE_GUI_HISTORY_MISSING')
                ui.root.after(150,check_history)
            ui.root.after(2400,check_maintenance_window)
            def check_public_catalog():
                from vpic_catalog import cache_models
                cache_models(ui.db,[{
                    'make_id':514,'model_id':1200,'make_name':'MITSUBISHI',
                    'model_name':'Lancer','model_year':2008}])
                catalog=ui.public_catalog()
                catalog.make_var.set('MITSUBISHI')
                catalog.year_var.set('2008')
                catalog.load_offline_models()
                if len(catalog.models_tree.get_children())!=1:
                    raise RuntimeError('VPIC_OFFLINE_GUI_MODEL_MISSING')
                if ui.db.stats()[0]!=1:
                    raise RuntimeError('VPIC_GUI_AUTO_INSERTED_PERSONAL_VEHICLE')
            ui.root.after(3050,check_public_catalog)
            ui.root.after(4850,ui.close)
            try:
                ui.run()
            finally:
                smoke_messagebox.showerror=previous_showerror
                smoke_messagebox.showinfo=previous_showinfo
            if gui_errors:
                raise RuntimeError('GUI_SMOKE_FAILED: '+'; '.join(gui_errors))
        return 0
    if args.probe_idf:
        report=probe_idf(args.probe_idf)
        Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
        print('IDF_PROBE=PASS count='+str(report['count']));return 0
    database=Path(args.db_path) if args.db_path else db_path()
    if args.restore_zip:
        if not args.restore_dir:ap.error('--restore-zip necesită --restore-dir')
        target=restore_bundle(args.restore_zip,args.restore_dir)
        print('RESTORE_ZIP=PASS database='+str(target));return 0
    if (args.export_json or args.import_records or args.check_db or args.backup_zip
        or args.import_specs or args.export_specs or args.list_specs
        or args.export_procedures_json or args.export_procedure_html
        or args.search_all is not None):

        store=Store(database)
        try:
            if args.search_all is not None:
                rows=search_catalog(store,args.search_all,vehicle_id=args.search_vehicle_id,
                                    limit=args.search_limit)
                print(json.dumps({'schema':'atelierdata-search-v1','results':rows},
                                 ensure_ascii=False,indent=2))
                return 0
            if args.export_procedures_json:
                count=export_procedures_json(store,args.export_procedures_json)
                print('EXPORT_PROCEDURES_JSON=PASS count='+str(count));return 0
            if args.export_procedure_html:
                if args.procedure_id is None:
                    ap.error('--export-procedure-html necesită --procedure-id')
                target=export_procedure_html(store,args.procedure_id,
                                             args.export_procedure_html)
                print('EXPORT_PROCEDURE_HTML=PASS path='+str(target));return 0
            if args.import_specs:
                result=import_specs(store,args.import_specs)
                print('IMPORT_SPECS=PASS '+json.dumps(result,ensure_ascii=False));return 0
            if args.export_specs:
                n=export_specs(store,args.export_specs)
                print('EXPORT_SPECS=PASS count='+str(n));return 0
            if args.list_specs:
                items=[dict(x) for x in list_specs(store,search=args.search_specs)]
                print(json.dumps(items,ensure_ascii=False,indent=2));return 0
            if args.backup_zip:
                report=backup_bundle(store,args.backup_zip)
                print('BACKUP_ZIP=PASS '+json.dumps(report));return 0
            if args.export_json:
                n=export_records(store,args.export_json)
                print('EXPORT_JSON=PASS count='+str(n));return 0
            if args.import_records:
                result=import_records(store,args.import_records)
                print('IMPORT_RECORDS='+json.dumps(result,ensure_ascii=False))
                return 1 if result['rejected'] else 0
            report=integrity_check(store)
            print('DATABASE_INTEGRITY='+json.dumps(report,ensure_ascii=False))
            return 0 if report['ok'] else 1
        finally:store.close()
    App(database).run();return 0

if __name__=='__main__':sys.exit(main())
