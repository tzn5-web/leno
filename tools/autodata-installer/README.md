# Autodata originală — instalator privat cu verificări de sursă și licență

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
- `verify_original_manifest.py`: verifică fiecare fragment SHA-256 al celor 105 fișiere ADCDA2 față de `INVENTAR.json` privat, fără să ruleze executabile.
- `build.ps1`: refuză compilarea fără `INVENTAR.json`, `-ReviewRecord` privat cu verificările reale de proveniență, licență, instrucțiuni, dependințe Sentinel și discrepanța 3.44/3.45, confirmarea dreptului de utilizare și scanarea Microsoft Defender fără detecții raportate. Nu execută fișierele aplicației.
- `release_gate.py`: verifică faptul că atestările obligatorii au fost înregistrate; un `true` declarat de utilizator nu este dovada independentă a licenței. Nu setați aceste valori fără verificări reale.
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
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -PayloadRoot "D:\Autodata_3.45" -Inventory "D:\INVENTAR.json" -ReviewRecord "D:\Private\autodata_review.json" -AuthorizedUseConfirmed -OutputDir "D:\Autodata_Setup"
```

Dacă toate cele 105 fișiere există, au dimensiunile și hashurile pe fragmente identice cu inventarul privat, iar Defender nu raportează detecții,
rezultatul este `Autodata_Original_Licensed_Setup.exe`. Acest EXE **doar
copiază fișierele aplicației și creează scurtătura**. Scanarea și verificarea SHA-256 nu dovedesc autenticitatea furnizorului sau validitatea licenței. Nu instalează automat
drivere Sentinel, nu importă registrul și nu activează licența: acești
pași necesită instrucțiunile oficiale verificate și metode legitime.
Este posibil ca aplicația să nu pornească doar din copierea fișierelor.

`INVENTAR.txt` și dimensiunile sale sunt dovezi de consistență, **nu**
dovezi că fișierele sunt sigure sau autentice. Verificați proveniența
și semnăturile executabilelor înainte de instalare.

## Dovezi suplimentare din fișierele accesibile

Documentele `ADCDA2/ENG/RegMessage.htm`, `TERMCOND.TXT`, `COPY.txt` și `COMMON/VERINFO.DAT` au fost citite inert din ZIP-ul 0004, cu SHA-256 confirmat în `INVENTAR.json`. Ele indică o procedură istorică de înregistrare prin cod furnizat de Autodata și o licență de abonament. `VERINFO.DAT` indică `ProductCode=CDA3.44`, astfel că denumirea arhivei „3.45” **nu confirmă versiunea internă**. Instrucțiunile de instalare din ZIP-ul 0016 rămân necitite. Detalii: `AUDIT.md`.

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

## Coordonare definitivă a proiectelor (31 octombrie 2026)

- **Proiectul canonic pentru instalarea programului original:** această ramură `autodata-installer-20261030`, director `tools/autodata-installer/`.
- **Analiză statică originală:** `autodata-colab-20261030`, notebookul și instrumentele IDF/REA/Ghidra. Șablonul `tools/autodata-oneclick/` din acea ramură este **arhivat logic** pentru referință, nu o a doua linie de construire. Nu îl mai dezvoltați ca instalator concurent.
- **Aplicație independentă:** `atelierdata-20261030`, explicit în afara scopului acestui instalator.
- **Versiune:** numele arhivei spune 3.45, dar `COMMON/VERINFO.DAT` raportează `ProductCode=CDA3.44` și `VersionNo=9.200`. Eticheta afișată de șablon nu certifică versiunea produsului. `AppVersion=0.1.0` descrie numai șablonul de împachetare.
- **Cale implicită:** șablonul principal propune `{autopf}\Autodata Original\ADCDA2`, iar șablonul concurent propunea `C:\ADCDA2`. **Niciuna dintre aceste căi nu a fost confirmată drept cerință a programului original.** Instalarea Windows rămâne nevalidată; calea trebuie aleasă pe baza instrucțiunilor legitime și a unui test izolat.
- **Stare:** fără instalator original complet construit/testat; 100 din 139 fișiere logice verificabile, 39 indisponibile din ZIP-ul 0016; cinci DLL-uri `ADCDA2` lipsă pentru construirea completă; activarea autentică și compatibilitatea Windows nevalidate.
- **Niciun bypass:** nu descărcați/reîmpachetați `autodata_part_0016.zip` prin ocolirea protecției Drive; nu folosiți keygen, dongle emulator sau patchuri de activare.

## Cum interpretăm testele

Un PASS al testelor automate cu fișiere sintetice verifică numai validatoarele, scriptul PowerShell și compilarea șablonului Inno Setup. Nu confirmă instalarea, pornirea, licența sau identitatea versiunii Autodata. Buildul privat necesită o sursă completă, autorizată și verificată separat.
