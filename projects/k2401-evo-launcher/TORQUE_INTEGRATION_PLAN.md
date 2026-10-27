# Torque Pro — AIDL integration and real-hardware validation

Status: **implemented (source + Android 10 CI compile), physical ECU and installed Torque Pro not yet verified**.

Official entry point: `org.prowl.torque.remote.TorqueService`, package `org.prowl.torque`. Uses the official documented `org.prowl.torque.remote.ITorqueService` AIDL method order; **not** guessed manual Binder transaction numbers. Implementation: `app/src/main/java/ro/evolauncher/k2401/ObdReader.java`; AIDL: `app/src/main/aidl/org/prowl/torque/remote/ITorqueService.aidl`.

Read-only calls: `isConnectedToECU()`, `listAllPIDs()`, `listECUSupportedPIDs()`, `getPIDValues(String[])`, `getPIDUpdateTime(String[])`. The caller does **not** request an exclusive ELM adapter lock, send diagnostic ECU commands, activate Torque debug mode or modify ECU configuration.

Bank 1 OBD Mode 01 PIDs:
- `010C` — RPM in rpm.
- `0106` — STFT in percent.
- `0107` — LTFT in percent.
- `0105` — coolant temperature in °C.

The values Torque supplies are scaled into their respective native units already: do not apply raw OBD byte equations again. Poll at 650 ms on a worker; UI refresh from the main thread. Only display `live` readings with nonzero update timestamps not older than seven seconds (supporting wall-clock or uptime units), finite values and conservative bounds. Show `N/A` for every absent or stale PID. Disconnect and lifecycle pause clear all readings. No values are fabricated for a physical vehicle.

**Remaining physical release gate:** Android 10 head unit with Torque Pro installed, compatible ELM adapter paired *to Torque Pro*, ECU connected, measured PID changes (RPM under varying idle, STFT/LTFT with engine controls), and no binder permission denial. Capture a real Torque screenshot and paired launcher reading to prove agreement. On older Torque builds, the exported service or PID IDs may differ; diagnose instead of substituting mock values.

Reference: https://wiki.torque-bhp.com/view/PluginDocumentation
