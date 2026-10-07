#!/usr/bin/env python3
from pathlib import Path
import hashlib
import re
import sys

ROOT=Path(__file__).resolve().parents[1]

PINNED={
    "sof_core/p360_transport_core.c":"fe593c280b7d66a152fe28997b9e76ed5eecc59105ffddc1cc1acccdb642fbee",
    "sof_core/p360_transport_core.h":"e89e42e0ba5119dbd4670fa607f6e81d33f19c25eeb744df08e6713c661c41d5",
    "sof_core/loader/p360_loader.c":"b0bb47b151eba7dd1b0a149fa649e661f39aabb306c1ea70192b285307414148",
    "sof_core/loader/p360_loader.h":"425fb596171f80a5907c5d989c805fe4455afd88fff6d9d90c6c2cbd5d3a2a72",
    "sof_core/loader/p360_fw_image.c":"3b370ae00596ff8ae3f3ca4c30e62a078a9c178af6a261c4d0009164854b6ab7",
    "sof_core/loader/p360_ipc_timer.c":"37148efb6a24877ae4379038eb1c108ab8b8f02824a5bfda1051b2d21454a0e9",
    "sof_core/loader/p360_ipc_timer.h":"2df15b4d9e0b16380d96503e83192e03e5d4685121f36a27e11af9b4e7e891d3",
    "sof_core/loader/p360_irq.c":"04dae608b067e3c7d4bf399f025a30a5cf0a2dc37737cea686bd1b033f813d81",
    "sof_core/loader/p360_irq.h":"0afd7c95168b4bb27db871e48c4acd10f92ff808394ad66c733f83fb2164e42d",
}

# p360_loader.c/.h remain byte-pinned, but are now the audited B4-derived
# GLK loader rather than untouched B4 originals. The only admitted semantic
# delta is Linux-compatible stale-core normalization plus exact diagnostics.


for rel,want in PINNED.items():
    p=ROOT/rel
    if not p.is_file():
        raise SystemExit(f"missing pinned B4 file: {rel}")
    got=hashlib.sha256(p.read_bytes()).hexdigest()
    if got!=want:
        raise SystemExit(f"B4 provenance drift: {rel}: {got} != {want}")

loader_source=(ROOT/"sof_core/loader/p360_loader.c").read_text()
loader_header=(ROOT/"sof_core/loader/p360_loader.h").read_text()
for token in (
    "result->entry_adspcs=baseline;",
    "if (baseline&(CORES_SPA|CORES_CPA))",
    "rc=power_down(&e);",
    "if (baseline&(CORES_SPA|CORES_CPA)) {",
    "result->normalized_adspcs=baseline;",
    "stall -> reset -> prove reset -> clear SPA -> prove CPA=0",
):
    if token not in loader_source + "\n" + loader_header:
        raise SystemExit(f"Linux-compatible stale-core normalization missing: {token}")

if "if (baseline&(CORES_SPA|CORES_CPA)) {rc=P360_L_BUSY;goto finish;}" in loader_source:
    raise SystemExit("old powered-core hard BUSY guard was reintroduced")


for name in (
    "p360_loader.c","p360_loader.h","p360_dispatch.c","p360_dispatch.h",
    "p360_fw_image.c","p360_irq.c","p360_irq.h",
    "p360_ipc_timer.c","p360_ipc_timer.h"
):
    if (ROOT/"sof_core"/name).exists():
        raise SystemExit(f"duplicate B4 source reintroduced: sof_core/{name}")

for rel in (
    "sof_core/runtime/p360_irq_arm.c",
    "sof_core/runtime/p360_irq_arm.h",
    "sof_core/runtime/p360_irq_arm_adapter.c",
    "sof_core/runtime/p360_irq_arm_adapter.h",
):
    if (ROOT/rel).exists():
        raise SystemExit(f"stale duplicate IRQ arm source reintroduced: {rel}")

safety=(ROOT/"include/p360_safety.h").read_text()
if not re.search(r"#define\s+P360_ENABLE_INTERNAL_SPEAKER\s+0\b",safety):
    raise SystemExit("internal speaker compile-time barrier is not zero")

boot=(ROOT/"src/p360_cs_boot.c").read_text()
for forbidden in ("p360_cs_boot_set_processing", "P360_PPCTL_OFFSET"):
    if forbidden in boot:
        raise SystemExit(f"direct PPCTL ownership reintroduced: {forbidden}")

bus=(ROOT/"src/p360_cs_bus.c").read_text()
if "if (!bus->ppcap)" not in bus:
    raise SystemExit("CoolStar PP capability hard gate missing")

abi=(ROOT/"include/p360_coolstar_adsp.h").read_text()
for token in (
    "P360_CS_ADSP_INTERFACE_VERSION 1u",
    "0x752a2cae",
    "sizeof(P360_CS_ADSP_BUS_INTERFACE) == 144",
    "sizeof(P360_CS_PCI_BAR) == 16",
):
    if token not in abi:
        raise SystemExit(f"CoolStar ABI pin missing: {token}")


runtime_h=(ROOT/"include/p360_cs_runtime.h").read_text()
runtime=(ROOT/"src/p360_cs_runtime.c").read_text()
driver_h=(ROOT/"driver/p360_driver.h").read_text()
dispatch_h=(ROOT/"sof_core/loader/p360_dispatch.h").read_text()
dispatch=(ROOT/"sof_core/loader/p360_dispatch.c").read_text()
ipc3_tx_h=(ROOT/"sof_core/loader/p360_ipc3_tx.h").read_text()
ipc3_tx=(ROOT/"sof_core/loader/p360_ipc3_tx.c").read_text()
ipc3_topology_h=(ROOT/"sof_core/loader/p360_ipc3_topology.h").read_text()
ipc3_topology=(ROOT/"sof_core/loader/p360_ipc3_topology.c").read_text()
run_b4=(ROOT/"tests/run_b4_core.sh").read_text()
csaudio_h=(ROOT/"include/p360_csaudio.h").read_text()
csaudio=(ROOT/"src/p360_csaudio.c").read_text()
telemetry_h=(ROOT/"include/p360_telemetry.h").read_text()
telemetry=(ROOT/"src/p360_telemetry.c").read_text()
cs_bus=(ROOT/"src/p360_cs_bus.c").read_text()
state_h=(ROOT/"include/p360_state.h").read_text()
state=(ROOT/"src/p360_state.c").read_text()
playback=(ROOT/"src/p360_playback.c").read_text()

for token in (
    r"\\Registry\\Machine\\SYSTEM\\CurrentControlSet\\Services\\P360SofAudio\\Parameters",
    "P360_TELEM_STAGE_IPC_READY      50u",
    "P360_TELEM_STAGE_TONE_COMPLETE  110u",
    "P360_TELEM_STAGE_STOP_COMPLETE  120u",
    "p360_telemetry_reset(",
    "p360_telemetry_stage(",
    "p360_telemetry_boot_epoch(",
    "p360_telemetry_ipc(",
    "p360_telemetry_result(",
    "p360_telemetry_loader(",
    "LoaderPhase",
    "EntryAdspcs",
    "NormalizedAdspcs",
    "FinalAdspcs",
    "RomStatus",
    "RomError",
    "ZwCreateKey(",
    "ZwSetValueKey(",
):
    if token not in telemetry_h + "\n" + telemetry:
        raise SystemExit(f"runtime telemetry contract missing: {token}")

for token in (
    'L"\\\\CallBack\\\\CsAudioCallbackAPI"',
    "P360_CSAUDIO_ENDPOINT_DSP",
    "P360_CSAUDIO_ENDPOINT_SPEAKER",
    "P360_CSAUDIO_ENDPOINT_REGISTER",
    "P360_CSAUDIO_ENDPOINT_START",
    "P360_CSAUDIO_ENDPOINT_STOP",
    "P360_CSAUDIO_ENDPOINT_START_ACK",
    "P360_CSAUDIO_ENDPOINT_STOP_ACK",
    "P360_CSAUDIO_TRANSITION",
    "p360_csaudio_next_generation(",
    "p360_csaudio_require_ack(",
    "ExCreateCallback(",
    "ExRegisterCallback(",
    "ExNotifyCallback(",
    "C_ASSERT(sizeof(P360_CSAUDIO_ARG) == 24)",
):
    if token not in csaudio_h + "\n" + csaudio:
        raise SystemExit(f"CoolStar CSAudio bridge contract missing: {token}")

csa_start_i=csaudio.index("p360_csaudio_speaker_start(")
csa_start_ack_i=csaudio.index(
    "P360_CSAUDIO_ENDPOINT_START_ACK",
    csa_start_i)
csa_rollback_stop_i=csaudio.index(
    "P360_CSAUDIO_ENDPOINT_STOP",
    csa_start_ack_i)
csa_rollback_ack_i=csaudio.index(
    "P360_CSAUDIO_ENDPOINT_STOP_ACK",
    csa_rollback_stop_i)
csa_keep_latch_i=csaudio.index(
    "InterlockedExchange(&link->SpeakerStarted,1);",
    csa_rollback_ack_i)
if not (
    csa_start_i < csa_start_ack_i < csa_rollback_stop_i <
    csa_rollback_ack_i < csa_keep_latch_i
):
    raise SystemExit(
        "ambiguous MAX START no longer forces STOP_ACK or retains ownership")

for p in ROOT.rglob("*"):
    if p.suffix.lower() not in (".c",".h",".cpp"):
        continue
    if p.is_relative_to(ROOT/"max98357a_safe"):
        continue
    text=p.read_text(errors="ignore")
    for forbidden in (
        "IOCTL_GPIO_WRITE_PINS",
        "RESOURCE_HUB_CREATE_PATH_FROM_ID",
        "GpioWriteDataSynchronously",
    ):
        if forbidden in text:
            raise SystemExit(
                f"direct MAX98357A GPIO ownership reintroduced in {p.relative_to(ROOT)}: {forbidden}")

max_safe=(ROOT/"max98357a_safe/p360_max_safe.c").read_text()
max_safe_h=(ROOT/"max98357a_safe/p360_max_safe.h").read_text()
max_inf=(ROOT/"max98357a_safe/P360Max98357Safe.inx").read_text()
for token in (
    "return p360_max_force_low(ctx);",
    "P360_MAX_REQUEST_START_ACK",
    "P360_MAX_REQUEST_STOP_ACK",
    "TransitionLock",
    "WdfWaitLockAcquire(ctx->TransitionLock,NULL)",
    "WdfWaitLockRelease(ctx->TransitionLock)",
    "DesiredGeneration",
    "DesiredOn",
    "STATUS_CANCELLED",
    "p360_max_gpio_write(&ctx->Sdmode,0)",
    "p360_max_gpio_write(&ctx->Sdmode,1)",
    "ACPI\\MX98357A",
):
    if token not in max_safe + "\n" + max_safe_h + "\n" + max_inf:
        raise SystemExit(f"fail-closed MAX98357A contract missing: {token}")

if "gpio_data = 1" in max_safe or "gpio_data=1" in max_safe:
    raise SystemExit("legacy D0-on MAX98357A behavior was reintroduced")

