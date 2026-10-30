# Original Autodata — preflight reproducibil, 30 octombrie 2026

Aceasta este o verificare statică, fără extragerea sau executarea codului original și fără modificarea licențierii. Scriptul **original** publicat este `original_archive_preflight.py`; teste exclusiv sintetice în `test_original_archive_preflight.py`. Inventarul privat `INVENTAR.json`, arhivele și fișierele originale nu sunt publicate.

## Execuție efectivă pe cele 15 pachete furnizate

Comandă locală (director privat care conține manifestul și ZIP-urile):

```powershell
py -3 projects/atelierdata/original_archive_preflight.py --manifest "C:\AutodataPrivate\INVENTAR.json" --parts-dir "C:\AutodataPrivate" --output "C:\AutodataPrivate\preflight.json"
```

Cod de ieșire: **2** (arhivă incompletă), deși verificarea bazelor IDF a trecut. Este un rezultat intenționat, nu o excepție.

| Indicator | Rezultat |
| --- | --- |
| Fișiere în inventar | 139 |
| Pachete așteptate | 16 |
| Pachete disponibile | 15 |
| Fragmente în manifest | 163 |
| Fragmente verificate SHA256 | **124** |
| Fragmente indisponibile | **39**, toate în `autodata_part_0016.zip` |
| Fișiere IDF complete, cu toate fragmentele SHA256 corecte | **81 / 81** |
| Erori de hash în pachetele disponibile | **0** |
| Date IDF | **PASS** |
| Arhivă completă | **NU** |
| Original executat | **NU** |
| Licență / pornire Windows verificată | **NU** |

Fișierele IDF au fost verificate ca fișiere *complete* numai dacă fiecare fragment al aceluiași fișier a fost validat; testul sintetic pentru lipsa fragmentului final verifică explicit această regulă.

## Diagnostic PE și metadate din original

`ADBCD.exe` a fost citit din pachetul 0001 după validarea SHA256: `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`.

- PE32, arhitectură **x86** (`0x014c`), subsistem Windows GUI (2).
- DLL-uri în tabela directă de import: `ADVAPI32.dll`, `KERNEL32.dll`, `MSVCRT.dll`, `USER32.dll`.
- Executabilul conține literalul `SentinelKeyW.DLL`, dar nu în lista celor patru DLL-uri importate direct. Aceasta **nu demonstrează** o încărcare obligatorie; poate fi o referință de încărcare dinamică.
- `VERINFO.DAT` conține `ProductCode=CDA3.44`, `VersionNo=9.200`, `ExpiryDate=42004`; interpretarea câmpului de expirare nu este stabilită prin execuție.
- `COMMON/DC.DAT` conține textul `Autodata file date check`, ceea ce sugerează verificări de dată, fără a demonstra logica lor.
- `ENG/ERROR.TXT` conține mesaje de solicitare a CD/DVD-ului. Este posibil să existe și dependențe de media originală; nu a fost demonstrată condiția de declanșare.
- `ENG/RegMessage.htm` precizează explicit că produsul necesită înregistrare și cod emis de furnizor; `ENG/COPY.txt` rezervă drepturile asupra bazei comerciale.

## Blocaje reale și concluzie

1. `autodata_part_0016.zip` nu este accesibil prin Google Drive (HTTP 403, fișier marcat malware/spam); acolo apar `SentinelKeyW.DLL`, `RelLic.dll`, instalatoare, fișiere de registru și utilitare neoficiale. Nu se forțează accesul și nu se execută emulatorul.
2. Nu există dovada unei licențe originale valabile sau a unui kit autentic de instalare. Un patch al verificării de expirare ori emularea cheii nu este o reparație tehnică acceptabilă.
3. Fără mediul și licența autentice, nu se poate demonstra o instalare legală funcțională pe Windows, deși toate bazele IDF sunt intacte.

**Rezultat:** diagnosticarea integrității și a dependențelor statice este reproductibilă; repararea originalului este momentan **BLOCKED** de runtime/licență. Alternativa AtelierData continuă separat, fără import de date proprietare.

## Teste

```powershell
py -3 -m unittest discover -s projects/atelierdata -p "test_original_archive_preflight.py" -v
```

Sunt incluse 5 teste sintetice: PE32 import, ZIP complet, lipsa unui fragment dintr-un IDF împărțit, modificare de fragment și cale de manifest periculoasă. Nu folosesc executabile sau date originale.
