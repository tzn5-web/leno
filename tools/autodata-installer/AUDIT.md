# Autodata 3.45 — audit de ambalare, 30.10.2026

## Dovezi disponibile

Am citit `INVENTAR.txt`, `listare_7z.txt` și `TRANSFER_FINALIZAT.txt`
din folderul Google Drive al utilizatorului. Fișierele sunt metadate
generate la extragerea arhivei, nu o dovadă a autenticității furnizorului.

| Element | Valoare observată |
|---|---:|
| Arhivă RAR originală | 2.284.074.345 octeți |
| SHA-256 RAR raportat | e82235c262ea401c2f4609b1480787dbe05a953a6cf57f767d5c3465353267da |
| Fișiere extrase | 139 |
| Octeți extrași | 2.323.704.957 |
| Fragmente ZIP | 163 |
| Pachete ZIP | 16 |
| Fișiere în `ADCDA2` | 105 |
| Octeți în `ADCDA2` | 2.278.001.505 |
| Fișiere `.IDF` | 81 |
| Fișiere `.exe` | 17 |
| Fișiere `.dll` | 9 |
| Fișiere `.reg` | 6 |

## Structura observată

- `ADCDA2/ADBCD.exe` (18.102.272 octeți) — executabilul principal
  aparent; rolul efectiv nu a fost confirmat prin rulare.
- `ADCDA2/COMMON`, `ADCDA2/ENG`, `ADCDA2/GRAPHICS` —
  date `.IDF`, XML, documentație și resurse.
- `ADCDA2/RelLic.dll`, `ADCDA2/SentinelKeyW.DLL` — componente
  care par legate de licențiere; comportamentul nu este verificat.
- `vcredist_x86.exe`, `vcredist_x64.exe`, `Sentinel Protection Installer
  7.6.1.exe`, `Sentinel Protection Installer 7.6.6.exe` — instalatoare
  auxiliare identificate după nume, nu verificate sau executate.
- `INSTALLATION INSTRUCTIONS.txt` (3.294 octeți) și
  `Autodata 3.45_Keygen/install instructions_3.45.txt` (2.725 octeți)
  — **conținutul nu a putut fi citit**.
- `Install-x32.cmd`, `Install-x64.cmd`, `RegSettings*.reg`,
  `RegSvr.bat` — pot modifica registrul/sistemul; nu au fost executate.
- `Keygen`, `Autodata 3.45_Keygen`, `Emulators`, `dseo13b.exe`
  — componente cu risc ridicat; nu vor fi incluse în instalator.

## Documente originale citite inert din ZIP-ul 0004

Am accesat `autodata_part_0004.zip` prin conectorul Google Drive, am citit **numai bytes**, fără a executa nimic, și am verificat SHA-256 al fiecărui document cu `INVENTAR.json`:

| Document | Octeți | SHA-256 inventar | Concluzie |
|---|---:|---|---|
| `ADCDA2/COMMON/VERINFO.DAT` | 79 | verificat: PASS | `ProductCode=CDA3.44`, `VersionNo=9.200`, `ExpiryDate=42004`; semnificația datei de expirare nu este stabilită |
| `ADCDA2/COMMON/distinfo.xml` | 14.255 | verificat: PASS | metadate de distribuție; antet datat 28.10.2013 |
| `ADCDA2/ENG/RegMessage.htm` | 1.119 | verificat: PASS | înregistrare istorică prin cod unic transmis de Autodata, pe baza formularului și seriei |
| `ADCDA2/ENG/TERMCOND.TXT` | 13.175 | verificat: PASS | permis electronic și cod de înregistrare emis de furnizor/agent autorizat; abonament cu limitări și expirare |
| `ADCDA2/ENG/COPY.txt` | 1.398 | verificat: PASS | drepturi de autor și drepturi asupra bazei de date; copierea și distribuirea sunt restricționate |
| `ADCDA2/ENG/support.htm` | 5.208 | verificat: PASS | informații istorice de contact; disponibilitatea actuală nu este confirmată |

Acestea sunt fișiere din **arhiva utilizatorului**, nu documente autentificate independent de furnizor. În particular, **versiunea „3.45” nu este confirmată de metadatele interne**, care indică `CDA3.44`. O instalare cu succes nu echivalează cu activarea sau dreptul de utilizare.

`INSTALLATION INSTRUCTIONS.txt`, `Autodata 3.45_Keygen/install instructions_3.45.txt`, `License manual.pdf` și documentul PDF rusesc pentru Windows XP x32 apar doar în ZIP-ul 0016; **nu au fost citite** și nu putem deduce pașii lor reali.

## Blocaj specific