max_release_i=max_safe.index("P360MaxReleaseHardware(")
max_release_mute_i=max_safe.index("muteStatus=p360_max_force_low(ctx);",max_release_i)
max_release_unreg_i=max_safe.index("ExUnregisterCallback(",max_release_i)
max_release_gpio_i=max_safe.index("p360_max_gpio_deinit(",max_release_unreg_i)
max_release_lock_i=max_safe.index("WdfObjectDelete(ctx->TransitionLock)",max_release_gpio_i)
if not (
    max_release_i < max_release_mute_i < max_release_unreg_i <
    max_release_gpio_i < max_release_lock_i
):
    raise SystemExit("MAX98357A ReleaseHardware no longer proves mute before teardown")


for token in (
    "#define P360_DSP_UPBOX           0x81000u",
    "#define P360_HOST_DOWNBOX        0xa0000u",
    "#define P360_STREAM_BOX          0xc1000u",
    "#define P360_DISPATCH_MAP_BYTES  0xc2000u",
):
    if token not in dispatch_h:
        raise SystemExit(f"SOF mailbox map contract missing: {token}")

for token in (
    "stream=image+0xa0",
    "Stable(io,ctx,P360_DSP_UPBOX,reply,d->expected_reply_bytes)",
    "Stable(io,ctx,P360_STREAM_BOX,position,76)",
):
    if token not in dispatch:
        raise SystemExit(f"dispatcher mailbox routing contract missing: {token}")

for forbidden in ("P360_REPLY_BOX", "P360_NOTIFY_BOX"):
    if forbidden in dispatch_h + "\n" + dispatch + "\n" + ipc3_tx:
        raise SystemExit(f"ambiguous legacy mailbox symbol reintroduced: {forbidden}")

if "P360_CS_BOOL\np360_cs_runtime_interrupt" not in runtime_h:
    raise SystemExit("CoolStar interrupt callback ABI return type drifted")

for token in (
    "p360_rt_callback_close(rt);",
    "UnregisterInterrupt(",
    "p360_rt_wait_callbacks_closed(rt);",
    "WdfDpcCancel(rt->Dpc,TRUE)",
):
    if token not in runtime:
        raise SystemExit(f"runtime teardown proof missing: {token}")

close_i=runtime.index("p360_rt_callback_close(rt);")
unreg_i=runtime.index("UnregisterInterrupt(", close_i)
drain_i=runtime.index("p360_rt_wait_callbacks_closed(rt);", unreg_i)
cancel_i=runtime.index("WdfDpcCancel(rt->Dpc,TRUE)", drain_i)
if not (close_i < unreg_i < drain_i < cancel_i):
    raise SystemExit("runtime callback teardown ordering drifted")

stop_i=runtime.index("p360_cs_runtime_stop(")
active_i=runtime.index("InterlockedExchange(&rt->Active,0);", stop_i)
cb_idle_i=runtime.index("p360_rt_wait_callbacks_idle(rt);", active_i)
dpc_idle_i=runtime.index("p360_rt_wait_dpc_idle(rt);", cb_idle_i)
shutdown_i=runtime.index("p360_cs_boot_adapter_shutdown_live", dpc_idle_i)
if not (active_i < cb_idle_i < dpc_idle_i < shutdown_i):
    raise SystemExit("runtime stop ordering drifted")

bind_i=runtime.index("p360_cs_runtime_bind_live(")
arm_i=runtime.index("status = p360_rt_arm(rt);", bind_i)
arm_fail_i=runtime.index("if (!NT_SUCCESS(status)) {", arm_i)
bind_active_off_i=runtime.index("InterlockedExchange(&rt->Active,0);", arm_fail_i)
bind_mask_i=runtime.index("(void)p360_rt_mask(rt);", bind_active_off_i)
bind_fault_i=runtime.index("InterlockedExchange(&rt->Fault,1);", bind_mask_i)
bind_poison_i=runtime.index("p360_irq_poison(&rt->Irq);", bind_fault_i)
bind_dispatch_stop_i=runtime.index("p360_dispatch_stop(&rt->Dispatch);", bind_poison_i)
bind_unbound_i=runtime.index("rt->Bound = FALSE;", bind_dispatch_stop_i)
bind_epoch_i=runtime.index("rt->Epoch = 0;", bind_unbound_i)
if not (
    arm_i < arm_fail_i < bind_active_off_i < bind_mask_i <
    bind_fault_i < bind_poison_i < bind_dispatch_stop_i <
    bind_unbound_i < bind_epoch_i
):
    raise SystemExit("initial IRQ arm failure does not unwind fail-closed")

if not re.search(r"#define\s+P360_RUNTIME_BOOT_ENABLED\s+0\b", driver_h):
    raise SystemExit("runtime boot barrier was enabled without reviewed activation")

if not re.search(r"#define\s+P360_PORTCLS_SHELL_ENABLED\s+0\b", driver_h):
    raise SystemExit("PortCls shell barrier was enabled before lifecycle migration completed")

if not re.search(r"#define\s+P360_IPC_PROBE_ENABLED\s+0\b", driver_h):
    raise SystemExit("IPC3 proof barrier was enabled in the default driver")

if not re.search(r"#define\s+P360_SPEAKER_ENDPOINT_ENABLED\s+0\b", driver_h):
    raise SystemExit("speaker endpoint barrier was enabled in the default driver")

if not re.search(r"#define\s+P360_HOST_PLAYBACK_ENABLED\s+0\b", driver_h):
    raise SystemExit("HOST playback barrier was enabled in the default driver")

if not re.search(r"#define\s+P360_TONE_TOPOLOGY_PROOF_ENABLED\s+0\b", driver_h):
    raise SystemExit("hostless Tone topology proof barrier is not closed by default")

if not re.search(r"#define\s+P360_BOUNDED_TONE_TEST_ENABLED\s+0\b", driver_h):
    raise SystemExit("bounded Tone test barrier is not closed by default")

if "#define P360_BOUNDED_TONE_DURATION_MS 2000u" not in driver_h:
    raise SystemExit("final Tone duration is not the requested 2000 ms")
if "#define P360_DIAGNOSTIC_TONE_Q1_31 P360_IPC3_TONE_HALF_PERCENT_Q1_31" not in driver_h:
    raise SystemExit("final Tone amplitude is not pinned to 0.5% full-scale")
if "#define P360_DIAGNOSTIC_TONE_BLOCKS P360_IPC3_TONE_TWO_SECONDS_BLOCKS" not in driver_h:
    raise SystemExit("DSP-side final Tone duration is not pinned to 2 seconds")

for token in (
    "#ifndef P360_ENABLE_INTERNAL_SPEAKER",
    "#define P360_ENABLE_INTERNAL_SPEAKER 0",
):
    if token not in safety:
        raise SystemExit(f"speaker safety override contract missing: {token}")

speaker_endpoint=(ROOT/"src/p360_speaker_endpoint.cpp").read_text()
for token in (
    "CLSID_PortTopology",
    "CLSID_PortWaveRT",
    "PcRegisterSubdevice(",
    "PcRegisterPhysicalConnection(",
    "IID_IUnregisterSubdevice",
    "IID_IUnregisterPhysicalConnection",
    "P360_SPEAKER_PCM_VALID_BITS",
    "case KSSTATE_RUN:",
    "p360_host_playback_prepare(",
    "p360_host_playback_start(",
    "p360_host_playback_stop(",
    "p360_host_playback_release(",
    "p360_playback_stream_position(",
):
    if token not in speaker_endpoint:
        raise SystemExit(f"active WaveRT HOST playback contract missing: {token}")

run_i=speaker_endpoint.index("case KSSTATE_RUN:")
run_call_i=speaker_endpoint.index("p360_host_playback_start(",run_i)
if run_i >= run_call_i:
    raise SystemExit("WaveRT RUN still has no real SOF/HDA backend")

release_fn_i=speaker_endpoint.index("P360WaveStream::Release()")
release_guard_i=speaker_endpoint.index(
    "if (!p360_playback_memory_released(&m_Playback))",
    release_fn_i)
release_resurrect_i=speaker_endpoint.index(
    "InterlockedExchange(&m_Refs,1);",
    release_guard_i)
release_destructor_i=speaker_endpoint.index(
    "this->~P360WaveStream();",
    release_resurrect_i)
release_pool_free_i=speaker_endpoint.index(
    "ExFreePoolWithTag(this,P360_SPEAKER_POOL_TAG);",
    release_destructor_i)
if not (
    release_fn_i < release_guard_i < release_resurrect_i <
    release_destructor_i < release_pool_free_i
):
    raise SystemExit(
        "WaveRT object can be freed before DMA/SOF/MAX ownership is proved gone")

if "Hard barrier: the endpoint may enumerate" in speaker_endpoint:
    raise SystemExit("old enumerate-only WaveRT barrier was reintroduced")

for token in (
    "P360WaveStream::GetHWLatency(",
    "Latency->FifoSize=p360_playback_stream_fifo_size(",
):
    if token not in speaker_endpoint:
        raise SystemExit(f"WaveRT hardware latency contract missing: {token}")


for token in (
    "P360_SPEAKER_CONTAINER_BITS",
    "WAVE_FORMAT_EXTENSIBLE",
    "P360_SPEAKER_PCM_VALID_BITS",
):
    if token not in speaker_endpoint:
        raise SystemExit(f"32-container/16-valid WaveRT contract missing: {token}")

if "if (wave->wFormatTag==WAVE_FORMAT_PCM)" in speaker_endpoint:
    raise SystemExit("plain PCM was reintroduced; it cannot express 16 valid bits in a 32-bit container")

if "format.ValidBitsPerSample=P360_SPEAKER_CONTAINER_BITS;" not in playback:
    raise SystemExit("CoolStar HDA host descriptor must be programmed as 32-bit")

wave_test=(ROOT/"tools/P360_WAVERT_TEST.c").read_text()
for token in (
    "int32_t q16=(int32_t)(sin(phase)*163.0);",
    "int32_t v=q16 << 16;",
):
    if token not in wave_test:
        raise SystemExit(f"bounded WaveRT test is not 16-valid-bit left aligned: {token}")

host_pcm_begin=ipc3_topology.index("int p360_ipc3_build_host_pcm_params")
host_pcm_end=ipc3_topology.index("int p360_ipc3_build_pcm_free",host_pcm_begin)
host_pcm=ipc3_topology[host_pcm_begin:host_pcm_end]
for token in (
    "put32(d+60,P360_IPC3_FRAME_S32_LE);",
    "put16(d+76,2u); /* 16 valid bits */",
    "put16(d+78,4u); /* forced 32-bit Windows/HDA container */",
):
    if token not in host_pcm:
        raise SystemExit(f"SOF HOST container contract missing: {token}")

playback_dai_begin=ipc3_topology.index("int p360_ipc3_build_playback_dai_new")
playback_dai_end=ipc3_topology.index("int p360_ipc3_build_tone_new",playback_dai_begin)
if "P360_IPC3_FRAME_S16_LE" not in ipc3_topology[playback_dai_begin:playback_dai_end]:
    raise SystemExit("SOF DAI component is not fixed to the GLK SSP1 S16 backend")

