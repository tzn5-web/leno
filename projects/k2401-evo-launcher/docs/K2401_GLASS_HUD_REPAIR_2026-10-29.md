# K2401 EVO — repair audit from five physical-screen photographs (29 Oct 2026)

## Physical evidence and observed regressions
The five user-supplied photographs are of the actual 1280x720 K2401 display, not
emulator mockups. They show: (1) an aggressively blue/cyan car backdrop behind
two large dials and two small trims, with app labels too small; (2) an overly
flat red/white circular layout with a simplistic central car outline; (3) a
white angular-wing skin with an intrusive bright map; (4) a second, sparse
circular skin with a blank-looking dark field around the map; (5) a saturated
blue road scene, duplicated time, small app shortcuts and a visually busy rail.
These are **defect reports**, not approved visual references.

## Repair decisions
- Preserve the original skin IDs 0..20 and their data/navigation services.
- Restyle opt-in IDs 21..28 as black graphite, metallic silver and restrained
  red. No dominant cyan, neon-blue scenery, false car telemetry or opaque
  block-shaped mock gauges.
- Introduce native scalable glass panels, radial depth shading, chrome bezels,
  fine real-data arcs, translucent dial faces, and a noninteractive 3D
  holographic projection for skin 27.
- Replace the blue/artificial road in skin 28 with a newly rendered,
  deterministic **3840x2160** carbon-metal/red scene, not a resized photo.
- Keep the original 4K cinematic source assets for skins 22..24 in the APK;
  grade them on Canvas to a subdued neutral charcoal/silver appearance.
- Remove the duplicate top-right clock from skin 21, enlarge its six shortcut
  hit targets and increase app-label size.
- Use the same four live readings everywhere: RPM, coolant, STFT, LTFT. Values
  are never invented; NaN/disconnection is shown as N/A. The live date, time,
  ambient OBD temperature, MediaSession and real installed apps remain native.
- Preserve real navigation on skins 25/26 and the dedicated NAVI page. Skin 27
  intentionally has a decorative holographic center rather than a fake map.
- Preserve all four real navigation buttons and six user-editable slots.

## Automated acceptance (not subjective visual approval)
The Android 10 signed build must contain the original 21 skins and the true
3840x2160 asset, retain the persistent Azure Key Vault signing certificate,
and install side-by-side with the alternative package. The smoke suite captures
all eight redesigned skins from the **signed** APK at 1280x720, checks
nonblank native gauge text and restrained blue dominance, produces a montage,
individual PNGs, and a SHA-256 JSON report. Existing media, map, app chooser,
slot persistence, and recovery tests remain enabled.

Automated pixel checks cannot prove transparency quality, visual match to the
user's intended holographic reference, legibility in daylight, or performance
on the physical K2401. The head unit and ELM327 remain untested by CI.
No firmware/ECU modification or paid Azure VM is authorized.
