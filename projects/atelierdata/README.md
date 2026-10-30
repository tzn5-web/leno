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
