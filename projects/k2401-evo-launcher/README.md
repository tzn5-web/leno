# K2401 EVO Launcher — Android 10

## Implemented in v0.3.0-dev

Landscape HOME launcher for K2401_JT, 1280×720:

- **Left panel — interactive online map, no fake route.** Uses the real Google Maps Android SDK if a **restricted Google Maps API key** has been supplied to the build and Google Play Services is available on the head unit. Without that key/Google Play Services, it visibly switches to a real *OpenStreetMap* online basemap (Leaflet). GPS fix uses Android LocationManager, after permission. "RUTĂ GOOGLE MAPS" opens Google Maps for route planning and turn-by-turn; the Google Maps SDK by itself does **not** embed turn-by-turn navigation.
- **Under the map — native pinned-app dock.** Shows actual Android application icons and names; tap to launch, long-press a pin to replace, move left/right or delete; '+' opens the installed-app picker. The dock scrolls horizontally and its ordered package list persists in SharedPreferences across app restarts and device reboots. No fake application icons.
- **Upper right — YouTube Music.** Connects to Android's real YouTube Music MediaSession when Notification Listener permission is granted. Shows actual title, artist, album art and playback progress where provided, with previous/play/pause/next. If no session exists it says so, never fabricates titles or a progress bar. YouTube Music's full proprietary Activity is not embedded.
- **Lower right — exactly four analog live Torque Pro gauges in approved left-to-right order:** STFT B1 % (`0106`), LTFT B1 % (`0107`), RPM (`010C`), TEMP APĂ °C (`0105`). Needles only appear when the corresponding PID has a fresh finite value; disconnected/stale values display `N/A`. A generated Java AIDL stub binds to `org.prowl.torque.remote.TorqueService` and calls Torque's `isConnectedToECU()`, `listAllPIDs()`, `listECUSupportedPIDs()`, `getPIDValues()`, and `getPIDUpdateTime()`. Missing, non-finite or stale values appear `N/A`. No direct ELM Bluetooth takeover, ECU writes, Torque debug-test mode or synthetic readings in the production build.

## Build

Requires JDK 17, Android SDK 35 and Gradle 8.11.1:

```bash
gradle --no-daemon -p projects/k2401-evo-launcher :app:assembleDebug
```

For an **actual embedded Google map**, create an Android-restricted Google Maps key, enable Maps SDK for Android and Google Maps Platform billing in the appropriate Google Cloud account, then pass:

```bash
export K2401_MAPS_API_KEY='<YOUR_RESTRICTED_GOOGLE_MAPS_SDK_KEY>'
gradle --no-daemon -p projects/k2401-evo-launcher :app:assembleDebug
```

Alternatively, configure a **GitHub Actions secret** `K2401_MAPS_API_KEY` and pass it as an environment variable to the build step. Restrict the key to app package `ro.evolauncher.k2401` and the signing certificate SHA-1 of the APK that will actually be installed. A new GitHub-hosted debug runner may use a different signing certificate. Store no unrestricted key or keystore in the repository. A keyless APK is valid but uses OpenStreetMap in the pane, not Google Maps.

Location requires user permission and GPS/network provider availability. The OpenStreetMap fallback requires internet and third-party map-tile access; the map shows copyright attribution. It does not provide Google turn-by-turn inside the panel.

## Enable media + live OBD on the physical head unit

1. Install/update **Torque Pro** (`org.prowl.torque`), connect its compatible OBD2 adapter and verify values inside Torque before starting EVO Launcher.
2. Grant EVO Launcher **Notification access** in Android Settings so it can read the active YouTube Music MediaSession; open and play a track in YouTube Music.
3. Launch EVO Launcher and allow location permission. Confirm the actual position, the real current track and each supported PID. Fuel-trim values may be `N/A` when ECU or Torque does not report them.
4. If Torque reports values but the launcher does not, gather `adb logcat` + Torque version and inspect the binder/PID status. **A passing emulator cannot establish compatibility with the real installed Torque Pro version or the vehicle's ECU.**

## CI and release gates

GitHub Actions `K2401 EVO Android 10 APK and emulator` compiles the APK and tests six screens, landscape 1280×720, relaunch and AndroidRuntime crashes. The emulator checks dock picker selection and persisted pins as well as wallpaper preferences. The emulator cannot provide real Torque data, real Google Maps billing credentials, GPS driving, Google Maps navigation, CAN/MCU/steering controls, OEM radio or reversing camera. Do not claim a final vehicle release on CI PASS alone.

**Vehicle safety:** Do not set as the car's default HOME launcher until OEM radio, reversing camera, steering-wheel controls, sleep/wake and CANBUS are verified while parked. Do not flash firmware. Do not operate the debugging UI while driving.

**Cost:** Azure Windows VM emulator work is disabled for this build path because WHPX/nested virtualization was unavailable. The VM stays deallocated. The bounded native Azure AI diagnostic agent uses existing Container Apps and a model deployment with strict inference limits.
