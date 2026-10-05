#include <ntddk.h>
#include <wdf.h>
#include <initguid.h>

/*
 * P360AdspProbe v2: passive IRQ-callback diagnostic function driver for
 * CoolStar's CSAUDIO\ADSP child on Gemini Lake.
 *
 * Allowed operation: register/unregister the parent bus's already-exposed
 * software interrupt callback and atomically count callback invocations.
 *
 * Explicitly NOT performed:
 * - no GetResources call
 * - no MMIO mapping/read/write
 * - no DSP power-state call
 * - no SOF firmware boot
 * - no IPC
 * - no stream allocation/trigger
 * - no codec/GPIO writes
 * - no audio endpoint or playback
 */
DEFINE_GUID(GUID_ADSP_BUS_INTERFACE,
    0x752a2cae, 0x3455, 0x4d18, 0xa1, 0x84, 0x8b, 0x34, 0xb2, 0x26, 0x32, 0xce);

#define IOCTL_P360_PROBE_STATUS CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_READ_ACCESS)
#define P360_STATUS_MAGIC 0x50333630UL

#define P360_FLAG_INTERFACE_OK                0x00000001UL
#define P360_FLAG_RESOURCES_EXPORT_PRESENT    0x00000002UL
#define P360_FLAG_IRQ_REGISTER_EXPORT_PRESENT 0x00000004UL
#define P360_FLAG_IRQ_CALLBACK_REGISTERED     0x00000008UL
#define P360_FLAG_IRQ_TRAFFIC_SEEN            0x00000010UL

typedef LONG (*P360_ADSP_INTERRUPT_CALLBACK)(_In_ PVOID Context);
typedef NTSTATUS (*P360_REGISTER_ADSP_INTERRUPT)(
    _In_ PVOID Context,
    _In_ P360_ADSP_INTERRUPT_CALLBACK Callback,
    _In_ PVOID CallbackContext);
typedef NTSTATUS (*P360_UNREGISTER_ADSP_INTERRUPT)(_In_ PVOID Context);

typedef struct _P360_ADSP_BUS_INTERFACE {
    USHORT Size;
    USHORT Version;
    PVOID Context;
    PINTERFACE_REFERENCE InterfaceReference;
    PINTERFACE_DEREFERENCE InterfaceDereference;
    USHORT CtlrDevId;
    PVOID GetResources;
    PVOID SetDSPPowerState;
    P360_REGISTER_ADSP_INTERRUPT RegisterInterrupt;
    P360_UNREGISTER_ADSP_INTERRUPT UnregisterInterrupt;
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
    NTSTATUS RegisterStatus;
    ULONG Flags;
    USHORT ControllerDeviceId;
    USHORT InterfaceVersion;
    ULONG InterfaceSize;
    LONG64 IrqCount;
    ULONGLONG Reserved;
} P360_PROBE_STATUS, *PP360_PROBE_STATUS;

typedef struct _P360_DEVICE_CONTEXT {
    P360_ADSP_BUS_INTERFACE Bus;
    BOOLEAN BusReferenced;
    BOOLEAN IrqRegistered;
    NTSTATUS QueryStatus;
    NTSTATUS RegisterStatus;
    USHORT ControllerDeviceId;
    USHORT InterfaceVersion;
    ULONG InterfaceSize;
    ULONG Flags;
    volatile LONG64 IrqCount;
} P360_DEVICE_CONTEXT, *PP360_DEVICE_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(P360_DEVICE_CONTEXT, P360GetContext);

EVT_WDF_DRIVER_DEVICE_ADD P360EvtDeviceAdd;
EVT_WDF_DEVICE_PREPARE_HARDWARE P360EvtPrepareHardware;
EVT_WDF_DEVICE_RELEASE_HARDWARE P360EvtReleaseHardware;
EVT_WDF_IO_QUEUE_IO_DEVICE_CONTROL P360EvtIoDeviceControl;

DRIVER_INITIALIZE DriverEntry;

