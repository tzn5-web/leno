#include "../include/p360_cs_boot.h"

#define P360_BOOT_READY_OFFSET 0x81000u

#define P360_DSP_ADSPCS  0x04u
#define P360_DSP_HIPCT   0x40u
#define P360_DSP_HIPCTE  0x44u
#define P360_DSP_HIPCI   0x48u
#define P360_DSP_HIPCIE  0x4cu
#define P360_DSP_HIPCCTL 0x50u
#define P360_DSP_ROM_STATUS 0x80000u
#define P360_DSP_ROM_ERROR  0x80004u

static BOOLEAN
p360_cs_boot_passive(VOID)
{
    return KeGetCurrentIrql() == PASSIVE_LEVEL;
}

static VOID
p360_cs_boot_free_pages(
    _Inout_ P360_CS_BOOT_ADAPTER *a
    )
{
    if (!a)
        return;

    if (a->PayloadVa && a->PayloadMdl) {
        MmUnmapLockedPages(a->PayloadVa, a->PayloadMdl);
        a->PayloadVa = NULL;
    }

    if (a->PayloadMdl) {
        MmFreePagesFromMdl(a->PayloadMdl);
        ExFreePool(a->PayloadMdl);
        a->PayloadMdl = NULL;
    }
}

static NTSTATUS
p360_cs_boot_alloc_pages(
    _Inout_ P360_CS_BOOT_ADAPTER *a
    )
{
    PHYSICAL_ADDRESS low;
    PHYSICAL_ADDRESS high;
    PHYSICAL_ADDRESS skip;

    if (!a || a->PayloadMdl || a->PayloadVa)
        return STATUS_INVALID_DEVICE_STATE;

    low.QuadPart = 0;
    /*
     * Keep the boot DMA below 4 GiB even if GCAP advertises 64-bit DMA.
     * This is deliberately more restrictive than the hardware so the BDL is
     * valid on either 32-bit- or 64-bit-capable HDA engines.
     */
    high.QuadPart = MAXULONG32;
    skip.QuadPart = 0;

    a->PayloadMdl = MmAllocatePagesForMdl(
        low,
        high,
        skip,
        P360_CS_BOOT_DMA_BYTES);

    if (!a->PayloadMdl)
        return STATUS_INSUFFICIENT_RESOURCES;

    if (MmGetMdlByteCount(a->PayloadMdl) < P360_CS_BOOT_DMA_BYTES ||
        MmGetMdlByteOffset(a->PayloadMdl) != 0) {
        p360_cs_boot_free_pages(a);
        return STATUS_INSUFFICIENT_RESOURCES;
    }

    a->PayloadVa = MmMapLockedPagesSpecifyCache(
        a->PayloadMdl,
        KernelMode,
        MmNonCached,
        NULL,
        FALSE,
        NormalPagePriority | MdlMappingNoExecute);

    if (!a->PayloadVa) {
        p360_cs_boot_free_pages(a);
        return STATUS_INSUFFICIENT_RESOURCES;
    }

    return STATUS_SUCCESS;
}

static NTSTATUS
p360_cs_boot_fill_bdl(
    _Inout_ P360_CS_BOOT_ADAPTER *a
    )
{
    P360_CS_BDL_ENTRY *bdl;
    PPFN_NUMBER pfns;
    ULONG i;

    if (!a || !a->PayloadMdl || !a->BusBdl ||
        a->BdlEntries != P360_CS_BOOT_PAGE_COUNT)
        return STATUS_INVALID_DEVICE_STATE;

    bdl = (P360_CS_BDL_ENTRY *)a->BusBdl;
    pfns = MmGetMdlPfnArray(a->PayloadMdl);

    if (!pfns)
        return STATUS_INVALID_DEVICE_STATE;

    RtlZeroMemory(
        bdl,
        sizeof(P360_CS_BDL_ENTRY) * P360_CS_BOOT_PAGE_COUNT);

    for (i = 0; i < P360_CS_BOOT_PAGE_COUNT; ++i) {
        ULONGLONG pa = ((ULONGLONG)pfns[i]) << PAGE_SHIFT;

        if (pa > MAXULONG32)
            return STATUS_ADDRESS_NOT_ASSOCIATED;

        bdl[i].AddressLow = (UINT32)pa;
        bdl[i].AddressHigh = 0;
        bdl[i].Length = PAGE_SIZE;
        /*
         * Firmware boot is polled through ROM/FW_READY. Do not request
         * period interrupts from the HDA stream.
         */
        bdl[i].Ioc = 0;
    }

    KeMemoryBarrier();
    return STATUS_SUCCESS;
}