board_h=(ROOT/"include/p360_board.h").read_text()
for token in (
    "#define P360_SPEAKER_CHANNELS 2u",
    "#define P360_SPEAKER_CONTAINER_BITS 32u",
    "#define P360_SPEAKER_PCM_VALID_BITS 16u",
    "#define P360_SPEAKER_DAI_VALID_BITS 16u",
    "#define P360_SPEAKER_DAI_SLOT_BITS 16u",
    "#define P360_SPEAKER_SSP1_BCLK_HZ 1536000u",
    "#define P360_SPEAKER_SSP1_MCLK_HZ 19200000u",
    "#define P360_SPEAKER_SSP1_MCLK_ID 1u",
):
    if token not in board_h:
        raise SystemExit(f"Phaser360 PCM/SSP1 width contract missing: {token}")


portcls=(ROOT/"src/p360_portcls_bridge.cpp").read_text()
project=(ROOT/"driver/P360SofAudio.vcxproj").read_text()
portcls_shell=(ROOT/"src/p360_portcls_shell.cpp").read_text()
for token in (
    "PcGetPhysicalDeviceObject(",
    "IoGetLowerDeviceObject(",
    "WdfDeviceMiniportCreate(",
    "ObDereferenceObject(lower)",
):
    if token not in portcls:
        raise SystemExit(f"PortCls/WDF miniport bridge contract missing: {token}")

bus_source=(ROOT/"src/p360_cs_bus.c").read_text()
if "WdfFdoQueryForInterface(" not in bus_source:
    raise SystemExit("CoolStar bus query no longer uses the permitted WDF miniport FDO interface path")

for token in (
    r"..\src\p360_portcls_bridge.cpp",
    r"..\src\p360_portcls_shell.cpp",
    r"..\src\p360_speaker_endpoint.cpp",
    r"..\include\p360_speaker_endpoint.h",
    r"..\src\p360_safety.c",
    r"..\src\p360_csaudio.c",
    r"..\include\p360_csaudio.h",
    r"..\src\p360_playback.c",
    r"..\include\p360_playback.h",
    r"..\src\p360_telemetry.c",
    r"..\include\p360_telemetry.h",
    r"..\sof_core\loader\p360_ipc3_tx.c",
    r"..\sof_core\loader\p360_ipc3_tx.h",
    r"..\sof_core\loader\p360_ipc3_topology.c",
    r"..\sof_core\loader\p360_ipc3_topology.h",
    "PortCls.lib",
):
    if token not in project:
        raise SystemExit(f"PortCls/safety build integration missing: {token}")

for token in (
    "P360_RUNTIME_BOOT_ENABLED=$(P360RuntimeBootEnabled)",
    "P360_PORTCLS_SHELL_ENABLED=$(P360PortClsShellEnabled)",
    "P360_IPC_PROBE_ENABLED=$(P360IpcProbeEnabled)",
    "P360_SPEAKER_ENDPOINT_ENABLED=$(P360SpeakerEndpointEnabled)",
    "P360_HOST_PLAYBACK_ENABLED=$(P360HostPlaybackEnabled)",
    "P360_TONE_TOPOLOGY_PROOF_ENABLED=$(P360ToneTopologyProofEnabled)",
    "P360_ENABLE_INTERNAL_SPEAKER=$(P360InternalSpeakerEnabled)",
    "P360_BOUNDED_TONE_TEST_ENABLED=$(P360BoundedToneTestEnabled)",
):
    if token not in project:
        raise SystemExit(f"staged audio build gate is not parameterized: {token}")

workflow=(ROOT.parent/".github/workflows/phaser360-windows.yml").read_text()
runner=(ROOT/"tools/P360_AUDIO_GATE.ps1").read_text()
wavert_test=(ROOT/"tools/P360_WAVERT_TEST.c").read_text()
for token in (
    "P360_RATE 48000u",
    "P360_SECONDS 2u",
    "P360_AMPLITUDE 10737418.0",
    "P360_TONE_HZ 997.0",
    'contains_i(caps.szPname,L"PHASER360")',
    "WAVE_FORMAT_EXTENSIBLE",
    "wValidBitsPerSample=16",
    "wBitsPerSample=32",
    "waveOutOpen(",
    "waveOutWrite(",
    "waveOutReset(",
    'wcscmp(argv[1],L"--preflight")',
    "WAVE_FORMAT_QUERY",
    'wprintf(L"PREFLIGHT=PASS',
    'wprintf(L"PHYSICAL_COMMIT=YES',
    'wprintf(L"PHYSICAL_COMPLETE=YES',
    'wprintf(L"TEST=PASS',
):
    if token not in wavert_test:
        raise SystemExit(f"bounded WaveRT test contract missing: {token}")

runner_readme=(ROOT/"tools/P360_AUDIO_GATE_README.txt").read_text()
start_cmd=(ROOT/"tools/START_AUDIO_TEST.cmd").read_text()
restore_cmd=(ROOT/"tools/RESTORE_LAST_SESSION.cmd").read_text()

for token in (
    "successful run ends with working PHASER360 audio installed",
    "There is no automatic baseline rollback",
    "Only a proved quiesced stack may be",
    "NEEDS_DRIVER_PATCH",
    "Restore is manual only",
    "RESTORE_LAST_SESSION.cmd",
):
    if token not in runner_readme:
        raise SystemExit(f"self-healing audio README contract missing: {token}")

for forbidden in (
    "Restore the original ADSP driver, the exact original MAX98357A driver, firmware state and temporary test certificate.",
    "both ADSP and MAX98357A baselines are restored and verified at the end",
):
    if forbidden in runner_readme:
        raise SystemExit(f"README still documents restore-on-success behavior: {forbidden}")

for token in (
    'ValidateSet("Audio","Restore")',
    "ExpectedFirmwareBytes = 246528",
    "f68694b6197250016a9c5ffb46fa8adaa599a32db95aa19a0ecf5bd4ed1c62ab",
    "ExpectedFlags 47 -MinimumStage 70",
    "ExpectedFlags 47 -MinimumStage 120",
    "FINAL_HOST_AUDIO_CORE=PASS",
    "FINAL_WAVERT_2000MS_MAX_0P5PCT=PASS",
    "P360_WAVERT_TEST.exe",
    "[BitConverter]::ToInt32([BitConverter]::GetBytes($fwRaw),0)",
    "Disable-TargetAndProveStop",
    "Get-WindowsDriver -Online -All",
    "Assert-NoStaleTestPackage",
    "Get-SignedDriverOrNull",
    "OriginalHadDriver",
    "OriginalProblemCode",
    "OriginalService",
    "Wait-TargetPresent",
    "Clear-TestTelemetry",
    "STALE_TELEMETRY_CLEARED=",
    "Remove-And-RescanTarget",
    "TARGET_REENUM_BIND=PASS",
    "Assert-SafeBaselineBeforeNewTest",
    '"/remove-device"',
    "RESTORE_DELETE_TEST_PACKAGE=",
    "RESTORE_STAGE_BASELINE_EXIT=",
    "RESTORE_BOUND_BASELINE=PASS",
    "Restore-OriginalDriver",
    "Restore-Firmware",
    "Remove-TestCertificate",
    "Recover-PreviousBaselineIfNeeded",
    "RESUME_AFTER_REBOOT_SCHEDULED=YES",
    "MANUAL_WINDOWS_RESTART_REQUIRED=YES",
    "INTERNAL_READY_GATE=PASS",
    "PHYSICAL_AUDIO_TEST=BEGIN",
    "FINAL_WAVERT_2000MS_MAX_0P5PCT=PASS",
    "STREAM_STOP_AND_AMP_MUTE=PASS",
    "PERSISTENT_FINAL_STACK=YES",
    "ROLLBACK_ON_SUCCESS=NO",
    "AUTOMATIC_ROLLBACK=NO",
    "PERSISTENT_REPAIR_STATE=YES",
    "PERSISTENT_REPAIR_SESSION_RESUMED=YES",
    "Ensure-FinalCoreReady",
    "Ensure-WaveRtPreflight",
    "Invoke-PhysicalPlaybackRepairLoop",
    "Ensure-PhysicalQuiesced",
    "AUDIO_READY=PASS ENDPOINT_REMAINS_INSTALLED=YES",
    "AUDIO_GATE=PASS",
    "NO_AUTO_REBOOT=YES",
    r"D:\PHASER360_WORK\continuation_20261005\v10_17R_original\firmware\sof-apl.ri",
    '"D:\\PHASER360_WORK"',
):
    if token not in runner:
        raise SystemExit(f"hardware gate runner contract missing: {token}")


for token in (
    '$bundledDir = Join-Path $PackageRoot "firmware"',
    '$bundledFirmware = Join-Path $bundledDir "p360-f686.ri"',
    'FIRMWARE_BUNDLED=PASS PATH=',
    'Self-contained package firmware directory exists but p360-f686.ri is missing.',
):
    if token not in runner:
        raise SystemExit(f"self-contained firmware runner contract missing: {token}")

for token in (
    'Phaser360\\firmware\\p360-f686.ri.gz',
    '221f536ad2e1ccc53ec145573fb8556dd3d7d115322e085d5cfae3faf62e48c3',
    '[IO.Compression.GZipStream]::new(',
    'P360_EXACT_FIRMWARE_RECONSTRUCT=PASS',
    'Join-Path $root "p360-f686.ri"',
    'FirmwareSha256 = (Get-FileHash (Join-Path $root "p360-f686.ri")',
    'P360_PRODUCTION_VERIFY',
    'P360_PRODUCTION_PACKAGE=PASS',
):
    if token not in workflow:
        raise SystemExit(f"self-contained production firmware workflow contract missing: {token}")

for forbidden in (
    "Final speaker test did not reach fresh TONE_COMPLETE.",
    "FINAL_TONE_2000MS_MAX_0P5PCT=PASS",
    "-ExpectedFlags 31 -MinimumStage 110",
):
    if forbidden in runner:
        raise SystemExit(f"final runner regressed to hostless Tone semantics: {forbidden}")

for token in (
    'function Ensure-FinalCoreReady',
    'Install-TestPackage "FinalSpeaker"',
    'Wait-Telemetry -ExpectedFlags 47 -MinimumStage 70 -Seconds 25',
    'function Ensure-WaveRtPreflight',
    '@("--preflight")',
    'function Invoke-PhysicalPlaybackRepairLoop',
    'PHYSICAL_AUDIO_TEST=BEGIN ATTEMPT=',
    'PHYSICAL_PLAYBACK_COMMITTED=YES',
    'Wait-Telemetry -ExpectedFlags 47 -MinimumStage 120 -Seconds 6',
    'function Ensure-PhysicalQuiesced',
    'FORCED_MAX_MUTE=PASS',
    'FORCED_ADSP_QUIESCE=PASS',
    'FINAL_WAVERT_2000MS_MAX_0P5PCT=PASS',
):
    if token not in runner:
        raise SystemExit(f"self-healing WaveRT final-runner contract missing: {token}")

