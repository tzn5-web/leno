/*
 * PHASER360 fail-closed MAX98357A driver.
 * Derived from CoolStar/max98357a (Apache-2.0), pinned in LICENSE.txt.
 */
#include "p360_max_safe.h"

static VOID
p360_max_notify(
    _Inout_ P360_MAX_CONTEXT *Context,
    _In_ P360_MAX_ENDPOINT_REQUEST Request,
    _In_ UINT32 Generation,
    _In_ NTSTATUS Status,
    _In_ BOOLEAN PoweredOn)
{
    P360_MAX_CSAUDIO_ARG arg;

    if (!Context || !Context->Callback)
        return;

    RtlZeroMemory(&arg,sizeof(arg));
    arg.argSz=sizeof(arg);
    arg.endpointType=P360_MAX_ENDPOINT_SPEAKER;
    arg.endpointRequest=Request;
    arg.Payload.transition.generation=Generation;
    arg.Payload.transition.status=Status;
    arg.Payload.transition.poweredOn=PoweredOn ? 1u : 0u;

    ExNotifyCallback(
        Context->Callback,
        &arg,
        &Context->SenderCookie);
}

static NTSTATUS
p360_max_force_low(
    _Inout_ P360_MAX_CONTEXT *Context)
{
    NTSTATUS status;

    if (!Context)
        return STATUS_INVALID_PARAMETER;

    if (!Context->TransitionLock)
        return STATUS_INVALID_DEVICE_STATE;

    WdfWaitLockAcquire(Context->TransitionLock,NULL);

    InterlockedExchange(&Context->DesiredOn,0);
    InterlockedIncrement(&Context->DesiredGeneration);

    status=p360_max_gpio_write(&Context->Sdmode,0);
    if (NT_SUCCESS(status))
        InterlockedExchange(&Context->PoweredOn,0);

    WdfWaitLockRelease(Context->TransitionLock);
    return status;
}

static VOID
p360_max_register_endpoint(
    _Inout_ P360_MAX_CONTEXT *Context)
{
    P360_MAX_CSAUDIO_ARG arg;

    RtlZeroMemory(&arg,sizeof(arg));
    arg.argSz=sizeof(arg);
    arg.endpointType=P360_MAX_ENDPOINT_SPEAKER;
    arg.endpointRequest=P360_MAX_REQUEST_REGISTER;
    ExNotifyCallback(Context->Callback,&arg,&Context->SenderCookie);

    RtlZeroMemory(&arg,sizeof(arg));
    arg.argSz=sizeof(arg);
    arg.endpointType=P360_MAX_ENDPOINT_SPEAKER;
    arg.endpointRequest=P360_MAX_REQUEST_OVERRIDE_FORMAT;
    arg.Payload.formatOverride.bitsPerSample=16;
    arg.Payload.formatOverride.validBitsPerSample=16;
    arg.Payload.formatOverride.force32BitOutputContainer=TRUE;
    ExNotifyCallback(Context->Callback,&arg,&Context->SenderCookie);
}

