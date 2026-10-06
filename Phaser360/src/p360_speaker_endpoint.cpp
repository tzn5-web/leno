#define INITGUID
#include <initguid.h>
#include <ntddk.h>
#include <portcls.h>
#include <ksmedia.h>
#include <new>

#include "../include/p360_board.h"
#include "../include/p360_speaker_endpoint.h"

#define P360_SPEAKER_POOL_TAG ((ULONG)'S63P')
#define P360_WAVE_SYSTEM_PIN 0u
#define P360_WAVE_BRIDGE_PIN 1u
#define P360_TOPO_BRIDGE_PIN 0u
#define P360_TOPO_SPEAKER_PIN 1u
#define P360_MAX_WAVERT_BUFFER (4u * 1024u * 1024u)

static KSDATAFORMAT_WAVEFORMATEXTENSIBLE gP360SpeakerFormat = {
    {
        sizeof(KSDATAFORMAT_WAVEFORMATEXTENSIBLE),
        0,
        0,
        0,
        STATICGUIDOF(KSDATAFORMAT_TYPE_AUDIO),
        STATICGUIDOF(KSDATAFORMAT_SUBTYPE_PCM),
        STATICGUIDOF(KSDATAFORMAT_SPECIFIER_WAVEFORMATEX)
    },
    {
        {
            WAVE_FORMAT_EXTENSIBLE,
            P360_SPEAKER_CHANNELS,
            P360_SAMPLE_RATE,
            P360_SAMPLE_RATE * P360_SPEAKER_CHANNELS * 2u,
            P360_SPEAKER_CHANNELS * 2u,
            P360_SPEAKER_PCM_VALID_BITS,
            sizeof(WAVEFORMATEXTENSIBLE) - sizeof(WAVEFORMATEX)
        },
        P360_SPEAKER_PCM_VALID_BITS,
        KSAUDIO_SPEAKER_STEREO,
        STATICGUIDOF(KSDATAFORMAT_SUBTYPE_PCM)
    }
};

static KSDATARANGE_AUDIO gP360SpeakerStreamRange = {
    {
        sizeof(KSDATARANGE_AUDIO),
        0,
        0,
        0,
        STATICGUIDOF(KSDATAFORMAT_TYPE_AUDIO),
        STATICGUIDOF(KSDATAFORMAT_SUBTYPE_PCM),
        STATICGUIDOF(KSDATAFORMAT_SPECIFIER_WAVEFORMATEX)
    },
    P360_SPEAKER_CHANNELS,
    P360_SPEAKER_PCM_VALID_BITS,
    P360_SPEAKER_PCM_VALID_BITS,
    P360_SAMPLE_RATE,
    P360_SAMPLE_RATE
};

static KSDATARANGE gP360AnalogRange = {
    sizeof(KSDATARANGE),
    0,
    0,
    0,
    STATICGUIDOF(KSDATAFORMAT_TYPE_AUDIO),
    STATICGUIDOF(KSDATAFORMAT_SUBTYPE_ANALOG),
    STATICGUIDOF(KSDATAFORMAT_SPECIFIER_NONE)
};

static PKSDATARANGE gP360SpeakerStreamRanges[] = {
    reinterpret_cast<PKSDATARANGE>(&gP360SpeakerStreamRange)
};

static PKSDATARANGE gP360AnalogRanges[] = {
    &gP360AnalogRange
};

static PCPIN_DESCRIPTOR gP360WavePins[] = {
    {
        1,
        1,
        0,
        NULL,
        {
            0,
            NULL,
            0,
            NULL,
            RTL_NUMBER_OF(gP360SpeakerStreamRanges),
            gP360SpeakerStreamRanges,
            KSPIN_DATAFLOW_IN,
            KSPIN_COMMUNICATION_SINK,
            &KSCATEGORY_AUDIO,
            NULL,
            0
        }
    },
    {
        0,
        0,
        0,
        NULL,
        {
            0,
            NULL,
            0,
            NULL,
            RTL_NUMBER_OF(gP360AnalogRanges),
            gP360AnalogRanges,
            KSPIN_DATAFLOW_OUT,
            KSPIN_COMMUNICATION_NONE,
            &KSCATEGORY_AUDIO,
            NULL,
            0
        }
    }
};

static PCCONNECTION_DESCRIPTOR gP360WaveConnections[] = {
    { PCFILTER_NODE, P360_WAVE_SYSTEM_PIN, PCFILTER_NODE, P360_WAVE_BRIDGE_PIN }
};

