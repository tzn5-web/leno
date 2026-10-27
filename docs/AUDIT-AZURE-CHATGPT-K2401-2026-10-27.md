# Audit Azure / ChatGPT / K2401 EVO — 27 octombrie 2026

## Rezultat

Audit parțial executabil, cu blocaje externe confirmate. Nu reprezintă un release final APK sau dovada că toate operațiunile Azure funcționează.

- Abonament activ: 0ac7a514-32b3-47bf-bf89-e17906b1cc86.
- Tenant: 779623db-ec2e-495b-9828-85d42baa77ee.
- Compute: inventarierea VM și citirea instance view funcționează.
- VM existent: int34d2-lab, rg-phaser360-driverlab, Sweden Central, Windows, Standard_D4s_v5, provisioning Succeeded.
- Starea verificată înainte și după încercarea de pornire: deallocated.
- Nu a fost creată o VM și nu a fost pornită VM-ul existent în acest audit.
- Bugetul istoric este 200 USD total; soldul curent nu a fost verificat.

## Blocaj 1: confirmarea interactivă a conectorului

Comanda Compute de start a fost respinsă cu mesajul:

> This tool may perform destructive operations and requires user consent, but the client does not support elicitation. Operation rejected for security.

Aceasta este o respingere a conectorului înaintea executării operațiunii Azure, nu o eroare Azure de cotă, regiune, imagine sau VM.

Setarea aplicației Azure server a fost inspectată: app-specific Allow all actions, global Allow low-risk actions. Prin urmare setarea aplicației este deja permisivă și nu înlătură cerința internă de elicitation a serverului.

Nu există în instrumentele disponibile o comandă care să adauge suport de elicitation clientului sau să modifice implementarea serverului. Nu s-a folosit GitHub Actions, CLI, ARM REST sau un alt canal pentru a ocoli refuzul pornirii.

Remediere necesară în integrare: client compatibil cu elicitation și procesarea confirmării cerute de server, ori corectarea serverului astfel încât să suporte fluxul de autorizare al clientului. O simplă nouă atribuire Contributor nu repară acest mecanism.

Crearea unei VM noi nu a fost testată. Nu se afirmă că ar eșua din aceeași cauză, deși ruta de start este demonstrabil blocată.

## Blocaj 2: ARM OAuth

Chiar descoperirea comenzilor ARM a eșuat înainte de furnizarea schemei:

> IDW10502: An MsalUiRequiredException was thrown due to a challenge for the user.

Acest rezultat demonstrează o problemă de achiziție a tokenului pentru ruta ARM. Nu identifică singur cauza exactă: consimțământ incremental, conditional access/MFA sau lipsa unui token în cache pot necesita interacțiune.

Abonamentul și Compute folosesc rute care funcționează; acest lucru nu demonstrează că tokenul downstream ARM este disponibil.

Remediere necesară: reautentificarea conexiunii Azure pentru tenantul corect și parcurgerea challenge-ului downstream în integrarea care îl cere. Verificarea finală trebuie să repete descoperirea ARM și o operațiune ARM de citire. În această sesiune nu a fost furnizat un URL de autorizare, iar un URL cu client/scopes ghicite nu a fost construit.

Referințe Microsoft:
- https://github.com/AzureAD/microsoft-identity-web/wiki/Managing-incremental-consent-and-conditional-access
- https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/concepts
- https://github.com/microsoft/mcp/blob/main/servers/Azure.Mcp.Server/TROUBLESHOOTING.md

## RBAC verificat

Lista atribuirilor pentru abonament include:
- Owner pentru principalul User ba9245e9-df1b-4ad6-b707-40096a75a7af.
- Contributor la nivel de abonament pentru ServicePrincipal 32e6befe-9e61-4470-9758-ed89a907c1f4.
- Atribuiri suplimentare pentru VM, Container Apps și Cognitive Services.

Sursele identifică principalul 32e6... ca identitatea k2401-github-oidc, client 50a5c260-15a0-4aa0-9e02-5f0ad5c23df9. Nu s-a demonstrat că acesta este principalul folosit de fiecare rută a conectorului ChatGPT. Permisiunile GitHub OIDC și autentificarea delegată ChatGPT sunt mecanisme distincte.

Atribuirile nu constituie singure o analiză completă a deny assignments, Azure Policy, cotelor, provider registration sau permisiunilor efective pentru orice operațiune. Nu au fost adăugate roluri duplicate.

## Defect de automatizare remediat

Fișier: .github/workflows/k2401-azure-ai-agent.yml.

Înainte, workflow-ul calcula și afișa RUN_ID, apoi pornea jobul fără să îl transmită. Template-ul de provisioning conține K2401_RUN_ID=40382269545. Agentul putea diagnostica o rulare diferită de cea raportată în rezumat.

După:
1. Workflow-ul citește template-ul complet al jobului existent.
2. Înlocuiește numai K2401_RUN_ID din containerul k2401-agent.
3. Păstrează imaginea, command, args, resursele, celelalte containere și env/secretRef.
4. Folosește override de execuție --yaml, fără schimbarea configurației comune a jobului.
5. Refuză pornirea dacă nu există exact un container cu numele așteptat.
6. Workflow dispatch cere un run_id explicit; fallback-ul vechi este eliminat.
7. Push-urile verifică static sursele; nu declanșează automat inferență prin markerul vechi.

Validare:
- YAML parse PASS.
- bash -n pentru toate scripturile inline PASS.
- Execuție locală cu CLI dublat: ID nou transmis, template și secretRef păstrate PASS.
- Container greșit: eșec înainte de start PASS.
- GitHub run 40469962540: preflight success, run-when-authorized skipped.
- Commit inițial ece54cab4220cc851848012f05685cbdb351bdcd.
- Eliminare fallback b872b63c6f0216bf87994db59cbc5f3f107a1fcb.