install_test_begin=runner.index("function Install-TestPackage")
install_test_end=runner.index("function ",install_test_begin+1)
install_test_body=runner[install_test_begin:install_test_end]
if '"/install"' in install_test_body:
    raise SystemExit("P360 ADSP test packages must be staged without pnputil /install")

for token in (
    'function Assert-SafeAmpPackage',
    'function Backup-OriginalAmpDriver',
    'function Install-SafeAmpPackage',
    'function Restore-OriginalAmpDriver',
    'function Wait-AmpBinding',
    '$SafeAmpServiceName = "P360Max98357Safe"',
    '$SafeAmpProviderName = "PHASER360 Project"',
    '$SafeAmpDriverVersion = "2.0.0.0"',
    '$add=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/add-driver",$inf) -AllowFailure',
    '$remove=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/remove-device",$InstanceId) -AllowFailure',
    '$scan=Invoke-Tool -Exe "pnputil.exe" -Arguments @("/scan-devices") -AllowFailure',
    '[string]$script:State.AmpOriginalExportedInf) -AllowFailure',
    'AMP_SAFE_BIND=PASS',
    'AMP_RESTORE=PASS',
    'AmpRestoreVerified=$false',
):
    if token not in runner:
        raise SystemExit(f"safe MAX98357A bind/restore transaction missing: {token}")

safe_amp_install_begin=runner.index("function Install-SafeAmpPackage")
safe_amp_install_end=runner.index("function Restore-OriginalAmpDriver",safe_amp_install_begin)
safe_amp_install_body=runner[safe_amp_install_begin:safe_amp_install_end]
if '"/install"' in safe_amp_install_body:
    raise SystemExit("safe MAX98357A package must be staged before exact devnode remove/rescan")

for token in (
    "Compile fail-closed MAX98357A dependency",
    "P360_MAX98357_SAFE_COMPILE=PASS",
    'P360Max98357Safe.sys" = "P360Max98357Safe.sys"',
    '"P360Max98357Safe.sys"',
    'P360Max98357SafeSha256 = (Get-FileHash (Join-Path $root "P360Max98357Safe.sys")',
    "P360AudioBundle.inf",
    "P360AudioBundle.cat",
):
    if token not in workflow:
        raise SystemExit(f"production MAX98357A integration/signing workflow missing: {token}")

amp_backup_i=runner.index("Backup-OriginalAmpDriver $ampId")
amp_install_i=runner.index("Install-SafeAmpPackage $info $ampId",amp_backup_i)
amp_ready_i=runner.index("AMP_SAFE_READY=PASS",amp_install_i)
final_install_phase_i=runner.index('Write-RunLog "FINAL_STACK_INSTALL=BEGIN"',amp_ready_i)
if not amp_backup_i < amp_install_i < amp_ready_i < final_install_phase_i:
    raise SystemExit("safe MAX98357A proof is not complete before final stack install")

for forbidden in (
    "preaudio-proof.json",
    "Assert-PreAudioProof",
    "Write-PreAudioProof",
    'Write-RunLog "PREAUDIO_PHASE=BEGIN"',
    'Write-RunLog "PREAUDIO_CORE_AND_AMP_MUTE=PASS"',
):
    if forbidden in runner:
        raise SystemExit(f"separate/persistent PRE-AUDIO runtime path reintroduced: {forbidden}")

core_fn_i=runner.index("function Ensure-FinalCoreReady")
core_install_i=runner.index('Install-TestPackage "FinalSpeaker"',core_fn_i)
core_wait_i=runner.index("Wait-Telemetry -ExpectedFlags 47 -MinimumStage 70",core_install_i)
endpoint_fn_i=runner.index("function Ensure-WaveRtPreflight")
physical_fn_i=runner.index("function Invoke-PhysicalPlaybackRepairLoop")
preflight_i=runner.index("Ensure-WaveRtPreflight $WaveTest",physical_fn_i)
physical_begin_i=runner.index('Write-RunLog "PHYSICAL_AUDIO_TEST=BEGIN ATTEMPT=$round"',preflight_i)
wave_i=runner.index('$wave=Invoke-Tool -Exe $WaveTest -Arguments @() -AllowFailure',physical_begin_i)
quiesce_i=runner.index("Ensure-PhysicalQuiesced $InstanceId $AmpInstanceId $Info",wave_i)
repair_after_quiesce_i=runner.index("Rebind-FinalAdsp $InstanceId $Info",quiesce_i)
if not (
    core_fn_i < core_install_i < core_wait_i and
    endpoint_fn_i < physical_fn_i < preflight_i < physical_begin_i < wave_i <
    quiesce_i < repair_after_quiesce_i
):
    raise SystemExit("self-healing core/endpoint/physical ordering drifted")

main_core_i=runner.index("$telemetry=Ensure-FinalCoreReady",final_install_phase_i)
internal_pass_i=runner.index('Write-RunLog "INTERNAL_READY_GATE=PASS"',main_core_i)
main_physical_i=runner.index("$telemetry=Invoke-PhysicalPlaybackRepairLoop",internal_pass_i)
final_pass_i=runner.index('Write-RunLog "FINAL_WAVERT_2000MS_MAX_0P5PCT=PASS"',main_physical_i)
idle_pass_i=runner.index('Write-RunLog "STREAM_STOP_AND_AMP_MUTE=PASS"',final_pass_i)
stack_verify_i=runner.index("Assert-FinalAudioStack $info $targetId $ampId",idle_pass_i)
audio_ready_i=runner.index('Write-RunLog "AUDIO_READY=PASS ENDPOINT_REMAINS_INSTALLED=YES"',stack_verify_i)
persistent_i=runner.index('Write-RunLog "PERSISTENT_FINAL_STACK=YES"',audio_ready_i)
if not (
    final_install_phase_i < main_core_i < internal_pass_i < main_physical_i <
    final_pass_i < idle_pass_i < stack_verify_i < audio_ready_i < persistent_i
):
    raise SystemExit("self-healing final install -> repair -> playback -> persistent ordering drifted")

for token in (
    "AUTOMATIC_ROLLBACK=NO",
    "PERSISTENT_REPAIR_STATE=YES",
    "MANUAL_ROLLBACK=RESTORE_LAST_SESSION.cmd",
    "NEEDS_DRIVER_PATCH=YES",
    "HARD_STOP=YES REASON=MAX_MUTE_OR_STREAM_QUIESCE_NOT_PROVED",
):
    if token not in runner:
        raise SystemExit(f"persistent repair-state contract missing: {token}")

for forbidden in (
    "FAILURE_ROLLBACK_ADSP=PASS",
    "FAILURE_ROLLBACK_AMP=PASS",
    "FAILURE_ROLLBACK_FIRMWARE=PASS",
    "FAILURE_ROLLBACK_CERT=PASS",
    "FAILURE_ROLLBACK_BASELINE=PASS",
):
    if forbidden in runner:
        raise SystemExit(f"automatic failure rollback was reintroduced: {forbidden}")

if "3.0.100.1" not in runner[runner.index("function Test-IsReservedGateVersion"):runner.index("function Assert-NoStaleTestPackage")]:
    raise SystemExit("final persistent P360 driver version is not covered by rollback cleanup")

for token in (
    "AdspBackupComplete=$false",
    "AmpBackupComplete=$false",
    "$script:State.AdspBackupComplete = $true",
    "$script:State.AmpBackupComplete=$true",
    'RESTORE_ADSP_SKIPPED=backup_not_complete',
    'RESTORE_AMP_SKIPPED=backup_not_complete',
    '# Persist the identity before the first mutation so rollback can remove a',
):
    if token not in runner:
        raise SystemExit(f"crash-safe recovery-provenance contract missing: {token}")

for token in (
    '"bcdedit.exe" -Arguments @("/set","testsigning","on")',
    "TESTSIGNING_REPAIR=PASS RESTART_REQUIRED=YES",
):
    if token not in runner:
        raise SystemExit(f"TestSigning self-repair contract missing: {token}")

for token in (
    '"PhysicalCommitted","HardStop","NeedsDriverPatch","NeedsManualRestart"',
    'RESUME_SAFETY_RECOVERY=BEGIN',
    'Ensure-PhysicalQuiesced $targetId $ampId $info',
    'RESUME_SAFETY_RECOVERY=PASS',
    'Previous ambiguous physical ownership was cleared before repair continued.',
):
    if token not in runner:
        raise SystemExit(f"resume physical-ownership recovery contract missing: {token}")

for forbidden in (
    "Restart-Computer",
    "shutdown.exe",
    "/reboot",
):
    if forbidden.lower() in runner.lower():
        raise SystemExit(f"hardware gate runner gained forbidden automatic reboot: {forbidden}")

for token in (
    'cd /d "%~dp0"',
    "net session >nul 2>&1",
    "Start-Process -FilePath '%~f0' -Verb RunAs",
    'P360_AUDIO_GATE.ps1" -Mode Audio',
    "Diagnose and repair PnP/SOF/IRQ/IPC/topology/endpoint failures",
    "Preflight WaveRT silently before any physical sample buffer",
    "retry only after proved quiesce",
    "NO automatic baseline rollback",
    "Restore is manual only",
    "Return code: %RC%",
    "pause",
):
    if token not in start_cmd:
        raise SystemExit(f"self-healing one-click audio launcher contract missing: {token}")

if 'P360_AUDIO_GATE.ps1" -Mode Restore -SessionPath' in start_cmd:
    raise SystemExit("one-click launcher must use the single Audio transaction only")

for token in (
    'cd /d "%~dp0"',
    "net session >nul 2>&1",
    "Start-Process -FilePath '%~f0' -Verb RunAs",
    'P360_AUDIO_GATE.ps1" -Mode Restore -SessionPath',
    "P360_AUDIO_*",
    "P360_PREAUDIO_*",
    "pause",
):
    if token not in restore_cmd:
        raise SystemExit(f"one-click restore launcher contract missing: {token}")

for token in (
    "function Write-ResultZip",
    "[IO.Compression.ZipFile]::CreateFromDirectory(",
    'Write-RunLog "RESULT_ZIP_BEGIN=$zip"',
    'Write-Host "RESULT_ZIP_SHA256=$sha"',
    'Write-ResultZip "AUDIO" | Out-Null',
    'Write-ResultZip "RESTORE" | Out-Null',
):
    if token not in runner:
        raise SystemExit(f"single Desktop result ZIP contract missing: {token}")

report_i=runner.index('Write-Report $(if ($success) {"PASS"} else {"FAIL"}) $telemetry')
result_dir_i=runner.index('Write-RunLog "RESULT_DIR=$Session"',report_i)
result_zip_i=runner.index('Write-ResultZip "AUDIO" | Out-Null',result_dir_i)
final_exit_i=runner.index('if ($success) { exit 0 }',result_zip_i)
if not report_i < result_dir_i < result_zip_i < final_exit_i:
    raise SystemExit("result ZIP is not snapshotted after report and before final exit")

