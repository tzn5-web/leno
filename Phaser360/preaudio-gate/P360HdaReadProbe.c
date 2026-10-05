#include <ntddk.h>
#include <wdf.h>
#include <initguid.h>
#include <hdaudio.h>

#define IOCTL_P360_HDA_STATUS CTL_CODE(FILE_DEVICE_UNKNOWN,0x821,METHOD_BUFFERED,FILE_READ_ACCESS)
#define IOCTL_P360_HDA_READ_VENDOR CTL_CODE(FILE_DEVICE_UNKNOWN,0x822,METHOD_BUFFERED,FILE_READ_ACCESS|FILE_WRITE_ACCESS)
#define P360_HDA_MAGIC 0x48333630UL

typedef struct _P360_HDA_STATUS {
    ULONG Magic;
    ULONG Version;
    NTSTATUS QueryStatus;
    NTSTATUS TransferStatus;
    ULONG Flags;
    UCHAR CodecAddress;
    UCHAR FunctionGroupStartNode;
    USHORT BusInterfaceVersion;
    ULONG BusInterfaceSize;
    ULONG Command;
    ULONGLONG CompleteResponse;
    ULONG Response;
    ULONG ResponseValid;
    ULONG FifoOverrun;
    ULONG Reserved;
} P360_HDA_STATUS, *PP360_HDA_STATUS;

#define F_IFACE_OK       0x1UL
#define F_TRANSFER_OK    0x2UL
#define F_RESPONSE_VALID 0x4UL

typedef struct _P360_HDA_CTX {
    HDAUDIO_BUS_INTERFACE Bus;
    BOOLEAN BusReferenced;
    NTSTATUS QueryStatus;
    NTSTATUS TransferStatus;
    ULONG Flags;
    UCHAR CodecAddress;
    UCHAR FunctionGroupStartNode;
    ULONG LastCommand;
    HDAUDIO_CODEC_RESPONSE LastResponse;
} P360_HDA_CTX,*PP360_HDA_CTX;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(P360_HDA_CTX,P360HdaGetCtx);

EVT_WDF_DRIVER_DEVICE_ADD P360HdaEvtDeviceAdd;
EVT_WDF_DEVICE_PREPARE_HARDWARE P360HdaEvtPrepareHardware;
EVT_WDF_DEVICE_RELEASE_HARDWARE P360HdaEvtReleaseHardware;
EVT_WDF_IO_QUEUE_IO_DEVICE_CONTROL P360HdaEvtIoctl;
DRIVER_INITIALIZE DriverEntry;

NTSTATUS DriverEntry(_In_ PDRIVER_OBJECT DriverObject,_In_ PUNICODE_STRING RegistryPath)
{
    WDF_DRIVER_CONFIG c;
    WDF_DRIVER_CONFIG_INIT(&c,P360HdaEvtDeviceAdd);
    return WdfDriverCreate(DriverObject,RegistryPath,WDF_NO_OBJECT_ATTRIBUTES,&c,WDF_NO_HANDLE);
}

