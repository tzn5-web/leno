#include <ntddk.h>
#include <wdf.h>
#include <initguid.h>
#include <hdaudio.h>

/*
 * P360HdaIrqTrigger
 *
 * Diagnostic function driver for the existing HDAUDIO graphics-codec PDO
 * created by SklHDAudBus. It exposes exactly one fixed diagnostic operation:
 *
 *   GET_PARAMETER(Node 0, Vendor ID)
 *
 * This is a read-only HDA codec verb. There is no arbitrary verb input,
 * no DMA/stream allocation, no playback, no codec power write, no DSP/MMIO
 * access and no SOF firmware/IPC operation.
 *
 * A successful TransferCodecVerbs call requires the parent CORB/RIRB path.
 * In CoolStar SklHDAudBus, RIRB completion is handled from hda_interrupt()
 * and the registered ADSP callback is invoked at the start of that ISR.
 */
#define IOCTL_P360_HDA_READ_VENDOR CTL_CODE(FILE_DEVICE_UNKNOWN, 0x811, METHOD_BUFFERED, FILE_READ_ACCESS)
#define P360_HDA_MAGIC 0x48333630UL

#define P360_HDA_FLAG_INTERFACE_OK 0x00000001UL
#define P360_HDA_FLAG_RESPONSE_VALID 0x00000002UL
#define P360_HDA_FLAG_FIXED_READ_ONLY_VERB 0x00000004UL

typedef struct _P360_HDA_RESULT {
    ULONG Magic;
    ULONG Version;
    NTSTATUS QueryStatus;
    NTSTATUS TransferStatus;
    ULONG Command;
    ULONG Response;
    ULONG Flags;
    UCHAR CodecAddress;
    UCHAR FunctionGroupStartNode;
    USHORT Reserved16;
    ULONGLONG CompleteResponse;
} P360_HDA_RESULT, *PP360_HDA_RESULT;

typedef struct _P360_HDA_CONTEXT {
    HDAUDIO_BUS_INTERFACE Bus;
    BOOLEAN BusReferenced;
    NTSTATUS QueryStatus;
    UCHAR CodecAddress;
    UCHAR FunctionGroupStartNode;
    ULONG Flags;
} P360_HDA_CONTEXT, *PP360_HDA_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(P360_HDA_CONTEXT, P360HdaGetContext);

DRIVER_INITIALIZE DriverEntry;
EVT_WDF_DRIVER_DEVICE_ADD P360HdaEvtDeviceAdd;
EVT_WDF_DEVICE_PREPARE_HARDWARE P360HdaEvtPrepareHardware;
EVT_WDF_DEVICE_RELEASE_HARDWARE P360HdaEvtReleaseHardware;
EVT_WDF_IO_QUEUE_IO_DEVICE_CONTROL P360HdaEvtIoDeviceControl;

NTSTATUS
DriverEntry(_In_ PDRIVER_OBJECT DriverObject, _In_ PUNICODE_STRING RegistryPath)
{
    WDF_DRIVER_CONFIG config;
    WDF_DRIVER_CONFIG_INIT(&config, P360HdaEvtDeviceAdd);
    return WdfDriverCreate(DriverObject, RegistryPath, WDF_NO_OBJECT_ATTRIBUTES,
                           &config, WDF_NO_HANDLE);
}

