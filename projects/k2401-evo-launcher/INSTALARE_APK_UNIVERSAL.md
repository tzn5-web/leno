# K2401 EVO v119 — un singur APK pentru instalare sau actualizare

**Fișierul recomandat:** `K2401-EVO-UNIVERSAL-v119.apk`.

La deschiderea acestui fișier pe navigația Android 10, **sistemul Android**, nu aplicația, stabilește automat dacă este:
- **Actualizare:** există deja `ro.evolauncher.k2401`, instalat cu același certificat, cu o versiune mai veche. Android înlocuiește codul și păstrează configurația, aplicațiile alese și preferințele sale.
- **Instalare de la zero:** aplicația nu este instalată sau a fost dezinstalată. Android instalează tot pachetul, inclusiv resursele și cele 21 de teme originale, fără fișiere ZIP suplimentare. Se pornește cu setările implicite.

## Limite reale ale instalării Android
- **Același package ID + aceeași semnătură digitală** sunt necesare pentru actualizare fără dezinstalare. Acestea sunt stabilite la compilare, nu detectate și schimbate din interiorul APK.
- `ro.evolauncher.k2401.ultra` („EVO Ultra Test”) este o aplicație **separată**. Un APK destinat `ro.evolauncher.k2401` nu o poate actualiza: au identificatori diferiți.
- O versiune instalată anterior cu **alt certificat** (de exemplu debug sau APK modificat/resemnat) nu poate fi suprascrisă de APK-ul oficial. Android va afișa „App not installed” / `INSTALL_FAILED_UPDATE_INCOMPATIBLE`; nu se poate evita legal și sigur prin codul launcherului. Pentru a păstra datele, folosește varianta separată sau revino la certificatul corect; dezinstalarea variantei vechi îi șterge datele.
- Dezinstalarea șterge setările private ale aplicației; reinstalarea oferă toate funcțiile și temele incluse, dar **nu restabilește automat preferințele** sau sloturile salvate. Pentru recuperarea setărilor este necesar un backup făcut înainte.
- Dacă doar ștergi **fișierul APK descărcat**, dar aplicația rămâne instalată, nu se întâmplă nimic cu aplicația instalată.
- Android arată ecranul său de confirmare pentru instalare/actualizare. Un APK obișnuit nu poate face instalare silențioasă fără privilegii Device Owner/de sistem.

## Contract CI
GitHub Actions verifică același APK semnat în două scenarii pe un emulator Android 10: upgrade de la release-ul v118 (`versionCode 123`) la v119 (`versionCode 124`) cu păstrarea datelor și reinstalare completă după dezinstalare. Se folosește în continuare certificatul persistent din Azure Key Vault, fără mașină virtuală Azure.

Nu dezinstala aplicația funcțională doar pentru a instala o actualizare. Folosește APK-ul **UNIVERSAL** și confirmă operația „Actualizează” oferită de Android.
