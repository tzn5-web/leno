# K2401 EVO — design approvals and non-negotiable acceptance (29 October 2026)

## Approved as FINAL VISUAL DIRECTION — BLACK/RED RACE HUD
The user explicitly approved the immediately previous visual simulation in chat ("O poti marca drept tema finala"). It depicts a landscape black-carbon / silver-white / fine-red instrument cluster, two circular main gauges, central map area, four native HUD values, a player and 6 bottom shortcuts. Preserve this composition as its OWN selectable skin. **Approval applies to the visual direction, not to a compiled or hardware-verified APK.** The actual image-generation source must be sourced separately; never label an unrelated image or low-resolution surrogate as the approved image.

## STILL REQUIRED — SEPARATE ORIGINAL ANGULAR-WINGS ALAMY-INSPIRED SKIN
The same user also says "dar vreau si ce am cerut". This retains the earlier request: a SECOND, genuinely different landscape 16:9 / 3840x2160 Race HUD inspired by the user-supplied Alamy screenshot `19667.jpg` / angular-wings concept. Original design, do not reproduce licensed Alamy pixels or watermarks. Wings/crescents and sculptural metallic-white upper trim, restrained red highlights; **not merely a recolored/copy-pasted pair of circular gauges** from the approved skin. Both remain separately selectable; don't replace one with the other.

## Shared functional/visual contract for BOTH
- Android K2401 rectangular landscape navigation/head-unit (no pill-shaped gauge cluster); 16:9 safe layout, no status-bar/BT/Wi-Fi/time duplicates.
- **Only** RPM, engine coolant temperature, STFT and LTFT as instrument values. RPM via verified OBD reading; coolant in Celsius; fuel trims in percent. Unknown, invalid and disconnected inputs -> `N/A`; no illustrative fake ECU values at runtime.
- Actual Google Maps or OSM map panel running in the middle using existing native integration, not a screenshot, not AI-drawn roads, and no fictional route/street text.
- Live MediaSession player, with real track/album artwork from the currently selected media app; no baked example title/artist/album art.
- Precisely one live date/clock, ECU-derived outside temperature when available else `N/A`, and exactly one live BT/Wi-Fi status cluster.
- Four working, individually hit-tested controls by the player: `SETUP`, `APPS`, `NAVI`, `MUZICĂ`. Link to existing functional native pages (do not emulate click with decorative imagery).
- Precisely SIX separate personal-app slots. Single tap launches installed selected app; long press opens the chooser/replaces selected app; selections persist between launches; missing package handled safely. These are distinct from the four header controls.
- Never include PRNDS/gear status, speed, battery, fuel, boost/MAP, oil or voltage. Do not add substitute telemetry or decorative fake icons.
- Original 3840×2160 quality artwork rather than merely upsampling a soft screenshot and calling it "true 4K". Keep decorative scene imagery separate from all live text, maps, buttons and moving OBD needles. Prevent clipping, ghost typography, overlapped hitboxes and duplicate status items.
- Do not alter existing functional skins, OBD/MediaSession data acquisition, Maps, sleep/resume or installer identity merely to add decorative skins.
- Deliver independent, labeled previews. Actual APK completion requires Azure compilation, signed in-place update installation on Android 10, emulator screenshots and tapping/long-press regression tests on the final commit; report any visual mismatch. Never equate mockups with finished APKs.

## Current implementation status
**Black/Red Race HUD:** visual design APPROVED by user, full native APK implementation NOT YET VERIFIED.
**Angular-Wings Race HUD:** outstanding independent design request, NOT YET APPROVED as matching user's reference.
No GitHub CI, signed artifact, map integration or physical head-unit status should be inferred from this approval document.
