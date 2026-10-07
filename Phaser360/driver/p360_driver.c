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

static BOOLEAN
p360_runtime_boot_policy_enabled(VOID)
{
    return P360_RUNTIME_BOOT_ENABLED ? TRUE : FALSE;
}

static BOOLEAN
p360_ipc_probe_policy_enabled(VOID)
{
    return P360_IPC_PROBE_ENABLED ? TRUE : FALSE;
}

static BOOLEAN
p360_tone_topology_policy_enabled(VOID)
{
    return P360_TONE_TOPOLOGY_PROOF_ENABLED ? TRUE : FALSE;
}

static NTSTATUS
p360_runtime_send_zero_error(
    _Inout_ P360_DEVICE_CONTEXT *ctx,
    _In_ const struct p360_ipc3_message *message,
    _In_ ULONG expectedReplyBytes
    )
{
    LONG firmwareError=0;
    ULONG replyBytes=0;
    NTSTATUS status;

    if (!ctx || !message || !message->bytes ||
        message->bytes>sizeof(message->data) ||
        (expectedReplyBytes!=12u && expectedReplyBytes!=20u)) {
        return STATUS_INVALID_PARAMETER;
    }

    status=p360_cs_runtime_send_ipc(
        &ctx->Runtime,
        message->data,
        message->bytes,
        100u,
        &firmwareError,
        &replyBytes);
    if (!NT_SUCCESS(status))
        return status;

    if (firmwareError!=0 || replyBytes!=expectedReplyBytes)
        return STATUS_DEVICE_CONFIGURATION_ERROR;

    return STATUS_SUCCESS;
}

