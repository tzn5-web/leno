#include "../include/p360_playback.h"
#include "../include/p360_board.h"

#define P360_HDA_GCAP_OFFSET       0x00u
#define P360_HDA_SD_BASE           0x80u
#define P360_HDA_SD_INTERVAL       0x20u
#define P360_HDA_SD_CTL_OFFSET     0x00u
#define P360_HDA_SD_CTL_RUN        0x02u
#define P360_HDA_RUN_POLL_US       10u
#define P360_HDA_RUN_POLL_COUNT    1000u

static NTSTATUS
p360_playback_prove_hda_run(
    _In_ const P360_PLAYBACK_STREAM *p,
    _In_ BOOLEAN expectedRunning
    )
{
    UINT8 *hda;
    USHORT gcap;
    ULONG captureStreams;
    ULONG playbackStreams;
    ULONG streamIndex;
    ULONG ctlOffset;
    ULONG attempt;

    if (!p || !p->Bus || !p->Bus->resources_valid ||
        !p->Bus->hda.Base.baseptr ||
        p->Bus->hda.Len<sizeof(USHORT) ||
        p->StreamTag<1u) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    hda=p->Bus->hda.Base.baseptr;
    gcap=READ_REGISTER_USHORT(
        (volatile USHORT *)(hda+P360_HDA_GCAP_OFFSET));

    /*
     * Match the pinned CoolStar stream allocation exactly:
     * captureIndexOff=0, playbackIndexOff=captureStreams and Intel playback
     * tags are assigned 1..playbackStreams in descriptor order.
     */
    captureStreams=(gcap >> 8) & 0x0fu;
    playbackStreams=(gcap >> 12) & 0x0fu;
    if (!playbackStreams ||
        (ULONG)p->StreamTag>playbackStreams) {
        return STATUS_DEVICE_CONFIGURATION_ERROR;
    }

    streamIndex=captureStreams+(ULONG)p->StreamTag-1u;
    ctlOffset=P360_HDA_SD_BASE+
        P360_HDA_SD_INTERVAL*streamIndex+
        P360_HDA_SD_CTL_OFFSET;
    if (ctlOffset>=p->Bus->hda.Len)
        return STATUS_DEVICE_CONFIGURATION_ERROR;

    for (attempt=0;attempt<P360_HDA_RUN_POLL_COUNT;++attempt) {
        UCHAR ctl=READ_REGISTER_UCHAR(
            (volatile UCHAR *)(hda+ctlOffset));
        BOOLEAN running=(ctl&P360_HDA_SD_CTL_RUN) ? TRUE : FALSE;

        if (running==expectedRunning)
            return STATUS_SUCCESS;

        KeStallExecutionProcessor(P360_HDA_RUN_POLL_US);
    }

    return STATUS_IO_TIMEOUT;
}

static ULONG
p360_playback_page_table_required(
    _In_ ULONG pages
    )
{
    return (pages * 5u + 1u) / 2u;
}

static NTSTATUS
p360_playback_build_sof_page_table(
    _In_ PMDL mdl,
    _In_ ULONG bytes,
    _Out_writes_bytes_(tableBytes) UCHAR *table,
    _In_ ULONG tableBytes,
    _Out_ ULONG *pagesOut
    )
{
    PPFN_NUMBER pfns;
    ULONG pages;
    ULONG needed;
    ULONG i;

    if (!mdl || !bytes || !table || !tableBytes || !pagesOut)
        return STATUS_INVALID_PARAMETER;

    if (MmGetMdlByteOffset(mdl) != 0 ||
        MmGetMdlByteCount(mdl) < bytes) {
        return STATUS_INVALID_BUFFER_SIZE;
    }

    pages=(bytes + PAGE_SIZE - 1u) / PAGE_SIZE;
    needed=p360_playback_page_table_required(pages);
    if (!pages || needed>tableBytes)
        return STATUS_BUFFER_TOO_SMALL;

    pfns=MmGetMdlPfnArray(mdl);
    if (!pfns)
        return STATUS_INVALID_ADDRESS;

    RtlZeroMemory(table,tableBytes);

    /*
     * SOF IPC3 uses the same compressed 20-bit PFN table as Linux
     * snd_sof_create_page_table(): two PFNs occupy five bytes.
     */
    for (i=0;i<pages;++i) {
        ULONGLONG pfn=(ULONGLONG)pfns[i];
        ULONG index=(5u * i) >> 1;

        if (pfn>0xfffffu)
            return STATUS_CONFLICTING_ADDRESSES;

        if ((i & 1u)==0) {
            table[index]=(UCHAR)pfn;
            table[index+1]=(UCHAR)(pfn >> 8);
            table[index+2]=(UCHAR)((table[index+2] & 0xf0u) |
                ((UCHAR)(pfn >> 16) & 0x0fu));
        } else {
            table[index]=(UCHAR)((table[index] & 0x0fu) |
                (((UCHAR)pfn & 0x0fu) << 4));
            table[index+1]=(UCHAR)(pfn >> 4);
            table[index+2]=(UCHAR)(pfn >> 12);
        }
    }

    KeMemoryBarrier();
    *pagesOut=pages;
    return STATUS_SUCCESS;
}