static int
p360_cs_boot_read_pci(
    _In_ P360_CS_BOOT_ADAPTER *a,
    _Out_writes_bytes_(256) UCHAR config[256]
    )
{
    ULONG offset;

    if (!a || !a->Bus || !a->Bus->resources_valid)
        return P360_L_BUSY;

    for (offset = 0; offset < 256; offset += sizeof(ULONG)) {
        if (a->Bus->pci.GetBusData(
                a->Bus->pci.Context,
                PCI_WHICHSPACE_CONFIG,
                config + offset,
                offset,
                sizeof(ULONG)) != sizeof(ULONG)) {
            return P360_L_IO;
        }
    }

    return 0;
}

static int
p360_cs_boot_acquire(void *context)
{
    P360_CS_BOOT_ADAPTER *a = (P360_CS_BOOT_ADAPTER *)context;
    struct p360_pci_identity identity;
    UCHAR config[256];
    NTSTATUS status;
    int rc;

    if (!a || !a->Bus || !a->Bus->resources_valid ||
        a->Quarantined || a->Acquired || !p360_cs_boot_passive())
        return P360_L_BUSY;

    if (a->Bus->iface.SetDSPPowerState) {
        status = a->Bus->iface.SetDSPPowerState(
            a->Bus->iface.Context,
            PowerDeviceD0);

        if (!NT_SUCCESS(status))
            return P360_L_IO;

        a->PowerHeld = TRUE;
    }

    rc = p360_cs_boot_read_pci(a, config);
    if (rc)
        goto fail;

    if (p360_pci_validate(config, sizeof(config), &identity) ||
        (identity.command & 6u) != 6u) {
        rc = P360_L_BUSY;
        goto fail;
    }

    a->Acquired = TRUE;
    a->DmaDetached = TRUE;
    return 0;

fail:
    if (a->PowerHeld && a->Bus->iface.SetDSPPowerState) {
        (void)a->Bus->iface.SetDSPPowerState(
            a->Bus->iface.Context,
            PowerDeviceD3);
        a->PowerHeld = FALSE;
    }
    return rc;
}

static int
p360_cs_boot_prepare(
    void *context,
    const struct p360_fw_view *view,
    uint8_t *stream_tag
    )
{
    P360_CS_BOOT_ADAPTER *a = (P360_CS_BOOT_ADAPTER *)context;
    HDAUDIO_STREAM_FORMAT format;
    NTSTATUS status;

    if (stream_tag)
        *stream_tag = 0;

    if (!a || !view || !stream_tag || !a->Acquired ||
        a->Quarantined || a->StreamOwned || a->PayloadMdl ||
        view->bytes != P360_CS_BOOT_DMA_BYTES || !view->payload ||
        !p360_cs_boot_passive()) {
        return P360_L_ARGUMENT;
    }

    RtlZeroMemory(&format, sizeof(format));
    /*
     * CoolStar hdac_format() encodes this as 0x40, matching B4's proven
     * firmware-download stream format.
     */
    format.SampleRate = 48000;
    format.ValidBitsPerSample = 32;
    format.ContainerSize = 32;
    format.NumberOfChannels = 1;

    status = a->Bus->iface.GetRenderStream(
        a->Bus->iface.Context,
        format,
        &a->Stream,
        &a->StreamTag);

    if (!NT_SUCCESS(status) || !a->Stream ||
        a->StreamTag < 1 || a->StreamTag > 15) {
        a->Stream = NULL;
        a->StreamTag = 0;
        return P360_L_IO;
    }

    a->StreamOwned = TRUE;
    a->DmaDetached = TRUE;

    status = p360_cs_boot_alloc_pages(a);
    if (!NT_SUCCESS(status))
        return P360_L_IO;

    RtlCopyMemory(
        a->PayloadVa,
        view->payload,
        P360_CS_BOOT_DMA_BYTES);
    KeMemoryBarrier();

    a->BdlEntries = P360_CS_BOOT_PAGE_COUNT;

    status = a->Bus->iface.PrepareDSP(
        a->Bus->iface.Context,
        a->Stream,
        P360_CS_BOOT_DMA_BYTES,
        (int)a->BdlEntries,
        &a->BusBdl);

    if (!NT_SUCCESS(status) || !a->BusBdl)
        return P360_L_IO;

    a->StreamPrepared = TRUE;
    a->DmaDetached = FALSE;

    status = p360_cs_boot_fill_bdl(a);
    if (!NT_SUCCESS(status))
        return P360_L_IO;

    if (a->Bus->iface.DSPEnableSPIB) {
        a->Bus->iface.DSPEnableSPIB(
            a->Bus->iface.Context,
            a->Stream,
            P360_CS_BOOT_DMA_BYTES);
        a->SpibEnabled = TRUE;
    }

    KeMemoryBarrier();
    *stream_tag = a->StreamTag;
    return 0;
}

