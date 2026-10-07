#include <ntifs.h>
#include <wdf.h>
#include <wdfminiport.h>
#include <portcls.h>

#include "../driver/p360_driver.h"
#include "../include/p360_portcls_bridge.h"
#include "../include/p360_speaker_endpoint.h"

/*
 * Kernel builds do not use the CRT <new> header. This translation unit only
 * needs placement construction into ExAllocatePool2 memory.
 */
__forceinline void * __cdecl
operator new(
    size_t,
    void *memory
    ) noexcept
{
    return memory;
}

__forceinline void __cdecl
operator delete(
    void *,
    void *
    ) noexcept
{
}

typedef struct _P360_PORTCLS_INSTANCE {
    KSPIN_LOCK Lock;
    PDEVICE_OBJECT Fdo;
    WDFDEVICE FrameworkDevice;
    P360_DEVICE_CONTEXT *Context;
    volatile LONG Quarantined;
} P360_PORTCLS_INSTANCE;

static P360_PORTCLS_INSTANCE gP360PortClsInstance;
static PDRIVER_UNLOAD gP360PortClsUnloadRoutine=NULL;

#define P360_POWER_POOL_TAG 'w63P'

class P360AdapterPowerManagement final : public IAdapterPowerManagement
{
public:
    explicit P360AdapterPowerManagement(
        _Inout_ P360_DEVICE_CONTEXT *Context
        ) :
        m_Refs(1),
        m_Context(Context),
        m_PowerState(PowerDeviceD0)
    {
    }

    STDMETHODIMP QueryInterface(
        _In_ REFIID InterfaceId,
        _COM_Outptr_ PVOID *Interface
        ) override
    {
        if (!Interface)
            return STATUS_INVALID_PARAMETER;

        *Interface=NULL;
        if (IsEqualGUIDAligned(InterfaceId,IID_IUnknown) ||
            IsEqualGUIDAligned(
                InterfaceId,
                IID_IAdapterPowerManagement)) {
            *Interface=static_cast<IAdapterPowerManagement *>(this);
            AddRef();
            return STATUS_SUCCESS;
        }

        return STATUS_NOINTERFACE;
    }

    STDMETHODIMP_(ULONG) AddRef() override
    {
        return (ULONG)InterlockedIncrement(&m_Refs);
    }

    STDMETHODIMP_(ULONG) Release() override
    {
        LONG refs=InterlockedDecrement(&m_Refs);
        if (!refs) {
            this->~P360AdapterPowerManagement();
            ExFreePoolWithTag(this,P360_POWER_POOL_TAG);
        }
        return (ULONG)refs;
    }

    STDMETHODIMP_(void) PowerChangeState(
        _In_ POWER_STATE NewState
        ) override
    {
        P360_DEVICE_CONTEXT *ctx=m_Context;
        DEVICE_POWER_STATE target=NewState.DeviceState;
        NTSTATUS status=STATUS_SUCCESS;

        if (!ctx || target<PowerDeviceD0 || target>PowerDeviceD3)
            return;

        if (target==m_PowerState)
            return;

        /*
         * PortCls pauses active streams before a sleep transition. Thus the
         * WaveRT stream has already executed MAX mute -> SOF STOP -> HDA STOP
         * before we shut down the DSP here.
         */
        if (target==PowerDeviceD0) {
            status=p360_host_d0_entry(ctx);
        } else if (m_PowerState==PowerDeviceD0) {
            status=p360_host_d0_exit(ctx);
        }

        if (!NT_SUCCESS(status)) {
            p360_state_fail(
                &ctx->State,
                P360_FAIL_FIRMWARE);
        }

        /*
         * PowerChangeState has no return status: cache the state requested by
         * PortCls even on a driver fault and keep the audio path fail-closed.
         */
        m_PowerState=target;
    }

    STDMETHODIMP_(NTSTATUS) QueryPowerChangeState(
        _In_ POWER_STATE NewStateQuery
        ) override
    {
        DEVICE_POWER_STATE target=NewStateQuery.DeviceState;

        if (!m_Context)
            return STATUS_DELETE_PENDING;
        if (target<PowerDeviceD0 || target>PowerDeviceD3)
            return STATUS_INVALID_PARAMETER;

        return STATUS_SUCCESS;
    }

    STDMETHODIMP_(NTSTATUS) QueryDeviceCapabilities(
        _Inout_updates_bytes_(sizeof(DEVICE_CAPABILITIES))
            PDEVICE_CAPABILITIES PowerDeviceCaps
        ) override
    {
        return PowerDeviceCaps ?
            STATUS_SUCCESS :
            STATUS_INVALID_PARAMETER;
    }

    VOID DetachContext()
    {
        m_Context=NULL;
    }

