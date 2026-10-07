#include <ntifs.h>
#include <wdf.h>
#include <wdfminiport.h>
#include <portcls.h>

#include "../driver/p360_driver.h"
#include "../include/p360_portcls_bridge.h"
#include "../include/p360_speaker_endpoint.h"

typedef struct _P360_PORTCLS_INSTANCE {
    KSPIN_LOCK Lock;
    PDEVICE_OBJECT Fdo;
    WDFDEVICE FrameworkDevice;
    P360_DEVICE_CONTEXT *Context;
} P360_PORTCLS_INSTANCE;

static P360_PORTCLS_INSTANCE gP360PortClsInstance;
static PDRIVER_UNLOAD gP360PortClsUnloadRoutine=NULL;

static BOOLEAN
p360_speaker_endpoint_policy_enabled(VOID)
{
    return P360_SPEAKER_ENDPOINT_ENABLED ? TRUE : FALSE;
}

extern "C"
NTSTATUS
P360PortClsStartDevice(
    _In_ PDEVICE_OBJECT DeviceObject,
    _In_ PIRP Irp,
    _In_ PRESOURCELIST ResourceList
    );

extern "C"
NTSTATUS
P360PortClsPnpHandler(
    _In_ PDEVICE_OBJECT DeviceObject,
    _Inout_ PIRP Irp
    );

extern "C"
VOID
P360PortClsUnload(
    _In_ PDRIVER_OBJECT DriverObject
    );

static BOOLEAN
p360_portcls_publish_instance(
    _In_ PDEVICE_OBJECT Fdo,
    _In_ WDFDEVICE FrameworkDevice,
    _In_ P360_DEVICE_CONTEXT *Context
    )
{
    KIRQL oldIrql;
    BOOLEAN published=FALSE;

    KeAcquireSpinLock(&gP360PortClsInstance.Lock,&oldIrql);

    if (!gP360PortClsInstance.Fdo &&
        !gP360PortClsInstance.FrameworkDevice &&
        !gP360PortClsInstance.Context) {
        gP360PortClsInstance.Fdo=Fdo;
        gP360PortClsInstance.FrameworkDevice=FrameworkDevice;
        gP360PortClsInstance.Context=Context;
        published=TRUE;
    }

    KeReleaseSpinLock(&gP360PortClsInstance.Lock,oldIrql);
    return published;
}

static BOOLEAN
p360_portcls_take_instance(
    _In_ PDEVICE_OBJECT Fdo,
    _Out_ WDFDEVICE *FrameworkDevice,
    _Out_ P360_DEVICE_CONTEXT **Context
    )
{
    KIRQL oldIrql;
    BOOLEAN found=FALSE;

    if (!FrameworkDevice || !Context)
        return FALSE;

    *FrameworkDevice=NULL;
    *Context=NULL;

    KeAcquireSpinLock(&gP360PortClsInstance.Lock,&oldIrql);

    if (gP360PortClsInstance.Fdo==Fdo &&
        gP360PortClsInstance.FrameworkDevice &&
        gP360PortClsInstance.Context) {
        *FrameworkDevice=gP360PortClsInstance.FrameworkDevice;
        *Context=gP360PortClsInstance.Context;
        gP360PortClsInstance.Fdo=NULL;
        gP360PortClsInstance.FrameworkDevice=NULL;
        gP360PortClsInstance.Context=NULL;
        found=TRUE;
    }

    KeReleaseSpinLock(&gP360PortClsInstance.Lock,oldIrql);
    return found;
}

static PDEVICE_OBJECT
p360_portcls_current_fdo(VOID)
{
    KIRQL oldIrql;
    PDEVICE_OBJECT fdo;

    KeAcquireSpinLock(&gP360PortClsInstance.Lock,&oldIrql);
    fdo=gP360PortClsInstance.Fdo;
    KeReleaseSpinLock(&gP360PortClsInstance.Lock,oldIrql);

    return fdo;
}