static NTSTATUS
p360_runtime_prepare_tone_topology(
    _Inout_ P360_DEVICE_CONTEXT *ctx,
    _Out_ P360_FAILURE_REASON *failure
    )
{
    const struct p360_ipc3_speaker_ids ids={
        1u,   /* pipeline_id */
        100u, /* tone_id */
        101u, /* buffer_id */
        102u, /* dai_id */
        103u  /* pipe_comp_id */
    };
    const struct p360_ipc3_ssp1_profile ssp={
        P360_IPC3_DAI_FMT_I2S |
            P360_IPC3_DAI_FMT_NB_NF |
            P360_IPC3_DAI_FMT_CBC_CFC,
        P360_SPEAKER_SSP1_MCLK_ID,
        P360_SPEAKER_SSP1_MCLK_HZ,
        P360_SAMPLE_RATE,
        P360_SPEAKER_SSP1_BCLK_HZ,
        P360_SPEAKER_CHANNELS,
        3u,
        3u,
        P360_SPEAKER_DAI_VALID_BITS,
        P360_SPEAKER_DAI_SLOT_BITS,
        P360_IPC3_MCLK_CODEC_INPUT,
        0u, /* frame_pulse_width: upstream GLK default */
        0u, /* per-slot padding */
        0u, /* clks_control */
        0u, /* quirks */
        0u, /* bclk_delay */
        0u, /* group_id */
        0u  /* flags: SOF_DAI_CONFIG_FLAGS_NONE */
    };
    struct p360_ipc3_message message;
    NTSTATUS status;
    int rc;

    if (failure)
        *failure=P360_FAIL_TOPOLOGY;

    if (!ctx || !failure ||
        ctx->State.state!=P360_STATE_IPC_READY ||
        !ctx->State.ipc_ready ||
        !ctx->State.fw_ready ||
        !ctx->Runtime.Bound ||
        !InterlockedCompareExchange(&ctx->Runtime.Active,0,0) ||
        InterlockedCompareExchange(&ctx->Runtime.Fault,0,0) ||
        InterlockedCompareExchange(&ctx->Removing,0,0)!=0) {
        return STATUS_INVALID_DEVICE_STATE;
    }

#define P360_BUILD_AND_SEND(_builder,_expected)                         do {                                                                    RtlZeroMemory(&message,sizeof(message));                            rc=(_builder);                                                      if (rc!=P360_IPC3_TOPOLOGY_OK)                                         return STATUS_INVALID_PARAMETER;                                status=p360_runtime_send_zero_error(ctx,&message,(_expected));         if (!NT_SUCCESS(status))                                                return status;                                             } while (0)

    /*
     * SOF IPC3 firmware before ABI 3.19 restores static pipelines in this
     * order: components first, then routes, then scheduler PIPE_NEW and
     * PIPE_COMPLETE. Match that host behavior exactly.
     */
    P360_BUILD_AND_SEND(
        p360_ipc3_build_tone_new(
            &message,
            &ids,
            P360_SAMPLE_RATE),
        20u);

    P360_BUILD_AND_SEND(
        p360_ipc3_build_buffer_new(
            &message,
            &ids,
            768u), /* 2 x 1 ms S32 stereo periods */
        20u);

    P360_BUILD_AND_SEND(
        p360_ipc3_build_dai_new(
            &message,
            &ids,
            g_p360_phaser360_profile.ssp_amp),
        20u);

    P360_BUILD_AND_SEND(
        p360_ipc3_build_ssp1_config(
            &message,
            g_p360_phaser360_profile.ssp_amp,
            &ssp),
        12u);

    P360_BUILD_AND_SEND(
        p360_ipc3_build_connect(
            &message,
            ids.tone_id,
            ids.buffer_id),
        12u);

    P360_BUILD_AND_SEND(
        p360_ipc3_build_connect(
            &message,
            ids.buffer_id,
            ids.dai_id),
        12u);

    P360_BUILD_AND_SEND(
        p360_ipc3_build_pipe_new(
            &message,
            &ids,
            1000u,
            48u),
        20u);

    P360_BUILD_AND_SEND(
        p360_ipc3_build_pipe_complete(
            &message,
            &ids),
        12u);

#undef P360_BUILD_AND_SEND

    ctx->State.topology_ready=1;
    if (!p360_state_advance(
            &ctx->State,
            P360_STATE_TOPOLOGY_READY)) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    *failure=P360_FAIL_STREAM;

    RtlZeroMemory(&message,sizeof(message));
    rc=p360_ipc3_build_pcm_params(
        &message,
        ids.tone_id,
        P360_SAMPLE_RATE,
        P360_SPEAKER_CHANNELS);
    if (rc!=P360_IPC3_TOPOLOGY_OK)
        return STATUS_INVALID_PARAMETER;

    status=p360_runtime_send_zero_error(
        ctx,
        &message,
        20u);
    if (!NT_SUCCESS(status))
        return status;

    ctx->State.audio_core_ready=1;
    if (!p360_state_advance(
            &ctx->State,
            P360_STATE_AUDIO_CORE_READY)) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    return STATUS_SUCCESS;
}

static NTSTATUS
p360_loader_status_to_ntstatus(
    _In_ int rc)
{
    switch (rc) {
    case P360_L_IMAGE:
        return STATUS_INVALID_IMAGE_HASH;
    case P360_L_BUSY:
        return STATUS_DEVICE_BUSY;
    case P360_L_TIMEOUT:
        return STATUS_IO_TIMEOUT;
    case P360_L_CANCEL:
        return STATUS_CANCELLED;
    case P360_L_READY:
        return STATUS_DEVICE_NOT_READY;
    case P360_L_ARGUMENT:
        return STATUS_INVALID_PARAMETER;
    case P360_L_ROM_ERROR:
    case P360_L_IO:
    case P360_L_QUARANTINE:
    default:
        return STATUS_DEVICE_HARDWARE_ERROR;
    }
}