static NTSTATUS
p360_playback_fill_bdl(
    _In_ PMDL mdl,
    _In_ ULONG bytes,
    _Out_writes_(entries) P360_PLAYBACK_BDL_ENTRY *bdl,
    _In_ ULONG entries
    )
{
    PPFN_NUMBER pfns;
    ULONG pages;
    ULONG remaining;
    ULONG i;

    if (!mdl || !bytes || !bdl || !entries)
        return STATUS_INVALID_PARAMETER;

    if (MmGetMdlByteOffset(mdl)!=0 ||
        MmGetMdlByteCount(mdl)<bytes) {
        return STATUS_INVALID_BUFFER_SIZE;
    }

    pages=(bytes + PAGE_SIZE - 1u) / PAGE_SIZE;
    if (!pages || pages!=entries)
        return STATUS_INVALID_PARAMETER;

    pfns=MmGetMdlPfnArray(mdl);
    if (!pfns)
        return STATUS_INVALID_ADDRESS;

    RtlZeroMemory(
        bdl,
        sizeof(P360_PLAYBACK_BDL_ENTRY) * entries);

    remaining=bytes;
    for (i=0;i<entries;++i) {
        ULONGLONG address=((ULONGLONG)pfns[i]) << PAGE_SHIFT;
        ULONG chunk=remaining>PAGE_SIZE ? PAGE_SIZE : remaining;

        if (address>MAXULONG32 || !chunk)
            return STATUS_CONFLICTING_ADDRESSES;

        bdl[i].AddressLow=(UINT32)address;
        bdl[i].AddressHigh=0u;
        bdl[i].Length=chunk;
        /*
         * WaveRT position is read from CoolStar's controller position buffer.
         * No HDA period IRQ is required by this polling stream.
         */
        bdl[i].Ioc=0u;
        remaining-=chunk;
    }

    if (remaining)
        return STATUS_INVALID_BUFFER_SIZE;

    KeMemoryBarrier();
    return STATUS_SUCCESS;
}

static VOID
p360_playback_free_page_table(
    _Inout_ P360_PLAYBACK_STREAM *p
    )
{
    if (!p || !p->PageTable)
        return;

    MmFreeContiguousMemory(p->PageTable);
    p->PageTable=NULL;
    p->PageTablePhysical.QuadPart=0;
}

NTSTATUS
p360_playback_stream_init(
    P360_PLAYBACK_STREAM *p,
    P360_CS_BUS *bus
    )
{
    if (!p || !bus || !bus->resources_valid)
        return STATUS_INVALID_PARAMETER;

    RtlZeroMemory(p,sizeof(*p));
    p->Bus=bus;
    return STATUS_SUCCESS;
}