static PCFILTER_DESCRIPTOR gP360WaveFilter = {
    0,
    NULL,
    sizeof(PCPIN_DESCRIPTOR),
    RTL_NUMBER_OF(gP360WavePins),
    gP360WavePins,
    sizeof(PCNODE_DESCRIPTOR),
    0,
    NULL,
    RTL_NUMBER_OF(gP360WaveConnections),
    gP360WaveConnections,
    0,
    NULL
};

static PCPIN_DESCRIPTOR gP360TopologyPins[] = {
    {
        0,
        0,
        0,
        NULL,
        {
            0,
            NULL,
            0,
            NULL,
            RTL_NUMBER_OF(gP360AnalogRanges),
            gP360AnalogRanges,
            KSPIN_DATAFLOW_IN,
            KSPIN_COMMUNICATION_NONE,
            &KSCATEGORY_AUDIO,
            NULL,
            0
        }
    },
    {
        0,
        0,
        0,
        NULL,
        {
            0,
            NULL,
            0,
            NULL,
            RTL_NUMBER_OF(gP360AnalogRanges),
            gP360AnalogRanges,
            KSPIN_DATAFLOW_OUT,
            KSPIN_COMMUNICATION_NONE,
            &KSNODETYPE_SPEAKER,
            NULL,
            0
        }
    }
};

static PCCONNECTION_DESCRIPTOR gP360TopologyConnections[] = {
    { PCFILTER_NODE, P360_TOPO_BRIDGE_PIN, PCFILTER_NODE, P360_TOPO_SPEAKER_PIN }
};

static PCFILTER_DESCRIPTOR gP360TopologyFilter = {
    0,
    NULL,
    sizeof(PCPIN_DESCRIPTOR),
    RTL_NUMBER_OF(gP360TopologyPins),
    gP360TopologyPins,
    sizeof(PCNODE_DESCRIPTOR),
    0,
    NULL,
    RTL_NUMBER_OF(gP360TopologyConnections),
    gP360TopologyConnections,
    0,
    NULL
};

static BOOLEAN
p360_guid_equal(
    _In_ const GUID *Left,
    _In_ const GUID *Right
    )
{
    return Left && Right && IsEqualGUIDAligned(*Left,*Right);
}

static NTSTATUS
p360_copy_intersection(
    _In_reads_bytes_(Bytes) const VOID *Source,
    _In_ ULONG Bytes,
    _In_ ULONG OutputBufferLength,
    _Out_writes_bytes_to_opt_(OutputBufferLength,*ResultantFormatLength)
        PVOID ResultantFormat,
    _Out_ PULONG ResultantFormatLength
    )
{
    if (!Source || !ResultantFormatLength)
        return STATUS_INVALID_PARAMETER;

    *ResultantFormatLength=Bytes;

    if (!ResultantFormat)
        return STATUS_BUFFER_OVERFLOW;

    if (OutputBufferLength<Bytes)
        return STATUS_BUFFER_TOO_SMALL;

    RtlCopyMemory(ResultantFormat,Source,Bytes);
    return STATUS_SUCCESS;
}

static BOOLEAN
p360_format_supported(
    _In_ PKSDATAFORMAT DataFormat
    )
{
    PWAVEFORMATEX wave;

    if (!DataFormat ||
        DataFormat->FormatSize<sizeof(KSDATAFORMAT_WAVEFORMATEX) ||
        !p360_guid_equal(&DataFormat->MajorFormat,&KSDATAFORMAT_TYPE_AUDIO) ||
        !p360_guid_equal(&DataFormat->SubFormat,&KSDATAFORMAT_SUBTYPE_PCM) ||
        !p360_guid_equal(&DataFormat->Specifier,&KSDATAFORMAT_SPECIFIER_WAVEFORMATEX)) {
        return FALSE;
    }

    wave=reinterpret_cast<PWAVEFORMATEX>(DataFormat+1);

    if (wave->nChannels!=P360_SPEAKER_CHANNELS ||
        wave->nSamplesPerSec!=P360_SAMPLE_RATE ||
        wave->nAvgBytesPerSec!=
            P360_SAMPLE_RATE * P360_SPEAKER_CHANNELS * 2u ||
        wave->nBlockAlign!=P360_SPEAKER_CHANNELS * 2u ||
        wave->wBitsPerSample!=P360_SPEAKER_PCM_VALID_BITS) {
        return FALSE;
    }

    if (wave->wFormatTag==WAVE_FORMAT_PCM)
        return TRUE;

    if (wave->wFormatTag==WAVE_FORMAT_EXTENSIBLE &&
        wave->cbSize>=sizeof(WAVEFORMATEXTENSIBLE)-sizeof(WAVEFORMATEX) &&
        DataFormat->FormatSize>=sizeof(KSDATAFORMAT_WAVEFORMATEXTENSIBLE)) {
        PWAVEFORMATEXTENSIBLE ext=
            reinterpret_cast<PWAVEFORMATEXTENSIBLE>(wave);

        return ext->Samples.wValidBitsPerSample==
                   P360_SPEAKER_PCM_VALID_BITS &&
               ext->dwChannelMask==KSAUDIO_SPEAKER_STEREO &&
               p360_guid_equal(
                   &ext->SubFormat,
                   &KSDATAFORMAT_SUBTYPE_PCM);
    }

    return FALSE;
}

