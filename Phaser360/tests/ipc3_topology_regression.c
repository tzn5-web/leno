#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../sof_core/loader/p360_ipc3_topology.h"
#include "../include/p360_board.h"

static uint32_t u32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1]<<8) |
        ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}

int main(void)
{
    const struct p360_ipc3_speaker_ids ids={1u,100u,101u,102u,103u};
    struct p360_ipc3_ssp1_profile ssp={
        .format=P360_IPC3_DAI_FMT_I2S|P360_IPC3_DAI_FMT_NB_NF|
            P360_IPC3_DAI_FMT_CBC_CFC,
        .mclk_id=P360_SPEAKER_SSP1_MCLK_ID,
        .mclk_rate=P360_SPEAKER_SSP1_MCLK_HZ,
        .fsync_rate=P360_SAMPLE_RATE,
        .bclk_rate=P360_SPEAKER_SSP1_BCLK_HZ,
        .tdm_slots=P360_SPEAKER_CHANNELS,
        .rx_slots=3u,
        .tx_slots=3u,
        .sample_valid_bits=P360_SPEAKER_DAI_VALID_BITS,
        .tdm_slot_width=P360_SPEAKER_DAI_SLOT_BITS,
        .mclk_direction=P360_IPC3_MCLK_CODEC_INPUT,
        .frame_pulse_width=0u,
        .tdm_per_slot_padding_flag=0u,
        .clks_control=0u,
        .quirks=0u,
        .bclk_delay=0u,
        .group_id=0u,
        .flags=0u
    };
    struct p360_ipc3_message m;

    assert(p360_ipc3_speaker_ids_validate(&ids)==0);
    assert(p360_ipc3_build_tone_new(&m,&ids,48000u)==0);
    assert(m.bytes==100u && u32(m.data)==100u);
    assert(u32(m.data+4)==0x30010000u);
    assert(u32(m.data+8)==100u && u32(m.data+12)==10u);
    assert(u32(m.data+16)==1u && u32(m.data+28)==36u);
    assert(u32(m.data+48)==P360_IPC3_FRAME_S32_LE);
    assert(u32(m.data+64)==48000u);
    for (size_t i=68;i<100;i+=4)
        assert(u32(m.data+i)==0u);

    assert(p360_ipc3_build_buffer_new(&m,&ids,768u)==0);
    assert(m.bytes==44u && u32(m.data+12)==12u);
    assert(u32(m.data+28)==768u && u32(m.data+32)==113u);

    assert(p360_ipc3_build_dai_new(&m,&ids,1u)==0);
    assert(m.bytes==80u && u32(m.data+12)==2u);
    assert(u32(m.data+48)==P360_IPC3_FRAME_S16_LE);
    assert(u32(m.data+64)==0u && u32(m.data+68)==1u);
    assert(u32(m.data+72)==1u);

    assert(p360_ipc3_build_pipe_new(&m,&ids,1000u,48u)==0);
    assert(m.bytes==48u && u32(m.data+4)==0x30100000u);
    assert(u32(m.data+8)==103u && u32(m.data+12)==1u);
    assert(u32(m.data+16)==100u && u32(m.data+24)==1000u);
    assert(u32(m.data+36)==48u && u32(m.data+44)==1u);

    assert(p360_ipc3_build_connect(&m,100u,101u)==0);
    assert(m.bytes==16u && u32(m.data+4)==0x30030000u);
    assert(u32(m.data+8)==100u && u32(m.data+12)==101u);

    assert(p360_ipc3_build_connect(&m,101u,102u)==0);
    assert(u32(m.data+8)==101u && u32(m.data+12)==102u);

    assert(p360_ipc3_build_pipe_complete(&m,&ids)==0);
    assert(m.bytes==12u && u32(m.data+4)==0x30130000u);
    assert(u32(m.data+8)==103u);

    assert(p360_ipc3_ssp1_profile_validate(&ssp)==0);
    assert(p360_ipc3_build_ssp1_config(&m,1u,&ssp)==0);
    assert(m.bytes==P360_IPC3_DAI_CONFIG_BYTES &&
        m.bytes==216u && u32(m.data+4)==0x80010000u);
    assert(u32(m.data+8)==1u && u32(m.data+12)==1u);
    assert(m.data[16]==0x01u && m.data[17]==0x40u);
    assert(m.data[58]==1u && m.data[59]==0u);
    assert(u32(m.data+60)==19200000u);
    assert(u32(m.data+64)==48000u);
    assert(u32(m.data+68)==1536000u);
    assert(u32(m.data+72)==2u && u32(m.data+76)==3u);
    assert(u32(m.data+80)==3u && u32(m.data+84)==16u);
    assert(m.data[88]==16u && m.data[89]==0u);
    assert(u32(m.data+92)==P360_IPC3_MCLK_CODEC_INPUT);
    for (size_t i=112;i<216;i++)
        assert(m.data[i]==0u);

    assert(p360_ipc3_build_tone_amplitude_control(
        &m,ids.tone_id,0x01000000)==0);
    assert(m.bytes==140u && u32(m.data)==140u);
    assert(u32(m.data+4)==0x50030000u);
    assert(u32(m.data+12)==ids.tone_id);
    assert(u32(m.data+16)==3u && u32(m.data+20)==1u);
    assert(u32(m.data+24)==1u && u32(m.data+56)==2u);
    assert(u32(m.data+92)==0x00464f53u);
    assert(u32(m.data+100)==16u && u32(m.data+104)==0x03014000u);
    assert(u32(m.data+124)==0u && u32(m.data+128)==0x01000000u);
    assert(u32(m.data+132)==1u && u32(m.data+136)==0x01000000u);
    assert(p360_ipc3_build_tone_amplitude_control(
        &m,ids.tone_id,0x0147ae15)!=0);

    assert(p360_ipc3_build_pcm_params(
        &m,ids.tone_id,P360_SAMPLE_RATE,P360_SPEAKER_CHANNELS)==0);
    assert(m.bytes==108u && u32(m.data)==108u);
    assert(u32(m.data+4)==0x60010000u);
    assert(u32(m.data+8)==ids.tone_id);
    assert(u32(m.data+24)==84u);
    assert(u32(m.data+28)==28u);
    assert(u32(m.data+36)==0u && u32(m.data+40)==0u);
    assert(u32(m.data+56)==P360_IPC3_STREAM_PLAYBACK);
    assert(u32(m.data+60)==P360_IPC3_FRAME_S32_LE);
    assert(u32(m.data+64)==P360_IPC3_BUFFER_INTERLEAVED);
    assert(u32(m.data+68)==48000u);
    assert(m.data[74]==2u && m.data[75]==0u);
    assert(m.data[76]==4u && m.data[78]==4u);
    assert(m.data[84]==1u && m.data[85]==0u);
    assert(m.data[92]==P360_IPC3_CHMAP_FL);
    assert(m.data[94]==P360_IPC3_CHMAP_FR);

    assert(p360_ipc3_build_stream_trigger(&m,100u,1)==0);
    assert(m.bytes==12u && u32(m.data+4)==0x60040000u);
    assert(u32(m.data+8)==100u);
    assert(p360_ipc3_build_stream_trigger(&m,100u,0)==0);
    assert(u32(m.data+4)==0x60050000u);

    ssp.bclk_rate=3072000u;
    assert(p360_ipc3_ssp1_profile_validate(&ssp)!=0);
    assert(p360_ipc3_build_ssp1_config(&m,1u,&ssp)!=0);

    {
        struct p360_ipc3_speaker_ids bad=ids;
        bad.dai_id=bad.tone_id;
        assert(p360_ipc3_speaker_ids_validate(&bad)!=0);
        assert(p360_ipc3_build_tone_new(&m,&bad,48000u)!=0);
    }

    puts("IPC3 speaker topology builder regression: PASS");
    return 0;
}