NTSTATUS
p360_playback_stream_bind_buffer(
    P360_PLAYBACK_STREAM *p,
    PMDL audioMdl,
    ULONG bufferBytes,
    ULONG periodBytes
    )
{
    HDAUDIO_STREAM_FORMAT format;
    PHYSICAL_ADDRESS low;
    PHYSICAL_ADDRESS high;
    PHYSICAL_ADDRESS boundary;
    PVOID pageTable;
    PHYSICAL_ADDRESS pageTablePhysical;
    ULONG pages;
    NTSTATUS status;

    if (!p || !p->Bus || !p->Bus->resources_valid ||
        !audioMdl || p->StreamOwned || p->StreamPrepared ||
        p->PageTable || p->Quarantined ||
        KeGetCurrentIrql()!=PASSIVE_LEVEL) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    if (!bufferBytes ||
        bufferBytes>P360_PLAYBACK_MAX_BUFFER_BYTES ||
        (bufferBytes % (P360_SPEAKER_CHANNELS * (P360_SPEAKER_CONTAINER_BITS / 8u)))!=0 ||
        !periodBytes || periodBytes>bufferBytes ||
        (bufferBytes % periodBytes)!=0) {
        return STATUS_INVALID_BUFFER_SIZE;
    }

    low.QuadPart=0;
    high.QuadPart=MAXULONG32;
    boundary.QuadPart=0;

    pageTable=MmAllocateContiguousMemorySpecifyCache(
        P360_PLAYBACK_PAGE_TABLE_BYTES,
        low,
        high,
        boundary,
        MmNonCached);
    if (!pageTable)
        return STATUS_INSUFFICIENT_RESOURCES;

    pageTablePhysical=MmGetPhysicalAddress(pageTable);
    if (pageTablePhysical.HighPart!=0) {
        MmFreeContiguousMemory(pageTable);
        return STATUS_CONFLICTING_ADDRESSES;
    }

    status=p360_playback_build_sof_page_table(
        audioMdl,
        bufferBytes,
        (UCHAR *)pageTable,
        P360_PLAYBACK_PAGE_TABLE_BYTES,
        &pages);
    if (!NT_SUCCESS(status)) {
        MmFreeContiguousMemory(pageTable);
        return status;
    }

    RtlZeroMemory(&format,sizeof(format));
    format.SampleRate=P360_SAMPLE_RATE;
    /*
     * CoolStar SklHDAudBus currently derives HDA SD_FORMAT from
     * ValidBitsPerSample and ignores ContainerSize. The Windows/SOF host ring
     * is 32-bit containers with 16 valid bits, so request 32 here solely to
     * make the HDA descriptor consume 4 bytes/sample. SOF PCM_PARAMS still
     * carries sample_valid_bytes=2 and sample_container_bytes=4, and SSP1 is
     * independently configured as S16.
     */
    format.ValidBitsPerSample=P360_SPEAKER_CONTAINER_BITS;
    format.ContainerSize=P360_SPEAKER_CONTAINER_BITS;
    format.NumberOfChannels=P360_SPEAKER_CHANNELS;

    status=p->Bus->iface.GetRenderStream(
        p->Bus->iface.Context,
        format,
        &p->Stream,
        &p->StreamTag);
    if (!NT_SUCCESS(status) || !p->Stream ||
        p->StreamTag<1u || p->StreamTag>15u) {
        p->Stream=NULL;
        p->StreamTag=0;
        MmFreeContiguousMemory(pageTable);
        return NT_SUCCESS(status) ?
            STATUS_DEVICE_CONFIGURATION_ERROR :
            status;
    }

    p->StreamOwned=TRUE;
    p->PageTable=pageTable;
    p->PageTablePhysical=pageTablePhysical;
    p->AudioMdl=audioMdl;
    p->BufferBytes=bufferBytes;
    p->PeriodBytes=periodBytes;
    p->PageCount=pages;
    p->BdlEntries=pages;

    status=p->Bus->iface.PrepareDSP(
        p->Bus->iface.Context,
        p->Stream,
        bufferBytes,
        (int)pages,
        &p->BusBdl);
    if (!NT_SUCCESS(status) || !p->BusBdl) {
        status=NT_SUCCESS(status) ?
            STATUS_DEVICE_CONFIGURATION_ERROR :
            status;
        goto fail;
    }
    p->StreamPrepared=TRUE;

    status=p360_playback_fill_bdl(
        audioMdl,
        bufferBytes,
        (P360_PLAYBACK_BDL_ENTRY *)p->BusBdl,
        pages);
    if (!NT_SUCCESS(status))
        goto fail;

    /*
     * Keep SPIB disabled. Linux only enables SPIB in its no-rewind mode and
     * then updates the SPIB value on every application-pointer ACK. WaveRT
     * does not provide that ACK path here; a one-time SPIB=bufferBytes would
     * cap the HDA DMA after the first ring traversal.
     */
    if (p->Bus->iface.DSPDisableSPIB)
        p->Bus->iface.DSPDisableSPIB(
            p->Bus->iface.Context,
            p->Stream);
    p->SpibEnabled=FALSE;

    return STATUS_SUCCESS;

fail:
    (void)p360_playback_stream_retire(p);
    return status;
}