class P360TopologyMiniport final : public IMiniportTopology
{
public:
    P360TopologyMiniport() : m_Refs(1) {}

    STDMETHODIMP QueryInterface(
        _In_ REFIID InterfaceId,
        _COM_Outptr_ PVOID *Interface
        ) override
    {
        if (!Interface)
            return STATUS_INVALID_PARAMETER;

        *Interface=NULL;

        if (IsEqualGUIDAligned(InterfaceId,IID_IUnknown) ||
            IsEqualGUIDAligned(InterfaceId,IID_IMiniport) ||
            IsEqualGUIDAligned(InterfaceId,IID_IMiniportTopology)) {
            *Interface=static_cast<IMiniportTopology *>(this);
            AddRef();
            return STATUS_SUCCESS;
        }

        return STATUS_NOINTERFACE;
    }

    STDMETHODIMP_(ULONG) AddRef() override
    {
        return (ULONG)InterlockedIncrement(&m_Refs);
    }

    STDMETHODIMP_(ULONG) Release() override
    {
        LONG refs=InterlockedDecrement(&m_Refs);
        if (!refs) {
            this->~P360TopologyMiniport();
            ExFreePoolWithTag(this,P360_SPEAKER_POOL_TAG);
        }
        return (ULONG)refs;
    }

    STDMETHODIMP GetDescription(
        _Out_ PPCFILTER_DESCRIPTOR *Description
        ) override
    {
        if (!Description)
            return STATUS_INVALID_PARAMETER;
        *Description=&gP360TopologyFilter;
        return STATUS_SUCCESS;
    }

    STDMETHODIMP DataRangeIntersection(
        _In_ ULONG PinId,
        _In_ PKSDATARANGE DataRange,
        _In_ PKSDATARANGE MatchingDataRange,
        _In_ ULONG OutputBufferLength,
        _Out_writes_bytes_to_opt_(
            OutputBufferLength,
            *ResultantFormatLength)
            PVOID ResultantFormat,
        _Out_ PULONG ResultantFormatLength
        ) override
    {
        KSDATAFORMAT format;

        if (PinId>=RTL_NUMBER_OF(gP360TopologyPins) ||
            !DataRange || !MatchingDataRange ||
            !p360_guid_equal(
                &DataRange->MajorFormat,
                &MatchingDataRange->MajorFormat) ||
            !p360_guid_equal(
                &DataRange->SubFormat,
                &MatchingDataRange->SubFormat) ||
            !p360_guid_equal(
                &DataRange->Specifier,
                &MatchingDataRange->Specifier)) {
            return STATUS_NO_MATCH;
        }

        RtlZeroMemory(&format,sizeof(format));
        format.FormatSize=sizeof(format);
        format.MajorFormat=KSDATAFORMAT_TYPE_AUDIO;
        format.SubFormat=KSDATAFORMAT_SUBTYPE_ANALOG;
        format.Specifier=KSDATAFORMAT_SPECIFIER_NONE;

        return p360_copy_intersection(
            &format,
            sizeof(format),
            OutputBufferLength,
            ResultantFormat,
            ResultantFormatLength);
    }

    STDMETHODIMP Init(
        _In_ PUNKNOWN UnknownAdapter,
        _In_ PRESOURCELIST ResourceList,
        _In_ PPORTTOPOLOGY Port
        ) override
    {
        UNREFERENCED_PARAMETER(UnknownAdapter);
        UNREFERENCED_PARAMETER(ResourceList);

        return Port ? STATUS_SUCCESS : STATUS_INVALID_PARAMETER;
    }

    static NTSTATUS Create(_Outptr_ PUNKNOWN *Unknown)
    {
        PVOID memory;
        P360TopologyMiniport *object;

        if (!Unknown)
            return STATUS_INVALID_PARAMETER;
        *Unknown=NULL;

        memory=ExAllocatePool2(
            POOL_FLAG_NON_PAGED,
            sizeof(P360TopologyMiniport),
            P360_SPEAKER_POOL_TAG);
        if (!memory)
            return STATUS_INSUFFICIENT_RESOURCES;

        object=new(memory) P360TopologyMiniport();
        *Unknown=static_cast<IMiniportTopology *>(object);
        return STATUS_SUCCESS;
    }

private:
    volatile LONG m_Refs;
};