Google Drive a respins descărcarea `autodata_part_0016.zip` cu
HTTP 403, `cannotDownloadAbusiveFile`, marcând fișierul ca posibil
malware sau spam. Pachetul 16 conține 39 de fișiere, inclusiv cinci
DLL-uri din `ADCDA2`:
`SentinelKeyW.DLL`, `cw3220mt.dll`, `gdiplus.dll`,
`libeay32.dll`, `ssleay32.dll`.

Acest blocaj împiedică analiza instrucțiunilor și asamblarea integrală
a unui installer din materialele disponibile. Nu încercăm descărcarea
prin alte metode pentru a ocoli filtrul.

## Rezultat realizat

Proiectul `tools/autodata-installer` din ramura
`autodata-installer-20261030` conține un constructor de instalator
Inno Setup, un verificator SHA-256 bazat pe inventarul privat, un script de validare/copie, lista explicită de 105 fișiere
și teste automate cu fișiere sintetice.

Nu există încă un EXE final care să instaleze și să activeze Autodata.
Construirea unui EXE de instalare din fișierele originale este distinctă
de recompilarea aplicației proprietare, al cărei cod-sursă lipsește.
Activarea prin licență autentică rămâne obligatorie.

## Continuare: delimitare instalator original vs analiză .IDF (31 octombrie 2026)

**Proiect canonic:** `autodata-installer-20261030/tools/autodata-installer/`. Celălalt șablon `autodata-colab-20261030/tools/autodata-oneclick/` este păstrat numai istoric; proiectul `atelierdata-20261030` rămâne separat și **nu este Autodata originală**.

**Îmbunătățiri de validare:** constructorul `build.ps1` cere un `-ReviewRecord` privat verificat de `release_gate.py`, care impune atestarea examinării autenticității sursei, a licenței emise legal, a instrucțiunilor originale, a dependențelor Sentinel, a diferenței CDA3.44/3.45 și distribuirea privată. În lipsa oricărei atestări, scriptul refuză construirea. Testele noi sunt sintetice; rezultatele ultimei rulari CI nu sunt încă confirmate.

**Identitatea versiunii:** fișierul `COMMON/VERINFO.DAT`, citit inert din `autodata_part_0004.zip`, conține în cei 79 de octeți:

```ini
[PRODUCT INFORMATION]
ProductCode=CDA3.44
VersionNo=9.200
ExpiryDate=42004
```

Numele arhivei este `Autodata__3.45.rar`, dar **nu se poate stabili doar din metadatele disponibile dacă '3.45' este aceeași ediție, o etichetă a pachetului sau un kit amestecat**. Eticheta pachetului Inno este acum **Autodata Original (licensed files; edition unverified)**, iar `AppVersion=0.1.0` descrie exclusiv șablonul, nu produsul Autodata.

**Inspecție statică suplimentară `ADBCD.exe`**, citit exclusiv din ZIP 0001, SHA256 deja verificat față de manifest:

- Există exact o apariție ASCII a `SentinelKeyW.DLL` la offsetul de fișier **17.718.897**, urmată de `gdiplus.dll` la **17.718.931**, ambele în secțiunea PE numerotată `0000013`.
- Însă `SentinelKeyW.DLL` și `gdiplus.dll` **nu apar între cele patru DLL-uri importate static** în tabela PE clasică; relația funcțională poate fi indirectă și nu este încă trasată.
- Referințele ASCII `cw3220mt.dll`, `libeay32.dll`, `ssleay32.dll`, `RelLic.dll` și `C:\\ADCDA2` **nu au fost găsite** în scanarea completă a bytes-ilor executabilului. Absența unui nume literal nu dovedește independența funcțională.
- Lipsesc în continuare cinci DLL-uri din pachetul 0016 accesibil doar ca metadate. Nu se poate compila un original complet verificat din pachetele normale 0001–0015.

**Calea de instalare:** exemplul `C:\\ADCDA2` și alegerea implicită a șablonului sunt ipoteze nevalidate, nu instrucțiuni oficiale. Nu am executat aplicația, driverele Sentinel, scripturile de registry sau vreun activator. Nu am ocolit blocările Google Drive și nu am încă un test de lansare Windows.

**Criterii de finalizare rămase:** (1) surse complete, autentice și licențiate, accesibile printr-o cale autorizată; (2) toate SHA256 pentru cele 105 fișiere originale; (3) documentație legitimă privind calea instalării, dependențele și activarea; (4) test Windows izolat de instalare, lansare, acces date și dezinstalare; (5) compilare și revizuire a pachetului final. Un PASS cu fixture sintetic nu îndeplinește aceste criterii.
