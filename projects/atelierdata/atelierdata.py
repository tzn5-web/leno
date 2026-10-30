from __future__ import annotations
import argparse,csv,json,os,sqlite3,sys,tempfile,math,collections,zipfile
from pathlib import Path

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
        self.db.commit()
    def add_vehicle(self,make,model,engine='',years='',fuel='',variant=''):
        if not make.strip() or not model.strip():raise ValueError("Marca și modelul sunt obligatorii")
        cur=self.db.execute("INSERT INTO vehicles(make,model,engine,years,fuel,variant) VALUES(?,?,?,?,?,?)",
           (make.strip(),model.strip(),engine.strip(),years.strip(),fuel.strip(),variant.strip()))
        self.db.commit();return cur.lastrowid
    def list_vehicles(self,search=''):
        q='%'+search+'%'
        return self.db.execute("SELECT * FROM vehicles WHERE make LIKE ? OR model LIKE ? OR engine LIKE ? ORDER BY make,model,engine", (q,q,q)).fetchall()
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
        if search:
            query+=" AND (title LIKE ? OR content LIKE ?)";values.extend(['%'+search+'%']*2)
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
    path=Path(path)
    if path.suffix.lower()=='.csv':
        with path.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
    elif path.suffix.lower()=='.json':
        obj=json.loads(path.read_text(encoding='utf-8-sig'))
        rows=obj.get('records',[]) if isinstance(obj,dict) else obj
    else:raise ValueError("Accept doar CSV/JSON")
    if not isinstance(rows,list):raise ValueError("JSON invalid")
    result={'inserted':0,'rejected':[]}
    vehicles={}
    for i,row in enumerate(rows,1):
        try:
            if not isinstance(row,dict) or any(not str(row.get(k,'')).strip() for k in ('make','model','category','title')):
                raise ValueError("Câmpurile make, model, category, title sunt obligatorii")
            fields=[str(row.get(k,'')).strip() for k in ('make','model','engine','years','fuel','variant')]
            key=tuple(fields)
            if key not in vehicles:
                old=store.db.execute("SELECT id FROM vehicles WHERE make=? AND model=? AND engine=? AND years=? AND fuel=? AND variant=?",fields).fetchone()
                vehicles[key]=old['id'] if old else store.add_vehicle(*fields)
            store.add_article(vehicles[key],str(row['category']),str(row['title']),str(row.get('content',row.get('body',''))),str(row.get('source','')))
            result['inserted']+=1
        except (ValueError,KeyError,TypeError) as exc:result['rejected'].append(f"{i}: {exc}")
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
        for name,cmd in [('+ Vehicul',self.new_vehicle),('+ Document',self.new_article),
                         ('Import CSV/JSON',self.load),('Backup',self.backup),('Analiză IDF',self.analyze)]:
            ttk.Button(bar,text=name,command=cmd).pack(side='left',padx=(0,7))
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
                self.show(f"CATEGORIE: {a['category']}\nSURSĂ: {a['source'] or 'neprecizată'}\n\n{a['content']}")
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
    ap.add_argument('--probe-idf')
    ap.add_argument('--output',default='idf_probe.json')
    args=ap.parse_args()
    if args.self_test:return self_test()
    if args.probe_idf:
        report=probe_idf(args.probe_idf)
        Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
        print('IDF_PROBE=PASS count='+str(report['count']));return 0
    App(db_path()).run();return 0

if __name__=='__main__':sys.exit(main())
