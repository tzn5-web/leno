# Torque Pro integration contract

Source: Torque Pro (`org.prowl.torque`) via its documented plugin AIDL API (`org.prowl.torque.remote.ITorqueService`). The launcher must not open its own ELM327 Bluetooth socket when Torque owns the adapter.

Display Bank 1 PIDs: RPM `010C` (rpm), STFT `0106` (%), LTFT `0107` (%), coolant `0105` (°C). The UI must show `N/A` for unsupported, disconnected, non-finite or stale readings. Query `getPIDValues(String[])` and `getPIDUpdateTime(String[])` asynchronously; resolve IDs via `listAllPIDs()` and confirm support through `listECUSupportedPIDs()`. Verify the plugin binding intent/action against the Torque sample before implementing. UI refresh is not an ECU polling guarantee. Never use demo values on the physical head unit.

Current `ObdReader.java` directly opens an ELM Bluetooth socket and the existing gauge UI displays MAP, coolant, RPM and voltage. Both need replacement. This document does not claim runtime integration or a rebuilt APK.