static NTSTATUS
p360_portcls_cleanup_instance(
    _In_ PDEVICE_OBJECT Fdo
    )
{
    WDFDEVICE frameworkDevice=NULL;
    P360_DEVICE_CONTEXT *ctx=NULL;
    NTSTATUS endpointStatus=STATUS_SUCCESS;
    NTSTATUS d0Status=STATUS_SUCCESS;
    NTSTATUS releaseStatus=STATUS_SUCCESS;

    if (!Fdo || KeGetCurrentIrql()!=PASSIVE_LEVEL)
        return STATUS_INVALID_PARAMETER;

    if (!p360_portcls_take_instance(
            Fdo,
            &frameworkDevice,
            &ctx)) {
        return STATUS_SUCCESS;
    }

    if (ctx->SpeakerEndpointInstalled) {
        endpointStatus=p360_speaker_endpoint_uninstall(
            Fdo,
            &ctx->SpeakerTopologyPort,
            &ctx->SpeakerWavePort);
        ctx->SpeakerEndpointInstalled=FALSE;
    }

    d0Status=p360_host_d0_exit(ctx);
    releaseStatus=p360_host_release(ctx);

    if (!NT_SUCCESS(releaseStatus)) {
        /*
         * Never delete the framework miniport underneath a live/quarantined
         * DSP. Preserve the instance so unload can make one final teardown
         * attempt instead of creating a use-after-free path.
         */
        (void)p360_portcls_publish_instance(
            Fdo,
            frameworkDevice,
            ctx);
        return releaseStatus;
    }

    p360_portcls_delete_wdf_miniport(&frameworkDevice);

    if (!NT_SUCCESS(endpointStatus))
        return endpointStatus;

    return NT_SUCCESS(d0Status) ?
        STATUS_SUCCESS :
        d0Status;
}

extern "C"
NTSTATUS
P360PortClsAddDevice(
    _In_ PDRIVER_OBJECT DriverObject,
    _In_ PDEVICE_OBJECT PhysicalDeviceObject
    )
{
    if (!DriverObject || !PhysicalDeviceObject)
        return STATUS_INVALID_PARAMETER;

    /*
     * Endpoint filters are not installed yet, so reserve a deliberately small
     * object budget. WaveRT/topology will consume this budget only after their
     * own contracts are compiled and audited.
     */
    return PcAddAdapterDevice(
        DriverObject,
        PhysicalDeviceObject,
        P360PortClsStartDevice,
        4,
        0);
}

extern "C"
NTSTATUS
P360PortClsStartDevice(
    _In_ PDEVICE_OBJECT DeviceObject,
    _In_ PIRP Irp,
    _In_ PRESOURCELIST ResourceList
    )
{
    WDF_OBJECT_ATTRIBUTES attributes;
    WDFDEVICE frameworkDevice=NULL;
    P360_DEVICE_CONTEXT *ctx;
    NTSTATUS status;
    BOOLEAN d0Entered=FALSE;

    if (!DeviceObject || KeGetCurrentIrql()!=PASSIVE_LEVEL)
        return STATUS_INVALID_PARAMETER;

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(
        &attributes,
        P360_DEVICE_CONTEXT);

    status=p360_portcls_create_wdf_miniport(
        DeviceObject,
        &attributes,
        &frameworkDevice);
    if (!NT_SUCCESS(status))
        return status;

    ctx=P360GetContext(frameworkDevice);
    if (!ctx) {
        p360_portcls_delete_wdf_miniport(&frameworkDevice);
        return STATUS_INSUFFICIENT_RESOURCES;
    }

    ctx->FrameworkDevice=frameworkDevice;
    ctx->PortClsFdo=DeviceObject;

    status=p360_host_prepare(
        ctx,
        frameworkDevice);
    if (!NT_SUCCESS(status))
        goto fail;

    status=p360_host_d0_entry(ctx);
    if (!NT_SUCCESS(status))
        goto fail;

    d0Entered=TRUE;

    if (p360_speaker_endpoint_policy_enabled()) {
        status=p360_speaker_endpoint_install(
            DeviceObject,
            Irp,
            ResourceList,
            ctx,
            &ctx->SpeakerTopologyPort,
            &ctx->SpeakerWavePort);
        if (!NT_SUCCESS(status))
            goto fail;

        ctx->SpeakerEndpointInstalled=TRUE;
    }

    if (!p360_portcls_publish_instance(
            DeviceObject,
            frameworkDevice,
            ctx)) {
        status=STATUS_DEVICE_BUSY;
        goto fail;
    }

    return STATUS_SUCCESS;

fail:
    if (ctx && ctx->SpeakerEndpointInstalled) {
        (void)p360_speaker_endpoint_uninstall(
            DeviceObject,
            &ctx->SpeakerTopologyPort,
            &ctx->SpeakerWavePort);
        ctx->SpeakerEndpointInstalled=FALSE;
    }

    if (d0Entered)
        (void)p360_host_d0_exit(ctx);

    if (ctx->Prepared)
        (void)p360_host_release(ctx);

    p360_portcls_delete_wdf_miniport(&frameworkDevice);
    return status;
}

