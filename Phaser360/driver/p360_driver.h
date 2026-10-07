#pragma once

#include <ntddk.h>
#include <wdf.h>

#include "../include/p360_state.h"
#include "../include/p360_board.h"
#include "../include/p360_nhlt.h"
#include "../include/p360_cs_bus.h"
#include "../include/p360_cs_boot.h"
#include "../include/p360_cs_runtime.h"
#include "../include/p360_firmware.h"
#include "../include/p360_telemetry.h"
#include "../include/p360_csaudio.h"
#include "../include/p360_playback.h"
#include "../include/p360_safety.h"
#include "../sof_core/loader/p360_loader.h"
#include "../sof_core/loader/p360_ipc3_topology.h"

/*
 * Same final driver, staged safely. This switch controls only whether D0Entry
 * starts the already-integrated SOF loader; it does not select a probe driver.
 */
#ifndef P360_RUNTIME_BOOT_ENABLED
#define P360_RUNTIME_BOOT_ENABLED 0
#endif

/*
 * Final endpoint shell gate. PortCls bridge code is compiled and audited, but
 * the active DriverEntry remains the current KMDF host until the PortCls
 * adapter lifecycle is complete.
 */
#ifndef P360_PORTCLS_SHELL_ENABLED
#define P360_PORTCLS_SHELL_ENABLED 0
#endif

#ifndef P360_IPC_PROBE_ENABLED
#define P360_IPC_PROBE_ENABLED 0
#endif

#ifndef P360_SPEAKER_ENDPOINT_ENABLED
#define P360_SPEAKER_ENDPOINT_ENABLED 0
#endif

/*
 * Real Windows playback path:
 * WaveRT HOST -> CoolStar HDA render DMA -> SOF HOST -> SSP1 -> MAX98357A.
 */
#ifndef P360_HOST_PLAYBACK_ENABLED
#define P360_HOST_PLAYBACK_ENABLED 0
#endif

/*
 * Hostless Tone -> SSP1 topology/prepare proof. This can program the DSP/SSP
 * when explicitly enabled, but it never starts the stream or speaker amp.
 */
#ifndef P360_TONE_TOPOLOGY_PROOF_ENABLED
#define P360_TONE_TOPOLOGY_PROOF_ENABLED 0
#endif

/*
 * One-shot internal-speaker diagnostic. It is compiled out by default and is
 * only valid together with the proved SOF/IPC/topology chain and the explicit
 * internal-speaker safety override.
 */
#ifndef P360_BOUNDED_TONE_TEST_ENABLED
#define P360_BOUNDED_TONE_TEST_ENABLED 0
#endif

/*
 * Final one-click internal-speaker diagnostic. The SOF Tone generator is
 * programmed before PCM_PARAMS/prepare to 0.5% full-scale (about -46 dBFS)
 * and independently capped in firmware to 16000 x 125 us = 2 seconds.
 */
#define P360_BOUNDED_TONE_DURATION_MS 2000u
#define P360_DIAGNOSTIC_TONE_Q1_31 P360_IPC3_TONE_HALF_PERCENT_Q1_31
#define P360_DIAGNOSTIC_TONE_BLOCKS P360_IPC3_TONE_TWO_SECONDS_BLOCKS

#if P360_BOUNDED_TONE_TEST_ENABLED && \
    (!P360_RUNTIME_BOOT_ENABLED || !P360_IPC_PROBE_ENABLED || \
     !P360_TONE_TOPOLOGY_PROOF_ENABLED || !P360_ENABLE_INTERNAL_SPEAKER)
#error P360_BOUNDED_TONE_TEST_ENABLED requires all reviewed speaker proof gates
#endif


typedef struct _P360_DEVICE_CONTEXT {
    P360_STATE_MACHINE State;
    P360_NHLT_FACTS Nhlt;
    struct p360_pci_identity Identity;

    P360_CS_BUS Bus;
    P360_CS_BOOT_ADAPTER Boot;
    P360_CS_RUNTIME Runtime;
    P360_CSAUDIO_LINK CsAudio;
    struct p360_loader Loader;
    ULONGLONG BootEpoch;

    WDFDEVICE FrameworkDevice;
    PDEVICE_OBJECT PortClsFdo;
    PVOID SpeakerTopologyPort;
    PVOID SpeakerWavePort;

    BOOLEAN BusOpen;
    BOOLEAN BootInitialized;
    BOOLEAN RuntimeInitialized;
    BOOLEAN CsAudioInitialized;
    BOOLEAN SpeakerEndpointInstalled;
    BOOLEAN BoundedToneConsumed;
    BOOLEAN Prepared;
    volatile LONG Removing;
} P360_DEVICE_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(P360_DEVICE_CONTEXT,P360GetContext)

#ifdef __cplusplus
extern "C" {
#endif

NTSTATUS p360_host_prepare(
    _Inout_ P360_DEVICE_CONTEXT *ctx,
    _In_ WDFDEVICE Device);
NTSTATUS p360_host_release(
    _Inout_ P360_DEVICE_CONTEXT *ctx);
NTSTATUS p360_host_d0_entry(
    _Inout_ P360_DEVICE_CONTEXT *ctx);
NTSTATUS p360_host_d0_exit(
    _Inout_ P360_DEVICE_CONTEXT *ctx);

NTSTATUS p360_host_playback_prepare(
    _Inout_ P360_DEVICE_CONTEXT *ctx,
    _Inout_ P360_PLAYBACK_STREAM *playback,
    _In_ PMDL audioMdl,
    _In_ ULONG bufferBytes,
    _In_ ULONG periodBytes);
NTSTATUS p360_host_playback_start(
    _Inout_ P360_DEVICE_CONTEXT *ctx,
    _Inout_ P360_PLAYBACK_STREAM *playback);
NTSTATUS p360_host_playback_stop(
    _Inout_ P360_DEVICE_CONTEXT *ctx,
    _Inout_ P360_PLAYBACK_STREAM *playback);
NTSTATUS p360_host_playback_release(
    _Inout_ P360_DEVICE_CONTEXT *ctx,
    _Inout_ P360_PLAYBACK_STREAM *playback);

NTSTATUS p360_portcls_driver_initialize(
    _In_ PDRIVER_OBJECT DriverObject,
    _In_ PUNICODE_STRING RegistryPath);

DRIVER_INITIALIZE DriverEntry;
EVT_WDF_DRIVER_DEVICE_ADD P360EvtDeviceAdd;
EVT_WDF_DEVICE_PREPARE_HARDWARE P360EvtPrepareHardware;
EVT_WDF_DEVICE_RELEASE_HARDWARE P360EvtReleaseHardware;
EVT_WDF_DEVICE_D0_ENTRY P360EvtD0Entry;
EVT_WDF_DEVICE_D0_EXIT P360EvtD0Exit;

#ifdef __cplusplus
}
#endif
