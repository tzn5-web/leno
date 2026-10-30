# AtelierData — aplicație nouă pentru informații tehnice auto

Proiectul conține cod original pentru un catalog auto offline pe Windows, **nu** o copie 1:1 a Autodata și **nu** conține datele proprietare Autodata. Nu pretinde decodarea bazei .IDF.

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
