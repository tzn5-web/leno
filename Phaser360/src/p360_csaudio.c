#include "../include/p360_csaudio.h"

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

    if (arg->argSz < FIELD_OFFSET(P360_CSAUDIO_ARG,formatOverride) ||
        arg->argSz > sizeof(P360_CSAUDIO_ARG))
        return;

    RtlZeroMemory(&local,sizeof(local));
    RtlCopyMemory(&local,arg,arg->argSz);

    if (local.endpointType!=P360_CSAUDIO_ENDPOINT_SPEAKER)
        return;

    if (local.endpointRequest==P360_CSAUDIO_ENDPOINT_REGISTER) {
        InterlockedExchange(&link->SpeakerRegistered,1);
        return;
    }

    if (local.endpointRequest==P360_CSAUDIO_ENDPOINT_OVERRIDE_FORMAT &&
        local.argSz>=sizeof(P360_CSAUDIO_ARG)) {
        link->SpeakerChannels=local.formatOverride.channels;
        link->SpeakerFrequency=local.formatOverride.frequency;
        link->SpeakerBitsPerSample=local.formatOverride.bitsPerSample;
        link->SpeakerValidBitsPerSample=local.formatOverride.validBitsPerSample;
        link->SpeakerForce32=
            local.formatOverride.force32BitOutputContainer ? TRUE : FALSE;
        KeMemoryBarrier();
        InterlockedExchange(&link->SpeakerFormatSeen,1);
    }
}

static VOID
p360_csaudio_notify(
    _Inout_ P360_CSAUDIO_LINK *link,
    _In_ P360_CSAUDIO_ENDPOINT_TYPE endpoint,
    _In_ P360_CSAUDIO_ENDPOINT_REQUEST request
    )
{
    P360_CSAUDIO_ARG arg;

    RtlZeroMemory(&arg,sizeof(arg));
    arg.argSz=sizeof(arg);
    arg.endpointType=endpoint;
    arg.endpointRequest=request;

    ExNotifyCallback(
        link->Callback,
        &arg,
        &link->SenderCookie);
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
        P360_CSAUDIO_ENDPOINT_REGISTER);

    /*
     * If the amplifier answered, force its callback state to STOP while the
     * DSP topology is still absent. This preserves GPIO ownership in the
     * dedicated MAX98357A driver and keeps the speaker path fail-closed.
     */
    if (InterlockedCompareExchange(
            &link->SpeakerRegistered,0,0)) {
        p360_csaudio_notify(
            link,
            P360_CSAUDIO_ENDPOINT_SPEAKER,
            P360_CSAUDIO_ENDPOINT_STOP);
    }

    return STATUS_SUCCESS;
}

NTSTATUS
p360_csaudio_speaker_start(
    P360_CSAUDIO_LINK *link
    )
{
    if (!link || !link->Open || !link->Callback ||
        KeGetCurrentIrql()!=PASSIVE_LEVEL)
        return STATUS_INVALID_DEVICE_STATE;

    if (!InterlockedCompareExchange(
            &link->SpeakerRegistered,0,0))
        return STATUS_NOT_FOUND;

    if (InterlockedCompareExchange(
            &link->SpeakerStarted,1,0)!=0)
        return STATUS_DEVICE_BUSY;

    p360_csaudio_notify(
        link,
        P360_CSAUDIO_ENDPOINT_SPEAKER,
        P360_CSAUDIO_ENDPOINT_START);

    return STATUS_SUCCESS;
}

NTSTATUS
p360_csaudio_speaker_stop(
    P360_CSAUDIO_LINK *link
    )
{
    if (!link || !link->Open || !link->Callback ||
        KeGetCurrentIrql()!=PASSIVE_LEVEL)
        return STATUS_INVALID_DEVICE_STATE;

    if (!InterlockedCompareExchange(
            &link->SpeakerRegistered,0,0)) {
        InterlockedExchange(&link->SpeakerStarted,0);
        return STATUS_NOT_FOUND;
    }

    p360_csaudio_notify(
        link,
        P360_CSAUDIO_ENDPOINT_SPEAKER,
        P360_CSAUDIO_ENDPOINT_STOP);
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
            P360_CSAUDIO_ENDPOINT_STOP);
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
