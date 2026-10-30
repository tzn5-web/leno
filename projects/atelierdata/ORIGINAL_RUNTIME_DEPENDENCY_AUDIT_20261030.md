# AtelierData — dependențe Windows ale executabilului original (30.10.2026)

Audit **executat efectiv** pe inventarul privat și pachetele 0001–0015, fără extragere, instalare sau executare a programelor originale. Reproductibil cu scriptul original `original_runtime_dependency_audit.py`, care citește doar PE-urile din rădăcina ADCDA2, verifică SHA256 la fiecare, analizează antetele și urmărește numai importurile PE directe. Testele sintetice sunt în `test_original_runtime_dependency_audit.py`.

## Rezultate verificate

| Componentă în rădăcina ADCDA2 | Integritate/PE | Arhitectură |
| --- | --- | --- |
| ADBCD.exe | SHA256 PASS, PE32 | x86 |
| ChilkatCert.dll | SHA256 PASS, PE32 | x86 |
| ChilkatCrypt2.dll | SHA256 PASS, PE32 | x86 |
| ChilkatUtil.dll | SHA256 PASS, PE32 | x86 |
| RelLic.dll | SHA256 PASS, PE32 | x86 |
| SentinelKeyW.DLL | Pachetul 0016 indisponibil | neverificată |
| cw3220mt.dll | Pachetul 0016 indisponibil | neverificată |
| gdiplus.dll | Pachetul 0016 indisponibil | neverificată |
| libeay32.dll | Pachetul 0016 indisponibil | neverificată |
| ssleay32.dll | Pachetul 0016 indisponibil | neverificată |

**Corecție importantă față de diagnosticul preliminar:** `RelLic.dll` se află în **pachetul 0015**, nu în 0016. A fost verificat SHA256 și este x86. Din cele 10 componente EXE/DLL din rădăcina ADCDA2, **5 au fost verificate, 5 rămân indisponibile**.

**ADBCD.exe importă direct numai** `ADVAPI32.dll`, `KERNEL32.dll`, `MSVCRT.dll` și `USER32.dll`, toate candidate de biblioteci Windows. Închiderea tranzitivă a importurilor directe are **zero dependențe externe nerezolvate**, dar aceasta **nu dovedește** că programul pornește. Executabilul conține numele literale `SentinelKeyW.DLL` și `gdiplus.dll`; nu apar ca importuri directe. Pot fi încărcate dinamic, dar această ipoteză nu este demonstrată. Windows poate furniza propriul `gdiplus.dll`, deci lipsa copiei locale nu implică automat eșec.

`ChilkatCert.dll`, `ChilkatCrypt2.dll`, `ChilkatUtil.dll` și `RelLic.dll` sunt PE32/x86, fără nepotrivire de arhitectură între cele cinci componente inspectate. Cele trei DLL Chilkat importă biblioteci Windows; `RelLic.dll` importă direct `MSVCRT.dll`. Faptul că sunt livrate în distribuție nu dovedește că sunt încărcate de original la pornire.

**Blocaj exact:** pachetul 0016 este marcat malware/spam de Google Drive și nu este accesat forțat. Nu există licență autentică verificată, installer original complet sau test de pornire într-un Windows izolat. Nu se poate afirma că originalul este funcțional sau că Sentinel este cauza exactă a eșecului. Nu se execută emulatoare/keygen și nu se modifică verificările de licență.

## Reproducere locală, numai pe copii autorizate

```powershell
py -3 projects/atelierdata/original_runtime_dependency_audit.py --manifest "C:\AutodataPrivate\INVENTAR.json" --parts-dir "C:\AutodataPrivate" --output "C:\AutodataPrivate\runtime_audit.json"
py -3 -m unittest discover -s projects/atelierdata -p "test_original_runtime_dependency_audit.py" -v
```

Datele private, DLL-urile și executabilul nu sunt publicate. Manifestul SHA256 dovedește concordanța cu arhiva furnizată, **nu** autenticitatea provenienței sau licența.
