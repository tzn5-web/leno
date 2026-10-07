#!/usr/bin/env python3
from pathlib import Path
import hashlib
import re
import sys

ROOT=Path(__file__).resolve().parents[1]

PINNED={
    "sof_core/p360_transport_core.c":"fe593c280b7d66a152fe28997b9e76ed5eecc59105ffddc1cc1acccdb642fbee",
    "sof_core/p360_transport_core.h":"e89e42e0ba5119dbd4670fa607f6e81d33f19c25eeb744df08e6713c661c41d5",
    "sof_core/loader/p360_loader.c":"476a53cab8901a891a53a76eddfdb1b5f64dbdf270bfe0cbb3211e0623c05379",
    "sof_core/loader/p360_loader.h":"358dac81c37edcda164c4f075b7ed7644e989570221f0c29be43ce56cdd3d1df",
    "sof_core/loader/p360_fw_image.c":"3b370ae00596ff8ae3f3ca4c30e62a078a9c178af6a261c4d0009164854b6ab7",
    "sof_core/loader/p360_ipc_timer.c":"37148efb6a24877ae4379038eb1c108ab8b8f02824a5bfda1051b2d21454a0e9",
    "sof_core/loader/p360_ipc_timer.h":"2df15b4d9e0b16380d96503e83192e03e5d4685121f36a27e11af9b4e7e891d3",
    "sof_core/loader/p360_irq.c":"04dae608b067e3c7d4bf399f025a30a5cf0a2dc37737cea686bd1b033f813d81",
    "sof_core/loader/p360_irq.h":"0afd7c95168b4bb27db871e48c4acd10f92ff808394ad66c733f83fb2164e42d",
}

for rel,want in PINNED.items():
    p=ROOT/rel
    if not p.is_file():
        raise SystemExit(f"missing pinned B4 file: {rel}")
    got=hashlib.sha256(p.read_bytes()).hexdigest()
    if got!=want:
        raise SystemExit(f"B4 provenance drift: {rel}: {got} != {want}")

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

print("Phaser360 source contract: PASS")


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
state_h=(ROOT/"include/p360_state.h").read_text()
state=(ROOT/"src/p360_state.c").read_text()

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
    "ExCreateCallback(",
    "ExRegisterCallback(",
    "ExNotifyCallback(",
    "C_ASSERT(sizeof(P360_CSAUDIO_ARG) == 24)",
):
    if token not in csaudio_h + "\n" + csaudio:
        raise SystemExit(f"CoolStar CSAudio bridge contract missing: {token}")

for p in ROOT.rglob("*"):
    if p.suffix.lower() not in (".c",".h",".cpp"):
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

if not re.search(r"#define\s+P360_TONE_TOPOLOGY_PROOF_ENABLED\s+0\b", driver_h):
    raise SystemExit("hostless Tone topology proof barrier is not closed by default")

if not re.search(r"#define\s+P360_BOUNDED_TONE_TEST_ENABLED\s+0\b", driver_h):
    raise SystemExit("bounded Tone test barrier is not closed by default")

if "#define P360_BOUNDED_TONE_DURATION_MS 250u" not in driver_h:
    raise SystemExit("bounded Tone duration drifted from reviewed 250 ms proof")

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
    "return STATUS_DEVICE_NOT_READY;",
):
    if token not in speaker_endpoint:
        raise SystemExit(f"speaker WaveRT shell contract missing: {token}")

if "p360_csaudio_speaker_start(" in speaker_endpoint:
    raise SystemExit("speaker amplifier START is wired before SOF stream backend exists")

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
    "P360_TONE_TOPOLOGY_PROOF_ENABLED=$(P360ToneTopologyProofEnabled)",
    "P360_ENABLE_INTERNAL_SPEAKER=$(P360InternalSpeakerEnabled)",
    "P360_BOUNDED_TONE_TEST_ENABLED=$(P360BoundedToneTestEnabled)",
):
    if token not in project:
        raise SystemExit(f"staged audio build gate is not parameterized: {token}")

