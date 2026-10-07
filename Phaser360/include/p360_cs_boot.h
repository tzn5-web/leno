#pragma once

#include <ntddk.h>
#include "p360_cs_bus.h"
#include "../sof_core/loader/p360_loader.h"

#define P360_CS_BOOT_DMA_BYTES P360_FW_PAYLOAD_BYTES
#define P360_CS_BOOT_PAGE_COUNT (P360_CS_BOOT_DMA_BYTES / PAGE_SIZE)

typedef struct P360_CS_BDL_ENTRY {
    UINT32 AddressLow;
    UINT32 AddressHigh;
    UINT32 Length;
    UINT32 Ioc;
} P360_CS_BDL_ENTRY;

C_ASSERT(sizeof(P360_CS_BDL_ENTRY) == 16);
C_ASSERT((P360_CS_BOOT_DMA_BYTES % PAGE_SIZE) == 0);
C_ASSERT(P360_CS_BOOT_PAGE_COUNT == 70);

typedef struct P360_CS_BOOT_ADAPTER {
    P360_CS_BUS *Bus;

    HANDLE Stream;
    UINT8 StreamTag;
    PVOID BusBdl;
    ULONG BdlEntries;

    PMDL PayloadMdl;
    PVOID PayloadVa;

    volatile LONG Cancelled;

    BOOLEAN PowerHeld;
    BOOLEAN Acquired;
    BOOLEAN StreamOwned;
    BOOLEAN StreamPrepared;
    BOOLEAN SpibEnabled;
    BOOLEAN Running;
    BOOLEAN DmaDetached;
    BOOLEAN LiveDsp;
    BOOLEAN Quarantined;
} P360_CS_BOOT_ADAPTER;

NTSTATUS
p360_cs_boot_adapter_init(
    _Out_ P360_CS_BOOT_ADAPTER *Adapter,
    _Inout_ P360_CS_BUS *Bus
    );

VOID
p360_cs_boot_adapter_cancel(
    _Inout_ P360_CS_BOOT_ADAPTER *Adapter
    );

const struct p360_loader_ops *
p360_cs_boot_loader_ops(VOID);

/*
 * Releases only resources that are already proved detached. It deliberately
 * refuses to free a buffer that might still be referenced by HDA bus-master
 * hardware.
 */
NTSTATUS
p360_cs_boot_adapter_retire(
    _Inout_ P360_CS_BOOT_ADAPTER *Adapter
    );

/*
 * Runtime shutdown after a proved FW_READY handoff. Caller must already have
 * masked/drained IPC handling. This routine only quiesces DSP cores and drops
 * the D0 reference; it never touches codec/SSP/speaker state.
 */
NTSTATUS
p360_cs_boot_adapter_shutdown_live(
    _Inout_ P360_CS_BOOT_ADAPTER *Adapter
    );

/* Re-arm a clean adapter for the next D0 boot epoch after shutdown. */
NTSTATUS
p360_cs_boot_adapter_rearm(
    _Inout_ P360_CS_BOOT_ADAPTER *Adapter
    );