NTSTATUS P360HdaEvtDeviceAdd(_In_ WDFDRIVER Driver,_Inout_ PWDFDEVICE_INIT DeviceInit)
{
    WDF_PNPPOWER_EVENT_CALLBACKS pnp;
    WDF_OBJECT_ATTRIBUTES a;
    WDF_IO_QUEUE_CONFIG q;
    WDFDEVICE dev;
    WDFQUEUE queue;
    PP360_HDA_CTX ctx;
    UNICODE_STRING name,link,sddl;
    NTSTATUS st;
    UNREFERENCED_PARAMETER(Driver);

    WDF_PNPPOWER_EVENT_CALLBACKS_INIT(&pnp);
    pnp.EvtDevicePrepareHardware=P360HdaEvtPrepareHardware;
    pnp.EvtDeviceReleaseHardware=P360HdaEvtReleaseHardware;
    WdfDeviceInitSetPnpPowerEventCallbacks(DeviceInit,&pnp);
    WdfDeviceInitSetDeviceType(DeviceInit,FILE_DEVICE_UNKNOWN);
    WdfDeviceInitSetIoType(DeviceInit,WdfDeviceIoBuffered);

    RtlInitUnicodeString(&name,L"\\Device\\P360HdaReadProbe");
    st=WdfDeviceInitAssignName(DeviceInit,&name);
    if(!NT_SUCCESS(st)) return st;
    RtlInitUnicodeString(&sddl,L"D:P(A;;GA;;;SY)(A;;GA;;;BA)");
    st=WdfDeviceInitAssignSDDLString(DeviceInit,&sddl);
    if(!NT_SUCCESS(st)) return st;

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&a,P360_HDA_CTX);
    st=WdfDeviceCreate(&DeviceInit,&a,&dev);
    if(!NT_SUCCESS(st)) return st;
    ctx=P360HdaGetCtx(dev);
    RtlZeroMemory(ctx,sizeof(*ctx));
    ctx->QueryStatus=STATUS_NOT_SUPPORTED;
    ctx->TransferStatus=STATUS_NOT_SUPPORTED;

    WDF_IO_QUEUE_CONFIG_INIT_DEFAULT_QUEUE(&q,WdfIoQueueDispatchSequential);
    q.EvtIoDeviceControl=P360HdaEvtIoctl;
    st=WdfIoQueueCreate(dev,&q,WDF_NO_OBJECT_ATTRIBUTES,&queue);
    if(!NT_SUCCESS(st)) return st;

    RtlInitUnicodeString(&link,L"\\DosDevices\\P360HdaReadProbe");
    return WdfDeviceCreateSymbolicLink(dev,&link);
}

NTSTATUS P360HdaEvtPrepareHardware(_In_ WDFDEVICE Device,_In_ WDFCMRESLIST Raw,_In_ WDFCMRESLIST Translated)
{
    PP360_HDA_CTX ctx=P360HdaGetCtx(Device);
    NTSTATUS st;
    UNREFERENCED_PARAMETER(Raw);
    UNREFERENCED_PARAMETER(Translated);

    RtlZeroMemory(&ctx->Bus,sizeof(ctx->Bus));
    ctx->BusReferenced=FALSE;
    ctx->Flags=0;
    ctx->CodecAddress=0xFF;
    ctx->FunctionGroupStartNode=0;
    ctx->TransferStatus=STATUS_NOT_SUPPORTED;
    RtlZeroMemory(&ctx->LastResponse,sizeof(ctx->LastResponse));

    st=WdfFdoQueryForInterface(Device,&GUID_HDAUDIO_BUS_INTERFACE,
        (PINTERFACE)&ctx->Bus,sizeof(ctx->Bus),0x0100,NULL);
    ctx->QueryStatus=st;

    if(NT_SUCCESS(st)) {
        ctx->BusReferenced=TRUE;
        if(ctx->Bus.Size==sizeof(ctx->Bus) &&
           ctx->Bus.Version==0x0100 &&
           ctx->Bus.TransferCodecVerbs!=NULL &&
           ctx->Bus.GetResourceInformation!=NULL) {
            ctx->Flags|=F_IFACE_OK;
            ctx->Bus.GetResourceInformation(ctx->Bus.Context,
                &ctx->CodecAddress,&ctx->FunctionGroupStartNode);
        }
    }

    DbgPrintEx(DPFLTR_IHVDRIVER_ID,DPFLTR_INFO_LEVEL,
        "P360-HDA-PROBE: query=0x%08X addr=%u fg=%u size=%u ver=0x%04X flags=0x%08X\n",
        (ULONG)ctx->QueryStatus,(ULONG)ctx->CodecAddress,
        (ULONG)ctx->FunctionGroupStartNode,(ULONG)ctx->Bus.Size,
        (ULONG)ctx->Bus.Version,ctx->Flags);
    return STATUS_SUCCESS;
}