workflow=(ROOT.parent/".github/workflows/phaser360-windows.yml").read_text()
for token in (
    "/p:P360PortClsShellEnabled=1",
    "/p:P360RuntimeBootEnabled=0",
    "/p:P360RuntimeBootEnabled=1",
    "/p:P360IpcProbeEnabled=1",
    "/p:P360SpeakerEndpointEnabled=1",
    "/p:P360ToneTopologyProofEnabled=1",
    "/p:P360InternalSpeakerEnabled=1",
    "/p:P360BoundedToneTestEnabled=1",
    "P360SofAudio-portcls-shell.sys",
    "P360SofAudio-preaudio-ipc3.sys",
    "P360SofAudio-preaudio-ipc3.pdb",
    "PORTCLS_TONE_TOPOLOGY_PROOF_COMPILE=PASS",
    "PORTCLS_BOUNDED_TONE_TEST_COMPILE=PASS",
    "P360SofAudio-bounded-tone-test.sys",
    "P360SofAudio-bounded-tone-test.pdb",
    "P360SofAudio.inx",
    "P360_FIRMWARE_MANIFEST.txt",
    "PORTCLS_SPEAKER_ENDPOINT_COMPILE=PASS",
    "PORTCLS_SOF_BOOT_COMPILE=PASS",
    "PORTCLS_SOF_IPC3_PROOF_COMPILE=PASS",
):
    if token not in workflow:
        raise SystemExit(f"active PortCls linkage CI build missing: {token}")

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
    "extern \"C\" {",
):
    if token not in driver_h:
        raise SystemExit(f"PortCls shell C ABI/lifetime contract missing: {token}")

inf=(ROOT/"driver/P360SofAudio.inx").read_text()
for token in (
    "Class=System",
    "ClassGuid={4D36E97D-E325-11CE-BFC1-08002BE10318}",
    r"CSAUDIO\ADSP&CTLR_VEN_8086&CTLR_DEV_3198",
):
    if token not in inf:
        raise SystemExit(f"proven Phaser360 System-class binding contract missing: {token}")
for forbidden in (
    "Class=MEDIA",
    "ksthunk",
    "KS.Registration",
    "WDMAUDIO.Registration",
):
    if forbidden in inf:
        raise SystemExit(f"known-bad Phaser360 class/stack regression reintroduced: {forbidden}")

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
    "p360_ipc3_build_stream_trigger(",
):
    if token not in (ipc3_topology_h + "\n" + ipc3_topology):
        raise SystemExit(f"IPC3 speaker topology ABI contract missing: {token}")

if "tests/ipc3_topology_regression.c" not in run_b4:
    raise SystemExit("IPC3 speaker topology regression is not in the B4 gate")

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
    "p360_cs_runtime_send_ipc(",
    "p360_ipc3_tx_begin(",
    "p360_ipc_consume(",
):
    if token not in runtime_h + "\n" + runtime:
        raise SystemExit(f"generic serialized IPC3 runtime path missing: {token}")

bounded_call=driver.find(
    "if (p360_bounded_tone_policy_enabled() &&\n"
    "        !ctx->BoundedToneConsumed)")
if bounded_call < 0:
    raise SystemExit("bounded Tone one-shot is not skipped after first D0 lifetime run")

bounded_begin=driver.find("#if P360_BOUNDED_TONE_TEST_ENABLED")
bounded_end=driver.find(
    "#endif\n\nstatic NTSTATUS\np360_loader_status_to_ntstatus",
    bounded_begin)
if bounded_begin < 0 or bounded_end < 0:
    raise SystemExit("bounded speaker proof block is missing")
bounded_block=driver[bounded_begin:bounded_end]

for forbidden in (
    "p360_ipc3_build_stream_trigger(",
    "p360_csaudio_speaker_start(",
):
    if driver.count(forbidden) != bounded_block.count(forbidden):
        raise SystemExit(
            f"audio-start primitive escaped bounded speaker gate: {forbidden}")

for token in (
    "ctx->BoundedToneConsumed=TRUE;",
    "p360_ipc3_build_stream_trigger(",
    "p360_state_speaker_arm(&ctx->State)",
    "p360_csaudio_speaker_start(&ctx->CsAudio)",
    "P360_BOUNDED_TONE_DURATION_MS",
    "KeDelayExecutionThread(",
    "p360_csaudio_speaker_stop(&ctx->CsAudio)",
    "p360_state_speaker_disarm(&ctx->State)",
):
    if token not in bounded_block:
        raise SystemExit(f"bounded speaker proof contract missing: {token}")

