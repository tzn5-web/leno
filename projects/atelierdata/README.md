# AtelierData — aplicație nouă pentru informații tehnice auto

Proiectul conține cod original pentru un catalog auto offline pe Windows, **nu** o copie 1:1 a Autodata și **nu** conține datele proprietare Autodata. Nu pretinde decodarea bazei .IDF.

## Biblioteca tehnică offline — documente cu proveniență

**Nou în interfața Windows:** butonul **Bibliotecă tehnică offline**. Acesta oferă o bibliotecă locală de documente tehnice *ale utilizatorului sau păstrate cu permisiune*, legate de vehiculul exact din baza SQLite: `make`, `model`, `engine`, `years`, `variant`. Identitatea motorizării nu este dedusă din denumirea fișierului.

- Import explicit, local, numai PDF/PNG/JPG/JPEG/TXT, în limita existentă de 32 MiB pentru fiecare fișier. Fișierele nu sunt descărcate automat de pe site-urile catalogului.
- Pentru fiecare document: tip (manual atelier, schemă, procedură, buletin etc.), titlu, sursă/autor, URL HTTPS opțional, limbă, piață, revizie, notă de aplicabilitate și **dreptul de păstrare declarat**.
- Importul unui document nou este respins dacă dreptul de păstrare rămâne `neconfirmat`. Afirmarea unui drept de către utilizator nu reprezintă validare juridică independentă.
- Căutare locală în documente și filtrare după marcă, categorie, an și text. Atașamentele mai vechi apar și ele, chiar dacă nu au încă metadate; acestea pot fi completate ulterior.
- Deschiderea unui fișier trece prin verificarea **SHA-256** deja existentă și refuză fișiere lipsă/corupte. Nu se execută fișiere din arhiva Autodata.
- Metadatele se salvează în `library_documents`, cu cheie străină spre `attachments` și ștergere în cascadă. Backupul ZIP existent include automat și tabela în snapshotul SQLite; restaurarea păstrează documentele și proveniența.
- În catalogul **Surse tehnice online** a apărut și **„Salvează referință la vehicul”**: creează numai o notă cu URL, fără a importa conținutul sau a crea în mod fals o procedură de atelier; respinge sursele necorespunzătoare mărcii.

### Testare și limite

```powershell
python -m unittest discover -s projects/atelierdata -p "test_document_library.py" -v
python -m unittest discover -s projects/atelierdata -p "test_technical_source_references.py" -v
python projects/atelierdata/document_library_gui_smoke.py
```

Aceste teste utilizează doar vehicule, PDF-uri și date **sintetice**, plus o fereastră Tkinter locală. Testele sunt incluse în workflow-ul Windows `.github/workflows/atelierdata-windows.yml`. Un PASS al lor nu dovedește acoperirea manualelor reale sau valabilitatea valorilor tehnice. **Verificați un run GitHub Actions reușit înainte să numiți noul EXE testat.**

## Surse tehnice gratuite și oficiale — 31.10.2026

Nou în GUI: butonul **Surse tehnice online**. Catalogul conține **26 de surse** pentru Opel, Mitsubishi, BMW, Nissan, Škoda, Volkswagen, Audi, Ford, Renault, Dacia, Toyota și alte mărci. Filtrează după marcă (preselectată din vehiculul activ), tip (proceduri, scheme, diagnoză, documente, rechemări) și acces (gratuit, cont gratuit, mixt, neoficial, cu plată). Căutarea în catalog este **complet locală**; accesarea internetului are loc doar când utilizatorul apasă „Deschide sursa”.

