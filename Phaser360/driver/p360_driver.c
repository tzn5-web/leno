#include "p360_driver.h"

static NTSTATUS
p360_fail(
    _Inout_ P360_DEVICE_CONTEXT *ctx,
    _In_ P360_FAILURE_REASON reason,
    _In_ NTSTATUS status)
{
    if (ctx)
        p360_state_fail(&ctx->State,reason);
    return status;
}

NTSTATUS
DriverEntry(
    _In_ PDRIVER_OBJECT DriverObject,
    _In_ PUNICODE_STRING RegistryPath)
{
    WDF_DRIVER_CONFIG config;

    WDF_DRIVER_CONFIG_INIT(&config,P360EvtDeviceAdd);

    return WdfDriverCreate(
        DriverObject,
        RegistryPath,
        WDF_NO_OBJECT_ATTRIBUTES,
        &config,
        WDF_NO_HANDLE);
}

NTSTATUS
P360EvtDeviceAdd(
    _In_ WDFDRIVER Driver,
    _Inout_ PWDFDEVICE_INIT DeviceInit)
{
    WDF_PNPPOWER_EVENT_CALLBACKS pnp;
    WDF_OBJECT_ATTRIBUTES attributes;
    WDFDEVICE device;
    P360_DEVICE_CONTEXT *ctx;
    NTSTATUS status;

    UNREFERENCED_PARAMETER(Driver);

    WDF_PNPPOWER_EVENT_CALLBACKS_INIT(&pnp);
    pnp.EvtDevicePrepareHardware=P360EvtPrepareHardware;
    pnp.EvtDeviceReleaseHardware=P360EvtReleaseHardware;
    pnp.EvtDeviceD0Entry=P360EvtD0Entry;
    pnp.EvtDeviceD0Exit=P360EvtD0Exit;
    WdfDeviceInitSetPnpPowerEventCallbacks(DeviceInit,&pnp);

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(
        &attributes,
        P360_DEVICE_CONTEXT);

    status=WdfDeviceCreate(
        &DeviceInit,
        &attributes,
        &device);

    if (!NT_SUCCESS(status))
        return status;

    ctx=P360GetContext(device);
    p360_state_init(&ctx->State);
    InterlockedExchange(&ctx->Removing,0);

    return STATUS_SUCCESS;
}

NTSTATUS
P360EvtPrepareHardware(
    _In_ WDFDEVICE Device,
    _In_ WDFCMRESLIST ResourcesRaw,
    _In_ WDFCMRESLIST ResourcesTranslated)
{
    P360_DEVICE_CONTEXT *ctx=P360GetContext(Device);
    NTSTATUS status;

    UNREFERENCED_PARAMETER(ResourcesRaw);
    UNREFERENCED_PARAMETER(ResourcesTranslated);

    if (!ctx || ctx->Prepared || ctx->BusOpen)
        return STATUS_INVALID_DEVICE_STATE;

    p360_state_init(&ctx->State);
    RtlZeroMemory(&ctx->Nhlt,sizeof(ctx->Nhlt));
    RtlZeroMemory(&ctx->Identity,sizeof(ctx->Identity));
    ctx->BootInitialized=FALSE;
    ctx->RuntimeInitialized=FALSE;
    InterlockedExchange(&ctx->Removing,0);

    status=p360_cs_bus_open(&ctx->Bus,Device);
    if (!NT_SUCCESS(status))
        return p360_fail(ctx,P360_FAIL_RESOURCES,status);
    ctx->BusOpen=TRUE;

    status=p360_cs_bus_read_identity(&ctx->Bus,&ctx->Identity);
    if (!NT_SUCCESS(status))
        goto identity_fail;
    ctx->State.hardware_identity_ok=1;

    if (!p360_nhlt_parse(
            ctx->Bus.nhlt.nhlt,
            (size_t)ctx->Bus.nhlt.nhltSz,
            &ctx->Nhlt)) {
        status=STATUS_DEVICE_CONFIGURATION_ERROR;
        goto nhlt_fail;
    }
    ctx->State.nhlt_ok=1;

    if (!p360_state_advance(
            &ctx->State,
            P360_STATE_RESOURCES_OK)) {
        status=STATUS_INVALID_DEVICE_STATE;
        goto resource_state_fail;
    }

    p360_loader_init(&ctx->Loader);

    status=p360_cs_boot_adapter_init(
        &ctx->Boot,
        &ctx->Bus);
    if (!NT_SUCCESS(status))
        goto boot_init_fail;

    ctx->BootInitialized=TRUE;

    status=p360_cs_runtime_create(
        &ctx->Runtime,
        Device,
        &ctx->Bus,
        &ctx->Boot);
    if (!NT_SUCCESS(status))
        goto runtime_init_fail;

    ctx->RuntimeInitialized=TRUE;
    ctx->Prepared=TRUE;
    return STATUS_SUCCESS;

runtime_init_fail:
    p360_state_fail(&ctx->State,P360_FAIL_RESOURCES);
    if (ctx->BootInitialized) {
        NTSTATUS retireStatus=
            p360_cs_boot_adapter_retire(&ctx->Boot);
        if (!NT_SUCCESS(retireStatus))
            status=retireStatus;
        ctx->BootInitialized=FALSE;
    }
    goto cleanup;

boot_init_fail:
    p360_state_fail(&ctx->State,P360_FAIL_RESOURCES);
    goto cleanup;
resource_state_fail:
    p360_state_fail(&ctx->State,P360_FAIL_RESOURCES);
    goto cleanup;
nhlt_fail:
    p360_state_fail(&ctx->State,P360_FAIL_NHLT);
    goto cleanup;
identity_fail:
    p360_state_fail(&ctx->State,P360_FAIL_IDENTITY);

cleanup:
    if (ctx->BusOpen) {
        p360_cs_bus_close(&ctx->Bus);
        ctx->BusOpen=FALSE;
    }
    return status;
}