NTSTATUS
P360HdaEvtDeviceAdd(_In_ WDFDRIVER Driver, _Inout_ PWDFDEVICE_INIT DeviceInit)
{
    WDF_PNPPOWER_EVENT_CALLBACKS pnp;
    WDF_OBJECT_ATTRIBUTES attributes;
    WDF_IO_QUEUE_CONFIG queueConfig;
    WDFDEVICE device;
    WDFQUEUE queue;
    UNICODE_STRING name;
    UNICODE_STRING link;
    UNICODE_STRING sddl;
    PP360_HDA_CONTEXT ctx;
    NTSTATUS status;

    UNREFERENCED_PARAMETER(Driver);

    WDF_PNPPOWER_EVENT_CALLBACKS_INIT(&pnp);
    pnp.EvtDevicePrepareHardware = P360HdaEvtPrepareHardware;
    pnp.EvtDeviceReleaseHardware = P360HdaEvtReleaseHardware;
    WdfDeviceInitSetPnpPowerEventCallbacks(DeviceInit, &pnp);

    WdfDeviceInitSetDeviceType(DeviceInit, FILE_DEVICE_UNKNOWN);
    WdfDeviceInitSetIoType(DeviceInit, WdfDeviceIoBuffered);

    RtlInitUnicodeString(&name, L"\\Device\\P360HdaTrigger");
    status = WdfDeviceInitAssignName(DeviceInit, &name);
    if (!NT_SUCCESS(status)) return status;

    RtlInitUnicodeString(&sddl, L"D:P(A;;GA;;;SY)(A;;GA;;;BA)");
    status = WdfDeviceInitAssignSDDLString(DeviceInit, &sddl);
    if (!NT_SUCCESS(status)) return status;

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&attributes, P360_HDA_CONTEXT);
    status = WdfDeviceCreate(&DeviceInit, &attributes, &device);
    if (!NT_SUCCESS(status)) return status;

    ctx = P360HdaGetContext(device);
    RtlZeroMemory(ctx, sizeof(*ctx));
    ctx->QueryStatus = STATUS_NOT_SUPPORTED;
    ctx->Flags = P360_HDA_FLAG_FIXED_READ_ONLY_VERB;

    WDF_IO_QUEUE_CONFIG_INIT_DEFAULT_QUEUE(&queueConfig, WdfIoQueueDispatchSequential);
    queueConfig.EvtIoDeviceControl = P360HdaEvtIoDeviceControl;
    status = WdfIoQueueCreate(device, &queueConfig, WDF_NO_OBJECT_ATTRIBUTES, &queue);
    if (!NT_SUCCESS(status)) return status;

    RtlInitUnicodeString(&link, L"\\DosDevices\\P360HdaTrigger");
    return WdfDeviceCreateSymbolicLink(device, &link);
}

NTSTATUS
P360HdaEvtPrepareHardware(_In_ WDFDEVICE Device,
                          _In_ WDFCMRESLIST Raw,
                          _In_ WDFCMRESLIST Translated)
{
    PP360_HDA_CONTEXT ctx = P360HdaGetContext(Device);
    NTSTATUS status;

    UNREFERENCED_PARAMETER(Raw);
    UNREFERENCED_PARAMETER(Translated);

    RtlZeroMemory(&ctx->Bus, sizeof(ctx->Bus));
    ctx->BusReferenced = FALSE;
    ctx->QueryStatus = STATUS_NOT_SUPPORTED;
    ctx->CodecAddress = 0;
    ctx->FunctionGroupStartNode = 0;
    ctx->Flags = P360_HDA_FLAG_FIXED_READ_ONLY_VERB;

    status = WdfFdoQueryForInterface(
        Device,
        &GUID_HDAUDIO_BUS_INTERFACE,
        (PINTERFACE)&ctx->Bus,
        sizeof(ctx->Bus),
        1,
        NULL);

    ctx->QueryStatus = status;

    if (NT_SUCCESS(status)) {
        ctx->BusReferenced = TRUE;

        if (ctx->Bus.Size == sizeof(ctx->Bus) &&
            ctx->Bus.Version == 1 &&
            ctx->Bus.TransferCodecVerbs != NULL &&
            ctx->Bus.GetResourceInformation != NULL) {
            ctx->Flags |= P360_HDA_FLAG_INTERFACE_OK;

            /*
             * Read-only metadata from the PDO context. This does not touch
             * hardware and prevents hard-coding the codec address.
             */
            ctx->Bus.GetResourceInformation(
                ctx->Bus.Context,
                &ctx->CodecAddress,
                &ctx->FunctionGroupStartNode);
        }
    }

    DbgPrintEx(DPFLTR_IHVDRIVER_ID, DPFLTR_INFO_LEVEL,
               "P360-HDA-TRIGGER: query=0x%08X codec=%u fg=%u flags=0x%08lX\n",
               (ULONG)ctx->QueryStatus,
               (ULONG)ctx->CodecAddress,
               (ULONG)ctx->FunctionGroupStartNode,
               ctx->Flags);

    return STATUS_SUCCESS;
}