static VOID
p360_max_callback(
    _In_opt_ PVOID CallbackContext,
    _In_opt_ PVOID Argument1,
    _In_opt_ PVOID Argument2)
{
    WDFDEVICE device=(WDFDEVICE)CallbackContext;
    P360_MAX_CONTEXT *ctx;
    const P360_MAX_CSAUDIO_ARG *arg=
        (const P360_MAX_CSAUDIO_ARG *)Argument1;
    P360_MAX_CSAUDIO_ARG local;
    UINT32 generation;
    NTSTATUS status;
    LARGE_INTEGER delay;

    if (!device || !arg)
        return;

    ctx=P360MaxGetContext(device);
    if (!ctx || Argument2==&ctx->SenderCookie)
        return;

    if (arg->argSz<
            (UINT32)FIELD_OFFSET(P360_MAX_CSAUDIO_ARG,Payload) ||
        arg->argSz>sizeof(P360_MAX_CSAUDIO_ARG))
        return;

    RtlZeroMemory(&local,sizeof(local));
    RtlCopyMemory(&local,arg,arg->argSz);

    if (local.endpointType==P360_MAX_ENDPOINT_DSP &&
        local.endpointRequest==P360_MAX_REQUEST_REGISTER) {
        p360_max_register_endpoint(ctx);
        return;
    }

    if (local.endpointType!=P360_MAX_ENDPOINT_SPEAKER ||
        (local.endpointRequest!=P360_MAX_REQUEST_START &&
         local.endpointRequest!=P360_MAX_REQUEST_STOP))
        return;

    generation=local.Payload.transition.generation;

    if (local.argSz<sizeof(P360_MAX_CSAUDIO_ARG) ||
        !generation ||
        KeGetCurrentIrql()!=PASSIVE_LEVEL) {
        p360_max_notify(
            ctx,
            local.endpointRequest==P360_MAX_REQUEST_START ?
                P360_MAX_REQUEST_START_ACK :
                P360_MAX_REQUEST_STOP_ACK,
            generation,
            STATUS_INVALID_DEVICE_STATE,
            InterlockedCompareExchange(&ctx->PoweredOn,0,0)!=0);
        return;
    }

    if (local.endpointRequest==P360_MAX_REQUEST_STOP) {
        WdfWaitLockAcquire(ctx->TransitionLock,NULL);

        InterlockedExchange(
            &ctx->DesiredGeneration,
            (LONG)generation);
        InterlockedExchange(&ctx->DesiredOn,0);
        status=p360_max_gpio_write(&ctx->Sdmode,0);
        if (NT_SUCCESS(status))
            InterlockedExchange(&ctx->PoweredOn,0);

        WdfWaitLockRelease(ctx->TransitionLock);

        p360_max_notify(
            ctx,
            P360_MAX_REQUEST_STOP_ACK,
            generation,
            status,
            InterlockedCompareExchange(&ctx->PoweredOn,0,0)!=0);
        return;
    }

    /*
     * Match Linux MAX98357A semantics: remain muted first, wait for the
     * anti-pop interval, and only then assert SDMODE. A concurrent STOP
     * changes generation/DesiredOn and cancels this START before GPIO high.
     */
    WdfWaitLockAcquire(ctx->TransitionLock,NULL);
    InterlockedExchange(
        &ctx->DesiredGeneration,
        (LONG)generation);
    InterlockedExchange(&ctx->DesiredOn,1);

    status=p360_max_gpio_write(&ctx->Sdmode,0);
    if (!NT_SUCCESS(status)) {
        InterlockedExchange(&ctx->DesiredOn,0);
        WdfWaitLockRelease(ctx->TransitionLock);
        p360_max_notify(
            ctx,
            P360_MAX_REQUEST_START_ACK,
            generation,
            status,
            InterlockedCompareExchange(&ctx->PoweredOn,0,0)!=0);
        return;
    }
    InterlockedExchange(&ctx->PoweredOn,0);
    WdfWaitLockRelease(ctx->TransitionLock);

    delay.QuadPart=-10*1000*5; /* 5 ms */
    (void)KeDelayExecutionThread(
        KernelMode,
        FALSE,
        &delay);

    WdfWaitLockAcquire(ctx->TransitionLock,NULL);

    if ((UINT32)InterlockedCompareExchange(
            &ctx->DesiredGeneration,0,0)!=generation ||
        !InterlockedCompareExchange(&ctx->DesiredOn,0,0)) {
        WdfWaitLockRelease(ctx->TransitionLock);
        p360_max_notify(
            ctx,
            P360_MAX_REQUEST_START_ACK,
            generation,
            STATUS_CANCELLED,
            FALSE);
        return;
    }

    status=p360_max_gpio_write(&ctx->Sdmode,1);
    if (NT_SUCCESS(status)) {
        InterlockedExchange(&ctx->PoweredOn,1);
    } else {
        InterlockedExchange(&ctx->DesiredOn,0);
        InterlockedExchange(&ctx->PoweredOn,0);
    }

    WdfWaitLockRelease(ctx->TransitionLock);

    p360_max_notify(
        ctx,
        P360_MAX_REQUEST_START_ACK,
        generation,
        status,
        InterlockedCompareExchange(&ctx->PoweredOn,0,0)!=0);
}

