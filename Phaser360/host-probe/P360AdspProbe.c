#include <ntddk.h>
#include <wdf.h>
#include <initguid.h>

/*
 * P360AdspProbe: diagnostics-only KMDF function driver for the CoolStar
 * CSAUDIO\ADSP child on Gemini Lake. No MMIO, firmware, IPC, streams or
 * interrupt registration. It only queries the parent bus interface.
 *
 * Layout below matches the published sklhdaudbus/adsp.h ABI version 1.
 * Unused callbacks are opaque pointer slots; this probe never invokes them.
 */
DEFINE_GUID(GUID_ADSP_BUS_INTERFACE,
    0x752a2cae, 0x3455, 0x4d18, 0xa1, 0x84, 0x8b, 0x34, 0xb2, 0x26, 0x32, 0xce);

#define IOCTL_P360_PROBE_STATUS CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_READ_ACCESS)
#define P360_STATUS_MAGIC 0x50333630UL
#define P360_FLAG_INTERFACE_OK 0x1UL
#define P360_FLAG_RESOURCES_EXPORT_PRESENT 0x2UL
#define P360_FLAG_IRQ_REGISTER_EXPORT_PRESENT 0x4UL
#define P360_FLAG_NO_IRQ_TEST 0x8UL

typedef struct _P360_ADSP_BUS_INTERFACE {
    USHORT Size;
    USHORT Version;
    PVOID Context;
    PINTERFACE_REFERENCE InterfaceReference;
    PINTERFACE_DEREFERENCE InterfaceDereference;
    USHORT CtlrDevId;
    PVOID GetResources;
    PVOID SetDSPPowerState;
    PVOID RegisterInterrupt;
    PVOID UnregisterInterrupt;
    PVOID GetRenderStream;
    PVOID GetCaptureStream;
    PVOID FreeStream;
    PVOID PrepareDSP;
    PVOID CleanupDSP;
    PVOID TriggerDSP;
    PVOID StreamPosition;
    PVOID DSPEnableSPIB;
    PVOID DSPDisableSPIB;
} P360_ADSP_BUS_INTERFACE, *PP360_ADSP_BUS_INTERFACE;

typedef struct _P360_PROBE_STATUS {
    ULONG Magic;
    ULONG Version;
    NTSTATUS QueryStatus;
    ULONG Flags;
    USHORT ControllerDeviceId;
    USHORT InterfaceVersion;
    ULONG InterfaceSize;
    ULONGLONG Reserved;
} P360_PROBE_STATUS;

typedef struct _P360_DEVICE_CONTEXT {
    P360_ADSP_BUS_INTERFACE Bus;
    BOOLEAN BusReferenced;
    NTSTATUS QueryStatus;
    USHORT ControllerDeviceId;
    USHORT InterfaceVersion;
    ULONG InterfaceSize;
    ULONG Flags;
} P360_DEVICE_CONTEXT, *PP360_DEVICE_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(P360_DEVICE_CONTEXT, P360GetContext);

EVT_WDF_DRIVER_DEVICE_ADD P360EvtDeviceAdd;
EVT_WDF_DEVICE_PREPARE_HARDWARE P360EvtPrepareHardware;
EVT_WDF_DEVICE_RELEASE_HARDWARE P360EvtReleaseHardware;
EVT_WDF_IO_QUEUE_IO_DEVICE_CONTROL P360EvtIoDeviceControl;

DRIVER_INITIALIZE DriverEntry;

NTSTATUS
DriverEntry(_In_ PDRIVER_OBJECT DriverObject, _In_ PUNICODE_STRING RegistryPath)
{
    WDF_DRIVER_CONFIG config;
    WDF_DRIVER_CONFIG_INIT(&config, P360EvtDeviceAdd);
    return WdfDriverCreate(DriverObject, RegistryPath, WDF_NO_OBJECT_ATTRIBUTES,
                           &config, WDF_NO_HANDLE);
}

NTSTATUS
P360EvtDeviceAdd(_In_ WDFDRIVER Driver, _Inout_ PWDFDEVICE_INIT DeviceInit)
{
    WDF_PNPPOWER_EVENT_CALLBACKS pnp;
    WDF_OBJECT_ATTRIBUTES attributes;
    WDF_IO_QUEUE_CONFIG queueConfig;
    WDFDEVICE device;
    WDFQUEUE queue;
    PP360_DEVICE_CONTEXT context;
    UNICODE_STRING name, symLink, sddl;
    NTSTATUS status;

    UNREFERENCED_PARAMETER(Driver);

    WDF_PNPPOWER_EVENT_CALLBACKS_INIT(&pnp);
    pnp.EvtDevicePrepareHardware = P360EvtPrepareHardware;
    pnp.EvtDeviceReleaseHardware = P360EvtReleaseHardware;
    WdfDeviceInitSetPnpPowerEventCallbacks(DeviceInit, &pnp);

    WdfDeviceInitSetDeviceType(DeviceInit, FILE_DEVICE_UNKNOWN);
    WdfDeviceInitSetIoType(DeviceInit, WdfDeviceIoBuffered);
    RtlInitUnicodeString(&name, L"\\Device\\P360AdspProbe");
    status = WdfDeviceInitAssignName(DeviceInit, &name);
    if (!NT_SUCCESS(status)) return status;

    RtlInitUnicodeString(&sddl, L"D:P(A;;GA;;;SY)(A;;GA;;;BA)");
    status = WdfDeviceInitAssignSDDLString(DeviceInit, &sddl);
    if (!NT_SUCCESS(status)) return status;

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&attributes, P360_DEVICE_CONTEXT);
    status = WdfDeviceCreate(&DeviceInit, &attributes, &device);
    if (!NT_SUCCESS(status)) return status;

    context = P360GetContext(device);
    RtlZeroMemory(context, sizeof(*context));
    context->QueryStatus = STATUS_NOT_SUPPORTED;
    context->Flags = P360_FLAG_NO_IRQ_TEST;

    WDF_IO_QUEUE_CONFIG_INIT_DEFAULT_QUEUE(&queueConfig, WdfIoQueueDispatchSequential);
    queueConfig.EvtIoDeviceControl = P360EvtIoDeviceControl;
    status = WdfIoQueueCreate(device, &queueConfig, WDF_NO_OBJECT_ATTRIBUTES, &queue);
    if (!NT_SUCCESS(status)) return status;

    RtlInitUnicodeString(&symLink, L"\\DosDevices\\P360AdspProbe");
    status = WdfDeviceCreateSymbolicLink(device, &symLink);
    return status;
}

