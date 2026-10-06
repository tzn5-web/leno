#include "../include/p360_cs_runtime.h"

typedef struct P360_RUNTIME_DPC_LINK {
    P360_CS_RUNTIME *Owner;
} P360_RUNTIME_DPC_LINK;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(
    P360_RUNTIME_DPC_LINK,
    P360GetRuntimeDpcLink)

EVT_WDF_DPC P360RuntimeDpc;

static BOOLEAN
p360_rt_callback_acquire(
    _Inout_ P360_CS_RUNTIME *rt
    )
{
    LONG oldValue;
    LONG newValue;

    if (!rt)
        return FALSE;

    for (;;) {
        oldValue = InterlockedCompareExchange(
            &rt->CallbackState,0,0);

        if (((ULONG)oldValue & P360_RUNTIME_CALLBACK_CLOSING) != 0)
            return FALSE;

        if (((ULONG)oldValue & P360_RUNTIME_CALLBACK_COUNT) ==
            P360_RUNTIME_CALLBACK_COUNT)
            return FALSE;

        newValue = oldValue + 1;

        if (InterlockedCompareExchange(
                &rt->CallbackState,
                newValue,
                oldValue) == oldValue) {
            return TRUE;
        }
    }
}

static VOID
p360_rt_callback_release(
    _Inout_ P360_CS_RUNTIME *rt
    )
{
    if (rt)
        (void)InterlockedDecrement(&rt->CallbackState);
}

static VOID
p360_rt_callback_close(
    _Inout_ P360_CS_RUNTIME *rt
    )
{
    LONG oldValue;
    LONG newValue;

    if (!rt)
        return;

    for (;;) {
        oldValue = InterlockedCompareExchange(
            &rt->CallbackState,0,0);

        newValue = (LONG)(
            (ULONG)oldValue |
            P360_RUNTIME_CALLBACK_CLOSING);

        if (InterlockedCompareExchange(
                &rt->CallbackState,
                newValue,
                oldValue) == oldValue) {
            return;
        }
    }
}

static NTSTATUS
p360_rt_wait_callbacks_closed(
    _Inout_ P360_CS_RUNTIME *rt
    )
{
    ULONG i;
    LARGE_INTEGER delay;

    if (!rt || KeGetCurrentIrql() != PASSIVE_LEVEL)
        return STATUS_INVALID_DEVICE_STATE;

    delay.QuadPart = -10 * 1000; /* 1 ms */

    for (i = 0; i < 1000u; ++i) {
        LONG state = InterlockedCompareExchange(
            &rt->CallbackState,0,0);

        if (((ULONG)state & P360_RUNTIME_CALLBACK_COUNT) == 0)
            return STATUS_SUCCESS;

        (void)KeDelayExecutionThread(
            KernelMode,
            FALSE,
            &delay);
    }

    return STATUS_IO_TIMEOUT;
}

static NTSTATUS
p360_rt_read32(
    _In_ P360_CS_RUNTIME *rt,
    _In_ ULONG offset,
    _Out_ ULONG *value
    )
{
    if (!rt || !value || !rt->Bus ||
        !rt->Bus->resources_valid ||
        !rt->Bus->dsp.Base.baseptr ||
        (offset & 3u) ||
        offset > rt->Bus->dsp.Len - sizeof(ULONG)) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    *value = READ_REGISTER_ULONG(
        (volatile ULONG *)(
            rt->Bus->dsp.Base.baseptr + offset));

    return *value == MAXULONG ?
        STATUS_DEVICE_HARDWARE_ERROR :
        STATUS_SUCCESS;
}

static NTSTATUS
p360_rt_write_control(
    _In_ P360_CS_RUNTIME *rt,
    _In_ ULONG offset,
    _In_ ULONG value
    )
{
    if (!rt || !rt->Bus ||
        !rt->Bus->resources_valid ||
        !rt->Bus->dsp.Base.baseptr ||
        (offset != P360_DSP_ADSPIC &&
         offset != P360_DSP_HIPCCTL)) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    WRITE_REGISTER_ULONG(
        (volatile ULONG *)(
            rt->Bus->dsp.Base.baseptr + offset),
        value);
    KeMemoryBarrier();

    return STATUS_SUCCESS;
}