static NTSTATUS
p360_runtime_boot_start(
    _Inout_ P360_DEVICE_CONTEXT *ctx)
{
    P360_FIRMWARE_BLOB firmware;
    struct p360_loader_result result;
    P360_FAILURE_REASON failure=P360_FAIL_FIRMWARE;
    ULONGLONG epoch;
    NTSTATUS status;
    NTSTATUS cleanupStatus;
    int rc;

    if (!ctx || !ctx->Prepared || !ctx->BusOpen ||
        !ctx->BootInitialized || !ctx->RuntimeInitialized ||
        ctx->State.state!=P360_STATE_RESOURCES_OK ||
        InterlockedCompareExchange(&ctx->Removing,0,0)!=0) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    RtlZeroMemory(&firmware,sizeof(firmware));
    RtlZeroMemory(&result,sizeof(result));

    status=p360_firmware_load(&firmware);
    if (!NT_SUCCESS(status))
        return p360_fail(ctx,P360_FAIL_FIRMWARE,status);

    /*
     * Dispatcher preparation is immutable host-side validation of the same
     * pinned image used by the loader. It is performed once per runtime
     * object and does not touch DSP registers.
     */
    if (!ctx->Runtime.DispatcherPrepared) {
        status=p360_cs_runtime_prepare_dispatcher(
            &ctx->Runtime,
            firmware.Data,
            firmware.Bytes);
        if (!NT_SUCCESS(status))
            goto fail;
    }

    if (ctx->BootEpoch==MAXULONGLONG) {
        status=STATUS_INTEGER_OVERFLOW;
        goto fail;
    }

    epoch=++ctx->BootEpoch;
    if (!epoch ||
        !p360_state_advance(
            &ctx->State,
            P360_STATE_SOF_BOOTING)) {
        status=STATUS_INVALID_DEVICE_STATE;
        goto fail;
    }

    rc=p360_loader_run(
        &ctx->Loader,
        p360_cs_boot_loader_ops(),
        &ctx->Boot,
        firmware.Data,
        firmware.Bytes,
        epoch,
        &result);

    if (rc!=P360_L_OK) {
        status=p360_loader_status_to_ntstatus(rc);
        goto fail;
    }

    if (!result.ready_proved ||
        result.boot_epoch!=epoch ||
        !ctx->Boot.LiveDsp ||
        !ctx->Boot.PowerHeld ||
        ctx->Boot.Quarantined) {
        status=STATUS_DEVICE_NOT_READY;
        goto fail_live;
    }

    ctx->State.fw_ready=1;
    if (!p360_state_advance(
            &ctx->State,
            P360_STATE_SOF_READY)) {
        status=STATUS_INVALID_DEVICE_STATE;
        goto fail_live;
    }

    failure=P360_FAIL_IRQ;
    status=p360_cs_runtime_bind_live(
        &ctx->Runtime,
        epoch);
    if (!NT_SUCCESS(status))
        goto fail_live;

    /*
     * IRQ routing alone is not an IPC proof. Keep the state at SOF_READY
     * unless the explicit non-audio IPC3 transport probe is enabled and its
     * deterministic generic reply is observed.
     */
    if (p360_ipc_probe_policy_enabled()) {
        LONG firmwareError=0;

        failure=P360_FAIL_IPC;
        status=p360_cs_runtime_probe_ipc(
            &ctx->Runtime,
            &firmwareError);
        if (!NT_SUCCESS(status))
            goto fail_live;

        if (firmwareError!=P360_IPC3_PROOF_ERROR) {
            status=STATUS_DATA_ERROR;
            goto fail_live;
        }

        ctx->State.ipc_ready=1;
        if (!p360_state_advance(
                &ctx->State,
                P360_STATE_IPC_READY)) {
            status=STATUS_INVALID_DEVICE_STATE;
            goto fail_live;
        }
    }

    if (p360_tone_topology_policy_enabled()) {
        if (!p360_ipc_probe_policy_enabled() ||
            ctx->State.state!=P360_STATE_IPC_READY ||
            !ctx->State.ipc_ready) {
            failure=P360_FAIL_IPC;
            status=STATUS_INVALID_DEVICE_STATE;
            goto fail_live;
        }

        status=p360_runtime_prepare_tone_topology(
            ctx,
            &failure);
        if (!NT_SUCCESS(status))
            goto fail_live;
    }

    p360_firmware_release(&firmware);
    return STATUS_SUCCESS;

fail_live:
    /*
     * A successful loader owns a live DSP and D0 reference. Any handoff
     * failure must synchronously quiesce that DSP before D0Entry returns.
     */
    cleanupStatus=p360_cs_runtime_stop(&ctx->Runtime);
    if (!NT_SUCCESS(cleanupStatus) && ctx->Boot.LiveDsp) {
        status=cleanupStatus;
        failure=P360_FAIL_FIRMWARE;
    }

fail:
    p360_firmware_release(&firmware);
    return p360_fail(ctx,failure,status);
}

