#include <ntifs.h>
#include <wdf.h>
#include <wdfminiport.h>
#include <portcls.h>

#include "../driver/p360_driver.h"
#include "../include/p360_portcls_bridge.h"

extern "C"
NTSTATUS
P360PortClsStartDevice(
    _In_ PDEVICE_OBJECT DeviceObject,
    _In_ PIRP Irp,
    _In_ PRESOURCELIST ResourceList
    );

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
     * object budget. This shell stays activation-gated until WaveRT/topology
     * and power ownership are wired and audited.
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

    UNREFERENCED_PARAMETER(Irp);
    UNREFERENCED_PARAMETER(ResourceList);

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

    /*
     * The shell is intentionally not activatable until a PortCls-owned stop /
     * remove + power callback path can call host_d0_exit/host_release before
     * deleting this framework miniport. Keeping the handle in context makes
     * that lifetime explicit rather than relying on WDM->WDF lookup.
     */
    return STATUS_SUCCESS;

fail:
    if (ctx->Prepared)
        (void)p360_host_release(ctx);

    p360_portcls_delete_wdf_miniport(&frameworkDevice);
    return status;
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

    return PcInitializeAdapterDriver(
        DriverObject,
        RegistryPath,
        P360PortClsAddDevice);
}
