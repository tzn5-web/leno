#pragma once

#include <ntddk.h>
#include <wdf.h>

#include "p360_cs_bus.h"
#include "p360_cs_boot.h"
#include "../sof_core/loader/p360_irq.h"
#include "../sof_core/loader/p360_dispatch.h"
#include "../sof_core/loader/p360_ipc3_tx.h"
#include "../sof_core/adapter/p360_irq_arm_adapter.h"

#define P360_RUNTIME_CALLBACK_CLOSING 0x80000000u
#define P360_RUNTIME_CALLBACK_COUNT   0x7fffffffu

typedef struct P360_CS_RUNTIME {
    P360_CS_BUS *Bus;
    P360_CS_BOOT_ADAPTER *Boot;

    WDFDPC Dpc;
    WDFSPINLOCK DispatchLock;

    struct p360_irq Irq;
    struct p360_dispatch Dispatch;
    struct p360_irq_event PendingEvent;

    volatile LONG CallbackState;
    volatile LONG Active;
    volatile LONG Stopping;
    volatile LONG Fault;
    volatile LONG EventValid;
    volatile LONG DpcState;
    volatile LONG ArmInProgress;

    ULONGLONG Epoch;

    BOOLEAN Created;
    BOOLEAN DispatcherPrepared;
    BOOLEAN CallbackRegistered;
    BOOLEAN MaskConfirmed;
    BOOLEAN Bound;
} P360_CS_RUNTIME;

NTSTATUS
p360_cs_runtime_create(
    _Out_ P360_CS_RUNTIME *Runtime,
    _In_ WDFDEVICE Device,
    _Inout_ P360_CS_BUS *Bus,
    _Inout_ P360_CS_BOOT_ADAPTER *Boot
    );

NTSTATUS
p360_cs_runtime_prepare_dispatcher(
    _Inout_ P360_CS_RUNTIME *Runtime,
    _In_reads_bytes_(FirmwareBytes) const UCHAR *Firmware,
    _In_ SIZE_T FirmwareBytes
    );

NTSTATUS
p360_cs_runtime_bind_live(
    _Inout_ P360_CS_RUNTIME *Runtime,
    _In_ ULONGLONG BootEpoch
    );

NTSTATUS
p360_cs_runtime_send_ipc(
    _Inout_ P360_CS_RUNTIME *Runtime,
    _In_reads_bytes_(MessageBytes) const UCHAR *Message,
    _In_ ULONG MessageBytes,
    _In_ ULONG TimeoutMs,
    _Out_opt_ LONG *FirmwareError,
    _Out_opt_ ULONG *ReplyBytes
    );

NTSTATUS
p360_cs_runtime_probe_ipc(
    _Inout_ P360_CS_RUNTIME *Runtime,
    _Out_opt_ LONG *FirmwareError
    );

NTSTATUS
p360_cs_runtime_stop(
    _Inout_ P360_CS_RUNTIME *Runtime
    );

NTSTATUS
p360_cs_runtime_destroy(
    _Inout_ P360_CS_RUNTIME *Runtime
    );

P360_CS_BOOL
p360_cs_runtime_interrupt(
    _In_ PVOID Context
    );
