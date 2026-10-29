# K2401 — RACE HUD FINAL ALB–ROȘU (approved design)

Status: **APPROVED DESIGN**, not a claim that physical head-unit testing is complete.
Skin index: **25** (26th selectable theme), versionCode **120**.
Design source: the angular white/silver/red HUD preview approved by the user in chat on 2026-10-29. The user explicitly approved its aesthetic as a FINAL theme but requires all existing functional constraints.

## Unchangeable requirements
- Rectangular landscape K2401, 16:9. Fullscreen immersive; no overlapping Android bar, duplicated icons/clock, or ghost preprinted UI.
- Dark carbon angular/wings composition, very fine **white/silver** upper architecture, subtle red accents, not heavy cyan/purple lines. Device-scale vector UI; no false claim that interpolated low-resolution raster has optical 4K detail.
- Only real ECU values **RPM, coolant °C, STFT %, LTFT %**. Missing/unavailable values display N/A. Outside temp must be **actual OBD PID 0146** when available or N/A. No extra speed, PRNDS, fuel, battery, boost, oil or synthetic telemetry.
- Native clock/date displayed **exactly once**; Bluetooth/Wi-Fi status exactly once; media artwork/title/progress from current MediaSession, not artwork embedded with static text.
- Four fixed header buttons **SETUP, APPS, NAVI, MUZICĂ**, with independent working hitboxes.
- Six user-customizable installed-application shortcuts, persist in SharedPreferences. Single tap launches chosen package, long press changes it. Reuse existing UltraCockpitTheme persistent slots.
- **Actual interactive embedded map in the center**. Existing LiveMapPanel renders Google Maps SDK only with configured Maps key and available Play Services; otherwise it renders OpenStreetMap. This is not a privileged embedding of the standalone Google Maps app and does not claim licensed turn-by-turn directions.
- Existing 25 themes, OEM radio/Bluetooth/GPS/camera, existing page navigation and OBD drivers must not be broken.
- Render dynamic labels and gauges as antialiased vector shapes, not static text stored in wallpaper. Separate map View must accept real swipe/zoom/location/search.
- No declaration of verified final APK before Android 10 emulator smoke, signed release build and device installation checks. Physical K2401 testing remains distinct.

## Implementation
- `RaceHudFinalTheme.java`: exclusively dynamic HUD drawing, fixed header buttons, real MediaSession, selected six slots, live ECU and clock.
- `SkinEngine.java`: named final-approved skin selectable via existing gallery.
- `UltraCockpitTheme.java`: shared six editable app slots.
- `MainActivity.placeMap()`: place native Google Maps SDK / OSM view in center only for this skin on Home, preserve other skins' map behavior.
- `race-hud-final-emulator-smoke.sh`: actual screenshot, Android View hierarchy and header-touch checks.

## Audit distinctions
- App can have an exact 3840×2160 render target but optical image quality must be judged independently. Android Canvas vector gauges and labels remain sharp at arbitrary scaling; map tile detail comes from the actual map provider.
- User-approved **visual direction** does not imply scene-by-scene pixel-identical reproduction of the illustrative image. In production no invented sample labels, roads or timestamps should ever be used.
