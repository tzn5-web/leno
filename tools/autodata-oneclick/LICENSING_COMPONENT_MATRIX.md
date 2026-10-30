# Autodata 3.45 — licențiere, componente și pași de integrare (audit static)

**Status:** analiza inventarului original, NU analiza executabilelor de activare. Nu a fost executat vreun utilitar și nu a fost validată o activare.

## Ce există confirmat în arhiva utilizatorului

Sursa: `INVENTAR.json` original (139 fișiere, 163 fragmente), lista `7z` și conținutul `ADCDA2/ENG/RegMessage.htm`, `TERMCOND.TXT` și `COMMON/VERINFO.DAT` citit din pachetul 0004.

| Element | Fișiere identificate | Ce se poate concluziona | Acțiune în instalator |
| --- | --- | --- | --- |
| Aplicație | `ADCDA2/ADBCD.exe`, baze `.IDF`, DLL | Aplicație Windows PE32 / x86 | Copiere după verificarea SHA256 |
| DLL de bază | `ADCDA2/SentinelKeyW.DLL`, `cw3220mt.dll`, `gdiplus.dll`, `libeay32.dll`, `ssleay32.dll` | Sunt în `autodata_part_0016.zip` și nu au fost încă recuperate/verificate; pot fi necesare la rulare | Nu substitui DLL-uri necunoscute; livrare doar dintr-o sursă verificată și permisă |
| Driver de protecție | `Sentinel Protection Installer 7.6.1.exe`, `7.6.6.exe`, `SentinelDriver/SentinelProtectionInstaller7.6.6.exe` | Există executabile cu nume de instalatoare Sentinel; fără test, nu e confirmat că sunt autentice, semnate sau necesare | Nu rula automat înainte de verificarea semnăturii și compatibilității Windows |
| Configurare Windows | `RegSettings.reg`, `RegSettings64.reg`, `RegSettingsWin7.reg`, `RegSettings/RegSettings_x86.reg`, `RegSettings/RegSettings_x64.reg`, `RegSvr.bat` | Fișiere prezente, conținut neinspectat; nu știm ce chei seteză sau ce DLL înregistrează | Citește inert; importă doar setări justificate și sigure |
| Scripturi vechi | `Install-x32.cmd`, `Install-x64.cmd`, `VBScript/shortcut.vbs` | Numele sugerează instalare pe arhitecturi distincte, dar textul nu a fost încă citit | Analiză statică întâi, nu rulare automată |
| Runtime | `vcredist_x86.exe`, `vcredist_x64.exe` | Redistributable-uri incluse; nu este demonstrată versiunea necesară | Verifică semnătura și dependențele pentru PE32; instalare doar dacă e justificată |
| Licență / identitate | `GetUid-x32/getuid.exe`, `GetUid-x64/GetUid64.exe` | Numele sugerează preluarea unei identități locale; nu constituie o licență | Nu le executa până nu sunt verificate originea, comportamentul și necesitatea |
| Activare neoficială | `Keygen/keygen.cmd`, `Keygen/license.exe`, `Autodata 3.45_Keygen/License.exe`, `Emulators/Emulator_x86.exe`, `Emulator_x64.exe`, `win.i386-reg/AuDaS032.exe`, `win.amd64-reg/AuDaS064.exe`, `dseo13b.exe` | Numirea sugerează generatoare/emulatoare/semnare neoficială; existența nu dovedește drepturi de licență | Nu le integra sau executa; nu emula un dongle și nu modifica verificările aplicației |
| Documente utilizator | `INSTALLATION INSTRUCTIONS.txt`, `Autodata 3.45_Keygen/install instructions_3.45.txt`, `Autodata 3.45_Keygen/License manual.pdf`, PDF rusă | Există în pachetul 0016 blocat la descărcare | Nu inventa pașii până nu pot fi citite dintr-o sursă permisă |

**Constatare suplimentară:** manifestul nu evidențiază un fișier propriu-zis emis de furnizor cu extensie `.lic` sau un cod de înregistrare identificabil ca valid. `License.exe` nu trebuie confundat cu o licență. O verificare independentă a dreptului de utilizare rămâne necesară.

## Ce afirmă documentația de la producător, efectiv citită

`RegMessage.htm`: programul solicită un cod unic de înregistrare, emis de Autodata după trimiterea formularului. `TERMCOND.TXT`: accesul era controlat de un permis electronic cu coduri emise de Autodata sau un agent autorizat, pe bază de abonament; documentul mai precizează că suportul tip CD poate expira. `COPY.txt`: drepturile asupra bazelor de date și restricțiile de distribuție aparțin deținătorului.

`VERINFO.DAT` identifică `ProductCode=CDA3.44`, nu 3.45; versiunea reală a pachetului trebuie confirmată înainte de etichetarea finală.

## Integrare ONE-EXE (fără presupuneri)

1. Verifică întregul `ADCDA2` față de manifestul SHA256, inclusiv DLL-urile lipsă din ZIP 0016.
2. Analizează instrucțiunile TXT/PDF, registrele și CMD-urile doar ca date; documentează ordine, prerechizite și versiunile instalatoarelor.
3. Verifică semnăturile, versiunea și compatibilitatea DLL/driverelor; exclude orice element suspect sau neautorizat.
4. Construiește Inno Setup cu copiere, verificarea existenței componentelor, instalarea doar a dependențelor legitime necesare, scurtături și dezinstalare.
5. Pentru activare folosește doar fluxul/cheia autorizată de producător. Un instalator poate simplifica instalarea, nu genera drepturi de utilizare.
6. Testează pe Windows izolat cu captură de jurnal de instalare, deschidere, activare autentică și dezinstalare; marchează PASS doar dacă aplicația chiar pornește.

## Blocaj verificat

Google Drive a răspuns `403 cannotDownloadAbusiveFile` la descărcarea pachetului 0016. Documentele și 5 DLL-uri de bază sunt în acel pachet. Nu există o citire validată a conținutului fișierelor de instalare/licențiere. Nu trebuie folosite metode de ocolire a filtrului sau declarată o activare reușită.

## Instrumentul REA

`morluto/rea` oferă `inspect-desktop-application`, `inspect-pe-imports` și alte instrumente pentru analiză statică. Acestea ajută la identificarea structurii și dependențelor aplicației, nu oferă codul-sursă de recompilare al programului proprietar și nu constituie licență.