class P360WaveMiniport;

class P360WaveStream final : public IMiniportWaveRTStream
{
public:
    P360WaveStream(
        _In_ P360WaveMiniport *Owner,
        _In_ PPORTWAVERTSTREAM PortStream
        );

    ~P360WaveStream();

    STDMETHODIMP QueryInterface(
        _In_ REFIID InterfaceId,
        _COM_Outptr_ PVOID *Interface
        ) override;

    STDMETHODIMP_(ULONG) AddRef() override;
    STDMETHODIMP_(ULONG) Release() override;
    STDMETHODIMP SetFormat(_In_ PKSDATAFORMAT DataFormat) override;
    STDMETHODIMP SetState(_In_ KSSTATE State) override;
    STDMETHODIMP GetPosition(_Out_ PKSAUDIO_POSITION Position) override;

    STDMETHODIMP AllocateAudioBuffer(
        _In_ ULONG RequestedSize,
        _Out_ PMDL *AudioBufferMdl,
        _Out_ PULONG ActualSize,
        _Out_ PULONG OffsetFromFirstPage,
        _Out_ MEMORY_CACHING_TYPE *CacheType
        ) override;

    STDMETHODIMP_(VOID) FreeAudioBuffer(
        _In_opt_ PMDL AudioBufferMdl,
        _In_ ULONG BufferSize
        ) override;

    STDMETHODIMP_(VOID) GetHWLatency(
        _Out_ PKSRTAUDIO_HWLATENCY Latency
        ) override;

    STDMETHODIMP GetPositionRegister(
        _Out_ PKSRTAUDIO_HWREGISTER Register
        ) override;

    STDMETHODIMP GetClockRegister(
        _Out_ PKSRTAUDIO_HWREGISTER Register
        ) override;

    static NTSTATUS Create(
        _In_ P360WaveMiniport *Owner,
        _In_ PPORTWAVERTSTREAM PortStream,
        _Outptr_ PMINIPORTWAVERTSTREAM *Stream
        );

private:
    volatile LONG m_Refs;
    P360WaveMiniport *m_Owner;
    PPORTWAVERTSTREAM m_PortStream;
    KSSTATE m_State;
    PMDL m_Mdl;
    ULONG m_BufferBytes;
};

class P360WaveMiniport final : public IMiniportWaveRT
{
public:
    P360WaveMiniport() : m_Refs(1),m_StreamOpen(0) {}

    STDMETHODIMP QueryInterface(
        _In_ REFIID InterfaceId,
        _COM_Outptr_ PVOID *Interface
        ) override
    {
        if (!Interface)
            return STATUS_INVALID_PARAMETER;

        *Interface=NULL;

        if (IsEqualGUIDAligned(InterfaceId,IID_IUnknown) ||
            IsEqualGUIDAligned(InterfaceId,IID_IMiniport) ||
            IsEqualGUIDAligned(InterfaceId,IID_IMiniportWaveRT)) {
            *Interface=static_cast<IMiniportWaveRT *>(this);
            AddRef();
            return STATUS_SUCCESS;
        }

        return STATUS_NOINTERFACE;
    }

    STDMETHODIMP_(ULONG) AddRef() override
    {
        return (ULONG)InterlockedIncrement(&m_Refs);
    }

    STDMETHODIMP_(ULONG) Release() override
    {
        LONG refs=InterlockedDecrement(&m_Refs);
        if (!refs) {
            this->~P360WaveMiniport();
            ExFreePoolWithTag(this,P360_SPEAKER_POOL_TAG);
        }
        return (ULONG)refs;
    }

    STDMETHODIMP GetDescription(
        _Out_ PPCFILTER_DESCRIPTOR *Description
        ) override
    {
        if (!Description)
            return STATUS_INVALID_PARAMETER;
        *Description=&gP360WaveFilter;
        return STATUS_SUCCESS;
    }

