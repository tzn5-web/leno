#include "../include/p360_csaudio.h"
#include "../include/p360_board.h"

static VOID
p360_csaudio_callback(
    _In_opt_ PVOID CallbackContext,
    _In_opt_ PVOID Argument1,
    _In_opt_ PVOID Argument2
    )
{
    P360_CSAUDIO_LINK *link=(P360_CSAUDIO_LINK *)CallbackContext;
    const P360_CSAUDIO_ARG *arg=(const P360_CSAUDIO_ARG *)Argument1;
    P360_CSAUDIO_ARG local;

    if (!link || !arg || Argument2==&link->SenderCookie)
        return;

    if (arg->argSz < (UINT32)FIELD_OFFSET(P360_CSAUDIO_ARG,Payload) ||
        arg->argSz > sizeof(P360_CSAUDIO_ARG))
        return;

    RtlZeroMemory(&local,sizeof(local));
    RtlCopyMemory(&local,arg,arg->argSz);

    if (local.endpointType!=P360_CSAUDIO_ENDPOINT_SPEAKER)
        return;

    if ((local.endpointRequest==P360_CSAUDIO_ENDPOINT_START_ACK ||
         local.endpointRequest==P360_CSAUDIO_ENDPOINT_STOP_ACK) &&
        local.argSz>=sizeof(P360_CSAUDIO_ARG) &&
        local.Payload.transition.generation) {
        InterlockedExchange(
            &link->AckRequest,
            (LONG)local.endpointRequest);
        InterlockedExchange(
            &link->AckStatus,
            local.Payload.transition.status);
        InterlockedExchange(
            &link->AckPoweredOn,
            (LONG)local.Payload.transition.poweredOn);
        KeMemoryBarrier();
        InterlockedExchange(
            &link->AckGeneration,
            (LONG)local.Payload.transition.generation);
        return;
    }

    if (local.endpointRequest==P360_CSAUDIO_ENDPOINT_REGISTER) {
        InterlockedExchange(&link->SpeakerRegistered,1);
        return;
    }

    if (local.endpointRequest==P360_CSAUDIO_ENDPOINT_OVERRIDE_FORMAT &&
        local.argSz>=sizeof(P360_CSAUDIO_ARG)) {
        UINT16 channels=local.Payload.formatOverride.channels ?
            local.Payload.formatOverride.channels :
            (UINT16)P360_SPEAKER_CHANNELS;
        UINT16 frequency=local.Payload.formatOverride.frequency ?
            local.Payload.formatOverride.frequency :
            (UINT16)P360_SAMPLE_RATE;

        /*
         * CoolStar max98357a publishes bits=16, valid=16 and leaves
         * channels/frequency at zero while forcing a 32-bit output
         * container.  Zero therefore means "keep board default", not an
         * invalid 0 Hz/0 channel format.  Reject any incompatible callback
         * instead of silently changing the fixed Phaser360 speaker profile.
         */
        if (channels!=(UINT16)P360_SPEAKER_CHANNELS ||
            frequency!=(UINT16)P360_SAMPLE_RATE ||
            local.Payload.formatOverride.bitsPerSample!=16u ||
            local.Payload.formatOverride.validBitsPerSample!=
                (UINT16)P360_SPEAKER_PCM_VALID_BITS ||
            !local.Payload.formatOverride.force32BitOutputContainer) {
            return;
        }

        link->SpeakerChannels=channels;
        link->SpeakerFrequency=frequency;
        link->SpeakerBitsPerSample=local.Payload.formatOverride.bitsPerSample;
        link->SpeakerValidBitsPerSample=local.Payload.formatOverride.validBitsPerSample;
        link->SpeakerForce32=TRUE;
        KeMemoryBarrier();
        InterlockedExchange(&link->SpeakerFormatSeen,1);
    }
}

static VOID
p360_csaudio_notify(
    _Inout_ P360_CSAUDIO_LINK *link,
    _In_ P360_CSAUDIO_ENDPOINT_TYPE endpoint,
    _In_ P360_CSAUDIO_ENDPOINT_REQUEST request,
    _In_ UINT32 generation
    )
{
    P360_CSAUDIO_ARG arg;

    RtlZeroMemory(&arg,sizeof(arg));
    arg.argSz=sizeof(arg);
    arg.endpointType=endpoint;
    arg.endpointRequest=request;
    arg.Payload.transition.generation=generation;

    ExNotifyCallback(
        link->Callback,
        &arg,
        &link->SenderCookie);
}