NTSTATUS
P360EvtPrepareHardware(_In_ WDFDEVICE Device, _In_ WDFCMRESLIST Raw,
                       _In_ WDFCMRESLIST Translated)
{
    PP360_DEVICE_CONTEXT ctx = P360GetContext(Device);
    NTSTATUS status;
    UNREFERENCED_PARAMETER(Raw);
    UNREFERENCED_PARAMETER(Translated);

    RtlZeroMemory(&ctx->Bus, sizeof(ctx->Bus));
    ctx->BusReferenced = FALSE;
    ctx->Flags = P360_FLAG_NO_IRQ_TEST;
    ctx->ControllerDeviceId = 0;
    ctx->InterfaceVersion = 0;
    ctx->InterfaceSize = 0;

    status = WdfFdoQueryForInterface(Device, &GUID_ADSP_BUS_INTERFACE,
                                     (PINTERFACE)&ctx->Bus,
                                     sizeof(ctx->Bus), 1, NULL);
    ctx->QueryStatus = status;

    if (NT_SUCCESS(status)) {
        ctx->InterfaceSize = ctx->Bus.Size;
        ctx->InterfaceVersion = ctx->Bus.Version;
        ctx->ControllerDeviceId = ctx->Bus.CtlrDevId;
        ctx->BusReferenced = TRUE;

        if (ctx->Bus.Size == sizeof(ctx->Bus) &&
            ctx->Bus.Version == 1 &&
            ctx->Bus.CtlrDevId == 0x3198) {
            ctx->Flags |= P360_FLAG_INTERFACE_OK;
        }
        if (ctx->Bus.GetResources != NULL)
            ctx->Flags |= P360_FLAG_RESOURCES_EXPORT_PRESENT;
        if (ctx->Bus.RegisterInterrupt != NULL &&
            ctx->Bus.UnregisterInterrupt != NULL)
            ctx->Flags |= P360_FLAG_IRQ_REGISTER_EXPORT_PRESENT;
    }

    DbgPrintEx(DPFLTR_IHVDRIVER_ID, DPFLTR_INFO_LEVEL,
               "P360-PROBE: Query ADSP interface status=0x%08X dev=0x%04X ver=%u size=%lu flags=0x%08lX\n",
               (ULONG)status, (ULONG)ctx->ControllerDeviceId,
               (ULONG)ctx->InterfaceVersion, ctx->InterfaceSize, ctx->Flags);

    /* Query failure is reported through the read-only IOCTL, not hidden by
       a PnP start failure. This driver never calls any DSP callback. */
    return STATUS_SUCCESS;
}

NTSTATUS
P360EvtReleaseHardware(_In_ WDFDEVICE Device, _In_ WDFCMRESLIST Translated)
{
    PP360_DEVICE_CONTEXT ctx = P360GetContext(Device);
    UNREFERENCED_PARAMETER(Translated);

    if (ctx->BusReferenced && ctx->Bus.InterfaceDereference) {
        ctx->Bus.InterfaceDereference(ctx->Bus.Context);
    }

    ctx->BusReferenced = FALSE;
    RtlZeroMemory(&ctx->Bus, sizeof(ctx->Bus));
    ctx->QueryStatus = STATUS_NOT_SUPPORTED;
    ctx->Flags = P360_FLAG_NO_IRQ_TEST;
    return STATUS_SUCCESS;
}

VOID
P360EvtIoDeviceControl(_In_ WDFQUEUE Queue, _In_ WDFREQUEST Request,
                       _In_ size_t OutputBufferLength,
                       _In_ size_t InputBufferLength,
                       _In_ ULONG IoControlCode)
{
    PP360_PROBE_STATUS out;
    PP360_DEVICE_CONTEXT ctx;
    WDFDEVICE device;
    NTSTATUS status;
    UNREFERENCED_PARAMETER(OutputBufferLength);
    UNREFERENCED_PARAMETER(InputBufferLength);

    if (IoControlCode != IOCTL_P360_PROBE_STATUS) {
        WdfRequestComplete(Request, STATUS_INVALID_DEVICE_REQUEST);
        return;
    }

    device = WdfIoQueueGetDevice(Queue);
    ctx = P360GetContext(device);
    status = WdfRequestRetrieveOutputBuffer(Request, sizeof(*out),
                                             (PVOID*)&out, NULL);
    if (!NT_SUCCESS(status)) {
        WdfRequestComplete(Request, status);
        return;
    }

    RtlZeroMemory(out, sizeof(*out));
    out->Magic = P360_STATUS_MAGIC;
    out->Version = 1;
    out->QueryStatus = ctx->QueryStatus;
    out->Flags = ctx->Flags;
    out->ControllerDeviceId = ctx->ControllerDeviceId;
    out->InterfaceVersion = ctx->InterfaceVersion;
    out->InterfaceSize = ctx->InterfaceSize;
    WdfRequestCompleteWithInformation(Request, STATUS_SUCCESS, sizeof(*out));
}
