#define INITGUID
#include <initguid.h>
#include <ntddk.h>
#include <portcls.h>
#include <ksmedia.h>

#include "../include/p360_board.h"
#include "../include/p360_speaker_endpoint.h"
#include "../driver/p360_driver.h"

/*
 * WDK /kernel does not support the CRT <new> header because that header
 * exposes exception-handling machinery. These miniports only need placement
 * construction into ExAllocatePool2 memory, so provide the two non-allocating
 * placement operators locally and keep all object lifetime explicit.
 */
__forceinline void * __cdecl
operator new(
    size_t,
    void *memory
    ) noexcept
{
    return memory;
}

__forceinline void __cdecl
operator delete(
    void *,
    void *
    ) noexcept
{
}

/*
 * MSVC emits scalar deleting destructors for these COM-style C++ objects even
 * though normal lifetime is controlled by Release(). Provide the matching CRT
 * delete entry points so /kernel never pulls the user-mode C++ runtime.
 * They intentionally do not free memory: Release() runs the destructor and
 * ExFreePoolWithTag() exactly once.
 */
void __cdecl
operator delete(
    void *
    ) noexcept
{
}

void __cdecl
operator delete(
    void *,
    size_t
    ) noexcept
{
}

#define P360_SPEAKER_POOL_TAG ((ULONG)'S63P')
#define P360_WAVE_SYSTEM_PIN 0u
#define P360_WAVE_BRIDGE_PIN 1u
#define P360_TOPO_BRIDGE_PIN 0u
#define P360_TOPO_SPEAKER_PIN 1u

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
            P360_SAMPLE_RATE * P360_SPEAKER_CHANNELS *
                (P360_SPEAKER_CONTAINER_BITS / 8u),
            P360_SPEAKER_CHANNELS *
                (P360_SPEAKER_CONTAINER_BITS / 8u),
            P360_SPEAKER_CONTAINER_BITS,
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
    P360_SPEAKER_CONTAINER_BITS,
    P360_SPEAKER_CONTAINER_BITS,
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
            P360_SAMPLE_RATE * P360_SPEAKER_CHANNELS *
            (P360_SPEAKER_CONTAINER_BITS / 8u) ||
        wave->nBlockAlign!=
            P360_SPEAKER_CHANNELS *
            (P360_SPEAKER_CONTAINER_BITS / 8u) ||
        wave->wBitsPerSample!=P360_SPEAKER_CONTAINER_BITS) {
        return FALSE;
    }

    /*
     * CoolStar MAX98357A explicitly requests 16 valid bits in a forced
     * 32-bit output container. Plain WAVE_FORMAT_PCM cannot represent that
     * distinction, so admit only WAVE_FORMAT_EXTENSIBLE.
     */
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

static BOOLEAN
p360_playback_memory_released(
    _In_ const P360_PLAYBACK_STREAM *Playback
    )
{
    if (!Playback)
        return FALSE;

    return !Playback->AudioMdl &&
        !Playback->PageTable &&
        !Playback->StreamOwned &&
        !Playback->StreamPrepared &&
        !Playback->Running &&
        !Playback->SofRunning &&
        !Playback->SofParamsPrepared;
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
        _In_ PPORTWAVERTSTREAM PortStream,
        _Inout_ P360_DEVICE_CONTEXT *Context
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
        _Inout_ P360_DEVICE_CONTEXT *Context,
        _Outptr_ PMINIPORTWAVERTSTREAM *Stream
        );

private:
    NTSTATUS EnsurePlaybackPrepared();

    volatile LONG m_Refs;
    P360WaveMiniport *m_Owner;
    PPORTWAVERTSTREAM m_PortStream;
    KSSTATE m_State;
    PMDL m_Mdl;
    ULONG m_BufferBytes;
    P360_DEVICE_CONTEXT *m_Context;
    WDFDEVICE m_FrameworkDevice;
    P360_PLAYBACK_STREAM m_Playback;
};

class P360WaveMiniport final : public IMiniportWaveRT
{
public:
    explicit P360WaveMiniport(
        _Inout_ P360_DEVICE_CONTEXT *Context
        ) : m_Refs(1),m_StreamOpen(0),m_Context(Context) {}

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
            m_Context,
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