static UINT32
p360_csaudio_next_generation(
    _Inout_ P360_CSAUDIO_LINK *link)
{
    LONG generation;

    generation=InterlockedIncrement(
        &link->SpeakerGeneration);
    if (!generation)
        generation=InterlockedIncrement(
            &link->SpeakerGeneration);

    return (UINT32)generation;
}

static VOID
p360_csaudio_reset_ack(
    _Inout_ P360_CSAUDIO_LINK *link)
{
    InterlockedExchange(&link->AckGeneration,0);
    InterlockedExchange(&link->AckRequest,0);
    InterlockedExchange(&link->AckStatus,STATUS_PENDING);
    InterlockedExchange(&link->AckPoweredOn,-1);
    KeMemoryBarrier();
}

static NTSTATUS
p360_csaudio_require_ack(
    _Inout_ P360_CSAUDIO_LINK *link,
    _In_ UINT32 generation,
    _In_ P360_CSAUDIO_ENDPOINT_REQUEST expectedRequest,
    _In_ BOOLEAN expectedPoweredOn)
{
    LONG ackGeneration;
    LONG ackRequest;
    LONG ackStatus;
    LONG ackPoweredOn;

    KeMemoryBarrier();
    ackGeneration=InterlockedCompareExchange(
        &link->AckGeneration,0,0);
    ackRequest=InterlockedCompareExchange(
        &link->AckRequest,0,0);
    ackStatus=InterlockedCompareExchange(
        &link->AckStatus,0,0);
    ackPoweredOn=InterlockedCompareExchange(
        &link->AckPoweredOn,0,0);

    if ((UINT32)ackGeneration!=generation ||
        ackRequest!=(LONG)expectedRequest)
        return STATUS_IO_TIMEOUT;

    if (!NT_SUCCESS((NTSTATUS)ackStatus))
        return (NTSTATUS)ackStatus;

    if (!!ackPoweredOn!=!!expectedPoweredOn)
        return STATUS_DEVICE_HARDWARE_ERROR;

    return STATUS_SUCCESS;
}

NTSTATUS
p360_csaudio_open(
    P360_CSAUDIO_LINK *link
    )
{
    UNICODE_STRING name;
    OBJECT_ATTRIBUTES attributes;
    NTSTATUS status;

    if (!link || KeGetCurrentIrql()!=PASSIVE_LEVEL)
        return STATUS_INVALID_PARAMETER;

    RtlZeroMemory(link,sizeof(*link));
    link->SenderCookie=0x36304143u; /* CA06 */

    RtlInitUnicodeString(
        &name,
        L"\\CallBack\\CsAudioCallbackAPI");

    InitializeObjectAttributes(
        &attributes,
        &name,
        OBJ_KERNEL_HANDLE | OBJ_OPENIF | OBJ_CASE_INSENSITIVE,
        NULL,
        NULL);

    status=ExCreateCallback(
        &link->Callback,
        &attributes,
        TRUE,
        TRUE);
    if (!NT_SUCCESS(status))
        return status;

    link->Registration=ExRegisterCallback(
        link->Callback,
        p360_csaudio_callback,
        link);
    if (!link->Registration) {
        ObfDereferenceObject(link->Callback);
        link->Callback=NULL;
        return STATUS_NO_CALLBACK_ACTIVE;
    }

    link->Open=TRUE;

    /*
     * Announce the DSP endpoint. A loaded CoolStar MAX98357A driver responds
     * synchronously with Speaker/Register and OverrideFormat. Registration is
     * discovery only; it must never imply that the amplifier may be started.
     */
    p360_csaudio_notify(
        link,
        P360_CSAUDIO_ENDPOINT_DSP,
        P360_CSAUDIO_ENDPOINT_REGISTER,
        0u);

    /*
     * A legacy CoolStar amplifier can register but cannot prove SDMODE low.
     * The final Phaser360 driver requires the generation-tagged safe MAX
     * protocol before it will accept the speaker dependency.
     */
    if (InterlockedCompareExchange(
            &link->SpeakerRegistered,0,0)) {
        status=p360_csaudio_speaker_stop(link);
        if (!NT_SUCCESS(status)) {
            ExUnregisterCallback(link->Registration);
            link->Registration=NULL;
            ObfDereferenceObject(link->Callback);
            link->Callback=NULL;
            link->Open=FALSE;
            return status;
        }
    }

    return STATUS_SUCCESS;
}