NTSTATUS P360HdaEvtReleaseHardware(_In_ WDFDEVICE Device,_In_ WDFCMRESLIST Translated)
{
    PP360_HDA_CTX ctx=P360HdaGetCtx(Device);
    UNREFERENCED_PARAMETER(Translated);
    if(ctx->BusReferenced && ctx->Bus.InterfaceDereference)
        ctx->Bus.InterfaceDereference(ctx->Bus.Context);
    ctx->BusReferenced=FALSE;
    RtlZeroMemory(&ctx->Bus,sizeof(ctx->Bus));
    return STATUS_SUCCESS;
}

static VOID P360FillStatus(_In_ PP360_HDA_CTX ctx,_Out_ PP360_HDA_STATUS out)
{
    RtlZeroMemory(out,sizeof(*out));
    out->Magic=P360_HDA_MAGIC;
    out->Version=1;
    out->QueryStatus=ctx->QueryStatus;
    out->TransferStatus=ctx->TransferStatus;
    out->Flags=ctx->Flags;
    out->CodecAddress=ctx->CodecAddress;
    out->FunctionGroupStartNode=ctx->FunctionGroupStartNode;
    out->BusInterfaceVersion=ctx->Bus.Version;
    out->BusInterfaceSize=ctx->Bus.Size;
    out->Command=ctx->LastCommand;
    out->CompleteResponse=ctx->LastResponse.CompleteResponse;
    out->Response=ctx->LastResponse.Response;
    out->ResponseValid=ctx->LastResponse.IsValid ? 1UL : 0UL;
    out->FifoOverrun=ctx->LastResponse.HasFifoOverrun ? 1UL : 0UL;
}

VOID P360HdaEvtIoctl(_In_ WDFQUEUE Queue,_In_ WDFREQUEST Request,
    _In_ size_t OutputBufferLength,_In_ size_t InputBufferLength,_In_ ULONG IoControlCode)
{
    WDFDEVICE dev=WdfIoQueueGetDevice(Queue);
    PP360_HDA_CTX ctx=P360HdaGetCtx(dev);
    PP360_HDA_STATUS out;
    NTSTATUS st;
    HDAUDIO_CODEC_TRANSFER xfer;
    UNREFERENCED_PARAMETER(OutputBufferLength);
    UNREFERENCED_PARAMETER(InputBufferLength);

    if(IoControlCode!=IOCTL_P360_HDA_STATUS &&
       IoControlCode!=IOCTL_P360_HDA_READ_VENDOR) {
        WdfRequestComplete(Request,STATUS_INVALID_DEVICE_REQUEST);
        return;
    }

    st=WdfRequestRetrieveOutputBuffer(Request,sizeof(*out),(PVOID*)&out,NULL);
    if(!NT_SUCCESS(st)) {
        WdfRequestComplete(Request,st);
        return;
    }

    if(IoControlCode==IOCTL_P360_HDA_READ_VENDOR) {
        if(!(ctx->Flags&F_IFACE_OK) || ctx->CodecAddress>0x0F) {
            ctx->TransferStatus=STATUS_INVALID_DEVICE_STATE;
        } else {
            RtlZeroMemory(&xfer,sizeof(xfer));
            xfer.Output.Verb8.CodecAddress=ctx->CodecAddress;
            xfer.Output.Verb8.Node=0;
            xfer.Output.Verb8.VerbId=0xF00; /* GET_PARAMETER */
            xfer.Output.Verb8.Data=0x00;    /* Vendor ID parameter */
            ctx->LastCommand=xfer.Output.Command;

            /*
             * Read-only HDA verb. No stream allocation, no pin control,
             * no amp/codec write, no audio. A valid response requires the
             * parent CORB/RIRB/ISR path to complete.
             */
            st=ctx->Bus.TransferCodecVerbs(ctx->Bus.Context,1,&xfer,NULL,NULL);
            ctx->TransferStatus=st;
            ctx->LastResponse=xfer.Input;
            ctx->Flags&=~(F_TRANSFER_OK|F_RESPONSE_VALID);
            if(NT_SUCCESS(st)) ctx->Flags|=F_TRANSFER_OK;
            if(xfer.Input.IsValid) ctx->Flags|=F_RESPONSE_VALID;
        }
    }

    P360FillStatus(ctx,out);
    WdfRequestCompleteWithInformation(Request,STATUS_SUCCESS,sizeof(*out));
}