NTSTATUS
P360EvtReleaseHardware(
    _In_ WDFDEVICE Device,
    _In_ WDFCMRESLIST ResourcesTranslated)
{
    P360_DEVICE_CONTEXT *ctx=P360GetContext(Device);
    NTSTATUS status=STATUS_SUCCESS;

    UNREFERENCED_PARAMETER(ResourcesTranslated);

    if (!ctx)
        return STATUS_INVALID_DEVICE_STATE;

    InterlockedExchange(&ctx->Removing,1);

    if (ctx->RuntimeInitialized) {
        status=p360_cs_runtime_destroy(&ctx->Runtime);
        if (!NT_SUCCESS(status)) {
            p360_state_fail(&ctx->State,P360_FAIL_IRQ);
            return status;
        }

        ctx->RuntimeInitialized=FALSE;
    }

    if (ctx->BootInitialized) {
        p360_cs_boot_adapter_cancel(&ctx->Boot);

        status=p360_cs_boot_adapter_retire(&ctx->Boot);
        if (!NT_SUCCESS(status)) {
            /*
             * Do not close/dereference the parent bus underneath a live or
             * quarantined DSP. Runtime shutdown must prove quiescence first.
             */
            p360_state_fail(&ctx->State,P360_FAIL_FIRMWARE);
            return status;
        }

        ctx->BootInitialized=FALSE;
    }

    if (ctx->BusOpen) {
        p360_cs_bus_close(&ctx->Bus);
        ctx->BusOpen=FALSE;
    }

    ctx->Prepared=FALSE;
    return STATUS_SUCCESS;
}

NTSTATUS
P360EvtD0Entry(
    _In_ WDFDEVICE Device,
    _In_ WDF_POWER_DEVICE_STATE PreviousState)
{
    P360_DEVICE_CONTEXT *ctx=P360GetContext(Device);

    UNREFERENCED_PARAMETER(PreviousState);

    if (!ctx || !ctx->Prepared || !ctx->BusOpen ||
        ctx->State.state!=P360_STATE_RESOURCES_OK ||
        InterlockedCompareExchange(&ctx->Removing,0,0)!=0) {
        return STATUS_INVALID_DEVICE_STATE;
    }

#if P360_RUNTIME_BOOT_ENABLED
#error P360_RUNTIME_BOOT_ENABLED requires the reviewed firmware provider and runtime handoff path.
#endif

    return STATUS_SUCCESS;
}

NTSTATUS
P360EvtD0Exit(
    _In_ WDFDEVICE Device,
    _In_ WDF_POWER_DEVICE_STATE TargetState)
{
    P360_DEVICE_CONTEXT *ctx=P360GetContext(Device);

    UNREFERENCED_PARAMETER(TargetState);

    if (!ctx)
        return STATUS_INVALID_DEVICE_STATE;

    /*
     * Runtime boot is intentionally disabled in this build, so ordinary
     * D0->Dx power transitions have no active SOF transaction to cancel.
     * Do not latch Boot.Cancelled here: PrepareHardware is not guaranteed to
     * rerun on a simple sleep/resume cycle.
     *
     * Once runtime boot is enabled, this callback will synchronously quiesce
     * WaveRT -> topology -> IPC/IRQ -> DSP and release the held D0 reference,
     * then re-arm a fresh boot epoch for the next D0Entry.
     */
#if P360_RUNTIME_BOOT_ENABLED
#error P360_RUNTIME_BOOT_ENABLED requires reviewed D0Exit runtime shutdown.
#endif

    return STATUS_SUCCESS;
}