static int
p360_cs_boot_start(void *context)
{
    P360_CS_BOOT_ADAPTER *a = (P360_CS_BOOT_ADAPTER *)context;

    if (!a || !a->StreamOwned || !a->StreamPrepared ||
        a->DmaDetached || a->Running || a->Quarantined ||
        !p360_cs_boot_passive())
        return P360_L_BUSY;

    KeMemoryBarrier();
    a->Bus->iface.TriggerDSP(
        a->Bus->iface.Context,
        a->Stream,
        TRUE);
    KeMemoryBarrier();

    a->Running = TRUE;
    return 0;
}

static int
p360_cs_boot_stop(void *context)
{
    P360_CS_BOOT_ADAPTER *a = (P360_CS_BOOT_ADAPTER *)context;
    NTSTATUS status;

    if (!a || a->Quarantined || !p360_cs_boot_passive())
        return P360_L_QUARANTINE;

    if (!a->StreamOwned) {
        a->DmaDetached = TRUE;
        return 0;
    }

    if (a->Running) {
        a->Bus->iface.TriggerDSP(
            a->Bus->iface.Context,
            a->Stream,
            FALSE);
        a->Running = FALSE;
    }

    if (a->SpibEnabled && a->Bus->iface.DSPDisableSPIB) {
        a->Bus->iface.DSPDisableSPIB(
            a->Bus->iface.Context,
            a->Stream);
        a->SpibEnabled = FALSE;
    }

    if (a->StreamPrepared) {
        status = a->Bus->iface.CleanupDSP(
            a->Bus->iface.Context,
            a->Stream);

        if (!NT_SUCCESS(status)) {
            a->Quarantined = TRUE;
            return P360_L_QUARANTINE;
        }

        a->StreamPrepared = FALSE;
        a->BusBdl = NULL;
    }

    KeMemoryBarrier();
    a->DmaDetached = TRUE;
    return 0;
}

static int
p360_cs_boot_release_dma(void *context)
{
    P360_CS_BOOT_ADAPTER *a = (P360_CS_BOOT_ADAPTER *)context;
    NTSTATUS status;

    if (!a || a->Quarantined || !a->DmaDetached ||
        a->Running || a->StreamPrepared || !p360_cs_boot_passive())
        return P360_L_QUARANTINE;

    if (a->StreamOwned) {
        status = a->Bus->iface.FreeStream(
            a->Bus->iface.Context,
            a->Stream);

        if (!NT_SUCCESS(status)) {
            a->Quarantined = TRUE;
            return P360_L_QUARANTINE;
        }

        a->StreamOwned = FALSE;
        a->Stream = NULL;
        a->StreamTag = 0;
    }

    p360_cs_boot_free_pages(a);
    a->BdlEntries = 0;
    return 0;
}