    static NTSTATUS Create(
        _Inout_ P360_DEVICE_CONTEXT *Context,
        _Outptr_ PUNKNOWN *Unknown
        )
    {
        PVOID memory;
        P360AdapterPowerManagement *object;

        if (!Context || !Unknown)
            return STATUS_INVALID_PARAMETER;
        *Unknown=NULL;

        memory=ExAllocatePool2(
            POOL_FLAG_NON_PAGED,
            sizeof(P360AdapterPowerManagement),
            P360_POWER_POOL_TAG);
        if (!memory)
            return STATUS_INSUFFICIENT_RESOURCES;

        object=new(memory) P360AdapterPowerManagement(Context);
        *Unknown=static_cast<IAdapterPowerManagement *>(object);
        return STATUS_SUCCESS;
    }

private:
    volatile LONG m_Refs;
    P360_DEVICE_CONTEXT *m_Context;
    DEVICE_POWER_STATE m_PowerState;
};

static NTSTATUS
p360_portcls_detach_power(
    _In_ PDEVICE_OBJECT DeviceObject,
    _Inout_ P360_DEVICE_CONTEXT *Context
    )
{
    P360AdapterPowerManagement *power;
    NTSTATUS status;

    if (!DeviceObject || !Context)
        return STATUS_INVALID_PARAMETER;

    if (!Context->AdapterPowerManager)
        return STATUS_SUCCESS;

    /*
     * Stop PortCls from issuing any new PowerChangeState callback before the
     * adapter object loses its context/reference. Microsoft explicitly
     * requires unregistering an interface previously registered with
     * PcRegisterAdapterPowerManagement during adapter teardown.
     */
    status=PcUnregisterAdapterPowerManagement(DeviceObject);
    if (!NT_SUCCESS(status))
        return status;

    power=reinterpret_cast<P360AdapterPowerManagement *>(
        Context->AdapterPowerManager);
    Context->AdapterPowerManager=NULL;
    power->DetachContext();
    power->Release();
    return STATUS_SUCCESS;
}

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

static P360_DEVICE_CONTEXT *
p360_portcls_peek_context(
    _In_ PDEVICE_OBJECT Fdo
    )
{
    KIRQL oldIrql;
    P360_DEVICE_CONTEXT *ctx=NULL;

    KeAcquireSpinLock(&gP360PortClsInstance.Lock,&oldIrql);
    if (gP360PortClsInstance.Fdo==Fdo)
        ctx=gP360PortClsInstance.Context;
    KeReleaseSpinLock(&gP360PortClsInstance.Lock,oldIrql);

    /*
     * PnP minor IRPs for this FDO are serialized at PASSIVE_LEVEL, so the
     * instance cannot be removed by another PnP minor while this dispatch
     * routine is evaluating the returned context.
     */
    return ctx;
}

static NTSTATUS
p360_portcls_begin_pnp_query(
    _In_ PDEVICE_OBJECT Fdo
    )
{
    P360_DEVICE_CONTEXT *ctx;

    ctx=p360_portcls_peek_context(Fdo);
    if (!ctx)
        return STATUS_SUCCESS;

    if (InterlockedCompareExchange(
            &gP360PortClsInstance.Quarantined,0,0)!=0)
        return STATUS_DEVICE_HARDWARE_ERROR;

    if (InterlockedCompareExchange(
            &ctx->PnpQueryPending,1,0)!=0)
        return STATUS_SUCCESS;

    if (InterlockedCompareExchange(
            &ctx->Removing,1,0)!=0) {
        InterlockedExchange(&ctx->PnpQueryPending,0);
        return STATUS_DEVICE_BUSY;
    }

    KeMemoryBarrier();

    /*
     * Do not mutate a live WaveRT pin during a QUERY_* IRP. Veto the query
     * instead. This preserves the pin state if PnP later cancels the query
     * and guarantees no new prepare can race in behind the gate.
     */
    if (InterlockedCompareExchangePointer(
            (PVOID volatile *)&ctx->ActivePlayback,
            NULL,
            NULL)!=NULL ||
        InterlockedCompareExchange(
            &ctx->CsAudio.SpeakerStarted,0,0)!=0 ||
        ctx->State.speaker_runtime_armed) {
        InterlockedExchange(&ctx->Removing,0);
        InterlockedExchange(&ctx->PnpQueryPending,0);
        return STATUS_DEVICE_BUSY;
    }

    return STATUS_SUCCESS;
}

static VOID
p360_portcls_cancel_pnp_query(
    _In_ PDEVICE_OBJECT Fdo
    )
{
    P360_DEVICE_CONTEXT *ctx;

    ctx=p360_portcls_peek_context(Fdo);
    if (!ctx)
        return;

    if (InterlockedExchange(
            &ctx->PnpQueryPending,0)!=0 &&
        InterlockedCompareExchange(
            &gP360PortClsInstance.Quarantined,0,0)==0) {
        KeMemoryBarrier();
        InterlockedExchange(&ctx->Removing,0);
    }
}