for token in (
    "one result ZIP directly on Desktop",
    "P360_AUDIO_*.zip",
):
    if token not in runner_readme:
        raise SystemExit(f"result ZIP README contract missing: {token}")

if "Result ZIP: %USERPROFILE%\\Desktop\\P360_AUDIO_*.zip" not in start_cmd:
    raise SystemExit("one-click launcher does not publish Desktop result ZIP location")

for launcher_name, launcher in (
    ("START_AUDIO_TEST.cmd",start_cmd),
    ("RESTORE_LAST_SESSION.cmd",restore_cmd),
):
    for forbidden in (
        "shutdown",
        "bcdedit",
        "Restart-Computer",
    ):
        if forbidden.lower() in launcher.lower():
            raise SystemExit(
                f"{launcher_name} gained forbidden reboot/BCD mutation: {forbidden}")

for token in (
    "/p:P360PortClsShellEnabled=1",
    "/p:P360RuntimeBootEnabled=1",
    "/p:P360IpcProbeEnabled=1",
    "/p:P360SpeakerEndpointEnabled=1",
    "/p:P360HostPlaybackEnabled=1",
    "/p:P360InternalSpeakerEnabled=1",
    "PORTCLS_HOST_WAVERT_PLAYBACK_COMPILE=PASS",
    "P360SofAudio-host-playback.sys",
    "Compile WASAPI shared acceptance utility",
    "P360_WASAPI_SHARED_TEST_COMPILE=PASS",
    "Compile forced full-driver installer helper",
    "P360_FORCE_INSTALL_COMPILE=PASS",
    "P360_FORCE_INSTALL.cpp",
    "Prepare full-install audio package",
    "P360_FULL_INSTALL.ps1",
    "INSTALL_PHASER360_AUDIO.cmd",
    "RESTORE_PHASER360_AUDIO.cmd",
    "Build and audit full-install driver package",
    "P360_FULL_INSTALL_PACKAGE=PASS",
    "P360_FORCE_BINDING=PASS",
    "P360_FULL_INSTALL.zip",
    "Upload full-install audio driver",
    "P360-FULL-INSTALL-${{ github.sha }}",
):
    if token not in workflow:
        raise SystemExit(f"full-install audio CI contract missing: {token}")

for forbidden in (
    "P360-AUDIO-GATE-${{ github.sha }}",
    "P360-PRODUCTION-AUDIO-${{ github.sha }}",
    "Upload hardware gate package",
    "Upload production audio package",
    "Upload unsigned compile artifact",
):
    if forbidden in workflow:
        raise SystemExit(f"obsolete install/debug artifact is still public: {forbidden}")

pre_step_begin=workflow.index("- name: Compile pre-audio IPC3 proof path")
pre_step_end=workflow.index("- name: Compile hostless Tone topology proof",pre_step_begin)
pre_step=workflow[pre_step_begin:pre_step_end]
for token in (
    "/p:P360PortClsShellEnabled=1",
    "/p:P360RuntimeBootEnabled=1",
    "/p:P360IpcProbeEnabled=1",
):
    if token not in pre_step:
        raise SystemExit(f"PRE-AUDIO compile regression missing required gate: {token}")
for forbidden in (
    "/p:P360ToneTopologyProofEnabled=1",
    "/p:P360InternalSpeakerEnabled=1",
    "/p:P360BoundedToneTestEnabled=1",
    "/p:P360SpeakerEndpointEnabled=1",
):
    if forbidden in pre_step:
        raise SystemExit(f"PRE-AUDIO compile regression accidentally enables audio path: {forbidden}")

bounded_step_begin=workflow.index("- name: Compile bounded internal speaker proof")
bounded_step_end=workflow.index("- name: Compile speaker endpoint shell",bounded_step_begin)
bounded_step=workflow[bounded_step_begin:bounded_step_end]
for token in (
    "/p:P360PortClsShellEnabled=1",
    "/p:P360RuntimeBootEnabled=1",
    "/p:P360IpcProbeEnabled=1",
    "/p:P360ToneTopologyProofEnabled=1",
    "/p:P360InternalSpeakerEnabled=1",
    "/p:P360BoundedToneTestEnabled=1",
):
    if token not in bounded_step:
        raise SystemExit(f"bounded speaker compile regression missing required gate: {token}")
if "/p:P360SpeakerEndpointEnabled=1" in bounded_step:
    raise SystemExit("bounded speaker proof must not expose normal Windows speaker endpoint")

host_step_begin=workflow.index("- name: Compile real HOST WaveRT speaker path")
host_step_end=workflow.index("- name: Compile bounded WaveRT test utility",host_step_begin)
host_step=workflow[host_step_begin:host_step_end]
for token in (
    "/p:P360PortClsShellEnabled=1",
    "/p:P360RuntimeBootEnabled=1",
    "/p:P360IpcProbeEnabled=1",
    "/p:P360SpeakerEndpointEnabled=1",
    "/p:P360HostPlaybackEnabled=1",
    "/p:P360InternalSpeakerEnabled=1",
    "P360SofAudio-host-playback.sys",
    "PORTCLS_HOST_WAVERT_PLAYBACK_COMPILE=PASS",
):
    if token not in host_step:
        raise SystemExit(f"real HOST WaveRT build missing required gate/output: {token}")
for forbidden in (
    "/p:P360ToneTopologyProofEnabled=1",
    "/p:P360BoundedToneTestEnabled=1",
):
    if forbidden in host_step:
        raise SystemExit(f"real HOST WaveRT final build depends on legacy Tone path: {forbidden}")

production_inf=(ROOT/"production/P360AudioBundle.inx").read_text()
full_installer=(ROOT/"full_install/P360_FULL_INSTALL.ps1").read_text()
force_installer=(ROOT/"full_install/P360_FORCE_INSTALL.cpp").read_text()
wasapi_shared=(ROOT/"production/P360_WASAPI_TEST.cpp").read_text()

for token in (
    "DriverVer=10/07/2026,4.2.0.0",
    r"CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198",
    r"ACPI\MX98357A",
    "PKEY_AudioEngine_OEMFormat",
    "KSNODETYPE_SPEAKER",
    "FE,FF,02,00,80,BB,00,00,00,DC,05,00,08,00,20,00,16,00,10,00",
):
    if token not in production_inf:
        raise SystemExit(f"full-install INF contract missing: {token}")
if "PKEY_AudioEndpoint_Supports_EventDriven_Mode" in production_inf:
    raise SystemExit("full-install INF advertises unsupported event-driven WaveRT")
if "PKEY_AudioEndpoint_Association%,,%KSNODETYPE_ANY%" in production_inf:
    raise SystemExit("full-install speaker endpoint is still generic")

for token in (
    "PKEY_AudioEngine_OEMFormat",
    "PKEY_AudioEngine_DeviceFormat",
    "%ls_EXACT_P360=",
    "IAudioEndpointFormatControl",
    "ResetToDefault(0)",
    "MIX_INTERNAL_ENGINE_FORMAT=OBSERVED",
    "AUDCLNT_SHAREMODE_SHARED",
    "WASAPI_SHARED_PREFLIGHT=PASS",
):
    if token not in wasapi_shared:
        raise SystemExit(f"WASAPI no-sound endpoint verification missing: {token}")

for forbidden in (
    "WASAPI_TEST=FAIL stage=MixFormat",
    "MIX_EXACT_P360=",
):
    if forbidden in wasapi_shared:
        raise SystemExit(f"internal Audio Engine format is incorrectly treated as device format: {forbidden}")

for token in (
    "UpdateDriverForPlugAndPlayDevicesW(",
    "INSTALLFLAG_FORCE",
    "FULL_DRIVER_BIND=PASS",
    "REBOOT_REQUIRED=",
):
    if token not in force_installer:
        raise SystemExit(f"forced driver binding helper missing: {token}")

for function_name in (
    "Assert-Package",
    "Ensure-OriginalBackup",
    "Report-NonAudioBoot0000",
    "Force-FullDriverBinding",
    "Wait-FullBinding",
    "Restart-ExactDevices",
    "Restart-WindowsAudio",
    "Run-WasapiPreflight",
    "Reset-WasapiEndpointFormat",
    "Remove-StaleProjectPackages",
    "Install-FullStack",
    "Write-ResultZip",
    "Restore-Original",
):
    marker=f"function {function_name}"
    if full_installer.count(marker) != 1:
        raise SystemExit(f"full installer function must exist exactly once: {function_name}")

for token in (
    "PHASER360 FULL AUDIO DRIVER INSTALL",
    "PHYSICAL_AUDIO_TEST=NO",
    "P360_FORCE_INSTALL.exe",
    "FULL_INSTALL_ROUND=",
    "WINDOWS_AUDIO_ENDPOINT=PASS",
    "WASAPI_DEVICE_FORMAT_RESET=PASS",
    "NOT_AUDIO_BLOCKER=YES",
    "FULL_DRIVER_INSTALL=PASS",
    "AUDIO_DRIVER_READY=YES",
):
    if token not in full_installer:
        raise SystemExit(f"full installer convergence contract missing: {token}")

for forbidden in (
    'Run-Wasapi")',
    "PHYSICAL_WASAPI_ATTEMPT",
    "P360_WAVERT_TEST.exe",
):
    if forbidden in full_installer:
        raise SystemExit(f"physical/legacy test leaked into full installer: {forbidden}")

full_prepare_begin=workflow.index("- name: Prepare full-install audio package")
full_build_begin=workflow.index("- name: Build and audit full-install driver package",full_prepare_begin)
full_prepare=workflow[full_prepare_begin:full_build_begin]
for token in (
    'P360SofAudio-host-playback.sys" = "P360SofAudio.sys"',
    'P360Max98357Safe.sys" = "P360Max98357Safe.sys"',
    '"P360_WASAPI_TEST.exe"',
    '"P360_FORCE_INSTALL.exe"',
    '"P360_FULL_INSTALL.ps1"',
    '"INSTALL_PHASER360_AUDIO.cmd"',
    '"RESTORE_PHASER360_AUDIO.cmd"',
    "p360-f686.ri",
):
    if token not in full_prepare:
        raise SystemExit(f"full-install input assembly missing: {token}")

full_upload_begin=workflow.index("- name: Upload full-install audio driver",full_build_begin)
full_build=workflow[full_build_begin:full_upload_begin]
for token in (
    'InstallerMode = "FullInstall"',
    'ForceBindingApi = "UpdateDriverForPlugAndPlayDevices/INSTALLFLAG_FORCE"',
    "PhysicalAudioTest = $false",
    "P360SofAudioSha256",
    "P360Max98357SafeSha256",
    "WasapiTestSha256",
    "ForceInstallSha256",
    "P360_FULL_INSTALL_PACKAGE=PASS",
):
    if token not in full_build:
        raise SystemExit(f"full-install manifest/audit missing: {token}")