static BOOLEAN
p360_cs_boot_read_offset_allowed(UINT32 offset)
{
    return offset == P360_DSP_ADSPCS ||
           offset == P360_DSP_HIPCT ||
           offset == P360_DSP_HIPCTE ||
           offset == P360_DSP_HIPCI ||
           offset == P360_DSP_HIPCIE ||
           offset == P360_DSP_HIPCCTL ||
           offset == P360_DSP_ROM_STATUS ||
           offset == P360_DSP_ROM_ERROR ||
           (offset >= P360_BOOT_READY_OFFSET &&
            offset < P360_BOOT_READY_OFFSET + P360_FW_READY_BYTES);
}

static int
p360_cs_boot_read32(
    void *context,
    uint32_t offset,
    uint32_t *value
    )
{
    P360_CS_BOOT_ADAPTER *a = (P360_CS_BOOT_ADAPTER *)context;

    if (!a || !value || !a->Acquired || !a->Bus ||
        !a->Bus->resources_valid || !a->Bus->dsp.Base.baseptr ||
        (offset & 3u) ||
        offset > a->Bus->dsp.Len - sizeof(ULONG) ||
        !p360_cs_boot_read_offset_allowed(offset)) {
        return 1;
    }

    *value = READ_REGISTER_ULONG(
        (volatile ULONG *)(a->Bus->dsp.Base.baseptr + offset));

    return *value == MAXULONG;
}

static int
p360_cs_boot_write32(
    void *context,
    uint32_t offset,
    uint32_t value
    )
{
    P360_CS_BOOT_ADAPTER *a = (P360_CS_BOOT_ADAPTER *)context;
    uint32_t old;

    if (p360_cs_boot_read32(a, offset, &old))
        return 1;

    /*
     * Preserve B4's exact boot write policy. No SSP, codec, arbitrary DSP or
     * HDA register writes are admitted through this adapter.
     */
    if (offset == P360_DSP_ADSPCS) {
        if ((old ^ value) & ~0x03030303u)
            return 1;
    } else if (offset == P360_DSP_HIPCCTL) {
        if (value != (old & ~3u))
            return 1;
    } else if (offset == P360_DSP_HIPCT) {
        if (value != (old | 0x80000000u))
            return 1;
    } else if (offset == P360_DSP_HIPCIE) {
        if (value != (old | 0x40000000u))
            return 1;
    } else if (offset == P360_DSP_HIPCI) {
        if (value &&
            ((value & ~0x00001e00u) != 0x81004000u ||
             ((value >> 9) & 15u) > 14u)) {
            return 1;
        }
    } else {
        return 1;
    }

    WRITE_REGISTER_ULONG(
        (volatile ULONG *)(a->Bus->dsp.Base.baseptr + offset),
        value);
    KeMemoryBarrier();
    return 0;
}

static int
p360_cs_boot_read_ready(
    void *context,
    uint8_t out[P360_FW_READY_BYTES]
    )
{
    P360_CS_BOOT_ADAPTER *a = (P360_CS_BOOT_ADAPTER *)context;
    ULONG i;
    uint32_t value;

    if (!a || !out)
        return 1;

    KeMemoryBarrier();

    for (i = 0; i < P360_FW_READY_BYTES; i += sizeof(ULONG)) {
        if (p360_cs_boot_read32(
                a,
                P360_BOOT_READY_OFFSET + i,
                &value)) {
            return 1;
        }

        out[i]     = (UCHAR)value;
        out[i + 1] = (UCHAR)(value >> 8);
        out[i + 2] = (UCHAR)(value >> 16);
        out[i + 3] = (UCHAR)(value >> 24);
    }

    KeMemoryBarrier();
    return 0;
}

static uint64_t
p360_cs_boot_now_us(void *context)
{
    ULONGLONG qpc;
    UNREFERENCED_PARAMETER(context);
    return KeQueryInterruptTimePrecise(&qpc) / 10u;
}

static void
p360_cs_boot_wait_us(
    void *context,
    uint32_t us
    )
{
    LARGE_INTEGER interval;
    UNREFERENCED_PARAMETER(context);

    if (us <= 50) {
        KeStallExecutionProcessor(us);
        return;
    }

    interval.QuadPart = -(LONGLONG)us * 10;
    (void)KeDelayExecutionThread(
        KernelMode,
        FALSE,
        &interval);
}