    STDMETHODIMP DataRangeIntersection(
        _In_ ULONG PinId,
        _In_ PKSDATARANGE DataRange,
        _In_ PKSDATARANGE MatchingDataRange,
        _In_ ULONG OutputBufferLength,
        _Out_writes_bytes_to_opt_(
            OutputBufferLength,
            *ResultantFormatLength)
            PVOID ResultantFormat,
        _Out_ PULONG ResultantFormatLength
        ) override
    {
        if (!DataRange || !MatchingDataRange ||
            PinId>=RTL_NUMBER_OF(gP360WavePins)) {
            return STATUS_INVALID_PARAMETER;
        }

        if (PinId==P360_WAVE_SYSTEM_PIN) {
            if (!p360_guid_equal(
                    &DataRange->MajorFormat,
                    &KSDATAFORMAT_TYPE_AUDIO) ||
                !p360_guid_equal(
                    &DataRange->SubFormat,
                    &KSDATAFORMAT_SUBTYPE_PCM) ||
                !p360_guid_equal(
                    &DataRange->Specifier,
                    &KSDATAFORMAT_SPECIFIER_WAVEFORMATEX)) {
                return STATUS_NO_MATCH;
            }

            return p360_copy_intersection(
                &gP360SpeakerFormat,
                sizeof(gP360SpeakerFormat),
                OutputBufferLength,
                ResultantFormat,
                ResultantFormatLength);
        }

        if (!p360_guid_equal(
                &DataRange->MajorFormat,
                &MatchingDataRange->MajorFormat) ||
            !p360_guid_equal(
                &DataRange->SubFormat,
                &MatchingDataRange->SubFormat) ||
            !p360_guid_equal(
                &DataRange->Specifier,
                &MatchingDataRange->Specifier)) {
            return STATUS_NO_MATCH;
        }

        {
            KSDATAFORMAT format;
            RtlZeroMemory(&format,sizeof(format));
            format.FormatSize=sizeof(format);
            format.MajorFormat=KSDATAFORMAT_TYPE_AUDIO;
            format.SubFormat=KSDATAFORMAT_SUBTYPE_ANALOG;
            format.Specifier=KSDATAFORMAT_SPECIFIER_NONE;

            return p360_copy_intersection(
                &format,
                sizeof(format),
                OutputBufferLength,
                ResultantFormat,
                ResultantFormatLength);
        }
    }

    STDMETHODIMP Init(
        _In_ PUNKNOWN UnknownAdapter,
        _In_ PRESOURCELIST ResourceList,
        _In_ PPORTWAVERT Port
        ) override
    {
        UNREFERENCED_PARAMETER(UnknownAdapter);
        UNREFERENCED_PARAMETER(ResourceList);

        return Port ? STATUS_SUCCESS : STATUS_INVALID_PARAMETER;
    }

    STDMETHODIMP NewStream(
        _Outptr_ PMINIPORTWAVERTSTREAM *Stream,
        _In_ PPORTWAVERTSTREAM PortStream,
        _In_ ULONG Pin,
        _In_ BOOLEAN Capture,
        _In_ PKSDATAFORMAT DataFormat
        ) override
    {
        NTSTATUS status;

        if (!Stream || !PortStream || Capture ||
            Pin!=P360_WAVE_SYSTEM_PIN ||
            !p360_format_supported(DataFormat)) {
            return STATUS_INVALID_PARAMETER;
        }

        *Stream=NULL;

        if (InterlockedCompareExchange(&m_StreamOpen,1,0)!=0)
            return STATUS_DEVICE_BUSY;

        status=P360WaveStream::Create(
            this,
            PortStream,
            Stream);
        if (!NT_SUCCESS(status))
            InterlockedExchange(&m_StreamOpen,0);

        return status;
    }

    STDMETHODIMP GetDeviceDescription(
        _Out_ PDEVICE_DESCRIPTION DeviceDescription
        ) override
    {
        if (!DeviceDescription)
            return STATUS_INVALID_PARAMETER;

        RtlZeroMemory(
            DeviceDescription,
            sizeof(*DeviceDescription));
        DeviceDescription->Version=
            DEVICE_DESCRIPTION_VERSION;
        DeviceDescription->Master=TRUE;
        DeviceDescription->ScatterGather=TRUE;
        DeviceDescription->Dma32BitAddresses=TRUE;
        DeviceDescription->InterfaceType=PCIBus;
        DeviceDescription->MaximumLength=MAXULONG;
        return STATUS_SUCCESS;
    }

    static NTSTATUS Create(_Outptr_ PUNKNOWN *Unknown)
    {
        PVOID memory;
        P360WaveMiniport *object;

        if (!Unknown)
            return STATUS_INVALID_PARAMETER;
        *Unknown=NULL;

        memory=ExAllocatePool2(
            POOL_FLAG_NON_PAGED,
            sizeof(P360WaveMiniport),
            P360_SPEAKER_POOL_TAG);
        if (!memory)
            return STATUS_INSUFFICIENT_RESOURCES;

        object=new(memory) P360WaveMiniport();
        *Unknown=static_cast<IMiniportWaveRT *>(object);
        return STATUS_SUCCESS;
    }