static NTSTATUS
P360MaxPrepareHardware(
    _In_ WDFDEVICE Device,
    _In_ WDFCMRESLIST ResourcesRaw,
    _In_ WDFCMRESLIST ResourcesTranslated)
{
    P360_MAX_CONTEXT *ctx=P360MaxGetContext(Device);
    BOOLEAN found=FALSE;
    ULONG i;
    ULONG count;

    UNREFERENCED_PARAMETER(ResourcesRaw);

    if (!ctx)
        return STATUS_INVALID_DEVICE_STATE;

    count=WdfCmResourceListGetCount(ResourcesTranslated);
    for (i=0;i<count;++i) {
        PCM_PARTIAL_RESOURCE_DESCRIPTOR descriptor=
            WdfCmResourceListGetDescriptor(
                ResourcesTranslated,
                i);
        if (!descriptor)
            continue;

        if (descriptor->Type==CmResourceTypeConnection &&
            descriptor->u.Connection.Class==
                CM_RESOURCE_CONNECTION_CLASS_GPIO &&
            descriptor->u.Connection.Type==
                CM_RESOURCE_CONNECTION_TYPE_GPIO_IO) {
            if (found)
                return STATUS_DEVICE_CONFIGURATION_ERROR;

            ctx->Sdmode.ResourceHubId.LowPart=
                descriptor->u.Connection.IdLowPart;
            ctx->Sdmode.ResourceHubId.HighPart=
                descriptor->u.Connection.IdHighPart;
            found=TRUE;
        }
    }

    if (!found)
        return STATUS_NOT_FOUND;

    return p360_max_gpio_init(Device,&ctx->Sdmode);
}

static NTSTATUS
P360MaxReleaseHardware(
    _In_ WDFDEVICE Device,
    _In_ WDFCMRESLIST ResourcesTranslated)
{
    P360_MAX_CONTEXT *ctx=P360MaxGetContext(Device);
    NTSTATUS muteStatus=STATUS_SUCCESS;

    UNREFERENCED_PARAMETER(ResourcesTranslated);

    if (!ctx)
        return STATUS_INVALID_DEVICE_STATE;

    /*
     * Surprise removal can reach ReleaseHardware without a successful D0Exit.
     * Make one final synchronous LOW request while both GPIO and transition
     * lock are still valid, then tear down callbacks and resources.
     */
    if (ctx->TransitionLock && ctx->Sdmode.Target)
        muteStatus=p360_max_force_low(ctx);

    if (ctx->Registration) {
        ExUnregisterCallback(ctx->Registration);
        ctx->Registration=NULL;
    }

    if (ctx->Callback) {
        ObfDereferenceObject(ctx->Callback);
        ctx->Callback=NULL;
    }

    p360_max_gpio_deinit(Device,&ctx->Sdmode);

    if (ctx->TransitionLock) {
        WdfObjectDelete(ctx->TransitionLock);
        ctx->TransitionLock=NULL;
    }

    return muteStatus;
}

static NTSTATUS
P360MaxSelfManagedIoInit(
    _In_ WDFDEVICE Device)
{
    P360_MAX_CONTEXT *ctx=P360MaxGetContext(Device);
    UNICODE_STRING name;
    OBJECT_ATTRIBUTES attributes;
    NTSTATUS status;

    if (!ctx)
        return STATUS_INVALID_DEVICE_STATE;

    RtlInitUnicodeString(
        &name,
        L"\\CallBack\\CsAudioCallbackAPI");

    InitializeObjectAttributes(
        &attributes,
        &name,
        OBJ_KERNEL_HANDLE | OBJ_OPENIF |
            OBJ_CASE_INSENSITIVE | OBJ_PERMANENT,
        NULL,
        NULL);

    status=ExCreateCallback(
        &ctx->Callback,
        &attributes,
        TRUE,
        TRUE);
    if (!NT_SUCCESS(status))
        return status;

    ctx->Registration=ExRegisterCallback(
        ctx->Callback,
        p360_max_callback,
        Device);
    if (!ctx->Registration) {
        ObfDereferenceObject(ctx->Callback);
        ctx->Callback=NULL;
        return STATUS_NO_CALLBACK_ACTIVE;
    }

    p360_max_register_endpoint(ctx);
    return STATUS_SUCCESS;
}

