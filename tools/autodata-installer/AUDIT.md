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
Inno Setup, un script de validare/copie, lista explicită de 105 fișiere
și teste automate cu fișiere sintetice.

Nu există încă un EXE final care să instaleze și să activeze Autodata.
Construirea unui EXE de instalare din fișierele originale este distinctă
de recompilarea aplicației proprietare, al cărei cod-sursă lipsește.
Activarea prin licență autentică rămâne obligatorie.