static VOID
p360_portcls_mark_quarantined(
    _In_ PDEVICE_OBJECT Fdo,
    _In_ BOOLEAN DetachFromPortClsFdo
    )
{
    WDFDEVICE frameworkDevice=NULL;
    P360_DEVICE_CONTEXT *ctx=NULL;

    InterlockedExchange(
        &gP360PortClsInstance.Quarantined,
        1);

    if (!DetachFromPortClsFdo)
        return;

    /*
     * REMOVE/SURPRISE_REMOVE cannot be failed. If teardown cannot prove
     * ownership gone, detach the intentionally leaked/quarantined miniport
     * from the soon-to-disappear PortCls FDO instead of retaining a stale FDO
     * pointer or freeing a WaveRT/MDL object that hardware may still own.
     */
    if (p360_portcls_take_instance(
            Fdo,
            &frameworkDevice,
            &ctx)) {
        UNREFERENCED_PARAMETER(frameworkDevice);

        if (ctx) {
            ctx->PortClsFdo=NULL;
            InterlockedExchange(&ctx->PnpQueryPending,0);
            InterlockedExchange(&ctx->Removing,1);
            p360_state_fail(
                &ctx->State,
                P360_FAIL_STREAM);
        }
    }
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

    {
        NTSTATUS powerStatus=p360_portcls_detach_power(
            Fdo,
            ctx);
        if (!NT_SUCCESS(powerStatus)) {
            (void)p360_portcls_publish_instance(
                Fdo,
                frameworkDevice,
                ctx);
            return powerStatus;
        }
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

    if (InterlockedCompareExchange(
            &gP360PortClsInstance.Quarantined,0,0)!=0) {
        return STATUS_DEVICE_HARDWARE_ERROR;
    }

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

    {
        PUNKNOWN powerUnknown=NULL;

        status=P360AdapterPowerManagement::Create(
            ctx,
            &powerUnknown);
        if (!NT_SUCCESS(status))
            goto fail;

        status=PcRegisterAdapterPowerManagement(
            powerUnknown,
            DeviceObject);
        if (!NT_SUCCESS(status)) {
            powerUnknown->Release();
            goto fail;
        }

        /*
         * Keep our own reference until final cleanup. PortCls holds its own
         * registration reference for the adapter lifetime.
         */
        ctx->AdapterPowerManager=powerUnknown;
    }

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

    if (ctx && ctx->AdapterPowerManager)
        (void)p360_portcls_detach_power(
            DeviceObject,
            ctx);

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
    case IRP_MN_QUERY_STOP_DEVICE:
    case IRP_MN_QUERY_REMOVE_DEVICE:
        {
            NTSTATUS status=
                p360_portcls_begin_pnp_query(DeviceObject);

            if (!NT_SUCCESS(status)) {
                /*
                 * QUERY_* is the legal veto point. Complete a failed query
                 * here and do not pass it farther down the stack.
                 */
                Irp->IoStatus.Status=status;
                IoCompleteRequest(Irp,IO_NO_INCREMENT);
                return status;
            }

            Irp->IoStatus.Status=STATUS_SUCCESS;
        }
        break;

    case IRP_MN_CANCEL_STOP_DEVICE:
    case IRP_MN_CANCEL_REMOVE_DEVICE:
        p360_portcls_cancel_pnp_query(DeviceObject);
        Irp->IoStatus.Status=STATUS_SUCCESS;
        break;

    case IRP_MN_STOP_DEVICE:
        {
            NTSTATUS cleanupStatus=
                p360_portcls_cleanup_instance(DeviceObject);

            /*
             * STOP itself must succeed. A preceding QUERY_STOP should have
             * vetoed live ownership; a later hardware failure is quarantined
             * and prevents a second StartDevice until reboot.
             */
            if (!NT_SUCCESS(cleanupStatus))
                p360_portcls_mark_quarantined(
                    DeviceObject,
                    FALSE);
        }
        break;

    case IRP_MN_SURPRISE_REMOVAL:
    case IRP_MN_REMOVE_DEVICE:
        {
            NTSTATUS cleanupStatus;
            P360_DEVICE_CONTEXT *ctx=
                p360_portcls_peek_context(DeviceObject);

            /*
             * Mandatory-success path: stop all new host activity even if no
             * QUERY_REMOVE preceded this IRP, then make one fail-closed
             * cleanup attempt.
             */
            if (ctx) {
                InterlockedExchange(&ctx->PnpQueryPending,0);
                InterlockedExchange(&ctx->Removing,1);
            }

            cleanupStatus=
                p360_portcls_cleanup_instance(DeviceObject);
            if (!NT_SUCCESS(cleanupStatus))
                p360_portcls_mark_quarantined(
                    DeviceObject,
                    TRUE);
        }
        break;

    default:
        break;
    }

    /*
     * PortCls owns successful and mandatory PnP IRPs. STOP,
     * SURPRISE_REMOVAL and REMOVE are never failed here.
     */
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