    VOID StreamClosed()
    {
        InterlockedExchange(&m_StreamOpen,0);
    }

private:
    volatile LONG m_Refs;
    volatile LONG m_StreamOpen;
};

P360WaveStream::P360WaveStream(
    P360WaveMiniport *Owner,
    PPORTWAVERTSTREAM PortStream
    ) :
    m_Refs(1),
    m_Owner(Owner),
    m_PortStream(PortStream),
    m_State(KSSTATE_STOP),
    m_Mdl(NULL),
    m_BufferBytes(0)
{
    m_Owner->AddRef();
    m_PortStream->AddRef();
}

P360WaveStream::~P360WaveStream()
{
    if (m_Mdl) {
        m_PortStream->FreePagesFromMdl(m_Mdl);
        m_Mdl=NULL;
        m_BufferBytes=0;
    }

    if (m_PortStream) {
        m_PortStream->Release();
        m_PortStream=NULL;
    }

    if (m_Owner) {
        m_Owner->StreamClosed();
        m_Owner->Release();
        m_Owner=NULL;
    }
}

STDMETHODIMP
P360WaveStream::QueryInterface(
    REFIID InterfaceId,
    PVOID *Interface
    )
{
    if (!Interface)
        return STATUS_INVALID_PARAMETER;

    *Interface=NULL;

    if (IsEqualGUIDAligned(InterfaceId,IID_IUnknown) ||
        IsEqualGUIDAligned(InterfaceId,IID_IMiniportWaveRTStream)) {
        *Interface=static_cast<IMiniportWaveRTStream *>(this);
        AddRef();
        return STATUS_SUCCESS;
    }

    return STATUS_NOINTERFACE;
}

STDMETHODIMP_(ULONG)
P360WaveStream::AddRef()
{
    return (ULONG)InterlockedIncrement(&m_Refs);
}

STDMETHODIMP_(ULONG)
P360WaveStream::Release()
{
    LONG refs=InterlockedDecrement(&m_Refs);
    if (!refs) {
        this->~P360WaveStream();
        ExFreePoolWithTag(this,P360_SPEAKER_POOL_TAG);
    }
    return (ULONG)refs;
}

STDMETHODIMP
P360WaveStream::SetFormat(
    PKSDATAFORMAT DataFormat
    )
{
    if (m_State==KSSTATE_RUN)
        return STATUS_INVALID_DEVICE_STATE;

    return p360_format_supported(DataFormat) ?
        STATUS_SUCCESS :
        STATUS_NO_MATCH;
}

STDMETHODIMP
P360WaveStream::SetState(
    KSSTATE State
    )
{
    switch (State) {
    case KSSTATE_STOP:
        m_State=KSSTATE_STOP;
        return STATUS_SUCCESS;

    case KSSTATE_ACQUIRE:
    case KSSTATE_PAUSE:
        m_State=State;
        return STATUS_SUCCESS;

    case KSSTATE_RUN:
        /*
         * Hard barrier: the endpoint may enumerate and negotiate its fixed
         * PCM16 format, but playback cannot start until the SOF speaker
         * pipeline, SSP1 DAI and CoolStar render DMA are all bound to this
         * stream in a separately audited change.
         */
        return STATUS_DEVICE_NOT_READY;

    default:
        return STATUS_INVALID_PARAMETER;
    }
}

STDMETHODIMP
P360WaveStream::GetPosition(
    PKSAUDIO_POSITION Position
    )
{
    if (!Position)
        return STATUS_INVALID_PARAMETER;

    Position->PlayOffset=0;
    Position->WriteOffset=0;
    return STATUS_SUCCESS;
}

STDMETHODIMP
P360WaveStream::AllocateAudioBuffer(
    ULONG RequestedSize,
    PMDL *AudioBufferMdl,
    PULONG ActualSize,
    PULONG OffsetFromFirstPage,
    MEMORY_CACHING_TYPE *CacheType
    )
{
    PHYSICAL_ADDRESS high;
    PMDL mdl;

    if (!AudioBufferMdl || !ActualSize ||
        !OffsetFromFirstPage || !CacheType ||
        m_Mdl || !RequestedSize ||
        RequestedSize>P360_MAX_WAVERT_BUFFER) {
        return STATUS_INVALID_PARAMETER;
    }

    RequestedSize-=RequestedSize %
        (P360_SPEAKER_CHANNELS * 2u);
    if (!RequestedSize)
        return STATUS_INVALID_BUFFER_SIZE;

    high.QuadPart=MAXULONG;

    mdl=m_PortStream->AllocatePagesForMdl(
        high,
        RequestedSize);
    if (!mdl)
        return STATUS_INSUFFICIENT_RESOURCES;

    m_Mdl=mdl;
    m_BufferBytes=RequestedSize;

    *AudioBufferMdl=mdl;
    *ActualSize=RequestedSize;
    *OffsetFromFirstPage=0;
    *CacheType=MmCached;
    return STATUS_SUCCESS;
}