for token in (
    "WdfDriverInitNoDispatchOverride",
    "PcInitializeAdapterDriver(",
    "PcAddAdapterDevice(",
    "p360_portcls_create_wdf_miniport(",
    "p360_host_prepare(",
    "p360_host_d0_entry(",
    "p360_host_d0_exit(",
    "p360_host_release(",
    "p360_speaker_endpoint_install(",
    "p360_speaker_endpoint_uninstall(",
    "IRP_MN_STOP_DEVICE",
    "IRP_MN_SURPRISE_REMOVAL",
    "IRP_MN_REMOVE_DEVICE",
    "PcDispatchIrp(",
    "WdfDriverMiniportUnload(",
    "MajorFunction[IRP_MJ_PNP]",
    "DriverObject->DriverUnload=P360PortClsUnload",
):
    if token not in portcls_shell:
        raise SystemExit(f"PortCls lifecycle contract missing: {token}")

for token in (
    "WDFDEVICE FrameworkDevice;",
    "PDEVICE_OBJECT PortClsFdo;",
    "PVOID SpeakerTopologyPort;",
    "PVOID SpeakerWavePort;",
    "BOOLEAN SpeakerEndpointInstalled;",
    "volatile LONG PnpQueryPending;",
    "extern \"C\" {",
):
    if token not in driver_h:
        raise SystemExit(f"PortCls shell C ABI/lifetime contract missing: {token}")

inf=(ROOT/"driver/P360SofAudio.inx").read_text()
for token in (
    "Class=MEDIA",
    "ClassGuid={4D36E96C-E325-11CE-BFC1-08002BE10318}",
    r"CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198",
    "Include=ks.inf,wdmaudio.inf",
    "Needs=KS.Registration,WDMAUDIO.Registration",
    "AddInterface=%KSCATEGORY_AUDIO%,%KSNAME_WaveSpeaker%,P360.I.WaveSpeaker",
    "AddInterface=%KSCATEGORY_RENDER%,%KSNAME_WaveSpeaker%,P360.I.WaveSpeaker",
    "AddInterface=%KSCATEGORY_REALTIME%,%KSNAME_WaveSpeaker%,P360.I.WaveSpeaker",
    "AddInterface=%KSCATEGORY_TOPOLOGY%,%KSNAME_TopologySpeaker%,P360.I.TopologySpeaker",
    'KSNAME_WaveSpeaker="WaveSpeaker"',
    'KSNAME_TopologySpeaker="TopologySpeaker"',
    "HKR,,DeviceType,0x10001,0x0000001D",
):
    if token not in inf:
        raise SystemExit(f"real PortCls media binding contract missing: {token}")
for forbidden in (
    "Class=System",
    "ClassGuid={4D36E97D-E325-11CE-BFC1-08002BE10318}",
):
    if forbidden in inf:
        raise SystemExit(f"diagnostic System-class INF was reintroduced: {forbidden}")

for token in (
    "P360_IPC3_PROOF_COMMAND     0xe0000000u",
    "P360_IPC3_PROOF_ERROR       (-22)",
    "p360_dispatch_expect_message(",
    "io->write_box(context,P360_HOST_DOWNBOX,message,bytes)",
    "io->write32(context,P360_DSP_HIPCI,P360_HIPCI_BUSY)",
):
    if token not in (ipc3_tx_h + "\n" + ipc3_tx):
        raise SystemExit(f"IPC3 bounded TX contract missing: {token}")

if "tests/ipc3_tx_regression.c" not in run_b4:
    raise SystemExit("IPC3 TX regression is not in the B4 gate")

for token in (
    "expected_reply_bytes",
    "expected_reply_cmd",
    "expected_comp_id",
    "p360_dispatch_expect_message(",
):
    if token not in dispatch_h:
        raise SystemExit(f"structured IPC3 reply contract missing from header: {token}")

for token in (
    "d->expected_reply_bytes=20u",
    "d->expected_reply_cmd=command",
    "d->expected_comp_id=comp_id",
    "U32(reply+12)!=d->expected_comp_id",
    "CompleteStructured(&next,reply,d->expected_reply_bytes)",
):
    if token not in dispatch:
        raise SystemExit(f"structured IPC3 reply validation missing: {token}")

for token in (
    "command==0x30010000u",
    "command==0x30100000u",
    "command==0x30200000u",
    "command==0x60010000u",
    "command==0x50030000u",
    "d->expected_reply_bytes=140u",
    "d->expected_reply_bytes!=140u",
):
    if token not in dispatch:
        raise SystemExit(f"SOF IPC3 structured-reply whitelist missing: {token}")

if "tests/ipc3_reply_regression.c" not in run_b4:
    raise SystemExit("structured IPC3 reply regression is not in the B4 gate")

for token in (
    "P360_IPC3_TONE_NEW_BYTES       100u",
    "P360_IPC3_DAI_CONFIG_BYTES     216u",
    "P360_IPC3_PCM_PARAMS_BYTES     108u",
    "P360_IPC3_COMP_TONE  10u",
    "P360_IPC3_FRAME_S24_4LE 1u",
    "P360_IPC3_DAI_INTEL_SSP   1u",
    "p360_ipc3_build_tone_new(",
    "p360_ipc3_build_dai_new(",
    "p360_ipc3_build_ssp1_config(",
    "p360_ipc3_build_pcm_params(",
    "p360_ipc3_build_tone_amplitude(",
    "p360_ipc3_build_tone_length(",
    "p360_ipc3_build_stream_trigger(",
):
    if token not in (ipc3_topology_h + "\n" + ipc3_topology):
        raise SystemExit(f"IPC3 speaker topology ABI contract missing: {token}")

if "tests/ipc3_topology_regression.c" not in run_b4:
    raise SystemExit("IPC3 speaker topology regression is not in the B4 gate")

for pattern, label in (
    (r"#define\s+P360_IPC3_TONE_CONTROL_BYTES\s+140u\b", "Tone control size=140"),
    (r"#define\s+P360_IPC3_CTRL_TYPE_DATA_SET\s+5u\b", "SOF DATA_SET type=5"),
    (r"#define\s+P360_IPC3_TONE_HALF_PERCENT_Q1_31\s+10737418u\b", "Tone gain=0.5%"),
    (r"#define\s+P360_IPC3_TONE_TWO_SECONDS_BLOCKS\s+16000u\b", "Tone length=16000x125us"),
):
    if not re.search(pattern, ipc3_topology_h):
        raise SystemExit(f"SOF 1.9.3 low-volume Tone control ABI missing: {label}")

for token in (
    "put32(d+16,P360_IPC3_CTRL_TYPE_DATA_SET);",
    "put32(d+20,P360_IPC3_CTRL_CMD_ENUM);",
    "P360_IPC3_TONE_IDX_AMPLITUDE",
    "P360_IPC3_TONE_IDX_LENGTH",
    "put32(d+56,channels);",
    "put32(d+100,(uint32_t)channels * 8u)",
    "put32(d+104,P360_IPC3_SOF_ABI_3_20_0)",
):
    if token not in ipc3_topology:
        raise SystemExit(f"SOF 1.9.3 low-volume Tone control ABI missing: {token}")

for token in (
    "put_config(d+28,2u,0u,P360_IPC3_FRAME_S32_LE)",
    "put_config(d+28,0u,2u,P360_IPC3_FRAME_S16_LE)",
    "P360_IPC3_GLB_STREAM_MSG|P360_IPC3_STREAM_PCM_PARAMS",
    "put32(d+24,84u)",
    "put32(d+28,28u)",
    "put16(d+76,4u)",
    "put16(d+78,4u)",
    "P360_IPC3_MEM_RAM|P360_IPC3_MEM_HP|",
    "P360_IPC3_MEM_DMA|P360_IPC3_MEM_CACHE",
):
    if token not in ipc3_topology:
        raise SystemExit(f"corrected IPC3 speaker runtime contract missing: {token}")

for forbidden in (
    "P360_IPC3_DAI_CONFIG_BYTES     112u",
    "P360_SPEAKER_DAI_VALID_BITS 24u",
    "p->sample_valid_bits!=24u",
    "p->tdm_slot_width!=32u",
):
    if forbidden in ipc3_topology_h + "\n" + ipc3_topology + "\n" + board_h:
        raise SystemExit(f"stale GLK/MAX98357A speaker ABI reintroduced: {forbidden}")


driver=(ROOT/"driver/p360_driver.c").read_text()

for token in (
    "p360_build_flags(VOID)",
    "p360_telemetry_reset(",
    "P360_TELEM_STAGE_FW_LOADED",
    "P360_TELEM_STAGE_SOF_BOOTING",
    "P360_TELEM_STAGE_FW_READY",
    "P360_TELEM_STAGE_IRQ_READY",
    "p360_telemetry_ipc(",
    "P360_TELEM_STAGE_IPC_READY",
    "P360_TELEM_STAGE_TOPOLOGY_READY",
    "P360_TELEM_STAGE_AUDIO_CORE",
    "P360_TELEM_STAGE_STREAM_STARTED",
    "P360_TELEM_STAGE_SPEAKER_ARMED",
    "P360_TELEM_STAGE_AMP_STARTED",
    "P360_TELEM_STAGE_TONE_COMPLETE",
    "P360_TELEM_STAGE_STOP_COMPLETE",
):
    if token not in driver:
        raise SystemExit(f"hardware proof telemetry milestone missing: {token}")

for token in (
    "expectedReplyBytes!=P360_IPC3_TONE_CONTROL_BYTES",
    "P360_IPC3_TONE_CONTROL_BYTES);",
):
    if token not in driver:
        raise SystemExit(f"final Tone control reply-size contract missing: {token}")

for token in (
    "p360_cs_runtime_send_ipc(",
    "p360_ipc3_tx_begin(",
    "p360_ipc_consume(",
):
    if token not in runtime_h + "\n" + runtime:
        raise SystemExit(f"generic serialized IPC3 runtime path missing: {token}")

# The legacy hostless Tone diagnostic may remain compiled behind a closed
# build gate, but it is no longer the final audio architecture. Real audio
# primitives are now expected in the WaveRT/HOST playback lifecycle.
if "#if P360_BOUNDED_TONE_TEST_ENABLED" not in driver:
    raise SystemExit("legacy bounded Tone diagnostic gate disappeared unexpectedly")

playback_h=(ROOT/"include/p360_playback.h").read_text()

for token in (
    "P360_PLAYBACK_MAX_BUFFER_BYTES (64u * 1024u)",
    "P360_PLAYBACK_PAGE_TABLE_BYTES PAGE_SIZE",
    "P360_PLAYBACK_STREAM",
    "p360_playback_stream_bind_buffer(",
    "p360_playback_stream_start(",
    "p360_playback_stream_stop(",
    "p360_playback_stream_position(",
    "p360_playback_stream_fifo_size(",
    "p360_playback_stream_retire(",
):
    if token not in playback_h:
        raise SystemExit(f"real playback stream contract missing: {token}")

for token in (
    "MmAllocateContiguousMemorySpecifyCache(",
    "MmGetMdlPfnArray(",
    "pfn>0xfffffu",
    "GetRenderStream(",
    "PrepareDSP(",
    "DSPDisableSPIB",
    "TriggerDSP(",
    "StreamPosition(",
    "CleanupDSP(",
    "FreeStream(",
):
    if token not in playback:
        raise SystemExit(f"CoolStar/SOF host DMA bridge missing: {token}")

