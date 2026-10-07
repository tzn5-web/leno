#pragma once

#include <ntddk.h>
#include <wdf.h>
#include "p360_gpio.h"

typedef enum _P360_MAX_ENDPOINT_TYPE {
    P360_MAX_ENDPOINT_DSP = 0,
    P360_MAX_ENDPOINT_SPEAKER,
    P360_MAX_ENDPOINT_HEADPHONE,
    P360_MAX_ENDPOINT_MIC_ARRAY,
    P360_MAX_ENDPOINT_MIC_JACK
} P360_MAX_ENDPOINT_TYPE;

typedef enum _P360_MAX_ENDPOINT_REQUEST {
    P360_MAX_REQUEST_REGISTER = 0,
    P360_MAX_REQUEST_START,
    P360_MAX_REQUEST_STOP,
    P360_MAX_REQUEST_OVERRIDE_FORMAT,
    P360_MAX_REQUEST_START_ACK,
    P360_MAX_REQUEST_STOP_ACK
} P360_MAX_ENDPOINT_REQUEST;

typedef struct _P360_MAX_FORMAT_OVERRIDE {
    UINT16 channels;
    UINT16 frequency;
    UINT16 bitsPerSample;
    UINT16 validBitsPerSample;
    LONG force32BitOutputContainer;
} P360_MAX_FORMAT_OVERRIDE;

typedef struct _P360_MAX_TRANSITION {
    UINT32 generation;
    LONG status;
    UINT32 poweredOn;
} P360_MAX_TRANSITION;

typedef struct _P360_MAX_CSAUDIO_ARG {
    UINT32 argSz;
    P360_MAX_ENDPOINT_TYPE endpointType;
    P360_MAX_ENDPOINT_REQUEST endpointRequest;
    union {
        P360_MAX_FORMAT_OVERRIDE formatOverride;
        P360_MAX_TRANSITION transition;
    } Payload;
} P360_MAX_CSAUDIO_ARG;

C_ASSERT(sizeof(P360_MAX_FORMAT_OVERRIDE)==12);
C_ASSERT(sizeof(P360_MAX_TRANSITION)==12);
C_ASSERT(sizeof(P360_MAX_CSAUDIO_ARG)==24);

typedef struct _P360_MAX_CONTEXT {
    WDFDEVICE Device;
    P360_MAX_GPIO_CONTEXT Sdmode;
    PCALLBACK_OBJECT Callback;
    PVOID Registration;
    ULONG SenderCookie;
    WDFWAITLOCK TransitionLock;
    volatile LONG DesiredGeneration;
    volatile LONG DesiredOn;
    volatile LONG PoweredOn;
} P360_MAX_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(P360_MAX_CONTEXT,P360MaxGetContext)

DRIVER_INITIALIZE DriverEntry;
EVT_WDF_DRIVER_DEVICE_ADD P360MaxEvtDeviceAdd;
