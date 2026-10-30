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