Exemple verificate:
- [Operation CHARM](https://charm.li/): manuale de atelier gratuite, în special 1982–2013, acoperire și versiune de piață variabile;
- [AUTODOC CLUB România](https://club.autodoc24.ro/manuals): proceduri și tutoriale gratuite pentru utilizatori înregistrați;
- [Auto-Data.net](https://www.auto-data.net/ro/): specificații generale, **nu** cupluri de strângere garantate;
- [MMC Manuals Lancer X / 4A91 1.5](https://www.mmc-manuals.ru/Mitsubishi_Lancer_X%3A_Service_Manuals): pagini publice, statutul reutilizării materialelor trebuie verificat;
- [Škoda manuale oficiale în română](https://manual.skoda-auto.com/599/ro-RO), [BMW manuale utilizator](https://www.bmw.co.uk/en/topics/owners/bmw-owners-manual.html), [Toyota manuale România](https://www.toyota.ro/support/owners-manuals);
- [Opel manuale utilizator](https://www.opel.lv/owners/manuals.html), [Mitsubishi inclusiv Lancer](https://www.mitsubishi-motors.nl/handleidingen), [Nissan UK](https://www.nissan.co.uk/owners/car-repair/car-owner-manual.html), [Volkswagen](https://www.volkswagen.ie/en/owners-and-services/customer-information/digital-manual.html), [Škoda tutoriale video](https://www.skoda-auto.com/services/video-manuals): gratuite, dar pot avea limitări de an, piață și limbă;
- [BMW AOS](https://aos-q2.bmwgroup.com/), [Škoda erWin](https://skoda.erwin-store.com/erwin/showInfoTour.do), [Nissan TechInfo](https://www.nissan-techinfo.com/help), [Stellantis Service Box](https://public.servicebox-parts.com/), [Renault ASOS](https://asos.asdh.aws.renault.com/offers/documentation), [Toyota TechDoc](https://www.toyota-tech.eu/): **documentația profesională este în general condiționată de cont și/sau abonament**;
- [AndrOBD](https://f-droid.org/packages/com.fr3ts0n.ecu.gui.androbd/), [Carmin](https://play.google.com/store/apps/details?id=com.min.car): aplicații suplimentare, Carmin include reclame/cumpărături.
- [NHTSA](https://www.nhtsa.gov/recalls): date SUA, neechivalente cu rechemările UE.

**Limitări:** catalogul este un director de linkuri cu proveniență, nu descarcă sau copiază automat manualele de pe site-uri, nu ocolește abonamente și nu garantează acoperirea fiecărui motor. Un manual public gratuit nu este neapărat reutilizabil legal într-o aplicație distribuită. Înregistrările tehnice în SQLite necesită în continuare import/introducere autorizată cu sursă verificată. Nu trimitem automat VIN sau informații private către site-uri.

Implementare: `technical_sources.py`, `technical_sources_gui.py`, `test_technical_sources.py`. Teste: `python -m unittest discover -s projects/atelierdata -p "test_technical_sources.py" -v`. Build Windows: `.github/workflows/atelierdata-windows.yml`; **nu declarați EXE verificat până la rezultatul PASS și verificarea artefactului**.

**Funcțional:** interfață originală cu selectare marcă/model/motor, SQLite local, 16 categorii tehnice, căutare în documente, adăugare/editare/ștergere vehicule și proceduri, import CSV/JSON și backup SQLite, analiză statică a antetelor IDF.

**Nu este încă implementat:** date complete reale pe toate mărcile, diagrame și ilustrații originale, decodare IDF, echivalență completă cu Autodata. Înregistrările se populează prin importul legal al propriilor date sau al unui export autorizat. Pentru date Autodata comerciale, se poate evalua [API-ul oficial Autodata](https://developer.autodata-group.com/) cu abonament/licență și chei corespunzătoare.

**Rulare:** Python 3.12 cu Tkinter inclus; execută \`python projects/atelierdata/atelierdata.py\`.

**Teste:** \`python projects/atelierdata/atelierdata.py --self-test\`.

**IDF:** \`python projects/atelierdata/atelierdata.py --probe-idf "DIRECTOR" --output idf_probe.json\`. Doar antete și entropie; nu execută fișiere și nu decriptează conținutul.

**Windows EXE:** [GitHub Actions](../../actions/workflows/atelierdata-windows.yml) compilează \`AtelierData.exe\` (PyInstaller --onefile --windowed) și rulează testul bazei de date în executabil. Artefactul de build va fi disponibil la workflow după PASS. Fișierul local SQLite este creat la %LOCALAPPDATA%\\AtelierData\\atelierdata.sqlite3 și nu se trimite în cloud.

## Format de import

CSV sau JSON (array sau {\"records\": [...]}). Coloane obligatorii: \`make\`, \`model\`, \`category\`, \`title\`; opționale: \`engine\`, \`years\`, \`fuel\`, \`variant\`, \`content\`, \`source\`.

Niciun cuplu de strângere, interval de service, procedură sau diagramă nu este inventat. Nu publica date proprietare/chei în repository-ul public.


## Funcții noi — verificare, documente și backup complet

Aplicația acceptă atașamente locale PDF/PNG/JPG/JPEG/TXT, copiate în directorul administrat `documents/` și verificate SHA256 înainte de deschidere. Fișierele executabile sunt respinse. Exportul JSON conține exclusiv datele introduse/importate legal de utilizator, nu fișierele atașate. Backup-ul complet ZIP include snapshot SQLite și atașamentele administrate; restaurarea verifică hashurile și baza SQLite și creează **un director nou**, fără suprascrierea bazei active.

```powershell
python projects/atelierdata/atelierdata.py --db-path .\work\atelierdata.sqlite3 --check-db
python projects/atelierdata/atelierdata.py --db-path .\work\atelierdata.sqlite3 --export-json .\work\records.json
python projects/atelierdata/atelierdata.py --db-path .\work\atelierdata.sqlite3 --import-records .\work\authorized.csv
python projects/atelierdata/atelierdata.py --db-path .\work\atelierdata.sqlite3 --backup-zip .\work\backup.zip
python projects/atelierdata/atelierdata.py --restore-zip .\work\backup.zip --restore-dir .\work\restored-new-folder
python projects/atelierdata/idf_static_evidence.py --self-test
```

Pentru analiza statică a celor 57 de fișiere IDF verificate SHA256 din două pachete private, vezi `IDF_STATIC_EVIDENCE_20261030.md`. Scriptul Java Ghidra 12.1.4 este în `tools/ghidra/AtelierData_IDF_Xrefs.java`; analiza statică headless **a fost executată** pe originalul verificat SHA256, fără autoanaliză completă. Referințele către încărcătorul IDF nu sunt încă demonstrate. Rapoartele private și binarele originale nu se publică în acest repository.

**Limitare de test:** autotestele și smoke-testul GUI din CI verifică funcțiile selectate și pornirea executabilului, nu echivalența cu Autodata sau acuratețea unor proceduri reale.


## Specificații tehnice structurate — modul nou

Butonul **Specificații** deschide un tabel asociat motorizării selectate, cu câmpurile `Sistem`, `Parametru`, `Valoare`, `Unitate`, `Condiții de măsurare` și `Sursa exactă`.

- Adaugă, modifică, șterge și caută valori tehnice pe fiecare vehicul.
- Importă în mod tranzacțional date licențiate introduse de utilizator din CSV/JSON și nu păstrează importuri parțiale când detectează rânduri invalide.
- Detectează înregistrări identice deja existente și raportează numărul lor, fără să le dubleze.
- Exportă valorile într-un JSON cu formatul `atelierdata-specifications-v1`. Backup-ul ZIP existent conține și noul tabel SQLite.
- În mod intenționat nu sunt introduse valori de reparație exemplificative care ar putea fi confundate cu date reale.

Exemplu de CSV (numai câmpuri text, fără valori tehnice inventate):
```csv
make,model,engine,years,fuel,variant,system,parameter,value,unit,conditions,source
Exemplu,Model fictiv,MOTOR-DEMO,N/A,,,"Sistem demonstrativ","Parametru test","DOAR TEST",,,"Date sintetice pentru test"
```

Rulare fără GUI:
```powershell
python projects/atelierdata/atelierdata.py --db-path .\work\atelierdata.sqlite3 --import-specs .\specifications.csv
python projects/atelierdata/atelierdata.py --db-path .\work\atelierdata.sqlite3 --list-specs --search-specs motor
python projects/atelierdata/atelierdata.py --db-path .\work\atelierdata.sqlite3 --export-specs .\specifications.json
python -m unittest discover -s projects/atelierdata -p "test_*.py" -v
```

**Stadiu:** funcțiile de administrare a specificațiilor sunt implementate și supuse testelor automate Windows. Numărul și calitatea înregistrărilor reale depind în continuare de o sursă tehnică autorizată. Analiza formatului proprietar `.IDF` rămâne o investigație separată.


## Proceduri de reparație și referințe autorizate

Butonul **Proceduri** deschide un editor pentru proceduri de atelier asociate
motorizării selectate. Fiecare procedură are sistem, titlu, descriere,
avertisment general și **sursă obligatorie**. Pașii se pot adăuga, edita,
șterge și reordona; fiecare pas poate avea avertisment separat și referință
la un articol sau o schemă deja introdusă pentru **același vehicul**.
Ștergerea articolului elimină legătura, nu lasă un ID invalid.

Pentru a lega un document de un pas, selectează pasul și apasă **Alege document**.
Fereastra afișează doar articolele vehiculului curent, cu categoria, titlul și
proveniența lor; poți căuta inclusiv după sursă, apoi **Leagă documentul selectat**
sau **Elimină legătura**. Nu mai este necesar să cunoști ID-ul numeric al
articolului. Legătura nu copiază și nu modifică documentul; pașii și
avertismentele existente sunt păstrate. Lista este locală, fără interogări web.

**Navigare directă procedură → schemă:** în fereastra **Proceduri**, selectează
pasul care are un document din categoriile „Scheme electrice” sau
„Siguranțe și relee” și apasă **Vezi schema**. Se deschide vizualizatorul
pe exact documentul asociat, fără schimbarea vehiculului sau motorizării.
Prima imagine locală PNG/JPEG asociată este afișată automat numai după
verificarea SHA256; fișierele PDF/TXT nu sunt executate automat.
Referințele către documente obișnuite, șterse sau aparținând altui vehicul
sunt respinse. Nu sunt incluse scheme proprietare în aplicație.

Căutarea acoperă titlul, sistemul, rezumatul, avertismentele, sursa,
instrucțiunile pașilor și titlurile documentelor asociate. Butonul
**Document asociat** arată conținutul și atașamentele autorizate. Deschiderea
unui PDF/PNG/JPG/TXT se face doar după verificarea integrității SHA256 a
fișierului administrat.

**Export HTML** creează o fișă imprimabilă offline cu pași, avertismente și
sursă. Conținutul este escap-at HTML, nu include scripturi sau resurse
externe și nu încorporează fișiere atașate. **Export JSON** salvează
procedurile și proveniența, dar nu include octeții documentelor. Pentru
arhivarea integrală a bazei și atașamentelor, folosește **Backup ZIP**.

Comenzi pentru export din Windows PowerShell:

~~~powershell
python projects/atelierdata/atelierdata.py --db-path .\work\atelierdata.sqlite3 --export-procedures-json .\work\proceduri.json
python projects/atelierdata/atelierdata.py --db-path .\work\atelierdata.sqlite3 --procedure-id 1 --export-procedure-html .\work\procedura.html
python -m unittest discover -s projects/atelierdata -p "test_*.py" -v
~~~

ID-ul procedurii se referă la o procedură existentă în baza proprie. Testele
automate folosesc exclusiv conținut sintetic, nu valori tehnice reale.
Aplicația nu distribuie, nu decodifică și nu revendică datele proprietare
Autodata. Pentru fișe tehnice reale sunt necesare surse autorizate.


## Diagnosticare DTC — modul offline

Fila **Diagnosticare DTC** este un catalog original de informații introduse de utilizator sau obținute din surse tehnice cu licență. Fiecare cod este legat de marcă, model și motorizare, conținând sistemul, descrierea, simptomele, cauzele posibile, verificările, notele și sursa exactă. Sunt acceptate codurile standardizate ca formă \`P/B/C/U\` urmate de patru cifre hexazecimale. Aplicația **nu presupune semnificația unui cod doar din formatul lui**.

Modulul include căutare, creare, editare, ștergere, import CSV/JSON tranzacțional, export JSON, control pentru înregistrări duplicate după vehicul/cod/sursă și legături opționale către proceduri și articole ale **aceluiași vehicul**. Baza SQLite include și aceste date în backupul ZIP complet existent. Datele DTC nu sunt incluse în aplicația distribuită.

Nu există conexiune OBD-II, comenzi către ECU, anularea erorilor sau promisiuni de identificare automată a defectelor. Modulul este pentru consultarea documentației tehnice.

Fișier CSV pentru import (exemplu exclusiv sintetic):

\`\`\`csv
make,model,engine,years,fuel,variant,code,system,title,symptoms,possible_causes,checks,notes,source
DEMO,Model fictiv,MOTOR-DEMO,N/A,,,P0A01,Sistem fictiv,DESCRIERE DOAR TEST,Simptom demonstrativ,Cauză demonstrativă,Verificare fictivă,Nicio valoare reală,SYNTHETIC TEST
\`\`\`

Pachetul de teste include validarea formatului codului, păstrarea sursei, interzicerea legăturilor către alt vehicul, import/export JSON, teste CSV, deduplicare și verificarea SQLite. Rularea Windows testează și deschiderea ferestrei DTC din executabilul real.

## Plan de întreținere și istoric verificabil

Butonul **Întreținere** deschide un modul original de planificare pentru fiecare motorizare.

- Operație, sistem, interval în kilometri și/sau luni, condiții speciale și sursă explicită
- Jurnalul intervențiilor efectuate, cu data reală, kilometrajul și note
- Calculul scadenței de la ultima intervenție consemnată, nu dintr-un kilometraj ori o dată inventate
- Stări: în termen, scadent, fără istoric sau necalculat (kilometraj lipsă)
- Scadență la primul dintre pragurile de kilometri și dată; lipsa kilometrajului nu dovedește că operația este în termen
- Verificare date ISO YYYY-MM-DD, control kilometrajului față de intervențiile anterioare și tratarea lunilor calendaristice, inclusiv anii bisecți
- Administrare și ștergere planuri/intervenții; SQLite include istoricul în backupul ZIP complet

**Nu conține intervale producător precompletate.** Datele trebuie să provină dintr-o sursă validă pentru motorizarea și regimul de utilizare exact. Calculul este orientativ și nu înlocuiește instrucțiunile producătorului.

Teste automate: python -m unittest discover -s projects/atelierdata -p test_maintenance_plans.py -v. Buildul Windows deschide și fereastra Întreținere folosind o mașină și o operație sintetice.


## Audit de integritate pentru proceduri și documente

În fereastra „Proceduri” selectează o procedură și apasă „Audit documente”. Verificarea este numai pentru citire și nu trimite documente sau date despre vehicul în cloud. Raportul afișează numărul de pași, fișierele atașate validate SHA256, erori și avertismente. Fiecare problemă indică pasul; dublu-clic sau „Mergi la pasul selectat” navighează la acesta.

Verificările includ numerotarea pașilor, sursa procedurii, existența și proveniența documentelor asociate, interzicerea referințelor către alt vehicul, fișiere lipsă/modificate și lipsa unei imagini PNG/JPEG previzualizabile pentru scheme. PDF-urile autorizate pot fi deschise prin vizualizatorul sistemului, dar nu sunt redate ca imagini în vizualizatorul de scheme. Un SHA256 corect **nu** demonstrează corectitudinea tehnică sau existența unei licențe. Nu sunt incluse proceduri ori valori tehnice proprietare.

Codul: `procedure_audit.py`; teste sintetice: `test_procedure_audit.py`. Testul de interfață Windows verifică deschiderea raportului și integritatea unui atașament sintetic, atât în Python, cât și în executabilul PyInstaller.

## Referințe inverse: schemă → proceduri

În fereastra **Scheme / imagini**, selectează o schemă și apasă **„Folosit în proceduri”**.
Lista arată toate procedurile și etapele din **același vehicul** care folosesc
documentul, inclusiv avertismentele și proveniența introdusă de autor. Selectează
o intrare și apasă **„Deschide pasul selectat”** pentru navigare la procedura și
pasul exact. O referință ștearsă sau modificată este verificată din nou înainte
de navigare. Interogarea nu schimbă SQLite și nu extrage date proprietare.

Teste: `python -m unittest discover -s projects/atelierdata -p 'test_procedure_usage.py' -v`
și testul integrat Windows `python projects/atelierdata/atelierdata.py --ui-smoke`.


## Căutare detaliată → documentul pasului (2026-10-31)

În **Proceduri**, introdu un termen literal și deschide **„Rezultate detaliate → pas”**.
Selectează un rezultat care identifică un pas și apasă **„Documentul pasului găsit”**.
Aplicația verifică din nou existența procedurii, pasului și documentului,
precum și apartenența acestora la **același vehicul**, înainte de a afișa
conținutul local și proveniența documentului. Rezultatele de tip antet
de procedură nu au automat un document de pas. Atașamentele externe sunt
deschise separat și numai după verificarea SHA256.

O protecție suplimentară în `list_steps` împiedică afișarea titlurilor
documentelor altui vehicul dacă o bază SQLite importată conține o referință
inconsistentă. Referința greșită rămâne detectabilă prin **Audit documente**,
dar nu divulgă titlul în lista de pași sau în fișa textuală.

Verificare: `test_repair_procedures.py` include regresia de izolare a
titlurilor; `atelierdata.py --ui-smoke` navighează efectiv dintr-un rezultat
de căutare într-un document sintetic. Ambele rulează în workflow-ul Windows,
inclusiv în executabilul PyInstaller. Datele reale trebuie să fie introduse
de utilizator sau obținute cu drept de utilizare; nu sunt distribuite date
proprietare și nu sunt inventate proceduri de reparație.


## Export raport audit procedură JSON (2026-10-31)

În **Proceduri → Audit documente**, butonul **„Exportă raport audit JSON”**
recalculează verificările pentru procedura curentă și salvează un raport
UTF-8 cu schema `atelierdata-procedure-audit-v1`. Sunt incluse identificarea
vehiculului, proveniența procedurii, numărul de pași, numărul atașamentelor
verificate, codurile de eroare/avertisment și referințele la pașii afectați.
Nu se exportă conținutul fișierelor atașate și nu se adaugă valori tehnice.

Exportul este atomic și nu modifică SQLite. Se refuză exportul către fișierul
bazei de date, către depozitul intern `documents/`, către extensii altele
decât `.json` sau către o procedură aparținând altui vehicul. Raportul
este un instantaneu; la export verificările se refac pentru a evita
rezultate învechite. SHA256 dovedește numai integritatea fișierului stocat,
nu validitatea tehnică, dreptul de utilizare ori compatibilitatea cu mașina.

Verificare: `python -m unittest discover -s projects/atelierdata -p 'test_procedure_audit_export.py' -v`;
testul integrat `atelierdata.py --ui-smoke` generează și citește un raport
JSON din fereastra Windows și verifică faptul că SQLite nu a fost modificat.

## Export audit HTML imprimabil, fără conexiune (2026-10-31)

În **Proceduri → Audit documente** există **„Exportă raport audit HTML”**.
Fișierul .html/.htm conține un instantaneu al constatărilor curente,
identificarea vehiculului, proveniența procedurii, numărul pașilor, verificările
SHA256, codurile de eroare și avertismentele per pas. Este un document
imprimabil și funcționează offline, fără JavaScript, resurse externe sau
atașamente incluse. Datele provenite din SQLite sunt escapate pentru HTML;
o politică CSP blochează încărcarea resurselor externe.

La fiecare export verificările se refac din SQLite și din fișierele gestionate.
Scrierea este atomică, nu modifică SQLite și nu poate suprascrie baza de date
sau fișiere din depozitul intern documents/. Procedurile și documentele
altor vehicule nu pot fi exportate prin selectarea unei proceduri diferite.
Raportul **nu** certifică siguranța intervenției, corectitudinea valorilor,
dreptul de utilizare sau aplicabilitatea la vehicul.

Teste sintetice: test_procedure_audit_html.py (inclusiv XSS, date ale altui
vehicul, refuz suprascriere, verificări actualizate și integritatea SQLite).
atelierdata.py --ui-smoke verifică și butonul HTML din GUI Windows,
atât în Python, cât și în executabilul PyInstaller.


## Căutare globală în catalog (2026-10-31)

Butonul **Căutare globală** interoghează în mod local șase tipuri de
înregistrări: vehicule, documente, proceduri (inclusiv pașii), specificații
tehnice, DTC și planuri de întreținere. Fiecare rezultat indică vehiculul
și sursa înregistrării. Căutarea este literală: caracterele `%`,
`_` și `\` nu devin wildcard SQL; termenul este parametrizat,
limitat la 200 de caractere, iar rezultatele sunt paginate și ordonate
determinist. Nu se fac cereri de rețea și nu se modifică baza de date.
Rezultatele pot fi filtrate după vehicul; dublu-click deschide vehiculul,
documentul sau modulul relevant. Pentru specificații se deschide modulul,
fără selecție automată a rândului.

Interfața CLI pentru testare/integrare:

```powershell
python projects/atelierdata/atelierdata.py --db-path .\work\atelierdata.sqlite3 --search-all "frâne" --search-limit 100
python projects/atelierdata/atelierdata.py --db-path .\work\atelierdata.sqlite3 --search-all "P0123" --search-vehicle-id 1
python -m unittest discover -s projects/atelierdata -p "test_catalog_search.py" -v
```

Teste sintetice locale: **5/5 PASS**, acoperind toate cele șase tipuri,
literalitatea metacaracterelor, izolarea vehiculelor, paginarea și
respingerea parametrilor invalizi. Aceste teste sunt integrate și în
Windows CI; un nou artifact EXE se declară validat numai după PASS-ul
workflow-ului asociat commitului curent.