for token in (
    "P360_HDA_GCAP_OFFSET",
    "P360_HDA_SD_BASE",
    "P360_HDA_SD_INTERVAL",
    "P360_HDA_SD_CTL_RUN",
    "P360_HDA_SD_FIFOSIZE_OFFSET",
    "p360_playback_stream_fifo_size(",
    "READ_REGISTER_USHORT(",
    "READ_REGISTER_UCHAR(",
    "captureStreams=(gcap >> 8) & 0x0fu;",
    "playbackStreams=(gcap >> 12) & 0x0fu;",
    "streamIndex=captureStreams+(ULONG)p->StreamTag-1u;",
    "p360_playback_prove_hda_run(p,TRUE)",
    "p360_playback_prove_hda_run(p,FALSE)",
    "p->Quarantined=TRUE;",
):
    if token not in playback:
        raise SystemExit(f"HDA RUN readback proof missing: {token}")

start_fn_i=playback.index("p360_playback_stream_start(")
start_trigger_i=playback.index("TriggerDSP(",start_fn_i)
start_proof_i=playback.index("p360_playback_prove_hda_run(p,TRUE)",start_trigger_i)
start_running_i=playback.index("p->Running=TRUE;",start_proof_i)
if not start_fn_i < start_trigger_i < start_proof_i < start_running_i:
    raise SystemExit("HDA START is not proved before local Running latch")

stop_fn_i=playback.index("p360_playback_stream_stop(")
stop_trigger_i=playback.index("TriggerDSP(",stop_fn_i)
stop_proof_i=playback.index("p360_playback_prove_hda_run(p,FALSE)",stop_trigger_i)
stop_running_i=playback.index("p->Running=FALSE;",stop_proof_i)
if not stop_fn_i < stop_trigger_i < stop_proof_i < stop_running_i:
    raise SystemExit("HDA STOP is not proved before local Running clear")

if "DSPEnableSPIB" in playback:
    raise SystemExit("static SPIB was reintroduced into cyclic WaveRT playback")

# The compressed SOF page table must be created from the WaveRT MDL and the
# audio MDL must remain owned by PortCls; the bridge may not allocate a second
# hidden audio buffer.
for forbidden in (
    "MmAllocatePagesForMdl(",
    "P360_CS_BOOT_DMA_BYTES",
):
    if forbidden in playback:
        raise SystemExit(f"playback bridge introduced a second audio-buffer owner: {forbidden}")

host_prepare_i=driver.index("p360_host_playback_prepare(")
active_publish_i=driver.index(
    "InterlockedCompareExchangePointer(",
    host_prepare_i)
removing_recheck_i=driver.index(
    "InterlockedCompareExchange(&ctx->Removing,0,0)!=0",
    active_publish_i)
active_withdraw_i=driver.index(
    "InterlockedCompareExchangePointer(",
    removing_recheck_i)
if not (
    host_prepare_i < active_publish_i < removing_recheck_i <
    active_withdraw_i
):
    raise SystemExit(
        "QUERY_STOP/REMOVE race can publish ActivePlayback after the PnP gate")

bind_buffer_i=driver.index("p360_playback_stream_bind_buffer(",host_prepare_i)
host_pcm_i=driver.index("p360_ipc3_build_host_pcm_params(",bind_buffer_i)
host_pcm_attempt_i=driver.index("pcmParamsAttempted=TRUE;",host_pcm_i)
host_prepare_done_i=driver.index("playback->SofParamsPrepared=TRUE;",host_pcm_attempt_i)
host_prepare_fail_i=driver.index("fail:",host_prepare_done_i)
host_prepare_quiesce_i=driver.index(
    "p360_host_playback_force_quiesce(",
    host_prepare_fail_i)
if not (
    host_prepare_i < bind_buffer_i < host_pcm_i < host_pcm_attempt_i <
    host_prepare_done_i < host_prepare_fail_i < host_prepare_quiesce_i
):
    raise SystemExit(
        "WaveRT PCM_PARAMS failure no longer forces ownership quiescence")

allocate_i=speaker_endpoint.index("P360WaveStream::AllocateAudioBuffer(")
allocate_prepare_i=speaker_endpoint.index(
    "p360_host_playback_prepare(",
    allocate_i)
allocate_fail_i=speaker_endpoint.index(
    "if (!NT_SUCCESS(status))",
    allocate_prepare_i)
allocate_release_check_i=speaker_endpoint.index(
    "p360_playback_memory_released(&m_Playback)",
    allocate_fail_i)
allocate_quarantine_mdl_i=speaker_endpoint.index(
    "m_Mdl=mdl;",
    allocate_release_check_i)
allocate_return_i=speaker_endpoint.index(
    "return status;",
    allocate_quarantine_mdl_i)
if not (
    allocate_i < allocate_prepare_i < allocate_fail_i <
    allocate_release_check_i < allocate_quarantine_mdl_i <
    allocate_return_i
):
    raise SystemExit(
        "AllocateAudioBuffer can free/lose the MDL before failed prepare ownership is gone")

host_start_i=driver.index("p360_host_playback_start(")
dma_start_i=driver.index("p360_playback_stream_start(playback)",host_start_i)
sof_start_i=driver.index("p360_ipc3_build_stream_trigger(",dma_start_i)
sof_running_latch_i=driver.index("playback->SofRunning=TRUE;",sof_start_i)
sof_start_send_i=driver.index("p360_runtime_send_zero_error(",sof_running_latch_i)
speaker_arm_i=driver.index("p360_state_speaker_arm(&ctx->State)",sof_start_send_i)
amp_start_i=driver.index("p360_csaudio_speaker_start(&ctx->CsAudio)",speaker_arm_i)
amp_mirror_i=driver.index(
    "ctx->CsAudio.SpeakerStarted",
    amp_start_i)
amp_fail_stop_i=driver.index(
    "p360_host_playback_stop(",
    amp_mirror_i)
if not (
    host_start_i < dma_start_i < sof_start_i < sof_running_latch_i <
    sof_start_send_i < speaker_arm_i < amp_start_i < amp_mirror_i <
    amp_fail_stop_i
):
    raise SystemExit(
        "HOST START ambiguity contract drifted: ownership must latch before IPC and MAX failure must stop")

host_stop_i=driver.index("p360_host_playback_stop(")
amp_stop_i=driver.index("p360_csaudio_speaker_stop(&ctx->CsAudio)",host_stop_i)
speaker_disarm_i=driver.index("p360_state_speaker_disarm(&ctx->State)",amp_stop_i)
sof_stop_i=driver.index("p360_ipc3_build_stream_trigger(",speaker_disarm_i)
dma_stop_i=driver.index("p360_playback_stream_stop(playback)",sof_stop_i)
if not host_stop_i < amp_stop_i < speaker_disarm_i < sof_stop_i < dma_stop_i:
    raise SystemExit("HOST playback STOP ordering is not MAX mute -> SOF -> HDA stop")
if "P360_TELEM_STAGE_STOP_COMPLETE" not in driver[host_stop_i:dma_stop_i+1200]:
    raise SystemExit("HOST WaveRT stop does not publish STOP_COMPLETE telemetry")

host_release_i=driver.index("p360_host_playback_release(")
pcm_free_i=driver.index("p360_ipc3_build_pcm_free(",host_release_i)
retire_i=driver.index("p360_playback_stream_retire(playback)",pcm_free_i)
if not host_release_i < pcm_free_i < retire_i:
    raise SystemExit("HOST playback release does not free SOF PCM before HDA ownership")

if "ctx->State.speaker_policy_enabled=" not in driver or    "P360_ENABLE_INTERNAL_SPEAKER ? 1u : 0u" not in driver:
    raise SystemExit("speaker policy state is not bound to the explicit compile barrier")

for token in (
    "p360_state_speaker_arm(",
    "p360_state_speaker_disarm(",
):
    if token not in state_h or token not in state:
        raise SystemExit(f"atomic speaker state transition missing: {token}")

if "to == P360_STATE_SPEAKER_ARMED" not in state or    "return 0;" not in state[state.index("to == P360_STATE_SPEAKER_ARMED"):]:
    raise SystemExit("generic state transition can still bypass speaker arm policy")
driver_entry_i=driver.index("DriverEntry(")
shell_gate_i=driver.index("#if P360_PORTCLS_SHELL_ENABLED", driver_entry_i)
shell_init_i=driver.index("p360_portcls_driver_initialize(", shell_gate_i)
kmdf_init_i=driver.index("WDF_DRIVER_CONFIG_INIT(&config,P360EvtDeviceAdd);", shell_init_i)
if not (driver_entry_i < shell_gate_i < shell_init_i < kmdf_init_i):
    raise SystemExit("PortCls shell activation gate no longer preserves KMDF baseline")

for token in (
    "p360_runtime_boot_start(",
    "p360_firmware_load(&firmware)",
    "p360_cs_runtime_prepare_dispatcher(",
    "p360_loader_run(",
    "p360_cs_runtime_bind_live(",
    "p360_runtime_boot_stop(",
    "p360_cs_runtime_stop(&ctx->Runtime)",
):
    if token not in driver:
        raise SystemExit(f"compiled dormant runtime handoff missing: {token}")

if "#error P360_RUNTIME_BOOT_ENABLED" in driver:
    raise SystemExit("runtime handoff is still hidden behind a compile-time #error")

policy_i=driver.index("p360_runtime_boot_policy_enabled(VOID)")
host_entry_i=driver.index("p360_host_d0_entry(")
boot_gate_i=driver.index("if (p360_runtime_boot_policy_enabled())", host_entry_i)
boot_call_i=driver.index("return p360_runtime_boot_start(ctx);", boot_gate_i)
entry_i=driver.index("P360EvtD0Entry(", boot_call_i)
entry_forward_i=driver.index("return p360_host_d0_entry(", entry_i)
host_exit_i=driver.index("p360_host_d0_exit(", entry_forward_i)
stop_gate_i=driver.index("if (p360_runtime_boot_policy_enabled())", host_exit_i)
stop_call_i=driver.index("return p360_runtime_boot_stop(ctx);", stop_gate_i)
exit_i=driver.index("P360EvtD0Exit(", stop_call_i)
exit_forward_i=driver.index("return p360_host_d0_exit(", exit_i)
if not (
    policy_i < host_entry_i < boot_gate_i < boot_call_i <
    entry_i < entry_forward_i < host_exit_i < stop_gate_i <
    stop_call_i < exit_i < exit_forward_i
):
    raise SystemExit("shell-neutral D0 runtime policy ordering drifted")