STDMETHODIMP_(VOID)
P360WaveStream::FreeAudioBuffer(
    PMDL AudioBufferMdl,
    ULONG BufferSize
    )
{
    UNREFERENCED_PARAMETER(BufferSize);

    if (AudioBufferMdl && AudioBufferMdl==m_Mdl) {
        m_PortStream->FreePagesFromMdl(m_Mdl);
        m_Mdl=NULL;
        m_BufferBytes=0;
    }
}

STDMETHODIMP_(VOID)
P360WaveStream::GetHWLatency(
    PKSRTAUDIO_HWLATENCY Latency
    )
{
    if (Latency)
        RtlZeroMemory(Latency,sizeof(*Latency));
}

STDMETHODIMP
P360WaveStream::GetPositionRegister(
    PKSRTAUDIO_HWREGISTER Register
    )
{
    UNREFERENCED_PARAMETER(Register);
    return STATUS_NOT_IMPLEMENTED;
}

STDMETHODIMP
P360WaveStream::GetClockRegister(
    PKSRTAUDIO_HWREGISTER Register
    )
{
    UNREFERENCED_PARAMETER(Register);
    return STATUS_NOT_IMPLEMENTED;
}

NTSTATUS
P360WaveStream::Create(
    P360WaveMiniport *Owner,
    PPORTWAVERTSTREAM PortStream,
    PMINIPORTWAVERTSTREAM *Stream
    )
{
    PVOID memory;
    P360WaveStream *object;

    if (!Owner || !PortStream || !Stream)
        return STATUS_INVALID_PARAMETER;
    *Stream=NULL;

    memory=ExAllocatePool2(
        POOL_FLAG_NON_PAGED,
        sizeof(P360WaveStream),
        P360_SPEAKER_POOL_TAG);
    if (!memory)
        return STATUS_INSUFFICIENT_RESOURCES;

    object=new(memory) P360WaveStream(
        Owner,
        PortStream);
    *Stream=static_cast<IMiniportWaveRTStream *>(object);
    return STATUS_SUCCESS;
}

static NTSTATUS
p360_register_topology(
    _In_ PDEVICE_OBJECT DeviceObject,
    _In_opt_ PIRP Irp,
    _In_ PRESOURCELIST ResourceList,
    _Outptr_ PUNKNOWN *UnknownPort
    )
{
    PPORT port=NULL;
    PUNKNOWN miniport=NULL;
    WCHAR name[]=L"TopologySpeaker";
    NTSTATUS status;

    if (!UnknownPort)
        return STATUS_INVALID_PARAMETER;
    *UnknownPort=NULL;

    status=PcNewPort(&port,CLSID_PortTopology);
    if (!NT_SUCCESS(status))
        return status;

    status=P360TopologyMiniport::Create(&miniport);
    if (!NT_SUCCESS(status))
        goto done;

    status=port->Init(
        DeviceObject,
        Irp,
        miniport,
        NULL,
        ResourceList);
    if (!NT_SUCCESS(status))
        goto done;

    status=PcRegisterSubdevice(
        DeviceObject,
        name,
        port);
    if (!NT_SUCCESS(status))
        goto done;

    *UnknownPort=port;
    port=NULL;

done:
    if (miniport)
        miniport->Release();
    if (port)
        port->Release();
    return status;
}

static NTSTATUS
p360_register_wave(
    _In_ PDEVICE_OBJECT DeviceObject,
    _In_opt_ PIRP Irp,
    _In_ PRESOURCELIST ResourceList,
    _Outptr_ PUNKNOWN *UnknownPort
    )
{
    PPORT port=NULL;
    PUNKNOWN miniport=NULL;
    WCHAR name[]=L"WaveSpeaker";
    NTSTATUS status;

    if (!UnknownPort)
        return STATUS_INVALID_PARAMETER;
    *UnknownPort=NULL;

    status=PcNewPort(
        reinterpret_cast<PPORT *>(&port),
        CLSID_PortWaveRT);
    if (!NT_SUCCESS(status))
        return status;

    status=P360WaveMiniport::Create(&miniport);
    if (!NT_SUCCESS(status))
        goto done;

    status=port->Init(
        DeviceObject,
        Irp,
        miniport,
        NULL,
        ResourceList);
    if (!NT_SUCCESS(status))
        goto done;

    status=PcRegisterSubdevice(
        DeviceObject,
        name,
        port);
    if (!NT_SUCCESS(status))
        goto done;

    *UnknownPort=port;
    port=NULL;

done:
    if (miniport)
        miniport->Release();
    if (port)
        port->Release();
    return status;
}

