# Autodata IDF: reproducible static evidence (2026-10-30)

This investigation uses the **original private** `ADBCD.exe`, `autodata_part_0001.zip`, `autodata_part_0004.zip` and private `INVENTAR.json`. Original bytes remain outside this public repository. The program was **never executed**. The checked inputs do **not** include blocked `part_0016`.

The published `idf_static_evidence.py` script ran locally with explicit manifest SHA256 verification and a 64 MiB per-entry bound. Result: **57 distinct, complete .IDF files** from the two available ZIP packages passed SHA256 verification against their exact inventory ZIP entries. The full inventory lists **81 .IDF files**; 24 were not inspected in this run. Do not interpret 57 as all 139 files of the archive.

## Findings, not format claims

- For 49/57 IDF samples, **each** of the three 64 KiB windows (start/middle/end) has Shannon entropy at least 7.95 bits/byte. This is consistent with compressed or encrypted data and does **not** establish either.
- Several files have lower/variable entropy, including `FAS.IDF` (approx. 7.35–7.53), `TECDOC.IDF` (approx. 7.44–8.00), `SGINT.IDF` (approx. 7.72 at start, near 8 later), and `MIDTDoc.IDF` (approx. 7.72–7.99). Thus **not all IDF files have uniform statistical behavior**.
- `CONST.IDF` is only 10 bytes. Its entropy is not meaningful evidence of encryption.
- SHA256 of the inspected original `ADBCD.exe` is `a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4` (verified). A bounded literal scan found **zero exact ASCII/UTF-16LE occurrences** of `.IDF`, `MODELS.IDF`, `CONST.IDF`, `CSS.IDF` or `DTC.IDF` in that executable. Dynamic name construction, resources, other modules and indirect loaders remain possible.
- The executable contains `inflate 1.2.3` (ASCII file offset `0x6bedf1`) and `TFRMAUTODATABASE` (UTF-16LE file offset `0xa832a8`). These are leads for static xref inspection, **not** proof that IDF uses zlib, or that a Delphi form implements the loader.

## Reproducibility and status

- Tool: `projects/atelierdata/idf_static_evidence.py`, including a synthetic-data self-test that deliberately rejects a wrong SHA256.
- Private execution: 57 verified samples, 0 skipped for the configured size bound, output retained as private report `AtelierData_IDF_Static_Evidence_ALL_Available_20261030.json` in the conversation environment, **not uploaded to GitHub**.
- Ghidra 12.1.4: the **Java** script `tools/ghidra/AtelierData_IDF_Xrefs.java` was executed headlessly on the original SHA256-verified `ADBCD.exe` with `-noanalysis`, returning PASS and a private JSON report. The program was identified as x86:LE:32:default. `inflate 1.2.3` was located at memory address `00ac01f1` and `TFRMAUTODATABASE` at `00f170a8`. No existing xrefs were recorded in this no-analysis run. A full autoanalysis attempt timed out with decompiler/resource warnings, so a working loader call chain is **not** established.
- REA 6.8.0 `inspect-pe-resources` was also **actually executed** on the same SHA256-verified original PE. It returned complete resource-directory coverage: **1,299 directory entries and 644 resources**, including 190 RT_RCDATA (type 10), 337 RT_BITMAP (type 2), 65 RT_STRING (type 6), and 6 named `UNICODEDATA` entries. Named form resources include `TAUTODATAFORM`, `TFRMAUTODATABASE` and `TTECHDATAFORM`, consistent with Delphi/VCL form metadata. This identifies UI/resource structure, **not** the IDF loader or its encoding. The detailed resource inventory remains private. REA does not currently decode the IDF format.

**Status:** IDF decoder not proven. No vehicle data, repair procedure, wiring diagram, or proprietary content has been extracted. Next investigation should focus on the static loader/xref chain with private Ghidra evidence and an authorized export or format specification. Never bypass license checks or publish original files.

## Audit suplimentar REA/Ghidra — resurse PE și pointeri (2026-10-30)