Nu s-a executat un job Azure real pentru această corecție. Un PASS de preflight nu validează inferența și nici propagarea live a ID-ului. Workflow-ul existent raportează pornirea jobului, nu confirmă singur rezultatul final al diagnosticului.

Referință pentru template override:
https://learn.microsoft.com/en-us/azure/container-apps/jobs

## APK: identitate și stare reală

Proiectul din conversațiile recente este K2401 EVO Launcher pentru navigația auto K2401_JT. Repo: tzn5-web/leno. Cod Android pe feature/k2401-evo-launcher, infrastructură/agent pe main.

Snapshot Android inspectat: 1eb625821721651b1a24397be05d0b84b3e05d63.
VersionName 0.3.0-dev, versionCode 3, minSdk 26, targetSdk 28, compileSdk 35.
Nu este implementat target API 36 în acest snapshot.

Cerințe recuperate din conversații:
- launcher fluid, fără animații/consum inutil;
- Home cu Maps în stânga, YouTube Music sus-dreapta, patru instrumente Torque/ECU jos-dreapta;
- în cerințele recente: RPM, STFT B1, LTFT B1, temperatura apei;
- cele șase pagini: Acasă, Muzică, Navigație, Mașină, Aplicații, Setări;
- compilare și testare cu capturi înainte de declararea APK-ului final.

| Funcție | Implementare observată | Ce nu este demonstrat/finalizat |
| --- | --- | --- |
| Home / șase pagini | UI Canvas, landscape 1280×720, panou MapView/WebView | conformitate vizuală finală cu referințele utilizatorului, performanță pe K2401 |
| Hartă | Google Maps SDK dacă există cheia și Play Services; fallback Leaflet/OSM, LocationManager | cheie reală configurată, GPS fizic și navigație integrată turn-by-turn |
| Rută | deschide Google Maps extern | navigație în jumătatea Home, fără părăsirea launcherului |
| YouTube Music | MediaSession, metadata, artă, progres, previous/play-pause/next | redare reală și compatibilitate pe unitate, UI complet YouTube Music în panou |
| Torque / ECU | Binder/AIDL, PID 010C/0106/0107/0105, filtrare date vechi/N/A | compatibilitate cu versiunea Torque Pro instalată și ECU real |
| Radio / Bluetooth | unele butoane deschid Android Settings | integrare radio OEM, comenzi volan, CAN/MCU, cameră marșarier |
| Sleep/wake | ciclul Activity există | suspendare/trezire pe head unit, revenire media/GPS/Torque |
| APK release | build debug | semnare release și verificare pe dispozitiv |

MainActivity evită pornirea clientului OBD când detectează emulatorul; testul emulatorului nu poate demonstra că binding-ul Torque funcționează. Absența datelor sintetice este corectă, dar nu este dovada datelor live.

Probleme de verificat suplimentar:
- reconectarea Torque la onBindingDied/onNullBinding nu face rebind explicit până la reluarea Activity;
- schimbarea permisiunii GPS cheamă pause/start pentru hartă, fără un resume explicit în callback; trebuie verificată secvența reală a lifecycle-ului;
- pagina Radio OEM și Bluetooth nu are încă rutare OEM dedicată;
- cele două ramuri trebuie integrate controlat; main singur nu conține aplicația completă.

## Ce dovedesc testele existente

GitHub run 40464873714: completed/success, branch feature/k2401-evo-launcher, SHA 1eb6258...
https://github.com/tzn5-web/leno/actions/runs/40464873714

Job 122057762377: build, verificare APK, upload, KVM și emulator success.

emulator-smoke.sh:
- instalare și pornire APK;
- șase capturi PNG cu dimensiunea 1280×720;
- schimbări de pagină, relansare;
- verificare proces și loguri crash/ANR;
- captură meminfo și gfxinfo.

Nu verifică semantic conținutul fiecărei pagini, muzică reală, hartă complet încărcată, un prag de performanță, Torque sau hardware-ul mașinii. Nu există testDebugUnitTest în acest workflow. PASS înseamnă smoke test trecut.

## Emulatorul Azure și agentul AI

Workflow-ul emulatorului Windows poate încă fi declanșat manual și are o fereastră lungă de execuție. README spune că această cale nu se mai folosește din cauza lipsei WHPX/nested virtualization. Nu trebuie confundată pornirea VM cu disponibilitatea acceleratorului Android.

În audit nu a fost pornit din nou emulatorul. Eroarea WHPX_NOT_READY este recuperată din istoric și din verificările surselor; nu a fost reprodusă live.

Agentul azure_entry.py este diagnostic-only, limitează modelul la 450 tokens și interzice mutațiile VM/cod prin designul promptului. El nu este un executor autonom de reparații. Comentariile despre identitate read-only nu descriu fidel rolul Contributor observat pentru identitatea partajată; separarea identității runtime rămâne neimplementată/verificată.

## Ordinea de finalizare

1. Rezolvarea confirmării interactive și a challenge-ului ARM în integrarea client/conector.
2. Repetarea operațiunilor de citire ARM; apoi o probă autorizată de start/deallocate cu verificarea stării și costului.
3. Verificarea live a corecției RUN_ID, cu un ID explicit și raport final al execuției.
4. Integrarea ramurilor aplicației și infrastructurii, cu reluarea CI.
5. Finalizarea navigației integrate și a integrărilor OEM cerute.
6. Probe reale Maps/GPS, YouTube Music, Torque/ECU, sleep/wake și hardware.
7. Abia după dovezile de mai sus: release APK semnat și audit final.

Nu este justificat încă verdictul „tot implementat” sau „APK final”.
