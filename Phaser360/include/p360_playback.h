#pragma once

#include <ntddk.h>
#include <hdaudio.h>

#include "p360_cs_bus.h"

#ifdef __cplusplus
extern "C" {
#endif

#define P360_PLAYBACK_MAX_BUFFER_BYTES (64u * 1024u)
#define P360_PLAYBACK_PAGE_TABLE_BYTES PAGE_SIZE

typedef struct P360_PLAYBACK_BDL_ENTRY {
    UINT32 AddressLow;
    UINT32 AddressHigh;
    UINT32 Length;
    UINT32 Ioc;
} P360_PLAYBACK_BDL_ENTRY;

C_ASSERT(sizeof(P360_PLAYBACK_BDL_ENTRY) == 16);

typedef struct P360_PLAYBACK_STREAM {
    P360_CS_BUS *Bus;
    HANDLE Stream;
    UINT8 StreamTag;
    PVOID BusBdl;

    PMDL AudioMdl;
    ULONG BufferBytes;
    ULONG PeriodBytes;
    ULONG PageCount;
    ULONG BdlEntries;

    PVOID PageTable;
    PHYSICAL_ADDRESS PageTablePhysical;

    BOOLEAN StreamOwned;
    BOOLEAN StreamPrepared;
    BOOLEAN SpibEnabled;
    BOOLEAN Running;
    BOOLEAN SofParamsPrepared;
    BOOLEAN SofRunning;
    BOOLEAN SpeakerArmed;
    BOOLEAN SpeakerStarted;
    BOOLEAN Quarantined;
} P360_PLAYBACK_STREAM;

NTSTATUS
p360_playback_stream_init(
    _Out_ P360_PLAYBACK_STREAM *Playback,
    _Inout_ P360_CS_BUS *Bus
    );

NTSTATUS
p360_playback_stream_bind_buffer(
    _Inout_ P360_PLAYBACK_STREAM *Playback,
    _In_ PMDL AudioMdl,
    _In_ ULONG BufferBytes,
    _In_ ULONG PeriodBytes
    );

NTSTATUS
p360_playback_stream_start(
    _Inout_ P360_PLAYBACK_STREAM *Playback
    );

NTSTATUS
p360_playback_stream_stop(
    _Inout_ P360_PLAYBACK_STREAM *Playback
    );

UINT32
p360_playback_stream_position(
    _In_ const P360_PLAYBACK_STREAM *Playback
    );

UINT32
p360_playback_stream_fifo_size(
    _In_ const P360_PLAYBACK_STREAM *Playback
    );

NTSTATUS
p360_playback_stream_retire(
    _Inout_ P360_PLAYBACK_STREAM *Playback
    );

UINT32
p360_playback_page_table_physical32(
    _In_ const P360_PLAYBACK_STREAM *Playback
    );

#ifdef __cplusplus
}
#endif
