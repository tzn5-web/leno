#pragma once

#include <ntddk.h>

#define P360_TELEM_STAGE_RESET          0u
#define P360_TELEM_STAGE_FW_LOADED      10u
#define P360_TELEM_STAGE_SOF_BOOTING    20u
#define P360_TELEM_STAGE_FW_READY       30u
#define P360_TELEM_STAGE_IRQ_READY      40u
#define P360_TELEM_STAGE_IPC_READY      50u
#define P360_TELEM_STAGE_TOPOLOGY_READY 60u
#define P360_TELEM_STAGE_AUDIO_CORE     70u
#define P360_TELEM_STAGE_STREAM_STARTED 80u
#define P360_TELEM_STAGE_SPEAKER_ARMED  90u
#define P360_TELEM_STAGE_AMP_STARTED    100u
#define P360_TELEM_STAGE_TONE_COMPLETE  110u
#define P360_TELEM_STAGE_STOP_COMPLETE  120u

/*
 * PrepareHardware diagnostic steps. These are deliberately separate from the
 * runtime Stage milestones so a failed device start can report the exact
 * substep without being mistaken for FW/IRQ/IPC proof.
 */
#define P360_PREP_STEP_NONE                0u
#define P360_PREP_STEP_HOST_BEGIN          1u
#define P360_PREP_STEP_BUS_QUERY_INTERFACE 2u
#define P360_PREP_STEP_BUS_ABI_VALIDATE    3u
#define P360_PREP_STEP_BUS_GET_RESOURCES   4u
#define P360_PREP_STEP_BUS_VALIDATE        5u
#define P360_PREP_STEP_PCI_IDENTITY        6u
#define P360_PREP_STEP_NHLT_PARSE          7u
#define P360_PREP_STEP_STATE_READY         8u
#define P360_PREP_STEP_BOOT_ADAPTER        9u
#define P360_PREP_STEP_RUNTIME_CREATE     10u
#define P360_PREP_STEP_CSAUDIO_OPEN       11u
#define P360_PREP_STEP_COMPLETE           12u

/* PrepareDetail pinpoints the failing member/bit inside a prepare step. */
#define P360_PREP_ABI_SIZE                (1u << 0)
#define P360_PREP_ABI_VERSION             (1u << 1)
#define P360_PREP_ABI_DEVICE_ID           (1u << 2)
#define P360_PREP_ABI_CONTEXT             (1u << 3)
#define P360_PREP_ABI_GET_RESOURCES       (1u << 4)
#define P360_PREP_ABI_SET_POWER           (1u << 5)
#define P360_PREP_ABI_REGISTER_IRQ        (1u << 6)
#define P360_PREP_ABI_UNREGISTER_IRQ      (1u << 7)
#define P360_PREP_ABI_GET_RENDER          (1u << 8)
#define P360_PREP_ABI_GET_CAPTURE         (1u << 9)
#define P360_PREP_ABI_FREE_STREAM         (1u << 10)
#define P360_PREP_ABI_PREPARE_DSP         (1u << 11)
#define P360_PREP_ABI_CLEANUP_DSP         (1u << 12)
#define P360_PREP_ABI_TRIGGER_DSP         (1u << 13)
#define P360_PREP_ABI_STREAM_POSITION     (1u << 14)

#define P360_PREP_RES_HDA_BASE            (1u << 0)
#define P360_PREP_RES_HDA_LEN             (1u << 1)
#define P360_PREP_RES_DSP_BASE            (1u << 2)
#define P360_PREP_RES_DSP_LEN             (1u << 3)
#define P360_PREP_RES_PPCAP               (1u << 4)
#define P360_PREP_RES_NHLT_PTR            (1u << 5)
#define P360_PREP_RES_NHLT_SIZE           (1u << 6)
#define P360_PREP_RES_PCI_GET             (1u << 7)
#define P360_PREP_RES_PCI_SET             (1u << 8)

#define P360_PREP_ID_READ                 0x40000000u
#define P360_PREP_ID_VALIDATE             0x20000000u
#define P360_PREP_ID_COMMAND              0x10000000u

#define P360_PREP_NHLT_DMIC               (1u << 16)
#define P360_PREP_NHLT_SSP1_RENDER        (1u << 17)
#define P360_PREP_NHLT_SSP2_RENDER        (1u << 18)
#define P360_PREP_NHLT_SSP2_CAPTURE       (1u << 19)

/* RUNTIME_CREATE PrepareDetail values. */
#define P360_PREP_RUNTIME_SPINLOCK_CREATE  1u
#define P360_PREP_RUNTIME_DPC_CREATE       2u
#define P360_PREP_RUNTIME_COMPLETE         3u

#define P360_TELEM_FLAG_RUNTIME_BOOT     (1u << 0)
#define P360_TELEM_FLAG_IPC_PROBE        (1u << 1)
#define P360_TELEM_FLAG_HOST_TOPOLOGY    (1u << 2)
#define P360_TELEM_FLAG_TONE_TOPOLOGY    P360_TELEM_FLAG_HOST_TOPOLOGY /* legacy diagnostic alias */
#define P360_TELEM_FLAG_INTERNAL_SPEAKER (1u << 3)
#define P360_TELEM_FLAG_BOUNDED_TONE     (1u << 4)
#define P360_TELEM_FLAG_SPEAKER_ENDPOINT (1u << 5)

NTSTATUS p360_telemetry_reset(_In_ ULONG BuildFlags);
NTSTATUS p360_telemetry_stage(_In_ ULONG Stage);
NTSTATUS p360_telemetry_prepare(_In_ ULONG Step,_In_ ULONG Detail,_In_ NTSTATUS Status);
NTSTATUS p360_telemetry_boot_epoch(_In_ ULONGLONG Epoch);
NTSTATUS p360_telemetry_ipc(_In_ LONG FirmwareError,_In_ ULONG ReplyBytes);
NTSTATUS p360_telemetry_result(_In_ ULONG FailureReason,_In_ NTSTATUS Status);


NTSTATUS
p360_telemetry_loader(
    _In_ ULONG Phase,
    _In_ LONG LoaderError,
    _In_ LONG CleanupError,
    _In_ ULONG EntryAdspcs,
    _In_ ULONG NormalizedAdspcs,
    _In_ ULONG FinalAdspcs,
    _In_ ULONG RomStatus,
    _In_ ULONG RomError);
