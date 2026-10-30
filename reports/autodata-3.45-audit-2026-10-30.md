# Autodata 3.45 — audit pe conținut real (31 octombrie 2026)

> Obiect: **arhiva originală Autodata 3.45**, nu dezvoltarea unei alte aplicații. Fără Azure. Fișierele executable și scripturile din arhivă nu au fost executate.

## Verificare efectivă Google Drive și ZIP

Sursă: https://drive.google.com/drive/folders/1XqpDaYI5zkdUXY85wLSvpsklatT0P0Bd

- Google Drive listează toate cele **16** ZIP-uri. Acest fapt nu dovedește, singur, integritatea lor.
- Au fost descărcate pe calea normală, fără niciun bypass, **ZIP-urile 0001–0015** și examinate numai static, cu Python `zipfile`.
- Am calculat independent SHA-256 pentru **124/124 intrări** accesibile, iar toate cele 124 SHA-256 și dimensiuni corespund manifestului `INVENTAR.json`. **PASS pentru toate intrările accesibile**: **2.271.754.801 octeți** verificați.
- Repartiția intrărilor verificate pe pachete: `0001:22; 0002:7; 0003:2; 0004:55; 0005:4; 0006:7; 0007:7; 0008:2; 0009:2; 0010:3; 0011:2; 0012:2; 0013:2; 0014:2; 0015:5`.
- Manifestul enumeră **139 fișiere logice**, **163 bucăți/intrări ZIP**, **2.323.704.957 octeți** pentru toate cele 16 ZIP-uri. Nu sunt duplicate de căi/chunk și nici nepotriviri de dimensiuni declarate.
- Toate cele **81 fișiere .IDF** (în total **2.231.509.692 octeți**, organizate în **105 bucăți ZIP**) sunt integral cuprinse în pachetele **0001–0015**, iar toate bucățile lor au trecut SHA-256. **0 fișiere .IDF în ZIP 0016**.

### Partea 0016 și securitatea

Raportul Drive anterior `Autodata_OneClick_Audit/SOURCE_ACCESS_STATUS.json` consemnează blocarea părții `autodata_part_0016.zip` prin HTTP 403 `cannotDownloadAbusiveFile`. Partea 0016 conține executabile/DLL-uri/instalatoare/keygen și documente auxiliare; **nu conține .IDF**. Nu am reîncercat, executat sau ocolit blocarea ei.

- Integritatea celor **39 de intrări** din ZIP 0016 rămâne **NEVERIFICATĂ**.
- SHA-256 al arhivei RAR originale `e82235c262ea401c2f4609b1480787dbe05a953a6cf57f767d5c3465353267da` este doar raportat de manifest, nu recalculat din RAR-ul original.
- Niciun program original, activator, keygen, DLL, CMD, BAT sau VBS nu a fost executat.

## Inspecție statică a conținutului

XML analizate prin `defusedxml`:

| Fișier | Rădăcină XML | Rezultat |
|---|---|---|
| `COMMON/distinfo.xml` | `Distributors` | 53 de noduri `Distributor` |
| `ENG/country.xml` | `Countries` | 24 de noduri `country` |
| `ENG/string.xml` | `AllText` | 2.167 noduri `Text` |

Analiza primilor 4096 octeți din fiecare `.IDF` a identificat o mediană a entropiei de aproximativ **7,954 biți/octet**; această distribuție este **compatibilă cu date comprimate sau criptate**, dar nu stabilește algoritmul ori formatul. Nu există încă un parser demonstrat. Există prefixe comune pentru anumite perechi (`SGINT.IDF`/`SGOPS.IDF`, 38 octeți; `MIDLINKS.IDF`/`RTINCJOB.IDF`, 20 octeți; `TDGRAPH.IDF`/`SD.IDF`, 20 octeți). Acestea sunt **indicii pentru cercetare**, nu dovezi de decodare.

## Starea reală

| Criteriu | Stare |
|---|---|
| 16/16 ZIP prezente în Drive | PASS (metadate) |
| 15 ZIP-uri accesibile, hashuri reale | **124/124 PASS** |
| Toate cele 81 .IDF — integritate hash | **PASS** |
| XML static | **3/3 parser PASS** |
| ZIP 0016 | BLOCKED (provider), **39 intrări neverificate** |
| RAR original SHA-256 | NEVERIFICAT |
| Format/cheie/decodare .IDF | NEDEMONSTRAT |
| Funcționarea aplicației Autodata originale | NEDEMONSTRAT |
| Notebook Colab | Publicat; nu mai este necesar pentru a recalcula cele 124 hashuri deja verificate direct |
| GitHub Actions test sintetic | Configurat; fără rezultat PASS observat |

## Direcția exactă

**Nu se începe o aplicație nouă.** Următorul pas tehnic este să cercetăm **structura reală a IDF** folosind fișierele deja verificate, fără a executa aplicațiile sau activatoarele originale. Priorități: antete și segmente cu prefixe comune, detectarea tipurilor de containere cunoscute, corelarea fișierelor COMMON/ENG/GRAPHICS, documentarea strictă a ipotezelor, teste repetabile. Dacă formatul rămâne criptat/proprietar, se raportează explicit această limită; nu se pretinde funcționare 1:1 fără probe.

Notebook: https://github.com/tzn5-web/leno/blob/autodata-colab-20261030/notebooks/autodata_3_45_static_audit.ipynb
