# HOLO V5 — native layered build

**User-selected design:** exactly the third cyan/lime blue hologram concept from this conversation. Reference image 1254 × 1254 pixels.

**Actual build completed locally:** `Watch6T_HOLO_V5_COMPLET.zip` (private download in the ChatGPT conversation). It contains the build source, private factory template recovered from the user's own installed GloryFit APK, original image, 240 × 240 graphic layer assets, manifest, and tests. No proprietary APK data or user-provided images were uploaded to this public GitHub repository.

## Technical results

- Native 240 × 240 pixel face derived from the exact 1254 × 1254 reference.
- A replacement background clears example number bands while keeping original ECG/hologram/bezel features.
- Factory-compatible **layer names and frame counts** for hour, minute, date, weekday, five-digit steps, five battery states and eleven step-progress states.
- 248 entries in each of the two candidate ZIP structures; original folder groups and frame counts preserved.
- Local validation: internal ZIP CRC, PNG dimensions, path geometry, number of elements and image sizes all **PASS**.
- Private artifact includes `Build-HOLO-V5.py`, `test_holo_v5.py` and a detailed Romanian README.
- `Verify-HOLO-V5.py` in this repository can independently check the private archive with Pillow installed.

**Important limitations:** no confirmed dynamic heart rate, SpO2 or weather fields in the APK's `dial_1_circle_240x240` custom template. The ECG waveform is decorative. The face has *not* been accepted or synchronized by an actual iHunt Watch6T on firmware `RB235DCEV004137`. A ZIP CRC pass is not a BLE or firmware compatibility proof.

Do not use the watch's firmware-upgrade menu to load these files.

## Installation-compatible interim option

The private archive contains `HOLO_V5_BACKGROUND_NATIVE_240.png`, which can be selected as a wallpaper in GloryFit **Custom dial** if this option is available for the particular watch. The app may add its own live clock according to its template. This does **not** make all sci-fi data widgets live.

## Binary variant

An earlier 343,944 byte `D1898001.bin` candidate preserves 22 original record types and alters preview/background only. It cannot add new live fields. It is not a substitute for a complete native watchface or a verified install process.