static LONG
P360IrqCallback(_In_ PVOID Context)
{
    PP360_DEVICE_CONTEXT ctx = (PP360_DEVICE_CONTEXT)Context;

    if (ctx != NULL) {
        InterlockedIncrement64(&ctx->IrqCount);
    }

    /*
     * Never claim the shared HDA interrupt. Returning FALSE allows the
     * parent SklHDAudBus ISR to continue its normal HDA handling.
     */
    return FALSE;
}

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
    context->RegisterStatus = STATUS_NOT_SUPPORTED;

    WDF_IO_QUEUE_CONFIG_INIT_DEFAULT_QUEUE(&queueConfig, WdfIoQueueDispatchSequential);
    queueConfig.EvtIoDeviceControl = P360EvtIoDeviceControl;
    status = WdfIoQueueCreate(device, &queueConfig, WDF_NO_OBJECT_ATTRIBUTES, &queue);
    if (!NT_SUCCESS(status)) return status;

    RtlInitUnicodeString(&symLink, L"\\DosDevices\\P360AdspProbe");
    return WdfDeviceCreateSymbolicLink(device, &symLink);
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
    ctx->IrqRegistered = FALSE;
    ctx->QueryStatus = STATUS_NOT_SUPPORTED;
    ctx->RegisterStatus = STATUS_NOT_SUPPORTED;
    ctx->ControllerDeviceId = 0;
    ctx->InterfaceVersion = 0;
    ctx->InterfaceSize = 0;
    ctx->Flags = 0;
    InterlockedExchange64(&ctx->IrqCount, 0);

    status = WdfFdoQueryForInterface(Device, &GUID_ADSP_BUS_INTERFACE,
                                     (PINTERFACE)&ctx->Bus,
                                     sizeof(ctx->Bus), 1, NULL);
    ctx->QueryStatus = status;

    if (NT_SUCCESS(status)) {
        ctx->BusReferenced = TRUE;
        ctx->InterfaceSize = ctx->Bus.Size;
        ctx->InterfaceVersion = ctx->Bus.Version;
        ctx->ControllerDeviceId = ctx->Bus.CtlrDevId;

        if (ctx->Bus.Size == sizeof(ctx->Bus) &&
            ctx->Bus.Version == 1 &&
            ctx->Bus.CtlrDevId == 0x3198) {
            ctx->Flags |= P360_FLAG_INTERFACE_OK;
        }

        if (ctx->Bus.GetResources != NULL) {
            ctx->Flags |= P360_FLAG_RESOURCES_EXPORT_PRESENT;
        }

        if (ctx->Bus.RegisterInterrupt != NULL &&
            ctx->Bus.UnregisterInterrupt != NULL) {
            ctx->Flags |= P360_FLAG_IRQ_REGISTER_EXPORT_PRESENT;

            /*
             * Register only a passive software callback into the parent's
             * existing ISR. No DSP register is read or written here.
             */
            ctx->RegisterStatus = ctx->Bus.RegisterInterrupt(
                ctx->Bus.Context, P360IrqCallback, ctx);

            if (NT_SUCCESS(ctx->RegisterStatus)) {
                ctx->IrqRegistered = TRUE;
                ctx->Flags |= P360_FLAG_IRQ_CALLBACK_REGISTERED;
            }
        }
    }

    DbgPrintEx(DPFLTR_IHVDRIVER_ID, DPFLTR_INFO_LEVEL,
               "P360-PROBE-V2: query=0x%08X register=0x%08X dev=0x%04X ver=%u size=%lu flags=0x%08lX\n",
               (ULONG)ctx->QueryStatus, (ULONG)ctx->RegisterStatus,
               (ULONG)ctx->ControllerDeviceId, (ULONG)ctx->InterfaceVersion,
               ctx->InterfaceSize, ctx->Flags);

    /*
     * Preserve diagnostic accessibility even if callback registration fails.
     * The failure is surfaced through IOCTL instead of hiding behind Code 10.
     */
    return STATUS_SUCCESS;
}

NTSTATUS
P360EvtReleaseHardware(_In_ WDFDEVICE Device, _In_ WDFCMRESLIST Translated)
{
    PP360_DEVICE_CONTEXT ctx = P360GetContext(Device);
    UNREFERENCED_PARAMETER(Translated);

    if (ctx->IrqRegistered && ctx->Bus.UnregisterInterrupt != NULL) {
        (void)ctx->Bus.UnregisterInterrupt(ctx->Bus.Context);
        ctx->IrqRegistered = FALSE;
    }

    if (ctx->BusReferenced && ctx->Bus.InterfaceDereference != NULL) {
        ctx->Bus.InterfaceDereference(ctx->Bus.Context);
    }

    ctx->BusReferenced = FALSE;
    RtlZeroMemory(&ctx->Bus, sizeof(ctx->Bus));
    ctx->QueryStatus = STATUS_NOT_SUPPORTED;
    ctx->RegisterStatus = STATUS_NOT_SUPPORTED;
    ctx->Flags = 0;
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
    LONG64 irqCount;

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

    irqCount = InterlockedCompareExchange64(&ctx->IrqCount, 0, 0);

    RtlZeroMemory(out, sizeof(*out));
    out->Magic = P360_STATUS_MAGIC;
    out->Version = 2;
    out->QueryStatus = ctx->QueryStatus;
    out->RegisterStatus = ctx->RegisterStatus;
    out->Flags = ctx->Flags;
    if (irqCount > 0) {
        out->Flags |= P360_FLAG_IRQ_TRAFFIC_SEEN;
    }
    out->ControllerDeviceId = ctx->ControllerDeviceId;
    out->InterfaceVersion = ctx->InterfaceVersion;
    out->InterfaceSize = ctx->InterfaceSize;
    out->IrqCount = irqCount;

    WdfRequestCompleteWithInformation(Request, STATUS_SUCCESS, sizeof(*out));
}