start_i=driver.index("p360_runtime_boot_start(")
loader_i=driver.index("p360_loader_run(", start_i)
loader_telem_i=driver.index("p360_telemetry_loader(", loader_i)
ready_i=driver.index("result.ready_proved", loader_telem_i)
bind_live_i=driver.index("p360_cs_runtime_bind_live(", ready_i)
probe_gate_i=driver.index("if (p360_ipc_probe_policy_enabled())", bind_live_i)
probe_call_i=driver.index("p360_cs_runtime_probe_ipc(", probe_gate_i)
ipc_flag_i=driver.index("ctx->State.ipc_ready=1;", probe_call_i)
ipc_state_i=driver.index("P360_STATE_IPC_READY", ipc_flag_i)
if not (start_i < loader_i < loader_telem_i < ready_i < bind_live_i < probe_gate_i <
        probe_call_i < ipc_flag_i < ipc_state_i):
    raise SystemExit("SOF boot -> FW_READY -> IRQ -> real IPC3 proof ordering drifted")

host_policy_i=driver.index("if (p360_host_playback_policy_enabled())", ipc_state_i)
host_prepare_call_i=driver.index("p360_runtime_prepare_host_topology(", host_policy_i)
helper_i=driver.index("p360_runtime_prepare_host_topology(")
helper_body_i=driver.index("{", helper_i)
host_new_i=driver.index("p360_ipc3_build_host_new(", helper_body_i)
buffer_new_i=driver.index("p360_ipc3_build_playback_buffer_new(", host_new_i)
dai_new_i=driver.index("p360_ipc3_build_playback_dai_new(", buffer_new_i)
dai_cfg_i=driver.index("p360_ipc3_build_ssp1_config(", dai_new_i)
connect1_i=driver.index("p360_ipc3_build_connect(", dai_cfg_i)
connect2_i=driver.index("p360_ipc3_build_connect(", connect1_i + 1)
pipe_new_i=driver.index("p360_ipc3_build_playback_pipe_new(", connect2_i)
pipe_done_i=driver.index("p360_ipc3_build_playback_pipe_complete(", pipe_new_i)
top_flag_i=driver.index("ctx->State.topology_ready=1;", pipe_done_i)
top_state_i=driver.index("P360_STATE_TOPOLOGY_READY", top_flag_i)
core_flag_i=driver.index("ctx->State.audio_core_ready=1;", top_state_i)
core_state_i=driver.index("P360_STATE_AUDIO_CORE_READY", core_flag_i)
if not (
    ipc_state_i < host_policy_i < host_prepare_call_i and
    helper_body_i < host_new_i < buffer_new_i < dai_new_i < dai_cfg_i <
    connect1_i < connect2_i < pipe_new_i < pipe_done_i <
    top_flag_i < top_state_i < core_flag_i < core_state_i
):
    raise SystemExit("SOF HOST -> buffer -> SSP1 DMA topology ordering drifted")

for token in (
    "#define P360_IPC3_COMP_HOST   1u",
    "#define P360_IPC3_HOST_NEW_BYTES        76u",
    "p360_ipc3_build_host_new(",
    "p360_ipc3_build_playback_buffer_new(",
    "p360_ipc3_build_playback_dai_new(",
    "p360_ipc3_build_playback_pipe_new(",
    "p360_ipc3_build_host_pcm_params(",
    "p360_ipc3_build_pcm_free(",
    "P360_IPC3_TIME_DMA",
):
    if token not in ipc3_topology_h + "\n" + ipc3_topology:
        raise SystemExit(f"SOF HOST IPC3 contract missing: {token}")

for token in (
    "p360_host_prepare(",
    "p360_host_release(",
    "p360_host_d0_entry(",
    "p360_host_d0_exit(",
):
    if token not in driver_h:
        raise SystemExit(f"shell-neutral host lifecycle declaration missing: {token}")

release_i=driver.index("p360_host_release(")
release_amp_close_i=driver.index("p360_csaudio_close(&ctx->CsAudio)", release_i)
release_stop_i=driver.index("p360_cs_runtime_stop(&ctx->Runtime)", release_amp_close_i)
release_destroy_i=driver.index("p360_cs_runtime_destroy(&ctx->Runtime)", release_stop_i)
release_retire_i=driver.index("p360_cs_boot_adapter_retire(&ctx->Boot)", release_destroy_i)
release_bus_i=driver.index("p360_cs_bus_close(&ctx->Bus)", release_retire_i)
if not (
    release_i < release_amp_close_i < release_stop_i < release_destroy_i <
    release_retire_i < release_bus_i
):
    raise SystemExit("host release no longer proves runtime -> boot -> bus teardown ordering")

if "ctx->BoundedToneConsumed=FALSE;" not in driver:
    raise SystemExit("bounded Tone one-shot latch is not reset on hardware prepare")

endpoint_uninstall_i=portcls_shell.index("p360_speaker_endpoint_uninstall(")
endpoint_d0_exit_i=portcls_shell.index("p360_host_d0_exit(ctx);", endpoint_uninstall_i)
if not endpoint_uninstall_i < endpoint_d0_exit_i:
    raise SystemExit("speaker endpoint teardown must precede DSP D0 exit")

for token in (
    "IRP_MN_QUERY_STOP_DEVICE",
    "IRP_MN_QUERY_REMOVE_DEVICE",
    "IRP_MN_CANCEL_STOP_DEVICE",
    "IRP_MN_CANCEL_REMOVE_DEVICE",
    "p360_portcls_begin_pnp_query(",
    "p360_portcls_cancel_pnp_query(",
    "p360_portcls_mark_quarantined(",
    "IoCompleteRequest(Irp,IO_NO_INCREMENT);",
    "volatile LONG Quarantined;",
):
    if token not in portcls_shell:
        raise SystemExit(f"PnP fail-closed lifecycle contract missing: {token}")

query_i=portcls_shell.index("case IRP_MN_QUERY_STOP_DEVICE:")
query_gate_i=portcls_shell.index(
    "p360_portcls_begin_pnp_query(DeviceObject)",
    query_i)
query_fail_complete_i=portcls_shell.index(
    "IoCompleteRequest(Irp,IO_NO_INCREMENT);",
    query_gate_i)
stop_i=portcls_shell.index("case IRP_MN_STOP_DEVICE:",query_fail_complete_i)
stop_cleanup_i=portcls_shell.index(
    "p360_portcls_cleanup_instance(DeviceObject)",
    stop_i)
surprise_i=portcls_shell.index(
    "case IRP_MN_SURPRISE_REMOVAL:",
    stop_cleanup_i)
remove_i=portcls_shell.index(
    "case IRP_MN_REMOVE_DEVICE:",
    surprise_i)
dispatch_i=portcls_shell.index(
    "return PcDispatchIrp(DeviceObject,Irp);",
    remove_i)
if not (
    query_i < query_gate_i < query_fail_complete_i <
    stop_i < stop_cleanup_i < surprise_i <= remove_i < dispatch_i
):
    raise SystemExit("PnP query-veto/mandatory-success ordering drifted")

mandatory_block=portcls_shell[stop_i:dispatch_i]
for forbidden in (
    "return cleanupStatus;",
    "Irp->IoStatus.Status=cleanupStatus;",
):
    if forbidden in mandatory_block:
        raise SystemExit(
            f"mandatory STOP/REMOVE path can still be failed: {forbidden}")

print("Phaser360 runtime lifecycle contract: PASS")


firmware_h=(ROOT/"include/p360_firmware.h").read_text()
firmware=(ROOT/"src/p360_firmware.c").read_text()

if r"\\SystemRoot\\System32\\drivers\\P360\\p360-f686.ri" not in firmware_h:
    raise SystemExit("firmware provider fixed path missing")

loader_h=(ROOT/"sof_core/loader/p360_loader.h").read_text()
if "P360_FW_FILE_BYTES 246528u" not in loader_h:
    raise SystemExit("firmware provider exact size contract missing")

for token in (
    "ZwCreateFile(",
    "ZwQueryInformationFile(",
    "ZwReadFile(",
    "p360_fw_validate(",
    "STATUS_INVALID_IMAGE_HASH",
):
    if token not in firmware:
        raise SystemExit(f"validated firmware load gate missing: {token}")

if "P360_RUNTIME_BOOT_ENABLED 0" not in driver_h:
    raise SystemExit("firmware provider was added but runtime boot barrier is not closed")

print("Phaser360 firmware-provider contract: PASS")


# PRE-AUDIO start-failure diagnostics must identify the exact PrepareHardware
# substep and preserve the minimal pre-audio/speaker separation.
for token in (
    "P360_PREP_STEP_BUS_QUERY_INTERFACE",
    "P360_PREP_STEP_BUS_ABI_VALIDATE",
    "P360_PREP_STEP_BUS_GET_RESOURCES",
    "P360_PREP_STEP_BUS_VALIDATE",
    "P360_PREP_STEP_PCI_IDENTITY",
    "P360_PREP_STEP_NHLT_PARSE",
    "P360_PREP_STEP_BOOT_ADAPTER",
    "P360_PREP_STEP_RUNTIME_CREATE",
    "P360_PREP_STEP_CSAUDIO_OPEN",
    "PrepareNtStatus",
):
    if token not in telemetry_h + "\n" + telemetry + "\n" + driver + "\n" + cs_bus:
        raise SystemExit(f"prepare diagnostic contract missing: {token}")

for token in (
    "TARGET_START_REPAIR=BEGIN",
    "Get-DeviceProblemStatusHex",
    "Get-PrepareStepName",
    "Get-PrepareDetailText",
    "Get-NtStatusName",
    "Get-LiveDriverIdentityOrNull",
    "DEVPKEY_Device_DriverInfPath",
    "DEVPKEY_Device_DriverVersion",
    "DEVPKEY_Device_DriverProvider",
    "FAIL_DIAGNOSTIC=",
    "PrepareNtStatus",
):
    if token not in runner:
        raise SystemExit(f"hardware gate exact-failure diagnostic missing: {token}")

amp_install_gate_i=runner.index("Install-SafeAmpPackage $info $ampId")
amp_ready_gate_i=runner.index("AMP_SAFE_READY=PASS",amp_install_gate_i)
final_stack_phase_gate_i=runner.index('Write-RunLog "FINAL_STACK_INSTALL=BEGIN"',amp_ready_gate_i)
final_core_gate_i=runner.index("$telemetry=Ensure-FinalCoreReady",final_stack_phase_gate_i)
if not (
    amp_install_gate_i < amp_ready_gate_i <
    final_stack_phase_gate_i < final_core_gate_i
):
    raise SystemExit("safe MAX98357A proof is not ahead of self-healing final core bind")


if "attributes.ExecutionLevel = WdfExecutionLevelDispatch" in runtime:
    raise SystemExit("WDFDPC still forces an invalid explicit ExecutionLevel")
for token in (
    "P360_PREP_RUNTIME_SPINLOCK_CREATE",
    "P360_PREP_RUNTIME_DPC_CREATE",
    "P360_PREP_RUNTIME_COMPLETE",
    "WdfDpcCreate(",
):
    if token not in telemetry_h + "\n" + runtime:
        raise SystemExit(f"runtime-create exact diagnostic/fix missing: {token}")

print("Phaser360 exact start-failure diagnostic contract: PASS")

print("Phaser360 source contract: PASS")
