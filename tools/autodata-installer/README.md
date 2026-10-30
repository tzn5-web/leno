# Autodata 3.45 — proiect de instalator Windows cu licență validă

## Stare verificată (30 octombrie 2026)

Acesta este un **proiect de împachetare**, nu un instalator complet testat și nu un
activator. Fișierele proprietare Autodata nu sunt publicate în GitHub.

Sursa de lucru este arhiva utilizatorului `Autodata__3.45.rar`, extrasă în
Google Colab și repartizată în 16 ZIP-uri în Google Drive. `INVENTAR.txt`
indică 139 de fișiere; dintre acestea, 105 se află în directorul `ADCDA2`,
însumând 2.278.001.505 octeți. Lista exactă se află în
`payload-allowlist.json`.

**Blocaj verificat:** `autodata_part_0016.zip` conține atât
`INSTALLATION INSTRUCTIONS.txt` și
`Autodata 3.45_Keygen/install instructions_3.45.txt`, cât și
`SentinelKeyW.DLL`, `vcredist_*.exe`, emulatoare și programe de generare a
licențelor. Google Drive refuză descărcarea acestui ZIP prin conector cu
`cannotDownloadAbusiveFile`. Prin urmare, instrucțiunile de instalare
**nu au fost citite**, nu putem confirma ordinea originală a pașilor, iar
un instalator complet funcțional nu a fost construit.

## Ce implementează proiectul

- `prepare_payload.py`: verifică existența și dimensiunea tuturor celor 105
  fișiere din `ADCDA2`, refuză căi nepermise și linkuri simbolice, copiază
  **numai** fișierele de pe lista explicită, calculează SHA-256.
- `installer.iss`: reîmpachetează fișierele autorizate într-un **singur EXE**
  folosind Inno Setup 6, cu dezinstalare și scurtătură Windows.
- `build.ps1`: construiește local instalatorul, dintr-un director licențiat
  și verificat. Nu execută fișierele aplicației.
- `tests/`: teste unitare cu date **sintetice**, fără binare Autodata.
- `.github/workflows/autodata-installer-ci.yml`: verifică în GitHub Actions
  scripturile și compilarea unui EXE de test cu date sintetice. Nu publică
  acel EXE drept instalator Autodata.

## Construirea locală din surse autentice și licențiate

Cerințe: Windows 10/11, Python 3.10+, Inno Setup 6, un director
`ADCDA2` provenit dintr-o sursă de încredere și o licență Autodata validă.

Din directorul `tools/autodata-installer`:

```powershell
python prepare_payload.py --source "D:\Autodata_3.45" --staging "D:\Autodata_stage" --dry-run
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -PayloadRoot "D:\Autodata_3.45" -OutputDir "D:\Autodata_Setup"
```

Dacă toate cele 105 fișiere există și au dimensiunile inventariate,
rezultatul este `Autodata_3_45_Licensed_Setup.exe`. Acest EXE **doar
copiază fișierele aplicației și creează scurtătura**. Nu instalează automat
drivere Sentinel, nu importă registrul și nu activează licența: acești
pași necesită instrucțiunile oficiale verificate și metode legitime.
Este posibil ca aplicația să nu pornească doar din copierea fișierelor.

`INVENTAR.txt` și dimensiunile sale sunt dovezi de consistență, **nu**
dovezi că fișierele sunt sigure sau autentice. Verificați proveniența
și semnăturile executabilelor înainte de instalare.

## Ce NU face proiectul

Nu recompilăm codul-sursă proprietar Autodata: `ADBCD.exe` și DLL-urile
existente sunt binare, nu cod-sursă. Un installer EXE este o **împachetare**
a fișierelor, nu recompilarea programului.

Nu executăm sau includem keygen, `license.exe`, `AuDaS0*.exe`,
emulatoare, `dseo13b.exe`, scripturi de registry sau metode de
ocolire a licenței. O licență autentică trebuie activată prin metoda
permisă de furnizor. Nu publicăm binare proprietare sau chei private în
GitHub.

## Ce lipsește pentru rezultatul final

1. O copie legitimă, accesibilă, verificată a fișierelor Autodata,
   inclusiv DLL-urile din ZIP-ul 16, fără executabile suspecte.
2. Instrucțiunile autentice de instalare/licențiere și identificarea
   dependențelor, accesibile fără ocolirea protecției Google.
3. Test de instalare într-o mașină Windows izolată și confirmarea
   funcționării cu o licență validă.

Până la îndeplinirea acestor condiții, nu trebuie prezentat niciun EXE
drept instalator final Autodata 3.45.
