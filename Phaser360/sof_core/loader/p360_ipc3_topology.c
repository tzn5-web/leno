/* SPDX-License-Identifier: BSD-3-Clause */
#include "p360_ipc3_topology.h"
#include "../../include/p360_board.h"

static void zero_message(struct p360_ipc3_message *m)
{
    size_t i;
    if (!m)
        return;
    m->bytes=0;
    for (i=0;i<sizeof(m->data);++i)
        m->data[i]=0;
}

static void put16(uint8_t *p,uint16_t v)
{
    p[0]=(uint8_t)v;
    p[1]=(uint8_t)(v >> 8);
}

static void put32(uint8_t *p,uint32_t v)
{
    p[0]=(uint8_t)v;
    p[1]=(uint8_t)(v >> 8);
    p[2]=(uint8_t)(v >> 16);
    p[3]=(uint8_t)(v >> 24);
}

static int ids_distinct(const struct p360_ipc3_speaker_ids *ids)
{
    const uint32_t v[5]={ids->pipeline_id,ids->tone_id,ids->buffer_id,
        ids->dai_id,ids->pipe_comp_id};
    size_t i,j;
    for (i=0;i<5;++i) {
        if (!v[i])
            return 0;
        for (j=0;j<i;++j)
            if (v[i]==v[j])
                return 0;
    }
    return 1;
}

int p360_ipc3_speaker_ids_validate(const struct p360_ipc3_speaker_ids *ids)
{
    if (!ids)
        return P360_IPC3_TOPOLOGY_ARGUMENT;
    return ids_distinct(ids) ?
        P360_IPC3_TOPOLOGY_OK :
        P360_IPC3_TOPOLOGY_RANGE;
}

static int playback_ids_distinct(const struct p360_ipc3_playback_ids *ids)
{
    const uint32_t v[5]={ids->pipeline_id,ids->host_id,ids->buffer_id,
        ids->dai_id,ids->pipe_comp_id};
    size_t i,j;
    for (i=0;i<5;++i) {
        if (!v[i])
            return 0;
        for (j=0;j<i;++j)
            if (v[i]==v[j])
                return 0;
    }
    return 1;
}

int p360_ipc3_playback_ids_validate(const struct p360_ipc3_playback_ids *ids)
{
    if (!ids)
        return P360_IPC3_TOPOLOGY_ARGUMENT;
    return playback_ids_distinct(ids) ?
        P360_IPC3_TOPOLOGY_OK :
        P360_IPC3_TOPOLOGY_RANGE;
}

int p360_ipc3_ssp1_profile_validate(const struct p360_ipc3_ssp1_profile *p)
{
    uint64_t expected_bclk;

    if (!p)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    if (p->format!=(P360_IPC3_DAI_FMT_I2S |
                    P360_IPC3_DAI_FMT_NB_NF |
                    P360_IPC3_DAI_FMT_CBC_CFC) ||
        p->mclk_id!=P360_SPEAKER_SSP1_MCLK_ID ||
        p->mclk_rate!=P360_SPEAKER_SSP1_MCLK_HZ ||
        p->fsync_rate!=P360_SAMPLE_RATE ||
        p->bclk_rate!=P360_SPEAKER_SSP1_BCLK_HZ ||
        p->tdm_slots!=P360_SPEAKER_CHANNELS ||
        p->rx_slots!=3u ||
        p->tx_slots!=3u ||
        p->sample_valid_bits!=P360_SPEAKER_DAI_VALID_BITS ||
        p->tdm_slot_width!=P360_SPEAKER_DAI_SLOT_BITS ||
        p->mclk_direction!=P360_IPC3_MCLK_CODEC_INPUT ||
        p->frame_pulse_width!=0u ||
        p->tdm_per_slot_padding_flag!=0u ||
        p->clks_control!=0u ||
        p->quirks!=0u ||
        p->bclk_delay!=0u ||
        p->group_id!=0u ||
        p->flags!=0u)
        return P360_IPC3_TOPOLOGY_PROFILE;

    expected_bclk=(uint64_t)p->fsync_rate *
        (uint64_t)p->tdm_slots *
        (uint64_t)p->tdm_slot_width;
    if (expected_bclk>UINT32_MAX ||
        p->bclk_rate!=(uint32_t)expected_bclk)
        return P360_IPC3_TOPOLOGY_PROFILE;

    return P360_IPC3_TOPOLOGY_OK;
}