static NTSTATUS
P360MaxD0Entry(
    _In_ WDFDEVICE Device,
    _In_ WDF_POWER_DEVICE_STATE PreviousState)
{
    P360_MAX_CONTEXT *ctx=P360MaxGetContext(Device);

    UNREFERENCED_PARAMETER(PreviousState);

    if (!ctx)
        return STATUS_INVALID_DEVICE_STATE;

    /*
     * Critical difference from upstream CoolStar: D0 is always muted. The
     * speaker can only become active after a generation-tagged START request.
     */
    return p360_max_force_low(ctx);
}

static NTSTATUS
P360MaxD0Exit(
    _In_ WDFDEVICE Device,
    _In_ WDF_POWER_DEVICE_STATE TargetState)
{
    P360_MAX_CONTEXT *ctx=P360MaxGetContext(Device);

    UNREFERENCED_PARAMETER(TargetState);

    if (!ctx)
        return STATUS_INVALID_DEVICE_STATE;

    return p360_max_force_low(ctx);
}

NTSTATUS
P360MaxEvtDeviceAdd(
    WDFDRIVER Driver,
    PWDFDEVICE_INIT DeviceInit)
{
    WDF_PNPPOWER_EVENT_CALLBACKS pnp;
    WDF_OBJECT_ATTRIBUTES attributes;
    WDFDEVICE device;
    P360_MAX_CONTEXT *ctx;
    NTSTATUS status;

    UNREFERENCED_PARAMETER(Driver);

    WDF_PNPPOWER_EVENT_CALLBACKS_INIT(&pnp);
    pnp.EvtDevicePrepareHardware=P360MaxPrepareHardware;
    pnp.EvtDeviceReleaseHardware=P360MaxReleaseHardware;
    pnp.EvtDeviceSelfManagedIoInit=P360MaxSelfManagedIoInit;
    pnp.EvtDeviceD0Entry=P360MaxD0Entry;
    pnp.EvtDeviceD0Exit=P360MaxD0Exit;
    WdfDeviceInitSetPnpPowerEventCallbacks(DeviceInit,&pnp);

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(
        &attributes,
        P360_MAX_CONTEXT);

    status=WdfDeviceCreate(
        &DeviceInit,
        &attributes,
        &device);
    if (!NT_SUCCESS(status))
        return status;

    ctx=P360MaxGetContext(device);
    RtlZeroMemory(ctx,sizeof(*ctx));
    ctx->Device=device;
    ctx->SenderCookie=0x3630584du; /* MX06 */

    {
        WDF_OBJECT_ATTRIBUTES lockAttributes;
        WDF_OBJECT_ATTRIBUTES_INIT(&lockAttributes);
        lockAttributes.ParentObject=device;

        status=WdfWaitLockCreate(
            &lockAttributes,
            &ctx->TransitionLock);
        if (!NT_SUCCESS(status))
            return status;
    }

    return STATUS_SUCCESS;
}

NTSTATUS
DriverEntry(
    PDRIVER_OBJECT DriverObject,
    PUNICODE_STRING RegistryPath)
{
    WDF_DRIVER_CONFIG config;

    WDF_DRIVER_CONFIG_INIT(
        &config,
        P360MaxEvtDeviceAdd);

    return WdfDriverCreate(
        DriverObject,
        RegistryPath,
        WDF_NO_OBJECT_ATTRIBUTES,
        &config,
        WDF_NO_HANDLE);
}
