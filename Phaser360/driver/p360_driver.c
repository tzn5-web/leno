#include "p360_driver.h"

static ULONG
p360_build_flags(VOID)
{
    ULONG flags=0;

    if (P360_RUNTIME_BOOT_ENABLED)
        flags|=P360_TELEM_FLAG_RUNTIME_BOOT;
    if (P360_IPC_PROBE_ENABLED)
        flags|=P360_TELEM_FLAG_IPC_PROBE;
    if (P360_HOST_PLAYBACK_ENABLED)
        flags|=P360_TELEM_FLAG_HOST_TOPOLOGY;
    else if (P360_TONE_TOPOLOGY_PROOF_ENABLED)
        flags|=P360_TELEM_FLAG_TONE_TOPOLOGY;
    if (P360_ENABLE_INTERNAL_SPEAKER)
        flags|=P360_TELEM_FLAG_INTERNAL_SPEAKER;
    if (P360_BOUNDED_TONE_TEST_ENABLED)
        flags|=P360_TELEM_FLAG_BOUNDED_TONE;
    if (P360_SPEAKER_ENDPOINT_ENABLED)
        flags|=P360_TELEM_FLAG_SPEAKER_ENDPOINT;

    return flags;
}

static NTSTATUS
p360_fail(
    _Inout_ P360_DEVICE_CONTEXT *ctx,
    _In_ P360_FAILURE_REASON reason,
    _In_ NTSTATUS status)
{
    if (ctx)
        p360_state_fail(&ctx->State,reason);

    (void)p360_telemetry_result(
        (ULONG)reason,
        status);
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
p360_host_playback_policy_enabled(VOID)
{
    return P360_HOST_PLAYBACK_ENABLED ? TRUE : FALSE;
}

static BOOLEAN
p360_tone_topology_policy_enabled(VOID)
{
    return P360_TONE_TOPOLOGY_PROOF_ENABLED ? TRUE : FALSE;
}

static BOOLEAN
p360_bounded_tone_policy_enabled(VOID)
{
    return P360_BOUNDED_TONE_TEST_ENABLED ? TRUE : FALSE;
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
        (expectedReplyBytes!=12u && expectedReplyBytes!=20u &&
         expectedReplyBytes!=P360_IPC3_TONE_CONTROL_BYTES)) {
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
p360_runtime_prepare_host_topology(
    _Inout_ P360_DEVICE_CONTEXT *ctx,
    _Out_ P360_FAILURE_REASON *failure
    )
{
    const struct p360_ipc3_playback_ids ids={
        P360_IPC3_SPEAKER_PIPELINE_ID,
        P360_IPC3_SPEAKER_HOST_ID,
        P360_IPC3_SPEAKER_BUFFER_ID,
        P360_IPC3_SPEAKER_DAI_ID,
        P360_IPC3_SPEAKER_SCHED_ID
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
        0u,
        0u,
        0u,
        0u,
        0u,
        0u,
        0u
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

#define P360_HOST_BUILD_AND_SEND(_builder,_expected)                    \
    do {                                                                \
        RtlZeroMemory(&message,sizeof(message));                         \
        rc=(_builder);                                                   \
        if (rc!=P360_IPC3_TOPOLOGY_OK)                                  \
            return STATUS_INVALID_PARAMETER;                            \
        status=p360_runtime_send_zero_error(ctx,&message,(_expected));   \
        if (!NT_SUCCESS(status))                                        \
            return status;                                              \
    } while (0)

    /*
     * Linux GLK playback model, reduced to the one physical speaker route:
     * HOST -> buffer -> SSP1 DAI. HOST owns the DMA scheduling domain.
     * PCM_PARAMS is intentionally deferred until WaveRT supplies the actual
     * host MDL, compressed SOF page table and CoolStar render stream tag.
     */
    P360_HOST_BUILD_AND_SEND(
        p360_ipc3_build_host_new(&message,&ids),
        20u);

    P360_HOST_BUILD_AND_SEND(
        p360_ipc3_build_playback_buffer_new(
            &message,
            &ids,
            384u), /* two 1 ms stereo S16 periods */
        20u);

    P360_HOST_BUILD_AND_SEND(
        p360_ipc3_build_playback_dai_new(
            &message,
            &ids,
            g_p360_phaser360_profile.ssp_amp),
        20u);

    P360_HOST_BUILD_AND_SEND(
        p360_ipc3_build_ssp1_config(
            &message,
            g_p360_phaser360_profile.ssp_amp,
            &ssp),
        12u);

    P360_HOST_BUILD_AND_SEND(
        p360_ipc3_build_connect(
            &message,
            ids.host_id,
            ids.buffer_id),
        12u);

    P360_HOST_BUILD_AND_SEND(
        p360_ipc3_build_connect(
            &message,
            ids.buffer_id,
            ids.dai_id),
        12u);

    P360_HOST_BUILD_AND_SEND(
        p360_ipc3_build_playback_pipe_new(
            &message,
            &ids,
            1000u,
            48u),
        20u);

    P360_HOST_BUILD_AND_SEND(
        p360_ipc3_build_playback_pipe_complete(
            &message,
            &ids),
        12u);

#undef P360_HOST_BUILD_AND_SEND

    ctx->State.topology_ready=1;
    if (!p360_state_advance(
            &ctx->State,
            P360_STATE_TOPOLOGY_READY)) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    status=p360_telemetry_stage(
        P360_TELEM_STAGE_TOPOLOGY_READY);
    if (!NT_SUCCESS(status))
        return status;

    ctx->State.audio_core_ready=1;
    if (!p360_state_advance(
            &ctx->State,
            P360_STATE_AUDIO_CORE_READY)) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    return p360_telemetry_stage(
        P360_TELEM_STAGE_AUDIO_CORE);
}

static NTSTATUS
p360_runtime_prepare_tone_topology(
    _Inout_ P360_DEVICE_CONTEXT *ctx,
    _Out_ P360_FAILURE_REASON *failure
    )
{
    const struct p360_ipc3_speaker_ids ids={
        P360_IPC3_SPEAKER_PIPELINE_ID,
        P360_IPC3_SPEAKER_TONE_ID,
        P360_IPC3_SPEAKER_BUFFER_ID,
        P360_IPC3_SPEAKER_DAI_ID,
        P360_IPC3_SPEAKER_SCHED_ID
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

    status=p360_telemetry_stage(
        P360_TELEM_STAGE_TOPOLOGY_READY);
    if (!NT_SUCCESS(status))
        return status;

    *failure=P360_FAIL_STREAM;

    /*
     * Program gain and duration before PCM_PARAMS causes tone_prepare().
     * This avoids the firmware default -20 dBFS first block and gives the DSP
     * its own hard 2-second silence bound independent of the Windows timer.
     */
    RtlZeroMemory(&message,sizeof(message));
    rc=p360_ipc3_build_tone_amplitude(
        &message,
        ids.tone_id,
        P360_DIAGNOSTIC_TONE_Q1_31,
        P360_SPEAKER_CHANNELS);
    if (rc!=P360_IPC3_TOPOLOGY_OK)
        return STATUS_INVALID_PARAMETER;

    status=p360_runtime_send_zero_error(
        ctx,
        &message,
        P360_IPC3_TONE_CONTROL_BYTES);
    if (!NT_SUCCESS(status))
        return status;

    RtlZeroMemory(&message,sizeof(message));
    rc=p360_ipc3_build_tone_length(
        &message,
        ids.tone_id,
        P360_DIAGNOSTIC_TONE_BLOCKS,
        P360_SPEAKER_CHANNELS);
    if (rc!=P360_IPC3_TOPOLOGY_OK)
        return STATUS_INVALID_PARAMETER;

    status=p360_runtime_send_zero_error(
        ctx,
        &message,
        P360_IPC3_TONE_CONTROL_BYTES);
    if (!NT_SUCCESS(status))
        return status;

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

    status=p360_telemetry_stage(
        P360_TELEM_STAGE_AUDIO_CORE);
    if (!NT_SUCCESS(status))
        return status;

    return STATUS_SUCCESS;
}

#if P360_BOUNDED_TONE_TEST_ENABLED
static NTSTATUS
p360_runtime_run_bounded_tone(
    _Inout_ P360_DEVICE_CONTEXT *ctx,
    _Out_ P360_FAILURE_REASON *failure
    )
{
    struct p360_ipc3_message message;
    LARGE_INTEGER delay;
    NTSTATUS status=STATUS_SUCCESS;
    NTSTATUS cleanupStatus;
    BOOLEAN streamStarted=FALSE;
    BOOLEAN speakerArmed=FALSE;
    BOOLEAN speakerStarted=FALSE;
    int rc;

    if (failure)
        *failure=P360_FAIL_SPEAKER_GUARD;

    if (!ctx || !failure ||
        !ctx->CsAudioInitialized ||
        ctx->State.state!=P360_STATE_AUDIO_CORE_READY ||
        !ctx->State.audio_core_ready ||
        !ctx->State.topology_ready ||
        !ctx->State.ipc_ready ||
        !ctx->State.fw_ready ||
        !p360_safety_can_start_speaker(&ctx->State) ||
        InterlockedCompareExchange(&ctx->Removing,0,0)!=0) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    /*
     * Consume the diagnostic before publishing any audio command. A failure
     * must never cause an automatic second speaker attempt in the same PnP
     * lifetime.
     */
    if (ctx->BoundedToneConsumed)
        return STATUS_DEVICE_BUSY;
    ctx->BoundedToneConsumed=TRUE;

    *failure=P360_FAIL_STREAM;
    RtlZeroMemory(&message,sizeof(message));
    rc=p360_ipc3_build_stream_trigger(
        &message,
        P360_IPC3_SPEAKER_TONE_ID,
        1);
    if (rc!=P360_IPC3_TOPOLOGY_OK)
        return STATUS_INVALID_PARAMETER;

    status=p360_runtime_send_zero_error(ctx,&message,12u);
    if (!NT_SUCCESS(status))
        return status;
    streamStarted=TRUE;

    status=p360_telemetry_stage(
        P360_TELEM_STAGE_STREAM_STARTED);
    if (!NT_SUCCESS(status))
        goto cleanup;

    *failure=P360_FAIL_SPEAKER_GUARD;
    if (!p360_state_speaker_arm(&ctx->State)) {
        status=STATUS_INVALID_DEVICE_STATE;
        goto cleanup;
    }
    speakerArmed=TRUE;

    status=p360_telemetry_stage(
        P360_TELEM_STAGE_SPEAKER_ARMED);
    if (!NT_SUCCESS(status))
        goto cleanup;

    status=p360_csaudio_speaker_start(&ctx->CsAudio);
    if (!NT_SUCCESS(status))
        goto cleanup;
    speakerStarted=TRUE;

    status=p360_telemetry_stage(
        P360_TELEM_STAGE_AMP_STARTED);
    if (!NT_SUCCESS(status))
        goto cleanup;

    /*
     * Gain is already capped at 0.5% full-scale and SOF tone_length is capped
     * at 2 seconds. Keep the Windows timer as an independent second bound,
     * then mute the amplifier before stopping SSP1.
     */
    delay.QuadPart=-(LONGLONG)P360_BOUNDED_TONE_DURATION_MS * 10 * 1000;
    status=KeDelayExecutionThread(
        KernelMode,
        FALSE,
        &delay);

cleanup:
    if (speakerStarted) {
        cleanupStatus=p360_csaudio_speaker_stop(&ctx->CsAudio);
        speakerStarted=FALSE;
        if (NT_SUCCESS(status) && !NT_SUCCESS(cleanupStatus)) {
            status=cleanupStatus;
            *failure=P360_FAIL_SPEAKER_GUARD;
        }
    }

    if (speakerArmed) {
        if (!p360_state_speaker_disarm(&ctx->State) &&
            NT_SUCCESS(status)) {
            status=STATUS_INVALID_DEVICE_STATE;
            *failure=P360_FAIL_SPEAKER_GUARD;
        }
        speakerArmed=FALSE;
    }

    if (streamStarted) {
        RtlZeroMemory(&message,sizeof(message));
        rc=p360_ipc3_build_stream_trigger(
            &message,
            P360_IPC3_SPEAKER_TONE_ID,
            0);
        if (rc!=P360_IPC3_TOPOLOGY_OK) {
            if (NT_SUCCESS(status))
                status=STATUS_INVALID_PARAMETER;
            *failure=P360_FAIL_STREAM;
        } else {
            cleanupStatus=
                p360_runtime_send_zero_error(ctx,&message,12u);
            if (NT_SUCCESS(status) && !NT_SUCCESS(cleanupStatus)) {
                status=cleanupStatus;
                *failure=P360_FAIL_STREAM;
            }
        }
    }

    if (NT_SUCCESS(status)) {
        status=p360_telemetry_stage(
            P360_TELEM_STAGE_TONE_COMPLETE);
    }

    return status;
}
#endif

NTSTATUS
p360_host_playback_prepare(
    P360_DEVICE_CONTEXT *ctx,
    P360_PLAYBACK_STREAM *playback,
    PMDL audioMdl,
    ULONG bufferBytes,
    ULONG periodBytes
    )
{
    struct p360_ipc3_message message;
    NTSTATUS status;
    UINT32 pageTablePhysical;
    int rc;

    if (!ctx || !playback || !audioMdl ||
        !p360_host_playback_policy_enabled() ||
        !ctx->Prepared || !ctx->BusOpen ||
        !ctx->CsAudioInitialized ||
        ctx->State.state!=P360_STATE_AUDIO_CORE_READY ||
        !ctx->State.fw_ready ||
        !ctx->State.ipc_ready ||
        !ctx->State.topology_ready ||
        !ctx->State.audio_core_ready ||
        InterlockedCompareExchange(&ctx->Removing,0,0)!=0) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    status=p360_playback_stream_init(
        playback,
        &ctx->Bus);
    if (!NT_SUCCESS(status))
        return status;

    status=p360_playback_stream_bind_buffer(
        playback,
        audioMdl,
        bufferBytes,
        periodBytes);
    if (!NT_SUCCESS(status))
        return status;

    pageTablePhysical=
        p360_playback_page_table_physical32(playback);
    if (!pageTablePhysical) {
        status=STATUS_DEVICE_CONFIGURATION_ERROR;
        goto fail;
    }

    RtlZeroMemory(&message,sizeof(message));
    rc=p360_ipc3_build_host_pcm_params(
        &message,
        P360_IPC3_SPEAKER_HOST_ID,
        pageTablePhysical,
        playback->PageCount,
        playback->BufferBytes,
        playback->PeriodBytes,
        playback->StreamTag,
        P360_SAMPLE_RATE,
        P360_SPEAKER_CHANNELS);
    if (rc!=P360_IPC3_TOPOLOGY_OK) {
        status=STATUS_INVALID_PARAMETER;
        goto fail;
    }

    status=p360_runtime_send_zero_error(
        ctx,
        &message,
        20u);
    if (!NT_SUCCESS(status))
        goto fail;

    playback->SofParamsPrepared=TRUE;
    return STATUS_SUCCESS;

fail:
    (void)p360_playback_stream_retire(playback);
    return status;
}

NTSTATUS
p360_host_playback_start(
    P360_DEVICE_CONTEXT *ctx,
    P360_PLAYBACK_STREAM *playback
    )
{
    struct p360_ipc3_message message;
    NTSTATUS status;
    NTSTATUS cleanupStatus;
    int rc;

    if (!ctx || !playback ||
        !playback->SofParamsPrepared ||
        playback->SofRunning ||
        playback->SpeakerArmed ||
        playback->SpeakerStarted ||
        ctx->State.state!=P360_STATE_AUDIO_CORE_READY ||
        !p360_safety_can_start_speaker(&ctx->State) ||
        InterlockedCompareExchange(&ctx->Removing,0,0)!=0) {
        return STATUS_INVALID_DEVICE_STATE;
    }

    /*
     * Match Linux SOF IPC3 ordering: start the platform HDA DMA first,
     * then issue STREAM_START. The MAX98357A amplifier is enabled last.
     */
    status=p360_playback_stream_start(playback);
    if (!NT_SUCCESS(status))
        return status;

    RtlZeroMemory(&message,sizeof(message));
    rc=p360_ipc3_build_stream_trigger(
        &message,
        P360_IPC3_SPEAKER_HOST_ID,
        1);
    if (rc!=P360_IPC3_TOPOLOGY_OK) {
        status=STATUS_INVALID_PARAMETER;
        goto fail_dma;
    }

    status=p360_runtime_send_zero_error(
        ctx,
        &message,
        12u);
    if (!NT_SUCCESS(status))
        goto fail_dma;
    playback->SofRunning=TRUE;

    status=p360_telemetry_stage(
        P360_TELEM_STAGE_STREAM_STARTED);
    if (!NT_SUCCESS(status))
        goto fail_sof;

    if (!p360_state_speaker_arm(&ctx->State)) {
        status=STATUS_INVALID_DEVICE_STATE;
        goto fail_sof;
    }
    playback->SpeakerArmed=TRUE;

    status=p360_telemetry_stage(
        P360_TELEM_STAGE_SPEAKER_ARMED);
    if (!NT_SUCCESS(status))
        goto fail_arm;

    status=p360_csaudio_speaker_start(&ctx->CsAudio);
    if (!NT_SUCCESS(status))
        goto fail_arm;
    playback->SpeakerStarted=TRUE;

    return p360_telemetry_stage(
        P360_TELEM_STAGE_AMP_STARTED);

fail_arm:
    if (playback->SpeakerArmed) {
        (void)p360_state_speaker_disarm(&ctx->State);
        playback->SpeakerArmed=FALSE;
    }

fail_sof:
    if (playback->SofRunning) {
        RtlZeroMemory(&message,sizeof(message));
        if (p360_ipc3_build_stream_trigger(
                &message,
                P360_IPC3_SPEAKER_HOST_ID,
                0)==P360_IPC3_TOPOLOGY_OK) {
            cleanupStatus=p360_runtime_send_zero_error(
                ctx,
                &message,
                12u);
            UNREFERENCED_PARAMETER(cleanupStatus);
        }
        playback->SofRunning=FALSE;
    }

fail_dma:
    (void)p360_playback_stream_stop(playback);
    return status;
}

NTSTATUS
p360_host_playback_stop(
    P360_DEVICE_CONTEXT *ctx,
    P360_PLAYBACK_STREAM *playback
    )
{
    struct p360_ipc3_message message;
    NTSTATUS firstStatus=STATUS_SUCCESS;
    NTSTATUS status;
    int rc;

    if (!ctx || !playback)
        return STATUS_INVALID_PARAMETER;

    /*
     * Fail-quiet ordering: mute the external amplifier before stopping
     * the SOF graph or HDA DMA.
     */
    if (playback->SpeakerStarted) {
        status=p360_csaudio_speaker_stop(&ctx->CsAudio);
        if (!NT_SUCCESS(status) && NT_SUCCESS(firstStatus))
            firstStatus=status;
        playback->SpeakerStarted=FALSE;
    }

    if (playback->SpeakerArmed) {
        if (!p360_state_speaker_disarm(&ctx->State) &&
            NT_SUCCESS(firstStatus)) {
            firstStatus=STATUS_INVALID_DEVICE_STATE;
        }
        playback->SpeakerArmed=FALSE;
    }

    if (playback->SofRunning) {
        RtlZeroMemory(&message,sizeof(message));
        rc=p360_ipc3_build_stream_trigger(
            &message,
            P360_IPC3_SPEAKER_HOST_ID,
            0);
        if (rc!=P360_IPC3_TOPOLOGY_OK) {
            if (NT_SUCCESS(firstStatus))
                firstStatus=STATUS_INVALID_PARAMETER;
        } else {
            status=p360_runtime_send_zero_error(
                ctx,
                &message,
                12u);
            if (!NT_SUCCESS(status) && NT_SUCCESS(firstStatus))
                firstStatus=status;
        }
        playback->SofRunning=FALSE;
    }

    status=p360_playback_stream_stop(playback);
    if (!NT_SUCCESS(status) && NT_SUCCESS(firstStatus))
        firstStatus=status;

    return firstStatus;
}

NTSTATUS
p360_host_playback_release(
    P360_DEVICE_CONTEXT *ctx,
    P360_PLAYBACK_STREAM *playback
    )
{
    struct p360_ipc3_message message;
    NTSTATUS firstStatus;
    NTSTATUS status;
    int rc;

    if (!ctx || !playback)
        return STATUS_INVALID_PARAMETER;

    firstStatus=p360_host_playback_stop(
        ctx,
        playback);

    if (playback->SofParamsPrepared) {
        RtlZeroMemory(&message,sizeof(message));
        rc=p360_ipc3_build_pcm_free(
            &message,
            P360_IPC3_SPEAKER_HOST_ID);
        if (rc!=P360_IPC3_TOPOLOGY_OK) {
            if (NT_SUCCESS(firstStatus))
                firstStatus=STATUS_INVALID_PARAMETER;
        } else {
            status=p360_runtime_send_zero_error(
                ctx,
                &message,
                12u);
            if (!NT_SUCCESS(status) && NT_SUCCESS(firstStatus))
                firstStatus=status;
        }
        playback->SofParamsPrepared=FALSE;
    }

    status=p360_playback_stream_retire(playback);
    if (!NT_SUCCESS(status) && NT_SUCCESS(firstStatus))
        firstStatus=status;

    return firstStatus;
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

    status=p360_telemetry_stage(
        P360_TELEM_STAGE_FW_LOADED);
    if (!NT_SUCCESS(status))
        goto fail;

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

    status=p360_telemetry_boot_epoch(epoch);
    if (!NT_SUCCESS(status))
        goto fail;
    status=p360_telemetry_stage(
        P360_TELEM_STAGE_SOF_BOOTING);
    if (!NT_SUCCESS(status))
        goto fail;

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

    status=p360_telemetry_stage(
        P360_TELEM_STAGE_FW_READY);
    if (!NT_SUCCESS(status))
        goto fail_live;

    failure=P360_FAIL_IRQ;
    status=p360_cs_runtime_bind_live(
        &ctx->Runtime,
        epoch);
    if (!NT_SUCCESS(status))
        goto fail_live;

    status=p360_telemetry_stage(
        P360_TELEM_STAGE_IRQ_READY);
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

        status=p360_telemetry_ipc(
            firmwareError,
            P360_IPC3_TONE_CONTROL_BYTES);
        if (!NT_SUCCESS(status))
            goto fail_live;

        ctx->State.ipc_ready=1;
        if (!p360_state_advance(
                &ctx->State,
                P360_STATE_IPC_READY)) {
            status=STATUS_INVALID_DEVICE_STATE;
            goto fail_live;
        }

        status=p360_telemetry_stage(
            P360_TELEM_STAGE_IPC_READY);
        if (!NT_SUCCESS(status))
            goto fail_live;
    }

    if (p360_host_playback_policy_enabled()) {
        if (!p360_ipc_probe_policy_enabled() ||
            ctx->State.state!=P360_STATE_IPC_READY ||
            !ctx->State.ipc_ready) {
            failure=P360_FAIL_IPC;
            status=STATUS_INVALID_DEVICE_STATE;
            goto fail_live;
        }

        status=p360_runtime_prepare_host_topology(
            ctx,
            &failure);
        if (!NT_SUCCESS(status))
            goto fail_live;
    } else if (p360_tone_topology_policy_enabled()) {
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

#if P360_BOUNDED_TONE_TEST_ENABLED
    if (p360_bounded_tone_policy_enabled() &&
        !ctx->BoundedToneConsumed) {
        status=p360_runtime_run_bounded_tone(
            ctx,
            &failure);
        if (!NT_SUCCESS(status))
            goto fail_live;
    }
#endif

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

    status=p360_telemetry_stage(
        P360_TELEM_STAGE_STOP_COMPLETE);
    if (!NT_SUCCESS(status))
        return p360_fail(
            ctx,
            P360_FAIL_IRQ,
            status);

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
    P360_FAILURE_REASON failure=P360_FAIL_RESOURCES;

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
    ctx->BoundedToneConsumed=FALSE;
    InterlockedExchange(&ctx->Removing,0);

    status=p360_telemetry_reset(
        p360_build_flags());
#if P360_RUNTIME_BOOT_ENABLED
    if (!NT_SUCCESS(status))
        return status;
#else
    UNREFERENCED_PARAMETER(status);
#endif

    (void)p360_telemetry_prepare(P360_PREP_STEP_HOST_BEGIN,0,STATUS_SUCCESS);

    status=p360_cs_bus_open(&ctx->Bus,Device);
    if (!NT_SUCCESS(status))
        goto cleanup;
    ctx->BusOpen=TRUE;

    (void)p360_telemetry_prepare(P360_PREP_STEP_PCI_IDENTITY,0,STATUS_PENDING);
    status=p360_cs_bus_read_identity(&ctx->Bus,&ctx->Identity);
    if (NT_SUCCESS(status))
        (void)p360_telemetry_prepare(
            P360_PREP_STEP_PCI_IDENTITY,
            (ULONG)ctx->Identity.command,
            status);
    if (!NT_SUCCESS(status)) {
        failure=P360_FAIL_IDENTITY;
        goto cleanup;
    }
    ctx->State.hardware_identity_ok=1;

    (void)p360_telemetry_prepare(P360_PREP_STEP_NHLT_PARSE,0,STATUS_PENDING);
    if (!p360_nhlt_parse(
            ctx->Bus.nhlt.nhlt,
            (size_t)ctx->Bus.nhlt.nhltSz,
            &ctx->Nhlt)) {
        status=STATUS_DEVICE_CONFIGURATION_ERROR;
        (void)p360_telemetry_prepare(
            P360_PREP_STEP_NHLT_PARSE,
            (ULONG)ctx->Bus.nhlt.nhltSz & 0xffffu,
            status);
        failure=P360_FAIL_NHLT;
        goto cleanup;
    }
    (void)p360_telemetry_prepare(
        P360_PREP_STEP_NHLT_PARSE,
        ((ULONG)ctx->Nhlt.table_length & 0xffffu) |
            (ctx->Nhlt.dmic_capture ? P360_PREP_NHLT_DMIC : 0) |
            (ctx->Nhlt.ssp1_render ? P360_PREP_NHLT_SSP1_RENDER : 0) |
            (ctx->Nhlt.ssp2_render ? P360_PREP_NHLT_SSP2_RENDER : 0) |
            (ctx->Nhlt.ssp2_capture ? P360_PREP_NHLT_SSP2_CAPTURE : 0),
        STATUS_SUCCESS);
    ctx->State.nhlt_ok=1;

    (void)p360_telemetry_prepare(P360_PREP_STEP_STATE_READY,0,STATUS_PENDING);
    if (!p360_state_advance(
            &ctx->State,
            P360_STATE_RESOURCES_OK)) {
        status=STATUS_INVALID_DEVICE_STATE;
        (void)p360_telemetry_prepare(P360_PREP_STEP_STATE_READY,0,status);
        goto cleanup;
    }
    (void)p360_telemetry_prepare(P360_PREP_STEP_STATE_READY,0,STATUS_SUCCESS);

    p360_loader_init(&ctx->Loader);

    (void)p360_telemetry_prepare(P360_PREP_STEP_BOOT_ADAPTER,0,STATUS_PENDING);
    status=p360_cs_boot_adapter_init(
        &ctx->Boot,
        &ctx->Bus);
    (void)p360_telemetry_prepare(P360_PREP_STEP_BOOT_ADAPTER,0,status);
    if (!NT_SUCCESS(status))
        goto cleanup;
    ctx->BootInitialized=TRUE;

    (void)p360_telemetry_prepare(P360_PREP_STEP_RUNTIME_CREATE,0,STATUS_PENDING);
    status=p360_cs_runtime_create(
        &ctx->Runtime,
        Device,
        &ctx->Bus,
        &ctx->Boot);
    if (!NT_SUCCESS(status))
        goto cleanup;
    ctx->RuntimeInitialized=TRUE;

    (void)p360_telemetry_prepare(P360_PREP_STEP_CSAUDIO_OPEN,0,STATUS_PENDING);
    status=p360_csaudio_open(&ctx->CsAudio);
    (void)p360_telemetry_prepare(P360_PREP_STEP_CSAUDIO_OPEN,0,status);
    if (!NT_SUCCESS(status))
        goto cleanup;
    ctx->CsAudioInitialized=TRUE;

    ctx->Prepared=TRUE;
    (void)p360_telemetry_prepare(P360_PREP_STEP_COMPLETE,0,STATUS_SUCCESS);
    return STATUS_SUCCESS;

cleanup:
    if (ctx->CsAudioInitialized) {
        p360_csaudio_close(&ctx->CsAudio);
        ctx->CsAudioInitialized=FALSE;
    }

    if (ctx->RuntimeInitialized) {
        NTSTATUS cleanupStatus=
            p360_cs_runtime_destroy(&ctx->Runtime);
        if (!NT_SUCCESS(cleanupStatus))
            status=cleanupStatus;
        ctx->RuntimeInitialized=FALSE;
    }

    if (ctx->BootInitialized) {
        NTSTATUS cleanupStatus=
            p360_cs_boot_adapter_retire(&ctx->Boot);
        if (!NT_SUCCESS(cleanupStatus))
            status=cleanupStatus;
        ctx->BootInitialized=FALSE;
    }

    if (ctx->BusOpen) {
        p360_cs_bus_close(&ctx->Bus);
        ctx->BusOpen=FALSE;
    }

    return p360_fail(ctx,failure,status);
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