static NTSTATUS
p360_rt_mask(
    _Inout_ P360_CS_RUNTIME *rt
    )
{
    ULONG adspicBefore;
    ULONG adspicAfter;
    ULONG hipcctlBefore;
    ULONG hipcctlAfter;
    NTSTATUS status;

    if (!rt)
        return STATUS_INVALID_PARAMETER;

    status = p360_rt_read32(rt,P360_DSP_ADSPIC,&adspicBefore);
    if (!NT_SUCCESS(status))
        goto fail;

    status = p360_rt_write_control(
        rt,
        P360_DSP_ADSPIC,
        adspicBefore & ~P360_ADSPIC_IPC);
    if (!NT_SUCCESS(status))
        goto fail;

    status = p360_rt_read32(rt,P360_DSP_ADSPIC,&adspicAfter);
    if (!NT_SUCCESS(status) ||
        (adspicAfter & P360_ADSPIC_IPC) ||
        (adspicAfter & ~P360_ADSPIC_IPC) !=
            (adspicBefore & ~P360_ADSPIC_IPC)) {
        status = STATUS_DEVICE_HARDWARE_ERROR;
        goto fail;
    }

    status = p360_rt_read32(rt,P360_DSP_HIPCCTL,&hipcctlBefore);
    if (!NT_SUCCESS(status))
        goto fail;

    status = p360_rt_write_control(
        rt,
        P360_DSP_HIPCCTL,
        hipcctlBefore &
        ~(P360_HIPCCTL_BUSY | P360_HIPCCTL_DONE));
    if (!NT_SUCCESS(status))
        goto fail;

    status = p360_rt_read32(rt,P360_DSP_HIPCCTL,&hipcctlAfter);
    if (!NT_SUCCESS(status) ||
        (hipcctlAfter &
         (P360_HIPCCTL_BUSY | P360_HIPCCTL_DONE)) ||
        (hipcctlAfter &
         ~(P360_HIPCCTL_BUSY | P360_HIPCCTL_DONE)) !=
        (hipcctlBefore &
         ~(P360_HIPCCTL_BUSY | P360_HIPCCTL_DONE))) {
        status = STATUS_DEVICE_HARDWARE_ERROR;
        goto fail;
    }

    rt->MaskConfirmed = TRUE;
    return STATUS_SUCCESS;

fail:
    rt->MaskConfirmed = FALSE;
    InterlockedExchange(&rt->Fault,1);
    return status;
}

static int
p360_rt_arm_permit(void *context)
{
    P360_CS_RUNTIME *rt = context;

    return rt &&
        rt->Bus &&
        rt->Bus->resources_valid &&
        rt->MaskConfirmed &&
        !InterlockedCompareExchange(&rt->Stopping,0,0) &&
        !InterlockedCompareExchange(&rt->Fault,0,0);
}

static int
p360_rt_arm_read32(
    void *context,
    uint32_t offset,
    uint32_t *value
    )
{
    ULONG v;
    NTSTATUS status;

    if (!value)
        return -1;

    status = p360_rt_read32(
        (P360_CS_RUNTIME *)context,
        (ULONG)offset,
        &v);

    if (!NT_SUCCESS(status))
        return -1;

    *value = (uint32_t)v;
    return 0;
}

static int
p360_rt_arm_write32(
    void *context,
    uint32_t offset,
    uint32_t value
    )
{
    P360_CS_RUNTIME *rt = context;

    if (offset != P360_DSP_ADSPIC &&
        offset != P360_DSP_HIPCCTL)
        return -1;

    return NT_SUCCESS(p360_rt_write_control(
        rt,
        (ULONG)offset,
        (ULONG)value)) ? 0 : -1;
}

static void
p360_rt_arm_barrier(void *context)
{
    UNREFERENCED_PARAMETER(context);
    KeMemoryBarrier();
}

static const struct p360_irq_arm_adapter_io g_p360_rt_arm_ops = {
    p360_rt_arm_permit,
    p360_rt_arm_read32,
    p360_rt_arm_write32,
    p360_rt_arm_barrier
};