    static NTSTATUS Create(
        _Inout_ P360_DEVICE_CONTEXT *Context,
        _Outptr_ PUNKNOWN *Unknown)
    {
        PVOID memory;
        P360WaveMiniport *object;

        if (!Context || !Unknown)
            return STATUS_INVALID_PARAMETER;
        *Unknown=NULL;

        memory=ExAllocatePool2(
            POOL_FLAG_NON_PAGED,
            sizeof(P360WaveMiniport),
            P360_SPEAKER_POOL_TAG);
        if (!memory)
            return STATUS_INSUFFICIENT_RESOURCES;

        object=new(memory) P360WaveMiniport(Context);
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
    P360_DEVICE_CONTEXT *m_Context;
};

P360WaveStream::P360WaveStream(
    P360WaveMiniport *Owner,
    PPORTWAVERTSTREAM PortStream,
    P360_DEVICE_CONTEXT *Context
    ) :
    m_Refs(1),
    m_Owner(Owner),
    m_PortStream(PortStream),
    m_State(KSSTATE_STOP),
    m_Mdl(NULL),
    m_BufferBytes(0),
    m_Context(Context),
    m_FrameworkDevice(Context ? Context->FrameworkDevice : NULL)
{
    RtlZeroMemory(&m_Playback,sizeof(m_Playback));
    if (m_FrameworkDevice)
        WdfObjectReference(m_FrameworkDevice);
    m_Owner->AddRef();
    m_PortStream->AddRef();
}

P360WaveStream::~P360WaveStream()
{
    if (m_Context &&
        (m_Playback.StreamOwned ||
         m_Playback.SofParamsPrepared ||
         m_Playback.PageTable)) {
        (void)p360_host_playback_release(
            m_Context,
            &m_Playback);
    }

    if (m_Mdl && !p360_playback_memory_released(&m_Playback)) {
        /*
         * A void COM destructor cannot report teardown failure. Fail closed:
         * retain the PortCls stream/framework references and its MDL rather
         * than free pages that SOF/HDA may still DMA into. This is a
         * quarantine/reboot path, not a normal leak.
         */
        if (m_Context)
            p360_state_fail(&m_Context->State,P360_FAIL_STREAM);
        return;
    }

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

    if (m_FrameworkDevice) {
        WdfObjectDereference(m_FrameworkDevice);
        m_FrameworkDevice=NULL;
    }
    m_Context=NULL;
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

NTSTATUS
P360WaveStream::EnsurePlaybackPrepared()
{
    if (!m_Context || !m_Mdl || !m_BufferBytes)
        return STATUS_DEVICE_NOT_READY;

    if (m_Playback.SofParamsPrepared)
        return STATUS_SUCCESS;

    /*
     * Normal D0Exit releases HOST/HDA ownership while PortCls may retain the
     * WaveRT pin and its MDL. After D0Entry rebuilds the SOF topology, bind
     * that same WaveRT buffer to a fresh CoolStar HDA stream/tag and resend
     * PCM_PARAMS. This is also harmless on the initial STOP->ACQUIRE path
     * because AllocateAudioBuffer has already prepared it.
     */
    return p360_host_playback_prepare(
        m_Context,
        &m_Playback,
        m_Mdl,
        m_BufferBytes,
        m_BufferBytes / 4u);
}

STDMETHODIMP
P360WaveStream::SetState(
    KSSTATE State
    )
{
    NTSTATUS status;

    if (!m_Context)
        return STATUS_INVALID_DEVICE_STATE;

    switch (State) {
    case KSSTATE_STOP:
        /*
         * STOP is a transport reset, not a pause. Release PCM/HDA ownership
         * so the next STOP->ACQUIRE transition receives a freshly reset HDA
         * descriptor and starts at byte zero. The WaveRT MDL remains owned by
         * PortCls and is rebound lazily by EnsurePlaybackPrepared().
         */
        status=p360_host_playback_release(
            m_Context,
            &m_Playback);
        if (NT_SUCCESS(status))
            m_State=KSSTATE_STOP;
        return status;

    case KSSTATE_ACQUIRE:
        status=EnsurePlaybackPrepared();
        if (!NT_SUCCESS(status))
            return status;
        m_State=KSSTATE_ACQUIRE;
        return STATUS_SUCCESS;

    case KSSTATE_PAUSE:
        if (m_State==KSSTATE_RUN) {
            status=p360_host_playback_stop(
                m_Context,
                &m_Playback);
            if (!NT_SUCCESS(status))
                return status;
        } else {
            status=EnsurePlaybackPrepared();
            if (!NT_SUCCESS(status))
                return status;
        }
        m_State=KSSTATE_PAUSE;
        return STATUS_SUCCESS;

    case KSSTATE_RUN:
        if (m_State==KSSTATE_RUN)
            return STATUS_SUCCESS;

        status=EnsurePlaybackPrepared();
        if (!NT_SUCCESS(status))
            return status;

        status=p360_host_playback_start(
            m_Context,
            &m_Playback);
        if (NT_SUCCESS(status))
            m_State=KSSTATE_RUN;
        return status;

    default:
        return STATUS_INVALID_PARAMETER;
    }
}

STDMETHODIMP
P360WaveStream::GetPosition(
    PKSAUDIO_POSITION Position
    )
{
    ULONGLONG position;

    if (!Position)
        return STATUS_INVALID_PARAMETER;

    if (m_State==KSSTATE_STOP) {
        Position->PlayOffset=0;
        Position->WriteOffset=0;
        return STATUS_SUCCESS;
    }

    if (!m_BufferBytes || !m_Playback.StreamOwned) {
        Position->PlayOffset=0;
        Position->WriteOffset=0;
        return STATUS_SUCCESS;
    }

    position=(ULONGLONG)p360_playback_stream_position(
        &m_Playback) % (ULONGLONG)m_BufferBytes;

    Position->PlayOffset=position;
    Position->WriteOffset=position;
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
        RequestedSize>P360_PLAYBACK_MAX_BUFFER_BYTES ||
        !m_Context) {
        return STATUS_INVALID_PARAMETER;
    }

    /*
     * Four periods keep SOF's host-period contract integral while preserving
     * frame alignment for stereo S16 WaveRT buffers.
     */
    {
        const ULONG alignment=
            P360_SPEAKER_CHANNELS *
            (P360_SPEAKER_CONTAINER_BITS / 8u) * 4u;
        const ULONG remainder=RequestedSize % alignment;

        if (remainder) {
            const ULONG delta=alignment-remainder;
            if (RequestedSize>P360_PLAYBACK_MAX_BUFFER_BYTES-delta)
                return STATUS_INVALID_BUFFER_SIZE;
            RequestedSize+=delta;
        }

        if (!RequestedSize ||
            RequestedSize>P360_PLAYBACK_MAX_BUFFER_BYTES)
            return STATUS_INVALID_BUFFER_SIZE;
    }

    high.QuadPart=MAXULONG;

    mdl=m_PortStream->AllocatePagesForMdl(
        high,
        RequestedSize);
    if (!mdl)
        return STATUS_INSUFFICIENT_RESOURCES;

    {
        NTSTATUS status=p360_host_playback_prepare(
            m_Context,
            &m_Playback,
            mdl,
            RequestedSize,
            RequestedSize / 4u);
        if (!NT_SUCCESS(status)) {
            m_PortStream->FreePagesFromMdl(mdl);
            return status;
        }
    }

    m_Mdl=mdl;
    m_BufferBytes=RequestedSize;

    *AudioBufferMdl=mdl;
    *ActualSize=RequestedSize;
    *OffsetFromFirstPage=0;
    *CacheType=MmWriteCombined;
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
        if (m_Context)
            (void)p360_host_playback_release(
                m_Context,
                &m_Playback);

        if (!p360_playback_memory_released(&m_Playback)) {
            /*
             * FreeAudioBuffer is void, so it cannot surface a failed SOF/HDA
             * release to PortCls. Retain the MDL instead of creating a DMA
             * use-after-free; normal PnP teardown will then remain blocked by
             * the same latched ownership.
             */
            if (m_Context)
                p360_state_fail(&m_Context->State,P360_FAIL_STREAM);
            return;
        }

        m_PortStream->FreePagesFromMdl(m_Mdl);
        m_Mdl=NULL;
        m_BufferBytes=0;
        m_State=KSSTATE_STOP;
        RtlZeroMemory(&m_Playback,sizeof(m_Playback));
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
    return STATUS_NOT_SUPPORTED;
}

STDMETHODIMP
P360WaveStream::GetClockRegister(
    PKSRTAUDIO_HWREGISTER Register
    )
{
    UNREFERENCED_PARAMETER(Register);
    return STATUS_NOT_SUPPORTED;
}

NTSTATUS
P360WaveStream::Create(
    P360WaveMiniport *Owner,
    PPORTWAVERTSTREAM PortStream,
    P360_DEVICE_CONTEXT *Context,
    PMINIPORTWAVERTSTREAM *Stream
    )
{
    PVOID memory;
    P360WaveStream *object;

    if (!Owner || !PortStream || !Context || !Stream)
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
        PortStream,
        Context);
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
    _Inout_ P360_DEVICE_CONTEXT *Context,
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

    status=P360WaveMiniport::Create(
        Context,
        &miniport);
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
    P360_DEVICE_CONTEXT *Context,
    PVOID *TopologyPort,
    PVOID *WavePort
    )
{
    PUNKNOWN topology=NULL;
    PUNKNOWN wave=NULL;
    NTSTATUS status;

    if (!DeviceObject || !ResourceList || !Context ||
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
        Context,
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
