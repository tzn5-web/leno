# AtelierData — verificare integritate arhivă originală (30 octombrie 2026)

Audit static, fără executarea fișierelor originale și fără publicarea conținutului lor.

## Rezultate verificate direct

- Inventar sursă: `INVENTAR.json` din Google Drive, 139 fișiere în 16 pachete, 81 fișiere `.IDF`.
- Pachete ZIP disponibile și inspectate efectiv: `0001`–`0015` (15/15).
- Toate intrările ZIP disponibile corespund manifestului la nume și dimensiune.
- Integritate SHA256 verificată prin citire completă: **124 fragmente, 100 fișiere**.
- Fișiere `.IDF`: **81/81 verificate SHA256**, 0 erori, inclusiv toate fragmentele fișierelor mari.
- În 70 din cele 81 `.IDF`, toate cele trei ferestre de 64 KiB (început, mijloc, sfârșit) au entropia >= 7,95 biți/octet. Acest fapt nu probează criptare.
- Mediana entropiei pe fiecare fereastră: **7,9971** biți/octet.
- Pachetul `0016` rămâne inaccesibil: 39 de fișiere din inventar, **niciunul `.IDF`**. Conține componente auxiliare DLL/instalare/licențiere. Nu s-a încercat ocolirea restricției.
- Executabilul principal, prezent în pachetul 0001, are SHA256 **a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4**. Antetul PE confirmă **PE32 x86, subsistem GUI**, versiune țintă Windows 5.0. Nu a fost executat.
- Tabela de import PE arată importuri directe din `KERNEL32.dll`, `USER32.dll`, `ADVAPI32.dll`, `MSVCRT.dll`, dar apar și `LoadLibraryA` și `GetProcAddress`; astfel, DLL-urile încărcate dinamic nu sunt acoperite de tabela de import.

## Interpretare

**Integritatea datelor: PASS pentru toate cele 81 fișiere IDF.**
**Integritatea pachetului complet: PARTIAL** (0016 inaccesibil).
**Rularea originalului: NEVER TESTED.**
**Licență validă: NEVER VERIFIED.**
**Decodorul IDF: NOT PROVEN.**

Verificarea s-a făcut numai din cele 15 pachete autorizate, cu manifestul oferit de utilizator; nu s-au executat utilitare de licențiere, emulare, drivere sau binare originale. Conținutul original nu este publicat aici.

## Diagnostic static suplimentar al executabilului și al versiunii

Verificare directă, numai prin citire, a fișierelor aflate în pachetele 0001–0015:

- `ADCDA2/COMMON/VERINFO.DAT` conține `ProductCode=CDA3.44`, `VersionNo=9.200`, `ExpiryDate=42004`. **Există o diferență între numele arhivei („3.45”) și codul produsului declarat de metadate („CDA3.44”)**; asta nu demonstrează singur incompatibilitatea.
- Dacă `42004` este interpretat ca număr serial de dată Windows/OLE, corespunde zilei **31 decembrie 2014**. Interpretarea câmpului în aplicație nu a fost demonstrată prin analiză de cod; nu trebuie modificat pentru a evita controlul de valabilitate.
- `ADCDA2/ENG/RegMessage.htm` descrie înregistrarea cu cod emis de furnizor.
- `ADCDA2/ENG/TERMCOND.TXT` descrie licențe de tip abonament cu perioade limitate și permise electronice. Aceste informații explică de ce simpla prezență a tuturor bazelor nu garantează utilizarea aplicației.
- Prezența `LoadLibraryA` / `GetProcAddress` în PE sugerează că analiza importurilor statice nu este suficientă pentru o listă completă de DLL-uri runtime.
- Niciun patch de licențiere, emulator sau executabil din arhivă nu a fost rulat. Diagnosticarea compatibilității autentice necesită o copie/licență autorizată și, după verificări de securitate, un mediu Windows izolat.

**Prioritate de depanare:** confirmați proveniența/licența și componentele runtime autentice, comparați codul de versiune cu mediul Windows, apoi analizați erorile de pornire. Modificarea datelor `.IDF` intacte nu este justificată de constatările curente.

## Reconstrucție fizică integrală a bazei de date IDF

Au fost reconstruite efectiv, într-un director privat izolat, **toate cele 81 fișiere IDF** din fragmentele ZIP verificate. Dimensiunea totală rezultată: **2.231.509.692 octeți**, cu exact 81 fișiere prezente în ierarhia de directoare originală, fără erori de verificare. Reconstrucția nu conține componentele din pachetul 0016. Originalele reconstruite nu se distribuie.

Un script original de verificare/reasamblare a fost testat pe date sintetice (inclusiv refuzul unui hash greșit, al unei traversări de cale și al suprascrierii unui director existent), apoi rulat pe cele 15 pachete reale. Reasamblarea este exclusiv pentru date `.IDF`, fără pornirea executabilelor.

**Control statistic suplimentar:** 77 semnături distincte pe primii 4 octeți pentru cele 81 IDF; niciun antet inițial ZIP, GZIP sau zlib convențional dintre cele testate. Aceste observații nu certifică un format, o cheie sau un algoritm de decodare.

**Concluzie:** toate datele IDF disponibile în arhiva originală sunt recuperabile byte-for-byte, dar nu există încă un decodor funcțional. Nici funcționarea originalului nu este confirmată.

## Legătura verificată între executabil și componenta lipsă

Scanarea statică, efectuată pe originalul SHA256-verificat, a identificat secvența ASCII exactă `SentinelKeyW.DLL` la offsetul de fișier `0x10E5E71` în `ADBCD.exe`. Manifestul original plasează fișierul omonim `ADCDA2/SentinelKeyW.DLL` **exclusiv în pachetul 0016**, inaccesibil. De aceea avem un **candidat concret de dependență runtime lipsă**, însă apariția unui literal nu demonstrează că DLL-ul este încărcat pe fiecare cale de executare.

Pentru utilizarea legală a unei licențe autentice, furnizorul de tehnologii Sentinel pune la dispoziție o [pagină oficială cu drivere](https://cpl.thalesgroup.com/software-monetization/sentinel-drivers). Instalarea unui driver oficial nu garantează licențierea și compatibilitatea aplicației vechi. Nu folosiți utilitarele neoficiale de activare/emulare din arhivă și nu ocoliți blocările furnizorului de stocare.

**Stadiu de recuperare a datelor: PASS. Stadiu de funcționare al aplicației originale: BLOCKED, licență/runtime neconfirmate.**
