# K2401 v117 — Two distinct HUD skins (implementation contract)

Base: v116, preserve all existing native behaviors and 21 skins. Add two NEW selectable skins; do not replace existing skin assets or native widgets.

## Race HUD
Asymmetric angular/crescent motorsport instrument architecture, fine silver/white top surfaces, restrained red segmented accents, black background. RPM and coolant temperature dominate opposite flanks; STFT and LTFT occupy two small central instruments. No extra instruments.

## Holographic HUD
Distinct minimalist symmetrical circular floating gauges and light floating panels, silver/white upper treatment, black background, restrained red accents; no cyan/blue/purple.

## Both
- Landscape 16:9 source art 3840x2160, render with correct fit on 1280x720 K2401 without stretching; separate background art and native UI overlay.
- Exactly RPM (010C), coolant temperature (0105), STFT (0106), LTFT (0107), live or N/A. No speed, fuel, battery, PRNDS, fake values.
- Real existing LiveMapPanel in central region; no static simulated map or fictitious routes. Preserve map recovery.
- Existing active MediaSession player at top; exactly one clock/date and vehicle-derived external temperature (show N/A if no actual vehicle source), one BT and Wi-Fi indicator each.
- Exactly four primary buttons: SETUP, APPS, NAVI, MUZICĂ. Six native application shortcuts, long press to select, tap to launch; persist package identifiers.
- Hitboxes must match visual controls and not intercept map gestures or other widgets. Native content rendered above background and clipped to its own hit regions.
- No hardcoded player titles, routes, road names or mock vehicle data.

## Release gates
Build on existing GitHub Actions Android 10 workflow; use existing Azure Key Vault signing only when authentication is valid. Capture screenshots of BOTH skins on Android emulator at 1280x720, test all six shortcuts, settings selection persistence, map panel interaction, media fallback, OBD N/A behavior, touch-region collisions and crash-free relaunch. Real vehicle hardware validation remains separate.

## Source references
User-supplied v116 APK and two independent 4K previews in conversation on 2026-10-29. Preview assets are not yet uploaded into this repository; do not claim integration, compilation or emulator PASS until source/assets and workflow logs confirm them.