static NTSTATUS
p360_runtime_boot_stop(
    _Inout_ P360_DEVICE_CONTEXT *ctx)
{
    NTSTATUS status;

    if (!ctx || !ctx->RuntimeInitialized || !ctx->BootInitialized)
        return STATUS_INVALID_DEVICE_STATE;

    if (!ctx->Boot.LiveDsp &&
        !ctx->Runtime.Bound &&
        !InterlockedCompareExchange(&ctx->Runtime.Active,0,0) &&
        !InterlockedCompareExchange(&ctx->Runtime.DpcState,0,0) &&
        !InterlockedCompareExchange(&ctx->Runtime.EventValid,0,0)) {
        return STATUS_SUCCESS;
    }

    status=p360_cs_runtime_stop(&ctx->Runtime);

    /*
     * If shutdown reported a latched software fault but proved the DSP and
     * D0 lease are gone, allow the power transition while keeping the state
     * failed so a later D0Entry cannot silently reuse the poisoned runtime.
     */
    if (!NT_SUCCESS(status)) {
        p360_state_fail(&ctx->State,P360_FAIL_IRQ);
        return ctx->Boot.LiveDsp ? status : STATUS_SUCCESS;
    }

    if (!p360_state_runtime_reset(&ctx->State,1))
        return p360_fail(
            ctx,
            P360_FAIL_IRQ,
            STATUS_INVALID_DEVICE_STATE);

    return STATUS_SUCCESS;
}