static NTSTATUS
p360_unregister_subdevice(
    _In_ PDEVICE_OBJECT DeviceObject,
    _In_opt_ PUNKNOWN Port
    )
{
    PUNREGISTERSUBDEVICE unregisterSubdevice=NULL;
    NTSTATUS status;

    if (!Port)
        return STATUS_SUCCESS;

    status=Port->QueryInterface(
        IID_IUnregisterSubdevice,
        reinterpret_cast<PVOID *>(&unregisterSubdevice));
    if (!NT_SUCCESS(status))
        return status;

    status=unregisterSubdevice->UnregisterSubdevice(
        DeviceObject,
        Port);
    unregisterSubdevice->Release();
    return status;
}

extern "C"
NTSTATUS
p360_speaker_endpoint_install(
    PDEVICE_OBJECT DeviceObject,
    PIRP Irp,
    PRESOURCELIST ResourceList,
    PVOID *TopologyPort,
    PVOID *WavePort
    )
{
    PUNKNOWN topology=NULL;
    PUNKNOWN wave=NULL;
    NTSTATUS status;

    if (!DeviceObject || !ResourceList ||
        !TopologyPort || !WavePort ||
        KeGetCurrentIrql()!=PASSIVE_LEVEL) {
        return STATUS_INVALID_PARAMETER;
    }

    *TopologyPort=NULL;
    *WavePort=NULL;

    status=p360_register_topology(
        DeviceObject,
        Irp,
        ResourceList,
        &topology);
    if (!NT_SUCCESS(status))
        goto done;

    status=p360_register_wave(
        DeviceObject,
        Irp,
        ResourceList,
        &wave);
    if (!NT_SUCCESS(status))
        goto done;

    status=PcRegisterPhysicalConnection(
        DeviceObject,
        wave,
        P360_WAVE_BRIDGE_PIN,
        topology,
        P360_TOPO_BRIDGE_PIN);
    if (!NT_SUCCESS(status))
        goto done;

    *TopologyPort=topology;
    *WavePort=wave;
    topology=NULL;
    wave=NULL;

done:
    if (!NT_SUCCESS(status)) {
        if (wave)
            (void)p360_unregister_subdevice(
                DeviceObject,
                wave);
        if (topology)
            (void)p360_unregister_subdevice(
                DeviceObject,
                topology);
    }

    if (wave)
        wave->Release();
    if (topology)
        topology->Release();

    return status;
}

extern "C"
NTSTATUS
p360_speaker_endpoint_uninstall(
    PDEVICE_OBJECT DeviceObject,
    PVOID *TopologyPort,
    PVOID *WavePort
    )
{
    PUNKNOWN topology;
    PUNKNOWN wave;
    PUNREGISTERPHYSICALCONNECTION unregisterConnection=NULL;
    NTSTATUS firstStatus=STATUS_SUCCESS;
    NTSTATUS status;

    if (!DeviceObject || !TopologyPort || !WavePort ||
        KeGetCurrentIrql()!=PASSIVE_LEVEL) {
        return STATUS_INVALID_PARAMETER;
    }

    topology=reinterpret_cast<PUNKNOWN>(*TopologyPort);
    wave=reinterpret_cast<PUNKNOWN>(*WavePort);

    if (topology && wave) {
        status=topology->QueryInterface(
            IID_IUnregisterPhysicalConnection,
            reinterpret_cast<PVOID *>(&unregisterConnection));
        if (NT_SUCCESS(status)) {
            status=unregisterConnection->UnregisterPhysicalConnection(
                DeviceObject,
                wave,
                P360_WAVE_BRIDGE_PIN,
                topology,
                P360_TOPO_BRIDGE_PIN);
            unregisterConnection->Release();
            unregisterConnection=NULL;
        }

        if (!NT_SUCCESS(status) &&
            NT_SUCCESS(firstStatus)) {
            firstStatus=status;
        }
    }

    status=p360_unregister_subdevice(
        DeviceObject,
        wave);
    if (!NT_SUCCESS(status) &&
        NT_SUCCESS(firstStatus)) {
        firstStatus=status;
    }

    status=p360_unregister_subdevice(
        DeviceObject,
        topology);
    if (!NT_SUCCESS(status) &&
        NT_SUCCESS(firstStatus)) {
        firstStatus=status;
    }

    if (wave) {
        wave->Release();
        *WavePort=NULL;
    }

    if (topology) {
        topology->Release();
        *TopologyPort=NULL;
    }

    return firstStatus;
}
