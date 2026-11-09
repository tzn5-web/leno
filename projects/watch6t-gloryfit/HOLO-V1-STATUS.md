# Watch6T HOLO – prototip tehnic V1

**Stare:** generat și verificat local ca pachet ZIP de cadran; **nu** a fost sincronizat sau testat pe iHunt Watch6T-D123. Nu este un firmware și NU trebuie folosit la „Upgrade de firmware”.

Sursă: designul holografic #3 ales în conversație + șablonul original `dial_1_circle_240x240` extras din APK-ul GloryFit instalat.

## Fișiere

- `HOLO_preview_dynamic_SIMULATION.png` — compoziție simulată cu valori demonstrative 14:26, 07.345 de pași și nivel de baterie. Nu este captură de pe ceas.
- `HOLO_base_240.png` — fundalul adaptat, cu numerele statice eliminate și machete neutre pentru senzorii fără mapare confirmată.
- `Watch6T_HOLO_dynamic_DIALROOT_UNTESTED.zip` — pachet candidat cu rădăcină `dial_1_circle_240x240/`, similar structurii ZIP descărcate din GloryFit.
- `Watch6T_HOLO_dynamic_STOCK_TEMPLATE_UNTESTED.zip` — aceeași structură de cadran, păstrând ruta originală din APK `assets/DialCustom/dial_1_circle_240x240/`.
- `validation.json` — inventar și hashuri SHA256 pentru verificare.
- `build_holo.py` — generator care necesită Python 3 și Pillow. NU efectuează transfer ADB/BLE și NU scrie pe ceas.

## Ce este confirmat

* 248 fișiere, aceleași nume de imagini / aceleași dimensiuni PNG precum șablonul original.
* 23 categorii de elemente, inclusiv oră, minute, dată, zi a săptămânii, număr de pași, progres pași, pictogramă de baterie cu 5 stări.
* Toate ZIP-urile se deschid și trec verificarea CRC internă ZIP; pozițiile configurate rămân în ecranul 240x240.

## Ce NU este confirmat

* Dacă ceasul permite instalarea unui ZIP modificat prin GloryFit sau îl respinge la verificare.
* Dacă firma folosește toate elementele din șablon pentru firmware-ul `RB235DCEV004137`.
* Legătura dinamică a pulsului, SpO₂ și vremii. Ele NU sunt prezentate ca măsurători live în HOLO V1.
* Un protocol de încărcare BLE sau o procedură de recuperare testată.

**Nu folosi fișierele candidate în meniul „Upgrade de firmware” și nu rescrie `.bin` în ceas.** Pentru următoarea etapă, trebuie verificat codul de transfer sau sincronizarea unui ZIP modificat pe o copie recuperabilă și/sau pe un aparat de test.