if bounded_block.count("p360_ipc3_build_stream_trigger(") != 2:
    raise SystemExit("bounded speaker proof must contain exactly START and STOP triggers")

bounded_start_i=bounded_block.index("p360_ipc3_build_stream_trigger(")
bounded_arm_i=bounded_block.index("p360_state_speaker_arm(&ctx->State)")
bounded_amp_start_i=bounded_block.index("p360_csaudio_speaker_start(&ctx->CsAudio)")
bounded_delay_i=bounded_block.index("KeDelayExecutionThread(")
bounded_amp_stop_i=bounded_block.index("p360_csaudio_speaker_stop(&ctx->CsAudio)")
bounded_disarm_i=bounded_block.index("p360_state_speaker_disarm(&ctx->State)")
bounded_stop_i=bounded_block.index(
    "p360_ipc3_build_stream_trigger(",
    bounded_start_i + 1)
if not (
    bounded_start_i < bounded_arm_i < bounded_amp_start_i <
    bounded_delay_i < bounded_amp_stop_i < bounded_disarm_i <
    bounded_stop_i
):
    raise SystemExit("bounded speaker START/STOP safety ordering drifted")

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
ready_i=driver.index("result.ready_proved", loader_i)
bind_live_i=driver.index("p360_cs_runtime_bind_live(", ready_i)
probe_gate_i=driver.index("if (p360_ipc_probe_policy_enabled())", bind_live_i)
probe_call_i=driver.index("p360_cs_runtime_probe_ipc(", probe_gate_i)
ipc_flag_i=driver.index("ctx->State.ipc_ready=1;", probe_call_i)
ipc_state_i=driver.index("P360_STATE_IPC_READY", ipc_flag_i)
if not (start_i < loader_i < ready_i < bind_live_i < probe_gate_i <
        probe_call_i < ipc_flag_i < ipc_state_i):
    raise SystemExit("SOF boot -> FW_READY -> IRQ -> real IPC3 proof ordering drifted")

tone_policy_i=driver.index("if (p360_tone_topology_policy_enabled())", ipc_state_i)
tone_prepare_call_i=driver.index("p360_runtime_prepare_tone_topology(", tone_policy_i)
helper_i=driver.index("p360_runtime_prepare_tone_topology(")
helper_body_i=driver.index("{", helper_i)
tone_new_i=driver.index("p360_ipc3_build_tone_new(", helper_body_i)
buffer_new_i=driver.index("p360_ipc3_build_buffer_new(", tone_new_i)
dai_new_i=driver.index("p360_ipc3_build_dai_new(", buffer_new_i)
dai_cfg_i=driver.index("p360_ipc3_build_ssp1_config(", dai_new_i)
connect1_i=driver.index("p360_ipc3_build_connect(", dai_cfg_i)
connect2_i=driver.index("p360_ipc3_build_connect(", connect1_i + 1)
pipe_new_i=driver.index("p360_ipc3_build_pipe_new(", connect2_i)
pipe_done_i=driver.index("p360_ipc3_build_pipe_complete(", pipe_new_i)
top_flag_i=driver.index("ctx->State.topology_ready=1;", pipe_done_i)
top_state_i=driver.index("P360_STATE_TOPOLOGY_READY", top_flag_i)
pcm_i=driver.index("p360_ipc3_build_pcm_params(", top_state_i)
core_flag_i=driver.index("ctx->State.audio_core_ready=1;", pcm_i)
core_state_i=driver.index("P360_STATE_AUDIO_CORE_READY", core_flag_i)
if not (
    ipc_state_i < tone_policy_i < tone_prepare_call_i and
    helper_body_i < tone_new_i < buffer_new_i < dai_new_i < dai_cfg_i <
    connect1_i < connect2_i < pipe_new_i < pipe_done_i <
    top_flag_i < top_state_i < pcm_i < core_flag_i < core_state_i
):
    raise SystemExit("hostless Tone -> SSP1 topology/prepare ordering drifted")

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