static NTSTATUS
p360_rt_arm(
    _Inout_ P360_CS_RUNTIME *rt
    )
{
    struct p360_irq_arm_adapter_result result;
    int rc;

    if (!rt || !rt->Bound || !rt->Epoch)
        return STATUS_INVALID_DEVICE_STATE;

    if (InterlockedCompareExchange(
            &rt->ArmInProgress,1,0) != 0)
        return STATUS_DEVICE_BUSY;

    rc = p360_irq_arm_adapter_run(
        &g_p360_rt_arm_ops,
        rt,
        rt->Epoch,
        rt->Irq.accepting,
        rt->Irq.count,
        rt->Irq.poisoned,
        (int)InterlockedCompareExchange(&rt->Fault,0,0),
        rt->MaskConfirmed,
        &result);

    InterlockedExchange(&rt->ArmInProgress,0);

    if (rc != 0) {
        if (result.writes_started || result.poison_required) {
            p360_irq_poison(&rt->Irq);
            InterlockedExchange(&rt->Fault,1);
        }

        rt->MaskConfirmed =
            result.rollback_proved ? TRUE : rt->MaskConfirmed;

        if (!rt->MaskConfirmed)
            (void)p360_rt_mask(rt);

        return STATUS_DEVICE_NOT_READY;
    }

    rt->MaskConfirmed = FALSE;
    return STATUS_SUCCESS;
}

static NTSTATUS
p360_rt_ack(
    _Inout_ P360_CS_RUNTIME *rt,
    _In_ ULONG offset,
    _In_ ULONG bit,
    _In_ ULONG captured
    )
{
    ULONG value;
    NTSTATUS status;

    if (!rt ||
        (offset != P360_DSP_HIPCIE &&
         offset != P360_DSP_HIPCT))
        return STATUS_INVALID_PARAMETER;

    status = p360_rt_read32(rt,offset,&value);
    if (!NT_SUCCESS(status) || value != captured)
        return STATUS_DEVICE_HARDWARE_ERROR;

    WRITE_REGISTER_ULONG(
        (volatile ULONG *)(
            rt->Bus->dsp.Base.baseptr + offset),
        value | bit);
    KeMemoryBarrier();

    status = p360_rt_read32(rt,offset,&value);
    if (!NT_SUCCESS(status) || (value & bit))
        return STATUS_DEVICE_HARDWARE_ERROR;

    return STATUS_SUCCESS;
}

static int
p360_rt_copy_box(
    void *context,
    uint32_t offset,
    uint8_t *out,
    uint32_t bytes
    )
{
    P360_CS_RUNTIME *rt = context;
    ULONG i;
    ULONG value;

    if (!rt || !out ||
        (offset & 3u) ||
        (bytes & 3u) ||
        offset > rt->Bus->dsp.Len ||
        bytes > rt->Bus->dsp.Len - offset)
        return -1;

    KeMemoryBarrier();

    for (i = 0; i < bytes; i += sizeof(ULONG)) {
        if (!NT_SUCCESS(p360_rt_read32(
                rt,
                (ULONG)offset + i,
                &value)))
            return -1;

        out[i]     = (UCHAR)value;
        out[i + 1] = (UCHAR)(value >> 8);
        out[i + 2] = (UCHAR)(value >> 16);
        out[i + 3] = (UCHAR)(value >> 24);
    }

    KeMemoryBarrier();
    return 0;
}

static uint64_t
p360_rt_now(void *context)
{
    UNREFERENCED_PARAMETER(context);
    return KeQueryInterruptTime();
}

static int
p360_rt_finish(
    void *context,
    const struct p360_irq_event *event
    )
{
    P360_CS_RUNTIME *rt = context;
    ULONG cie;
    ULONG ct;
    ULONG cte;

    if (!rt || !event ||
        !rt->Bound ||
        !rt->MaskConfirmed ||
        event->epoch != rt->Epoch ||
        rt->Irq.poisoned ||
        InterlockedCompareExchange(&rt->Fault,0,0))
        goto fail;

    if (!NT_SUCCESS(p360_rt_read32(rt,P360_DSP_HIPCIE,&cie)) ||
        !NT_SUCCESS(p360_rt_read32(rt,P360_DSP_HIPCT,&ct)) ||
        !NT_SUCCESS(p360_rt_read32(rt,P360_DSP_HIPCTE,&cte)) ||
        cie != event->hipcie ||
        ct != event->hipct ||
        cte != event->hipcte)
        goto fail;

    if ((event->causes & 1u) &&
        !NT_SUCCESS(p360_rt_ack(
            rt,
            P360_DSP_HIPCIE,
            P360_HIPCIE_DONE,
            event->hipcie)))
        goto fail;

    if ((event->causes & 2u) &&
        !NT_SUCCESS(p360_rt_ack(
            rt,
            P360_DSP_HIPCT,
            P360_HIPCT_BUSY,
            event->hipct)))
        goto fail;

    if (InterlockedCompareExchange(&rt->Stopping,0,0)) {
        return NT_SUCCESS(p360_rt_mask(rt)) ? 0 : -1;
    }

    return NT_SUCCESS(p360_rt_arm(rt)) ? 0 : -1;

fail:
    p360_irq_poison(&rt->Irq);
    InterlockedExchange(&rt->Fault,1);
    (void)p360_rt_mask(rt);
    return -1;
}