static int
p360_cs_boot_cancelled(void *context)
{
    P360_CS_BOOT_ADAPTER *a = (P360_CS_BOOT_ADAPTER *)context;

    return !a ||
        InterlockedCompareExchange(
            &a->Cancelled,
            0,
            0) != 0 ||
        a->Quarantined ||
        !a->Bus ||
        !a->Bus->resources_valid;
}

static int
p360_cs_boot_release_platform(
    void *context,
    int success
    )
{
    P360_CS_BOOT_ADAPTER *a = (P360_CS_BOOT_ADAPTER *)context;
    NTSTATUS status = STATUS_SUCCESS;

    if (!a || !a->Acquired || a->Quarantined)
        return P360_L_QUARANTINE;

    if (success) {
        if (!a->DmaDetached || a->StreamOwned || a->PayloadMdl ||
            a->Running || a->StreamPrepared) {
            a->Quarantined = TRUE;
            return P360_L_QUARANTINE;
        }

        /*
         * Keep the bus in D0. FW_READY has transferred live-DSP ownership to
         * the runtime/IPC layer, which will later own the shutdown path.
         */
        a->LiveDsp = TRUE;
        a->Acquired = FALSE;
        return 0;
    }

    if (a->StreamOwned || a->PayloadMdl ||
        a->Running || a->StreamPrepared || !a->DmaDetached) {
        a->Quarantined = TRUE;
        return P360_L_QUARANTINE;
    }

    if (a->PowerHeld && a->Bus->iface.SetDSPPowerState) {
        status = a->Bus->iface.SetDSPPowerState(
            a->Bus->iface.Context,
            PowerDeviceD3);

        if (!NT_SUCCESS(status)) {
            a->Quarantined = TRUE;
            return P360_L_QUARANTINE;
        }

        a->PowerHeld = FALSE;
    }

    a->Acquired = FALSE;
    return 0;
}

static const struct p360_loader_ops g_p360_cs_boot_ops = {
    p360_cs_boot_acquire,
    p360_cs_boot_release_platform,
    p360_cs_boot_prepare,
    p360_cs_boot_start,
    p360_cs_boot_stop,
    p360_cs_boot_release_dma,
    p360_cs_boot_read32,
    p360_cs_boot_write32,
    p360_cs_boot_read_ready,
    p360_cs_boot_now_us,
    p360_cs_boot_wait_us,
    p360_cs_boot_cancelled
};

NTSTATUS
p360_cs_boot_adapter_init(
    P360_CS_BOOT_ADAPTER *a,
    P360_CS_BUS *bus
    )
{
    if (!a || !bus || !bus->resources_valid)
        return STATUS_INVALID_PARAMETER;

    RtlZeroMemory(a, sizeof(*a));
    a->Bus = bus;
    a->DmaDetached = TRUE;
    return STATUS_SUCCESS;
}

VOID
p360_cs_boot_adapter_cancel(
    P360_CS_BOOT_ADAPTER *a
    )
{
    if (a)
        InterlockedExchange(&a->Cancelled, 1);
}

const struct p360_loader_ops *
p360_cs_boot_loader_ops(VOID)
{
    return &g_p360_cs_boot_ops;
}

NTSTATUS
p360_cs_boot_adapter_retire(
    P360_CS_BOOT_ADAPTER *a
    )
{
    if (!a || !p360_cs_boot_passive())
        return STATUS_INVALID_PARAMETER;

    if (a->Quarantined ||
        a->Running ||
        a->StreamPrepared ||
        !a->DmaDetached) {
        return STATUS_DEVICE_HARDWARE_ERROR;
    }

    if (a->StreamOwned) {
        if (p360_cs_boot_release_dma(a) != 0)
            return STATUS_DEVICE_HARDWARE_ERROR;
    } else {
        p360_cs_boot_free_pages(a);
    }

    if (!a->LiveDsp && a->PowerHeld &&
        a->Bus && a->Bus->iface.SetDSPPowerState) {
        NTSTATUS status = a->Bus->iface.SetDSPPowerState(
            a->Bus->iface.Context,
            PowerDeviceD3);

        if (!NT_SUCCESS(status))
            return status;

        a->PowerHeld = FALSE;
    }

    return STATUS_SUCCESS;
}