static void put_comp(uint8_t *d,uint32_t total,uint32_t id,uint32_t type,
    uint32_t pipeline_id)
{
    put32(d,total);
    put32(d+4,P360_IPC3_GLB_TPLG_MSG|P360_IPC3_TPLG_COMP_NEW);
    put32(d+8,id);
    put32(d+12,type);
    put32(d+16,pipeline_id);
    put32(d+20,0u);
    put32(d+24,0u);
}

static void put_config(uint8_t *d,uint32_t periods_sink,
    uint32_t periods_source,uint32_t frame_fmt)
{
    put32(d,36u);
    put32(d+4,0u);
    put32(d+8,periods_sink);
    put32(d+12,periods_source);
    put32(d+16,0u);
    put32(d+20,frame_fmt);
    put32(d+24,0u);
    put32(d+28,0u);
    put32(d+32,0u);
}

int p360_ipc3_build_host_new(struct p360_ipc3_message *out,
    const struct p360_ipc3_playback_ids *ids)
{
    uint8_t *d;

    if (!out || p360_ipc3_playback_ids_validate(ids))
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    zero_message(out);
    d=out->data;

    put_comp(d,P360_IPC3_HOST_NEW_BYTES,ids->host_id,
        P360_IPC3_COMP_HOST,ids->pipeline_id);
    /*
     * Upstream pipe-host-playback.m4: playback HOST has two sink periods,
     * zero source periods and is scheduled by the host DMA.
     */
    put_config(d+28,2u,0u,P360_IPC3_FRAME_S32_LE);
    put32(d+64,P360_IPC3_STREAM_PLAYBACK);
    put32(d+68,0u); /* no_irq: keep normal DMA scheduling */
    put32(d+72,0u); /* dmac_config: platform default */
    out->bytes=P360_IPC3_HOST_NEW_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_playback_buffer_new(struct p360_ipc3_message *out,
    const struct p360_ipc3_playback_ids *ids,uint32_t bytes)
{
    uint8_t *d;

    if (!out || p360_ipc3_playback_ids_validate(ids) ||
        !bytes || (bytes & 3u) || bytes>65536u)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    zero_message(out);
    d=out->data;
    put_comp(d,P360_IPC3_BUFFER_NEW_BYTES,ids->buffer_id,
        P360_IPC3_COMP_BUFFER,ids->pipeline_id);
    put32(d+28,bytes);
    put32(d+32,P360_IPC3_MEM_RAM|P360_IPC3_MEM_HP|
        P360_IPC3_MEM_DMA|P360_IPC3_MEM_CACHE);
    put32(d+36,0u);
    put32(d+40,0u);
    out->bytes=P360_IPC3_BUFFER_NEW_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_playback_dai_new(struct p360_ipc3_message *out,
    const struct p360_ipc3_playback_ids *ids,uint32_t dai_index)
{
    uint8_t *d;

    if (!out || p360_ipc3_playback_ids_validate(ids) || dai_index!=1u)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    zero_message(out);
    d=out->data;
    put_comp(d,P360_IPC3_DAI_NEW_BYTES,ids->dai_id,
        P360_IPC3_COMP_DAI,ids->pipeline_id);
    put_config(d+28,0u,2u,P360_IPC3_FRAME_S16_LE);
    put32(d+64,P360_IPC3_STREAM_PLAYBACK);
    put32(d+68,dai_index);
    put32(d+72,P360_IPC3_DAI_INTEL_SSP);
    put32(d+76,0u);
    out->bytes=P360_IPC3_DAI_NEW_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_tone_new(struct p360_ipc3_message *out,
    const struct p360_ipc3_speaker_ids *ids,uint32_t sample_rate)
{
    uint8_t *d;
    if (!out || p360_ipc3_speaker_ids_validate(ids) ||
        sample_rate!=48000u)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    zero_message(out);
    d=out->data;
    put_comp(d,P360_IPC3_TONE_NEW_BYTES,ids->tone_id,
        P360_IPC3_COMP_TONE,ids->pipeline_id);
    put_config(d+28,2u,0u,P360_IPC3_FRAME_S32_LE);
    put32(d+64,sample_rate);
    out->bytes=P360_IPC3_TONE_NEW_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_buffer_new(struct p360_ipc3_message *out,
    const struct p360_ipc3_speaker_ids *ids,uint32_t bytes)
{
    uint8_t *d;
    if (!out || p360_ipc3_speaker_ids_validate(ids) ||
        !bytes || (bytes & 3u) || bytes>65536u)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    zero_message(out);
    d=out->data;
    put_comp(d,P360_IPC3_BUFFER_NEW_BYTES,ids->buffer_id,
        P360_IPC3_COMP_BUFFER,ids->pipeline_id);
    put32(d+28,bytes);
    put32(d+32,P360_IPC3_MEM_RAM|P360_IPC3_MEM_HP|
        P360_IPC3_MEM_DMA|P360_IPC3_MEM_CACHE);
    put32(d+36,0u);
    put32(d+40,0u);
    out->bytes=P360_IPC3_BUFFER_NEW_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_dai_new(struct p360_ipc3_message *out,
    const struct p360_ipc3_speaker_ids *ids,uint32_t dai_index)
{
    uint8_t *d;
    if (!out || p360_ipc3_speaker_ids_validate(ids) || dai_index!=1u)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    zero_message(out);
    d=out->data;
    put_comp(d,P360_IPC3_DAI_NEW_BYTES,ids->dai_id,
        P360_IPC3_COMP_DAI,ids->pipeline_id);
    put_config(d+28,0u,2u,P360_IPC3_FRAME_S16_LE);
    put32(d+64,P360_IPC3_STREAM_PLAYBACK);
    put32(d+68,dai_index);
    put32(d+72,P360_IPC3_DAI_INTEL_SSP);
    put32(d+76,0u);
    out->bytes=P360_IPC3_DAI_NEW_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_playback_pipe_new(struct p360_ipc3_message *out,
    const struct p360_ipc3_playback_ids *ids,uint32_t period_us,
    uint32_t frames_per_sched)
{
    uint8_t *d;

    if (!out || p360_ipc3_playback_ids_validate(ids) ||
        period_us!=1000u || frames_per_sched!=48u)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    zero_message(out);
    d=out->data;
    put32(d,P360_IPC3_PIPE_NEW_BYTES);
    put32(d+4,P360_IPC3_GLB_TPLG_MSG|P360_IPC3_TPLG_PIPE_NEW);
    put32(d+8,ids->pipe_comp_id);
    put32(d+12,ids->pipeline_id);
    put32(d+16,ids->host_id);
    put32(d+20,0u);
    put32(d+24,period_us);
    put32(d+28,0u);
    put32(d+32,0u);
    put32(d+36,frames_per_sched);
    put32(d+40,0u);
    put32(d+44,P360_IPC3_TIME_DMA);
    out->bytes=P360_IPC3_PIPE_NEW_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_playback_pipe_complete(struct p360_ipc3_message *out,
    const struct p360_ipc3_playback_ids *ids)
{
    if (!out || p360_ipc3_playback_ids_validate(ids))
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    zero_message(out);
    put32(out->data,P360_IPC3_PIPE_READY_BYTES);
    put32(out->data+4,P360_IPC3_GLB_TPLG_MSG|P360_IPC3_TPLG_PIPE_DONE);
    put32(out->data+8,ids->pipe_comp_id);
    out->bytes=P360_IPC3_PIPE_READY_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_pipe_new(struct p360_ipc3_message *out,
    const struct p360_ipc3_speaker_ids *ids,uint32_t period_us,
    uint32_t frames_per_sched)
{
    uint8_t *d;
    if (!out || p360_ipc3_speaker_ids_validate(ids) ||
        period_us!=1000u || frames_per_sched!=48u)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    zero_message(out);
    d=out->data;
    put32(d,P360_IPC3_PIPE_NEW_BYTES);
    put32(d+4,P360_IPC3_GLB_TPLG_MSG|P360_IPC3_TPLG_PIPE_NEW);
    put32(d+8,ids->pipe_comp_id);
    put32(d+12,ids->pipeline_id);
    put32(d+16,ids->tone_id);
    put32(d+20,0u);
    put32(d+24,period_us);
    put32(d+28,0u);
    put32(d+32,0u);
    put32(d+36,frames_per_sched);
    put32(d+40,0u);
    put32(d+44,P360_IPC3_TIME_TIMER);
    out->bytes=P360_IPC3_PIPE_NEW_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_connect(struct p360_ipc3_message *out,
    uint32_t source_id,uint32_t sink_id)
{
    if (!out || !source_id || !sink_id || source_id==sink_id)
        return P360_IPC3_TOPOLOGY_ARGUMENT;
    zero_message(out);
    put32(out->data,P360_IPC3_CONNECT_BYTES);
    put32(out->data+4,P360_IPC3_GLB_TPLG_MSG|P360_IPC3_TPLG_CONNECT);
    put32(out->data+8,source_id);
    put32(out->data+12,sink_id);
    out->bytes=P360_IPC3_CONNECT_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_pipe_complete(struct p360_ipc3_message *out,
    const struct p360_ipc3_speaker_ids *ids)
{
    if (!out || p360_ipc3_speaker_ids_validate(ids))
        return P360_IPC3_TOPOLOGY_ARGUMENT;
    zero_message(out);
    put32(out->data,P360_IPC3_PIPE_READY_BYTES);
    put32(out->data+4,P360_IPC3_GLB_TPLG_MSG|P360_IPC3_TPLG_PIPE_DONE);
    put32(out->data+8,ids->pipe_comp_id);
    out->bytes=P360_IPC3_PIPE_READY_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_host_pcm_params(struct p360_ipc3_message *out,
    uint32_t comp_id,uint32_t page_table_phys,uint32_t pages,
    uint32_t buffer_bytes,uint32_t period_bytes,uint16_t stream_tag,
    uint32_t sample_rate,uint16_t channels)
{
    uint8_t *d;

    if (!out || !comp_id || !page_table_phys || !pages ||
        !buffer_bytes || !period_bytes || period_bytes>buffer_bytes ||
        (buffer_bytes % period_bytes)!=0 ||
        !stream_tag || stream_tag>15u ||
        sample_rate!=P360_SAMPLE_RATE ||
        channels!=P360_SPEAKER_CHANNELS)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    zero_message(out);
    d=out->data;

    put32(d,P360_IPC3_PCM_PARAMS_BYTES);
    put32(d+4,P360_IPC3_GLB_STREAM_MSG|P360_IPC3_STREAM_PCM_PARAMS);
    put32(d+8,comp_id);
    put32(d+12,0u);
    put32(d+16,0u);
    put32(d+20,0u);

    put32(d+24,84u);

    /* struct sof_ipc_host_buffer */
    put32(d+28,28u);
    put32(d+32,page_table_phys);
    put32(d+36,pages);
    put32(d+40,buffer_bytes);
    put32(d+44,0u);
    put32(d+48,0u);
    put32(d+52,0u);

    put32(d+56,P360_IPC3_STREAM_PLAYBACK);
    put32(d+60,P360_IPC3_FRAME_S32_LE);
    put32(d+64,P360_IPC3_BUFFER_INTERLEAVED);
    put32(d+68,sample_rate);
    put16(d+72,stream_tag);
    put16(d+74,channels);
    put16(d+76,2u); /* 16 valid bits */
    put16(d+78,4u); /* forced 32-bit Windows/HDA container */
    put32(d+80,period_bytes);

    /*
     * Position comes from the CoolStar HDA position buffer through
     * StreamPosition(), so suppress periodic SOF position IPCs.
     */
    put16(d+84,1u);
    d[86]=0u;
    d[87]=0u;
    put16(d+88,0u);
    put16(d+90,0u);
    put16(d+92,P360_IPC3_CHMAP_FL);
    put16(d+94,P360_IPC3_CHMAP_FR);

    out->bytes=P360_IPC3_PCM_PARAMS_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_pcm_free(struct p360_ipc3_message *out,
    uint32_t comp_id)
{
    if (!out || !comp_id)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    zero_message(out);
    put32(out->data,P360_IPC3_STREAM_BYTES);
    put32(out->data+4,P360_IPC3_GLB_STREAM_MSG|P360_IPC3_STREAM_PCM_FREE);
    put32(out->data+8,comp_id);
    out->bytes=P360_IPC3_STREAM_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_pcm_params(struct p360_ipc3_message *out,
    uint32_t comp_id,uint32_t sample_rate,uint16_t channels)
{
    uint8_t *d;

    if (!out || !comp_id ||
        sample_rate!=P360_SAMPLE_RATE ||
        channels!=P360_SPEAKER_CHANNELS)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    zero_message(out);
    d=out->data;

    /* struct sof_ipc_pcm_params */
    put32(d,P360_IPC3_PCM_PARAMS_BYTES);
    put32(d+4,P360_IPC3_GLB_STREAM_MSG|P360_IPC3_STREAM_PCM_PARAMS);
    put32(d+8,comp_id);
    put32(d+12,0u); /* flags */
    put32(d+16,0u);
    put32(d+20,0u);

    /* struct sof_ipc_stream_params starts at +24. */
    put32(d+24,84u);

    /* Hostless proof: preserve the nested host-buffer ABI but no pages. */
    put32(d+28,28u);
    put32(d+32,0u); /* phy_addr */
    put32(d+36,0u); /* pages */
    put32(d+40,0u); /* size */
    put32(d+44,0u);
    put32(d+48,0u);
    put32(d+52,0u);

    put32(d+56,P360_IPC3_STREAM_PLAYBACK);
    put32(d+60,P360_IPC3_FRAME_S32_LE);
    put32(d+64,P360_IPC3_BUFFER_INTERLEAVED);
    put32(d+68,sample_rate);
    put16(d+72,0u); /* stream_tag */
    put16(d+74,channels);
    put16(d+76,4u); /* valid bytes: S32 tone */
    put16(d+78,4u); /* container bytes */
    put32(d+80,0u); /* no host period for hostless pipeline */
    put16(d+84,1u); /* suppress host stream-position notifications */
    put16(d+86,0u);
    put16(d+88,0u);
    put16(d+90,0u);
    put16(d+92,P360_IPC3_CHMAP_FL);
    put16(d+94,P360_IPC3_CHMAP_FR);
    /* Remaining channel-map entries stay SOF_CHMAP_UNKNOWN (zero). */

    out->bytes=P360_IPC3_PCM_PARAMS_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}


static int p360_ipc3_build_tone_enum_control(
    struct p360_ipc3_message *out,
    uint32_t comp_id,
    uint32_t control_index,
    uint32_t value,
    uint16_t channels)
{
    uint8_t *d;

    if (!out || !comp_id || channels!=P360_SPEAKER_CHANNELS || !value)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    zero_message(out);
    d=out->data;

    /*
     * SOF v1.9.3 COMP_SET_DATA -> tone_cmd_set_data().
     * The Tone component expects an ENUM index and two
     * sof_ipc_ctrl_value_comp elements in the sof_abi_hdr payload.
     */
    put32(d,P360_IPC3_TONE_CONTROL_BYTES);
    put32(d+4,P360_IPC3_GLB_COMP_MSG|P360_IPC3_COMP_SET_DATA);
    put32(d+8,0u);
    put32(d+12,comp_id);
    put32(d+16,P360_IPC3_CTRL_TYPE_DATA_SET);
    put32(d+20,P360_IPC3_CTRL_CMD_ENUM);
    put32(d+24,control_index);

    /* Empty host buffer still carries its ABI struct size. */
    put32(d+28,28u);
    put32(d+56,channels);
    put32(d+60,0u);
    put32(d+64,0u);

    /* struct sof_abi_hdr followed by two stereo component values. */
    put32(d+92,P360_IPC3_SOF_ABI_MAGIC);
    put32(d+96,0u);
    put32(d+100,(uint32_t)channels * 8u);
    put32(d+104,P360_IPC3_SOF_ABI_3_20_0);

    put32(d+124,0u);
    put32(d+128,value);
    put32(d+132,1u);
    put32(d+136,value);

    out->bytes=P360_IPC3_TONE_CONTROL_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_tone_amplitude(struct p360_ipc3_message *out,
    uint32_t comp_id,uint32_t amplitude_q1_31,uint16_t channels)
{
    if (!amplitude_q1_31 ||
        amplitude_q1_31>P360_IPC3_TONE_HALF_PERCENT_Q1_31)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    return p360_ipc3_build_tone_enum_control(
        out,
        comp_id,
        P360_IPC3_TONE_IDX_AMPLITUDE,
        amplitude_q1_31,
        channels);
}

int p360_ipc3_build_tone_length(struct p360_ipc3_message *out,
    uint32_t comp_id,uint32_t blocks_125us,uint16_t channels)
{
    if (!blocks_125us ||
        blocks_125us>P360_IPC3_TONE_TWO_SECONDS_BLOCKS)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    return p360_ipc3_build_tone_enum_control(
        out,
        comp_id,
        P360_IPC3_TONE_IDX_LENGTH,
        blocks_125us,
        channels);
}

int p360_ipc3_build_stream_trigger(struct p360_ipc3_message *out,
    uint32_t comp_id,int start)
{
    if (!out || !comp_id || (start!=0 && start!=1))
        return P360_IPC3_TOPOLOGY_ARGUMENT;
    zero_message(out);
    put32(out->data,P360_IPC3_STREAM_BYTES);
    put32(out->data+4,P360_IPC3_GLB_STREAM_MSG|
        (start ? P360_IPC3_STREAM_START : P360_IPC3_STREAM_STOP));
    put32(out->data+8,comp_id);
    out->bytes=P360_IPC3_STREAM_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}

int p360_ipc3_build_ssp1_config(struct p360_ipc3_message *out,
    uint32_t dai_index,const struct p360_ipc3_ssp1_profile *p)
{
    uint8_t *d;
    if (!out || dai_index!=1u || p360_ipc3_ssp1_profile_validate(p))
        return P360_IPC3_TOPOLOGY_PROFILE;

    zero_message(out);
    d=out->data;
    put32(d,P360_IPC3_DAI_CONFIG_BYTES);
    put32(d+4,P360_IPC3_GLB_DAI_MSG|P360_IPC3_DAI_CONFIG);
    put32(d+8,P360_IPC3_DAI_INTEL_SSP);
    put32(d+12,dai_index);
    put16(d+16,p->format);
    d[18]=p->group_id;
    d[19]=p->flags;
    /* d+20 .. d+51 are ABI-reserved and remain zero. */
    put32(d+52,0u);
    put16(d+56,0u);
    put16(d+58,p->mclk_id);
    put32(d+60,p->mclk_rate);
    put32(d+64,p->fsync_rate);
    put32(d+68,p->bclk_rate);
    put32(d+72,p->tdm_slots);
    put32(d+76,p->rx_slots);
    put32(d+80,p->tx_slots);
    put32(d+84,p->sample_valid_bits);
    put16(d+88,p->tdm_slot_width);
    put16(d+90,0u);
    put32(d+92,p->mclk_direction);
    put16(d+96,p->frame_pulse_width);
    put16(d+98,p->tdm_per_slot_padding_flag);
    put32(d+100,p->clks_control);
    put32(d+104,p->quirks);
    put32(d+108,p->bclk_delay);
    out->bytes=P360_IPC3_DAI_CONFIG_BYTES;
    return P360_IPC3_TOPOLOGY_OK;
}