extern "C"
NTSTATUS
P360PortClsPnpHandler(
    _In_ PDEVICE_OBJECT DeviceObject,
    _Inout_ PIRP Irp
    )
{
    PIO_STACK_LOCATION stack;

    if (!DeviceObject || !Irp)
        return STATUS_INVALID_PARAMETER;

    stack=IoGetCurrentIrpStackLocation(Irp);

    switch (stack->MinorFunction) {
    case IRP_MN_STOP_DEVICE:
    case IRP_MN_SURPRISE_REMOVAL:
    case IRP_MN_REMOVE_DEVICE:
        /*
         * PortCls owns the PnP IRP. We release our SOF/WDF side first, then
         * always pass the IRP to PortCls exactly as the reference adapter
         * model does.
         */
        (void)p360_portcls_cleanup_instance(DeviceObject);
        break;

    default:
        break;
    }

    return PcDispatchIrp(DeviceObject,Irp);
}

extern "C"
VOID
P360PortClsUnload(
    _In_ PDRIVER_OBJECT DriverObject
    )
{
    PDEVICE_OBJECT fdo;

    if (!DriverObject)
        return;

    fdo=p360_portcls_current_fdo();
    if (fdo)
        (void)p360_portcls_cleanup_instance(fdo);

    if (gP360PortClsUnloadRoutine)
        gP360PortClsUnloadRoutine(DriverObject);

    if (WdfGetDriver()!=NULL)
        WdfDriverMiniportUnload(WdfGetDriver());
}

extern "C"
NTSTATUS
p360_portcls_driver_initialize(
    _In_ PDRIVER_OBJECT DriverObject,
    _In_ PUNICODE_STRING RegistryPath
    )
{
    WDF_DRIVER_CONFIG config;
    NTSTATUS status;

    if (!DriverObject || !RegistryPath ||
        KeGetCurrentIrql()!=PASSIVE_LEVEL)
        return STATUS_INVALID_PARAMETER;

    RtlZeroMemory(
        &gP360PortClsInstance,
        sizeof(gP360PortClsInstance));
    KeInitializeSpinLock(&gP360PortClsInstance.Lock);

    ExInitializeDriverRuntime(DrvRtPoolNxOptIn);

    WDF_DRIVER_CONFIG_INIT(
        &config,
        WDF_NO_EVENT_CALLBACK);

    /*
     * PortCls, not KMDF, owns dispatch/PnP/power for the audio FDO. KMDF is
     * present only to support the WDF miniport view created in StartDevice.
     */
    config.DriverInitFlags|=WdfDriverInitNoDispatchOverride;

    status=WdfDriverCreate(
        DriverObject,
        RegistryPath,
        WDF_NO_OBJECT_ATTRIBUTES,
        &config,
        WDF_NO_HANDLE);
    if (!NT_SUCCESS(status))
        return status;

    status=PcInitializeAdapterDriver(
        DriverObject,
        RegistryPath,
        P360PortClsAddDevice);
    if (!NT_SUCCESS(status)) {
        WdfDriverMiniportUnload(WdfGetDriver());
        return status;
    }

    DriverObject->MajorFunction[IRP_MJ_PNP]=
        P360PortClsPnpHandler;

    gP360PortClsUnloadRoutine=DriverObject->DriverUnload;
    DriverObject->DriverUnload=P360PortClsUnload;

    return STATUS_SUCCESS;
}