static const struct p360_dispatch_io g_p360_rt_dispatch_io = {
    p360_rt_copy_box,
    p360_rt_finish,
    p360_rt_now
};

static VOID
p360_rt_process_dpc(
    _Inout_ P360_CS_RUNTIME *rt
    )
{
    for (;;) {
        if (InterlockedCompareExchange(
                &rt->EventValid,0,0) != 0) {
            struct p360_irq_event event;
            int rc;

            KeMemoryBarrier();
            event = rt->PendingEvent;
            InterlockedExchange(&rt->EventValid,0);

            WdfSpinLockAcquire(rt->DispatchLock);
            rc = p360_dispatch_process(
                &rt->Dispatch,
                &event,
                &g_p360_rt_dispatch_io,
                rt);
            WdfSpinLockRelease(rt->DispatchLock);

            if (rc != 0) {
                InterlockedExchange(&rt->Fault,1);
                (void)p360_rt_mask(rt);
            }

            continue;
        }

        InterlockedExchange(&rt->DpcState,0);
        KeMemoryBarrier();

        if (InterlockedCompareExchange(
                &rt->EventValid,0,0) != 0 &&
            InterlockedCompareExchange(
                &rt->DpcState,1,0) == 0) {
            continue;
        }

        break;
    }
}

VOID
P360RuntimeDpc(
    WDFDPC Dpc
    )
{
    P360_RUNTIME_DPC_LINK *link =
        P360GetRuntimeDpcLink(Dpc);

    if (!link || !link->Owner)
        return;

    p360_rt_process_dpc(link->Owner);
}

BOOL
p360_cs_runtime_interrupt(
    PVOID Context
    )
{
    P360_CS_RUNTIME *rt = Context;
    ULONG adspis;
    ULONG hipci;
    ULONG hipcie;
    ULONG hipct;
    ULONG hipcte;
    struct p360_irq_event event;
    int captured;
    int taken;
    BOOL handled = FALSE;

    if (!p360_rt_callback_acquire(rt))
        return FALSE;

    if (!InterlockedCompareExchange(&rt->Active,0,0) ||
        InterlockedCompareExchange(&rt->Stopping,0,0) ||
        InterlockedCompareExchange(&rt->Fault,0,0)) {
        goto done;
    }

    if (!NT_SUCCESS(p360_rt_read32(rt,P360_DSP_ADSPIS,&adspis))) {
        InterlockedExchange(&rt->Fault,1);
        (void)p360_rt_mask(rt);
        goto done;
    }

    if (!(adspis & P360_ADSPIS_IPC))
        goto done;

    handled = TRUE;

    if (InterlockedCompareExchange(&rt->ArmInProgress,0,0) ||
        InterlockedCompareExchange(&rt->EventValid,0,0)) {
        InterlockedExchange(&rt->Fault,1);
        (void)p360_rt_mask(rt);
        goto done;
    }

    if (!NT_SUCCESS(p360_rt_read32(rt,P360_DSP_HIPCI,&hipci)) ||
        !NT_SUCCESS(p360_rt_read32(rt,P360_DSP_HIPCIE,&hipcie)) ||
        !NT_SUCCESS(p360_rt_read32(rt,P360_DSP_HIPCT,&hipct)) ||
        !NT_SUCCESS(p360_rt_read32(rt,P360_DSP_HIPCTE,&hipcte)) ||
        !NT_SUCCESS(p360_rt_mask(rt))) {
        InterlockedExchange(&rt->Fault,1);
        goto done;
    }

    captured = p360_irq_capture(
        &rt->Irq,
        adspis,
        hipci,
        hipcie,
        hipct,
        hipcte);

    if (captured != 1) {
        if (captured < 0)
            InterlockedExchange(&rt->Fault,1);
        goto done;
    }

    taken = p360_irq_take(
        &rt->Irq,
        rt->Epoch,
        &event);

    if (taken != 1) {
        p360_irq_poison(&rt->Irq);
        InterlockedExchange(&rt->Fault,1);
        goto done;
    }

    rt->PendingEvent = event;
    KeMemoryBarrier();
    InterlockedExchange(&rt->EventValid,1);

    if (InterlockedCompareExchange(&rt->DpcState,1,0) == 0) {
        if (!WdfDpcEnqueue(rt->Dpc)) {
            InterlockedExchange(&rt->DpcState,0);
            InterlockedExchange(&rt->Fault,1);
            (void)p360_rt_mask(rt);
        }
    }

done:
    p360_rt_callback_release(rt);
    return handled;
}

