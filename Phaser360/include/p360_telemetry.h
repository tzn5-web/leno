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

#define P360_TELEM_FLAG_RUNTIME_BOOT     (1u << 0)
#define P360_TELEM_FLAG_IPC_PROBE        (1u << 1)
#define P360_TELEM_FLAG_TONE_TOPOLOGY    (1u << 2)
#define P360_TELEM_FLAG_INTERNAL_SPEAKER (1u << 3)
#define P360_TELEM_FLAG_BOUNDED_TONE     (1u << 4)
#define P360_TELEM_FLAG_SPEAKER_ENDPOINT (1u << 5)

NTSTATUS p360_telemetry_reset(_In_ ULONG BuildFlags);
NTSTATUS p360_telemetry_stage(_In_ ULONG Stage);
NTSTATUS p360_telemetry_boot_epoch(_In_ ULONGLONG Epoch);
NTSTATUS p360_telemetry_ipc(_In_ LONG FirmwareError,_In_ ULONG ReplyBytes);
NTSTATUS p360_telemetry_result(_In_ ULONG FailureReason,_In_ NTSTATUS Status);
