#pragma once

#include <ntddk.h>

typedef enum P360_CSAUDIO_ENDPOINT_TYPE {
    P360_CSAUDIO_ENDPOINT_DSP = 0,
    P360_CSAUDIO_ENDPOINT_SPEAKER,
    P360_CSAUDIO_ENDPOINT_HEADPHONE,
    P360_CSAUDIO_ENDPOINT_MIC_ARRAY,
    P360_CSAUDIO_ENDPOINT_MIC_JACK
} P360_CSAUDIO_ENDPOINT_TYPE;

typedef enum P360_CSAUDIO_ENDPOINT_REQUEST {
    P360_CSAUDIO_ENDPOINT_REGISTER = 0,
    P360_CSAUDIO_ENDPOINT_START,
    P360_CSAUDIO_ENDPOINT_STOP,
    P360_CSAUDIO_ENDPOINT_OVERRIDE_FORMAT
} P360_CSAUDIO_ENDPOINT_REQUEST;

typedef struct P360_CSAUDIO_FORMAT_OVERRIDE {
    UINT16 channels;
    UINT16 frequency;
    UINT16 bitsPerSample;
    UINT16 validBitsPerSample;
    LONG force32BitOutputContainer; /* CoolStar BOOL ABI: 32-bit signed */
} P360_CSAUDIO_FORMAT_OVERRIDE;

typedef struct P360_CSAUDIO_ARG {
    UINT32 argSz;
    P360_CSAUDIO_ENDPOINT_TYPE endpointType;
    P360_CSAUDIO_ENDPOINT_REQUEST endpointRequest;
    union {
        P360_CSAUDIO_FORMAT_OVERRIDE formatOverride;
    };
} P360_CSAUDIO_ARG;

C_ASSERT(sizeof(P360_CSAUDIO_FORMAT_OVERRIDE) == 12);
C_ASSERT(sizeof(P360_CSAUDIO_ARG) == 24);

typedef struct P360_CSAUDIO_LINK {
    PCALLBACK_OBJECT Callback;
    PVOID Registration;
    ULONG SenderCookie;
    volatile LONG SpeakerRegistered;
    volatile LONG SpeakerFormatSeen;
    volatile LONG SpeakerStarted;
    UINT16 SpeakerChannels;
    UINT16 SpeakerFrequency;
    UINT16 SpeakerBitsPerSample;
    UINT16 SpeakerValidBitsPerSample;
    BOOLEAN SpeakerForce32;
    BOOLEAN Open;
} P360_CSAUDIO_LINK;

NTSTATUS
p360_csaudio_open(
    _Out_ P360_CSAUDIO_LINK *Link
    );

NTSTATUS
p360_csaudio_speaker_start(
    _Inout_ P360_CSAUDIO_LINK *Link
    );

NTSTATUS
p360_csaudio_speaker_stop(
    _Inout_ P360_CSAUDIO_LINK *Link
    );

VOID
p360_csaudio_close(
    _Inout_ P360_CSAUDIO_LINK *Link
    );