NTSTATUS
p360_cs_runtime_create(
    P360_CS_RUNTIME *rt,
    WDFDEVICE Device,
    P360_CS_BUS *Bus,
    P360_CS_BOOT_ADAPTER *Boot
    )
{
    WDF_DPC_CONFIG dpcConfig;
    WDF_OBJECT_ATTRIBUTES attributes;
    NTSTATUS status;

    if (!rt || !Device || !Bus || !Boot ||
        !Bus->resources_valid ||
        KeGetCurrentIrql() != PASSIVE_LEVEL)
        return STATUS_INVALID_PARAMETER;

    RtlZeroMemory(rt,sizeof(*rt));
    rt->Bus = Bus;
    rt->Boot = Boot;

    p360_irq_init(&rt->Irq);

    WDF_OBJECT_ATTRIBUTES_INIT(&attributes);
    attributes.ParentObject = Device;

    status = WdfSpinLockCreate(
        &attributes,
        &rt->DispatchLock);
    if (!NT_SUCCESS(status))
        return status;

    WDF_DPC_CONFIG_INIT(
        &dpcConfig,
        P360RuntimeDpc);
    dpcConfig.AutomaticSerialization = FALSE;

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(
        &attributes,
        P360_RUNTIME_DPC_LINK);
    attributes.ParentObject = Device;
    attributes.ExecutionLevel = WdfExecutionLevelDispatch;
    attributes.SynchronizationScope = WdfSynchronizationScopeNone;

    status = WdfDpcCreate(
        &dpcConfig,
        &attributes,
        &rt->Dpc);
    if (!NT_SUCCESS(status)) {
        WdfObjectDelete(rt->DispatchLock);
        RtlZeroMemory(rt,sizeof(*rt));
        return status;
    }

    P360GetRuntimeDpcLink(rt->Dpc)->Owner = rt;
    rt->Created = TRUE;
    return STATUS_SUCCESS;
}

NTSTATUS
p360_cs_runtime_prepare_dispatcher(
    P360_CS_RUNTIME *rt,
    const UCHAR *Firmware,
    SIZE_T FirmwareBytes
    )
{
    if (!rt || !rt->Created ||
        rt->DispatcherPrepared ||
        rt->Bound ||
        !Firmware ||
        KeGetCurrentIrql() != PASSIVE_LEVEL)
        return STATUS_INVALID_DEVICE_STATE;

    if (p360_dispatch_prepare(
            &rt->Dispatch,
            Firmware,
            FirmwareBytes,
            rt->Bus->dsp.Len) != 0) {
        return STATUS_INVALID_IMAGE_FORMAT;
    }

    rt->DispatcherPrepared = TRUE;
    return STATUS_SUCCESS;
}

NTSTATUS
p360_cs_runtime_bind_live(
    P360_CS_RUNTIME *rt,
    ULONGLONG BootEpoch
    )
{
    NTSTATUS status;

    if (!rt || !rt->Created ||
        !rt->DispatcherPrepared ||
        rt->Bound ||
        !BootEpoch ||
        !rt->Boot ||
        !rt->Boot->LiveDsp ||
        !rt->Boot->PowerHeld ||
        rt->Boot->Quarantined ||
        KeGetCurrentIrql() != PASSIVE_LEVEL) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    status = p360_rt_mask(rt);
    if (!NT_SUCCESS(status))
        return status;

    WdfSpinLockAcquire(rt->DispatchLock);

    if (p360_dispatch_bind(
            &rt->Dispatch,
            BootEpoch) != 0 ||
        p360_irq_bind_boot(
            &rt->Irq,
            BootEpoch) != 0) {
        WdfSpinLockRelease(rt->DispatchLock);
        InterlockedExchange(&rt->Fault,1);
        return STATUS_DEVICE_NOT_READY;
    }

    WdfSpinLockRelease(rt->DispatchLock);

    rt->Epoch = BootEpoch;
    rt->Bound = TRUE;
    InterlockedExchange(&rt->Stopping,0);
    InterlockedExchange(&rt->Fault,0);
    InterlockedExchange(&rt->Active,1);

    if (!rt->CallbackRegistered) {
        status = rt->Bus->iface.RegisterInterrupt(
            rt->Bus->iface.Context,
            p360_cs_runtime_interrupt,
            rt);

        if (!NT_SUCCESS(status)) {
            InterlockedExchange(&rt->Active,0);
            InterlockedExchange(&rt->Fault,1);
            return status;
        }

        rt->CallbackRegistered = TRUE;
    }

    status = p360_rt_arm(rt);
    if (!NT_SUCCESS(status)) {
        InterlockedExchange(&rt->Active,0);
        (void)p360_rt_mask(rt);
        return status;
    }

    return STATUS_SUCCESS;
}