NTSTATUS
p360_csaudio_speaker_start(
    P360_CSAUDIO_LINK *link
    )
{
    UINT32 generation;
    NTSTATUS status;

    if (!link || !link->Open || !link->Callback ||
        KeGetCurrentIrql()!=PASSIVE_LEVEL)
        return STATUS_INVALID_DEVICE_STATE;

    if (!InterlockedCompareExchange(
            &link->SpeakerRegistered,0,0))
        return STATUS_NOT_FOUND;

    if (!InterlockedCompareExchange(
            &link->SpeakerFormatSeen,0,0) ||
        link->SpeakerChannels!=(UINT16)P360_SPEAKER_CHANNELS ||
        link->SpeakerFrequency!=(UINT16)P360_SAMPLE_RATE ||
        link->SpeakerBitsPerSample!=16u ||
        link->SpeakerValidBitsPerSample!=
            (UINT16)P360_SPEAKER_PCM_VALID_BITS ||
        !link->SpeakerForce32) {
        return STATUS_DEVICE_CONFIGURATION_ERROR;
    }

    if (InterlockedCompareExchange(
            &link->SpeakerStarted,1,0)!=0)
        return STATUS_DEVICE_BUSY;

    generation=p360_csaudio_next_generation(link);
    p360_csaudio_reset_ack(link);

    p360_csaudio_notify(
        link,
        P360_CSAUDIO_ENDPOINT_SPEAKER,
        P360_CSAUDIO_ENDPOINT_START,
        generation);

    status=p360_csaudio_require_ack(
        link,
        generation,
        P360_CSAUDIO_ENDPOINT_START_ACK,
        TRUE);
    if (!NT_SUCCESS(status)) {
        InterlockedExchange(&link->SpeakerStarted,0);
        return status;
    }

    return STATUS_SUCCESS;
}

NTSTATUS
p360_csaudio_speaker_stop(
    P360_CSAUDIO_LINK *link
    )
{
    UINT32 generation;
    NTSTATUS status;

    if (!link || !link->Open || !link->Callback ||
        KeGetCurrentIrql()!=PASSIVE_LEVEL)
        return STATUS_INVALID_DEVICE_STATE;

    if (!InterlockedCompareExchange(
            &link->SpeakerRegistered,0,0))
        return STATUS_NOT_FOUND;

    generation=p360_csaudio_next_generation(link);
    p360_csaudio_reset_ack(link);

    p360_csaudio_notify(
        link,
        P360_CSAUDIO_ENDPOINT_SPEAKER,
        P360_CSAUDIO_ENDPOINT_STOP,
        generation);

    status=p360_csaudio_require_ack(
        link,
        generation,
        P360_CSAUDIO_ENDPOINT_STOP_ACK,
        FALSE);
    if (!NT_SUCCESS(status))
        return status;

    InterlockedExchange(&link->SpeakerStarted,0);
    return STATUS_SUCCESS;
}

VOID
p360_csaudio_close(
    P360_CSAUDIO_LINK *link
    )
{
    if (!link)
        return;

    if (link->Open && link->Callback &&
        InterlockedCompareExchange(
            &link->SpeakerRegistered,0,0)) {
        p360_csaudio_notify(
            link,
            P360_CSAUDIO_ENDPOINT_SPEAKER,
            P360_CSAUDIO_ENDPOINT_STOP,
            p360_csaudio_next_generation(link));
    }

    InterlockedExchange(&link->SpeakerStarted,0);

    if (link->Registration) {
        ExUnregisterCallback(link->Registration);
        link->Registration=NULL;
    }

    if (link->Callback) {
        ObfDereferenceObject(link->Callback);
        link->Callback=NULL;
    }

    link->Open=FALSE;
}
