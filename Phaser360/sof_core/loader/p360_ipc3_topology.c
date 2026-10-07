/* SPDX-License-Identifier: BSD-3-Clause */
#include "p360_ipc3_topology.h"

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

int p360_ipc3_ssp1_profile_validate(const struct p360_ipc3_ssp1_profile *p)
{
    uint64_t expected_bclk;

    if (!p)
        return P360_IPC3_TOPOLOGY_ARGUMENT;

    if ((p->format & 0x000fu)!=P360_IPC3_DAI_FMT_I2S ||
        p->fsync_rate!=48000u ||
        p->tdm_slots!=2u ||
        p->sample_valid_bits!=24u ||
        p->tdm_slot_width!=32u ||
        p->tx_slots!=3u ||
        !p->bclk_rate ||
        p->tdm_per_slot_padding_flag>1u ||
        p->frame_pulse_width>38u)
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
    put_config(d+28,2u,0u,P360_IPC3_FRAME_S24_4LE);
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
    put32(d+32,P360_IPC3_MEM_RAM|P360_IPC3_MEM_CACHE);
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
    put_config(d+28,0u,2u,P360_IPC3_FRAME_S24_4LE);
    put32(d+64,P360_IPC3_STREAM_PLAYBACK);
    put32(d+68,dai_index);
    put32(d+72,P360_IPC3_DAI_INTEL_SSP);
    put32(d+76,0u);
    out->bytes=P360_IPC3_DAI_NEW_BYTES;
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