NTSTATUS
P360HdaEvtReleaseHardware(_In_ WDFDEVICE Device,
                          _In_ WDFCMRESLIST Translated)
{
    PP360_HDA_CONTEXT ctx = P360HdaGetContext(Device);
    UNREFERENCED_PARAMETER(Translated);

    if (ctx->BusReferenced && ctx->Bus.InterfaceDereference != NULL) {
        ctx->Bus.InterfaceDereference(ctx->Bus.Context);
    }

    ctx->BusReferenced = FALSE;
    RtlZeroMemory(&ctx->Bus, sizeof(ctx->Bus));
    ctx->QueryStatus = STATUS_NOT_SUPPORTED;
    ctx->Flags = P360_HDA_FLAG_FIXED_READ_ONLY_VERB;
    return STATUS_SUCCESS;
}

VOID
P360HdaEvtIoDeviceControl(_In_ WDFQUEUE Queue,
                          _In_ WDFREQUEST Request,
                          _In_ size_t OutputBufferLength,
                          _In_ size_t InputBufferLength,
                          _In_ ULONG IoControlCode)
{
    PP360_HDA_CONTEXT ctx;
    PP360_HDA_RESULT out;
    HDAUDIO_CODEC_TRANSFER transfer;
    WDFDEVICE device;
    NTSTATUS status;

    UNREFERENCED_PARAMETER(OutputBufferLength);
    UNREFERENCED_PARAMETER(InputBufferLength);

    if (IoControlCode != IOCTL_P360_HDA_READ_VENDOR) {
        WdfRequestComplete(Request, STATUS_INVALID_DEVICE_REQUEST);
        return;
    }

    device = WdfIoQueueGetDevice(Queue);
    ctx = P360HdaGetContext(device);

    status = WdfRequestRetrieveOutputBuffer(
        Request, sizeof(*out), (PVOID*)&out, NULL);
    if (!NT_SUCCESS(status)) {
        WdfRequestComplete(Request, status);
        return;
    }

    RtlZeroMemory(out, sizeof(*out));
    out->Magic = P360_HDA_MAGIC;
    out->Version = 1;
    out->QueryStatus = ctx->QueryStatus;
    out->TransferStatus = STATUS_NOT_SUPPORTED;
    out->Flags = ctx->Flags;
    out->CodecAddress = ctx->CodecAddress;
    out->FunctionGroupStartNode = ctx->FunctionGroupStartNode;

    if (!NT_SUCCESS(ctx->QueryStatus) ||
        (ctx->Flags & P360_HDA_FLAG_INTERFACE_OK) == 0) {
        WdfRequestCompleteWithInformation(Request, STATUS_SUCCESS, sizeof(*out));
        return;
    }

    /*
     * Fixed read-only HDA command:
     * Codec = PDO-reported address
     * Node  = 0 (codec root)
     * Verb  = 0xF00 GET_PARAMETER
     * Data  = 0x00 Vendor ID parameter
     */
    RtlZeroMemory(&transfer, sizeof(transfer));
    transfer.Output.Verb8.CodecAddress = ctx->CodecAddress;
    transfer.Output.Verb8.Node = 0;
    transfer.Output.Verb8.VerbId = 0xF00;
    transfer.Output.Verb8.Data = 0x00;

    out->Command = transfer.Output.Command;

    status = ctx->Bus.TransferCodecVerbs(
        ctx->Bus.Context,
        1,
        &transfer,
        NULL,
        NULL);

    out->TransferStatus = status;
    out->Response = transfer.Input.Response;
    out->CompleteResponse = transfer.Input.CompleteResponse;

    if (transfer.Input.IsValid) {
        out->Flags |= P360_HDA_FLAG_RESPONSE_VALID;
    }

    WdfRequestCompleteWithInformation(Request, STATUS_SUCCESS, sizeof(*out));
}