A fost **rulat din nou REA 6.8.0** pe executabilul original privat, verificat SHA256
`a505bbc4f8678713f352faa8fc70337d9edbe5e0ebd23ba305ca3bccd0f6fce4`.
`inspect-pe-resources --json` a raportat `coverage=complete`, 1.299 intrări de director și
644 resurse. Scriptul original `rea_resource_audit.py` a reverificat independent
**fiecare dintre cele 644 hashuri SHA256 ale payloadurilor** și limitele offset/dimensiune,
raportând `REA_RESOURCE_AUDIT=PASS resource_count=644`. Rapoartele individuale, binarul
și numele/offseturile private rămân în spațiul privat; aici sunt doar statistici agregate.

| Tip resursă | Număr | Semnături obișnuite găsite | Entropie mediană, prima fereastră 64 KiB (resurse >=1 KiB) |
| --- | ---: | ---: | ---: |
| RT_RCDATA (10) | 190 | 0 antete DFM binare `TPF0`, 0 DFM text `object`/`inherited` | 7,9408 biți/octet |
| RT_BITMAP (2) | 337 | 0 antete DIB uzuale (12/40/52/56/108/124) | 7,9756 biți/octet |
| RT_STRING (6) | 65 | Nu s-a pretins decodarea șirurilor | 7,8494 biți/octet |
| RT_ICON (3) | 9 | Nu a fost încercată decodarea imaginii | 6,2439 biți/octet |
| UNICODEDATA | 6 | Nu a fost încercată decodarea | 7,9940 biți/octet |

Entropia mediană exclude resursele sub 1 KiB pentru a limita efectele eșantioanelor mici.
48 dintre cele 190 RT_RCDATA și 150 dintre cele 337 RT_BITMAP au dimensiune de cel puțin
4 KiB și entropia primei ferestre >= 7,9. Aceste rezultate sugerează că **payloadurile
resurselor nu sunt stocate în formele convenționale așteptate**, însă nu dovedesc criptare,
compresie, mecanismul de transformare, formatul IDF sau accesul la date.

A fost rulat efectiv **Ghidra 12.1.4** headless cu `-noanalysis` și scriptul
`tools/ghidra/AtelierData_IDF_PointerCandidates.java` pe același original verificat.
Rezultatul privat a regăsit `inflate 1.2.3` la `00ac01f1` și `TFRMAUTODATABASE`
la `00f170a8`, dar **zero apariții LE32 ale adreselor acestora în blocurile de memorie
scanate**. Căutarea literală `.IDF` a rămas fără rezultat. Acesta este un test static
limitat de pointeri, nu o analiză completă a fluxului de control; adresele pot fi
calculate dinamic și nu se poate exclude un încărcător indirect.

### Reproducere numai pe copii private autorizate

~~~bash
node rea-agents/scripts/rea.mjs inspect-pe-resources ORIGINAL.exe --json > rea-private.json
python projects/atelierdata/rea_resource_audit.py \
  --pe ORIGINAL.exe --rea-json rea-private.json \
  --expected-sha256 HASH_VERIFICAT \
  --public-output sumar-fara-date-originale.json \
  --private-output raport-privat.json
python projects/atelierdata/rea_resource_audit.py --self-test
~~~

Scriptul verifică exact hashul executabilului și fiecare digest din raportul REA;
respinge rapoartele incomplete, payloadurile modificate și offseturile invalide.
Autotestul folosește exclusiv PE și resurse **sintetice**. Analiza privată a fost
făcută local, fără executarea binarului original, fără ocolirea licenței, fără
folosirea arhivei `part_0016` și fără publicarea fișierelor proprietare.

**Stadiu neschimbat:** decodorul `.IDF` și lanțul de încărcare a datelor nu sunt
identificate. Următoarea direcție de investigare este localizarea statică a
rutinei care citește fișierele, cu dovezi de referințe și flux de date, nu
presupunerea unui algoritm pe baza entropiei.
