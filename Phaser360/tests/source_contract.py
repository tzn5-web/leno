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
    "Stable(io,ctx,P360_HOST_DOWNBOX,reply,size)",
    "Stable(io,ctx,P360_STREAM_BOX,position,76)",
):
    if token not in dispatch:
        raise SystemExit(f"dispatcher mailbox routing contract missing: {token}")

# SOF IPC3 command replies share HOST_DOWNBOX with requests. A stable bounded
# header permits a generic negative reply for failed structured commands;
# successful NEW/PCM_PARAMS replies must match their 20-byte exact contract.
# All validation must finish before the hardware ACK.
for token in (
    "uint8_t reply[20],position[76]",
    "uint8_t header[12],other[12]",
    "io->copy(ctx,P360_HOST_DOWNBOX,header,sizeof(header))",
    "io->copy(ctx,P360_HOST_DOWNBOX,other,sizeof(other))",
    "if(size!=12u && size!=20u) return -1",
    "if(header[i]!=reply[i]) return -1",
    "(d->expected_reply_bytes!=12u && d->expected_reply_bytes!=20u)",
    "ReadReply(io,ctx,reply,&reply_bytes)",
    "generic_reply=reply_bytes==12u && U32(reply+4)==0x10000000u",
    "if(!d->expected_generic && Signed32(U32(reply+8))>=0)",
    "if(d->expected_generic || reply_bytes!=20u",
    "U32(reply+4)!=d->expected_reply_cmd",
    "d->expected_reply_bytes!=20u",
    "d->expected_reply_cmd!=0x60010000u",
    "!TopologyNewCommand(d->expected_reply_cmd)",
    "U32(reply+8)!=0",
    "U32(reply+12)!=d->expected_comp_id",
    "if(TopologyNewCommand(d->expected_reply_cmd) && U32(reply+16)!=0)",
    "if(generic_reply)",
    "CompleteStructured(&next,reply,reply_bytes)",
):
    if token not in dispatch:
        raise SystemExit(f"IPC3 exact reply contract missing: {token}")

process_i=dispatch.index("int p360_dispatch_process(")
reply_read_i=dispatch.index(
    "ReadReply(io,ctx,reply,&reply_bytes)", process_i)
reply_command_i=dispatch.index("U32(reply+4)!=d->expected_reply_cmd", reply_read_i)
reply_component_i=dispatch.index("U32(reply+12)!=d->expected_comp_id", reply_command_i)
structured_complete_i=dispatch.index(
    "CompleteStructured(&next,reply,reply_bytes)", reply_component_i)
finish_i=dispatch.index("if(io->finish(ctx,e))", structured_complete_i)
publish_i=dispatch.index("d->ipc=next;", finish_i)
if not (process_i < reply_read_i < reply_command_i < reply_component_i <
        structured_complete_i < finish_i < publish_i):
    raise SystemExit("IPC3 reply validation/ACK/publication ordering drifted")

if "Stable(io,ctx,P360_DSP_UPBOX,reply" in dispatch or \
        "io->copy(ctx,P360_DSP_UPBOX,header" in dispatch:
    raise SystemExit("IPC3 command reply was routed to DSP notification UPBOX")

topology_new=re.search(
    r"static int TopologyNewCommand\(uint32_t command\)\s*\{([^}]+)\}",
    dispatch)
if topology_new is None:
    raise SystemExit("IPC3 structured topology NEW reply allowlist missing")
allowlist=re.sub(r"/\*.*?\*/", "", topology_new.group(1), flags=re.S)
allowlist=re.sub(r"\s+", "", allowlist)
if allowlist != ("returncommand==0x30010000u||command==0x30100000u||"
                 "command==0x30200000u;"):
    raise SystemExit("IPC3 structured topology NEW reply allowlist drifted")

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
    raise SystemExit("hostless topology proof barrier was enabled in the default driver")

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
    "P360SofAudio-portcls-shell.sys",
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

tx_compact=re.sub(r"\s+", "", ipc3_tx)
expect_token="p360_dispatch_expect_message(d,io->now(context),timeout_ms,message,bytes)"
if expect_token not in tx_compact:
    raise SystemExit("IPC3 TX no longer binds the pending reply to the exact message")
expect_i=tx_compact.index(expect_token)
write_i=tx_compact.index("io->write_box(context,P360_HOST_DOWNBOX,message,bytes)", expect_i)
doorbell_i=tx_compact.index("io->write32(context,P360_DSP_HIPCI,P360_HIPCI_BUSY)", write_i)
if not expect_i < write_i < doorbell_i:
    raise SystemExit("IPC3 request expectation/mailbox/doorbell ordering drifted")

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
    "d->expected_comp_id=command==0x60010000u ? comp_id : 0u",
    "U32(reply+12)!=d->expected_comp_id",
    "CompleteStructured(&next,reply,reply_bytes)",
):
    if token not in dispatch:
        raise SystemExit(f"structured IPC3 reply validation missing: {token}")

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

if "p360_csaudio_speaker_start(" in driver:
    raise SystemExit("speaker START wired before topology/audio-core activation gate")

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