NTSTATUS
DriverEntry(
    _In_ PDRIVER_OBJECT DriverObject,
    _In_ PUNICODE_STRING RegistryPath)
{
#if P360_PORTCLS_SHELL_ENABLED
    return p360_portcls_driver_initialize(
        DriverObject,
        RegistryPath);
#else
    WDF_DRIVER_CONFIG config;

    WDF_DRIVER_CONFIG_INIT(&config,P360EvtDeviceAdd);

    return WdfDriverCreate(
        DriverObject,
        RegistryPath,
        WDF_NO_OBJECT_ATTRIBUTES,
        &config,
        WDF_NO_HANDLE);
#endif
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
p360_host_prepare(
    _Inout_ P360_DEVICE_CONTEXT *ctx,
    _In_ WDFDEVICE Device)
{
    NTSTATUS status;

    if (!ctx || !Device || ctx->Prepared || ctx->BusOpen)
        return STATUS_INVALID_DEVICE_STATE;

    p360_state_init(&ctx->State);
    ctx->State.speaker_policy_enabled=
        P360_ENABLE_INTERNAL_SPEAKER ? 1u : 0u;
    RtlZeroMemory(&ctx->Nhlt,sizeof(ctx->Nhlt));
    RtlZeroMemory(&ctx->Identity,sizeof(ctx->Identity));
    ctx->BootInitialized=FALSE;
    ctx->RuntimeInitialized=FALSE;
    ctx->CsAudioInitialized=FALSE;
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

    status=p360_csaudio_open(&ctx->CsAudio);
    if (!NT_SUCCESS(status))
        goto csaudio_init_fail;

    ctx->CsAudioInitialized=TRUE;
    ctx->Prepared=TRUE;
    return STATUS_SUCCESS;

csaudio_init_fail:
    p360_state_fail(&ctx->State,P360_FAIL_RESOURCES);
    if (ctx->RuntimeInitialized) {
        NTSTATUS destroyStatus=
            p360_cs_runtime_destroy(&ctx->Runtime);
        if (!NT_SUCCESS(destroyStatus))
            status=destroyStatus;
        ctx->RuntimeInitialized=FALSE;
    }

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
P360EvtPrepareHardware(
    _In_ WDFDEVICE Device,
    _In_ WDFCMRESLIST ResourcesRaw,
    _In_ WDFCMRESLIST ResourcesTranslated)
{
    UNREFERENCED_PARAMETER(ResourcesRaw);
    UNREFERENCED_PARAMETER(ResourcesTranslated);

    return p360_host_prepare(
        P360GetContext(Device),
        Device);
}

NTSTATUS
p360_host_release(
    _Inout_ P360_DEVICE_CONTEXT *ctx)
{
    NTSTATUS status=STATUS_SUCCESS;
    NTSTATUS stopStatus=STATUS_SUCCESS;

    if (!ctx)
        return STATUS_INVALID_DEVICE_STATE;

    InterlockedExchange(&ctx->Removing,1);

    /*
     * Speaker mute/endpoint callback teardown comes before DSP teardown.
     * The MAX98357A driver remains the sole GPIO owner; this host only emits
     * CSAudio endpoint requests.
     */
    if (ctx->CsAudioInitialized) {
        p360_csaudio_close(&ctx->CsAudio);
        ctx->CsAudioInitialized=FALSE;
    }

    if (ctx->RuntimeInitialized &&
        (ctx->Runtime.Bound ||
         InterlockedCompareExchange(&ctx->Runtime.Active,0,0) ||
         InterlockedCompareExchange(&ctx->Runtime.DpcState,0,0) ||
         InterlockedCompareExchange(&ctx->Runtime.EventValid,0,0) ||
         (ctx->BootInitialized && ctx->Boot.LiveDsp))) {
        stopStatus=p360_cs_runtime_stop(&ctx->Runtime);
        if (!NT_SUCCESS(stopStatus)) {
            p360_state_fail(&ctx->State,P360_FAIL_IRQ);

            /*
             * A latched runtime fault may be reported after a proved shutdown.
             * Only refuse teardown when the DSP is still live; otherwise let
             * destroy/retire provide the remaining quiescence proofs.
             */
            if (ctx->BootInitialized && ctx->Boot.LiveDsp)
                return stopStatus;
        }
    }

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
P360EvtReleaseHardware(
    _In_ WDFDEVICE Device,
    _In_ WDFCMRESLIST ResourcesTranslated)
{
    UNREFERENCED_PARAMETER(ResourcesTranslated);

    return p360_host_release(
        P360GetContext(Device));
}

NTSTATUS
p360_host_d0_entry(
    _Inout_ P360_DEVICE_CONTEXT *ctx)
{
    if (!ctx || !ctx->Prepared || !ctx->BusOpen ||
        ctx->State.state!=P360_STATE_RESOURCES_OK ||
        InterlockedCompareExchange(&ctx->Removing,0,0)!=0) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    if (p360_runtime_boot_policy_enabled())
        return p360_runtime_boot_start(ctx);

    return STATUS_SUCCESS;
}

NTSTATUS
P360EvtD0Entry(
    _In_ WDFDEVICE Device,
    _In_ WDF_POWER_DEVICE_STATE PreviousState)
{
    UNREFERENCED_PARAMETER(PreviousState);

    return p360_host_d0_entry(
        P360GetContext(Device));
}

NTSTATUS
p360_host_d0_exit(
    _Inout_ P360_DEVICE_CONTEXT *ctx)
{
    if (!ctx)
        return STATUS_INVALID_DEVICE_STATE;

    /*
     * Boot remains disabled by policy in the shipping test build, but the
     * complete shutdown path is compiled and audited now. Do not use the boot
     * adapter's cancellation latch for ordinary D0 transitions; it is reserved
     * for removal/retirement.
     */
    if (p360_runtime_boot_policy_enabled())
        return p360_runtime_boot_stop(ctx);

    return STATUS_SUCCESS;
}

NTSTATUS
P360EvtD0Exit(
    _In_ WDFDEVICE Device,
    _In_ WDF_POWER_DEVICE_STATE TargetState)
{
    UNREFERENCED_PARAMETER(TargetState);

    return p360_host_d0_exit(
        P360GetContext(Device));
}