NTSTATUS
p360_playback_stream_start(
    P360_PLAYBACK_STREAM *p
    )
{
    if (!p || !p->Bus || !p->StreamOwned ||
        !p->StreamPrepared || p->Running ||
        p->Quarantined ||
        KeGetCurrentIrql()!=PASSIVE_LEVEL) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    KeMemoryBarrier();
    p->Bus->iface.TriggerDSP(
        p->Bus->iface.Context,
        p->Stream,
        TRUE);
    KeMemoryBarrier();

    {
        NTSTATUS status=p360_playback_prove_hda_run(p,TRUE);
        if (!NT_SUCCESS(status)) {
            NTSTATUS stopProof;

            /*
             * TriggerDSP has a void ABI. If RUN did not latch, synchronously
             * request STOP and prove RUN=0 before returning the start error.
             * If even STOP cannot be proved, quarantine the stream so its MDL
             * can never be released underneath a possibly live HDA engine.
             */
            p->Bus->iface.TriggerDSP(
                p->Bus->iface.Context,
                p->Stream,
                FALSE);
            KeMemoryBarrier();
            stopProof=p360_playback_prove_hda_run(p,FALSE);
            if (!NT_SUCCESS(stopProof)) {
                p->Quarantined=TRUE;
                p->Running=TRUE;
                return stopProof;
            }

            p->Running=FALSE;
            return status;
        }
    }

    p->Running=TRUE;
    return STATUS_SUCCESS;
}

NTSTATUS
p360_playback_stream_stop(
    P360_PLAYBACK_STREAM *p
    )
{
    if (!p || !p->Bus || p->Quarantined ||
        KeGetCurrentIrql()!=PASSIVE_LEVEL) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    if (!p->Running)
        return STATUS_SUCCESS;

    p->Bus->iface.TriggerDSP(
        p->Bus->iface.Context,
        p->Stream,
        FALSE);
    KeMemoryBarrier();

    {
        NTSTATUS status=p360_playback_prove_hda_run(p,FALSE);
        if (!NT_SUCCESS(status)) {
            /*
             * Never translate the legacy void TriggerDSP ABI into an
             * unproved local STOP. Keep ownership latched and quarantine the
             * stream so the WaveRT MDL/page table cannot be freed.
             */
            p->Quarantined=TRUE;
            p->Running=TRUE;
            return status;
        }
    }

    p->Running=FALSE;
    return STATUS_SUCCESS;
}

UINT32
p360_playback_stream_position(
    const P360_PLAYBACK_STREAM *p
    )
{
    if (!p || !p->Bus || !p->StreamOwned ||
        !p->Bus->iface.StreamPosition) {
        return 0u;
    }

    return p->Bus->iface.StreamPosition(
        p->Bus->iface.Context,
        p->Stream);
}

UINT32
p360_playback_page_table_physical32(
    const P360_PLAYBACK_STREAM *p
    )
{
    if (!p || !p->PageTable ||
        p->PageTablePhysical.HighPart!=0) {
        return 0u;
    }

    return p->PageTablePhysical.LowPart;
}

NTSTATUS
p360_playback_stream_retire(
    P360_PLAYBACK_STREAM *p
    )
{
    NTSTATUS status;

    if (!p || !p->Bus ||
        KeGetCurrentIrql()!=PASSIVE_LEVEL)
        return STATUS_INVALID_PARAMETER;

    if (p->Quarantined)
        return STATUS_DEVICE_HARDWARE_ERROR;

    status=p360_playback_stream_stop(p);
    if (!NT_SUCCESS(status))
        return status;

    if (p->SpibEnabled && p->Bus->iface.DSPDisableSPIB) {
        p->Bus->iface.DSPDisableSPIB(
            p->Bus->iface.Context,
            p->Stream);
        p->SpibEnabled=FALSE;
    }

    if (p->StreamPrepared) {
        status=p->Bus->iface.CleanupDSP(
            p->Bus->iface.Context,
            p->Stream);
        if (!NT_SUCCESS(status)) {
            p->Quarantined=TRUE;
            return status;
        }

        p->StreamPrepared=FALSE;
        p->BusBdl=NULL;
    }

    if (p->StreamOwned) {
        status=p->Bus->iface.FreeStream(
            p->Bus->iface.Context,
            p->Stream);
        if (!NT_SUCCESS(status)) {
            p->Quarantined=TRUE;
            return status;
        }

        p->StreamOwned=FALSE;
        p->Stream=NULL;
        p->StreamTag=0;
    }

    p360_playback_free_page_table(p);
    p->AudioMdl=NULL;
    p->BufferBytes=0;
    p->PeriodBytes=0;
    p->PageCount=0;
    p->BdlEntries=0;

    return STATUS_SUCCESS;
}