static NTSTATUS
p360_rt_wait_dpc_idle(
    _Inout_ P360_CS_RUNTIME *rt
    )
{
    ULONG i;
    LARGE_INTEGER delay;

    if (!rt || KeGetCurrentIrql() != PASSIVE_LEVEL)
        return STATUS_INVALID_DEVICE_STATE;

    delay.QuadPart = -10 * 1000; /* 1 ms */

    for (i = 0; i < 1000u; ++i) {
        if (!InterlockedCompareExchange(&rt->DpcState,0,0) &&
            !InterlockedCompareExchange(&rt->EventValid,0,0))
            return STATUS_SUCCESS;

        (void)KeDelayExecutionThread(
            KernelMode,
            FALSE,
            &delay);
    }

    return STATUS_IO_TIMEOUT;
}

NTSTATUS
p360_cs_runtime_stop(
    P360_CS_RUNTIME *rt
    )
{
    NTSTATUS status;
    NTSTATUS shutdownStatus;

    if (!rt || !rt->Created ||
        KeGetCurrentIrql() != PASSIVE_LEVEL)
        return STATUS_INVALID_DEVICE_STATE;

    InterlockedExchange(&rt->Stopping,1);
    InterlockedExchange(&rt->Active,0);

    status = p360_rt_mask(rt);
    if (!NT_SUCCESS(status))
        return status;

    status = p360_rt_wait_dpc_idle(rt);
    if (!NT_SUCCESS(status)) {
        InterlockedExchange(&rt->Fault,1);
        return status;
    }

    WdfSpinLockAcquire(rt->DispatchLock);
    p360_irq_close(&rt->Irq);
    p360_dispatch_stop(&rt->Dispatch);
    WdfSpinLockRelease(rt->DispatchLock);

    rt->Bound = FALSE;
    rt->Epoch = 0;

    if (rt->Boot && rt->Boot->LiveDsp) {
        shutdownStatus =
            p360_cs_boot_adapter_shutdown_live(rt->Boot);

        if (!NT_SUCCESS(shutdownStatus)) {
            InterlockedExchange(&rt->Fault,1);
            return shutdownStatus;
        }

        shutdownStatus =
            p360_cs_boot_adapter_rearm(rt->Boot);

        if (!NT_SUCCESS(shutdownStatus)) {
            InterlockedExchange(&rt->Fault,1);
            return shutdownStatus;
        }
    }

    InterlockedExchange(&rt->Stopping,0);

    return InterlockedCompareExchange(&rt->Fault,0,0) ?
        STATUS_DEVICE_HARDWARE_ERROR :
        STATUS_SUCCESS;
}

NTSTATUS
p360_cs_runtime_destroy(
    P360_CS_RUNTIME *rt
    )
{
    NTSTATUS status = STATUS_SUCCESS;

    if (!rt || !rt->Created ||
        KeGetCurrentIrql() != PASSIVE_LEVEL)
        return STATUS_INVALID_DEVICE_STATE;

    if (InterlockedCompareExchange(&rt->Active,0,0) ||
        InterlockedCompareExchange(&rt->DpcState,0,0) ||
        InterlockedCompareExchange(&rt->EventValid,0,0) ||
        (rt->Boot && rt->Boot->LiveDsp)) {
        return STATUS_DEVICE_BUSY;
    }

    p360_rt_callback_close(rt);

    if (rt->CallbackRegistered) {
        status = rt->Bus->iface.UnregisterInterrupt(
            rt->Bus->iface.Context);

        if (!NT_SUCCESS(status))
            return status;

        rt->CallbackRegistered = FALSE;
    }

    status = p360_rt_wait_callbacks_closed(rt);
    if (!NT_SUCCESS(status))
        return status;

    rt->Created = FALSE;
    return STATUS_SUCCESS;
}
