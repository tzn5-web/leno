#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../sof_core/loader/p360_ipc3_topology.h"

static uint32_t u32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1]<<8) |
        ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}

int main(void)
{
    const struct p360_ipc3_speaker_ids ids={1u,100u,101u,102u,103u};
    struct p360_ipc3_ssp1_profile ssp={
        P360_IPC3_DAI_FMT_I2S|P360_IPC3_DAI_FMT_NB_NF|
            P360_IPC3_DAI_FMT_CBC_CFC,
        0u,0u,48000u,3072000u,2u,3u,3u,24u,32u,
        0u,0u,0u,0u,0u,0u,0u,0u
    };
    struct p360_ipc3_message m;

    assert(p360_ipc3_speaker_ids_validate(&ids)==0);
    assert(p360_ipc3_build_tone_new(&m,&ids,48000u)==0);
    assert(m.bytes==100u && u32(m.data)==100u);
    assert(u32(m.data+4)==0x30010000u);
    assert(u32(m.data+8)==100u && u32(m.data+12)==10u);
    assert(u32(m.data+16)==1u && u32(m.data+28)==36u);
    assert(u32(m.data+48)==1u);
    assert(u32(m.data+64)==48000u);
    for (size_t i=68;i<100;i+=4)
        assert(u32(m.data+i)==0u);

    assert(p360_ipc3_build_buffer_new(&m,&ids,768u)==0);
    assert(m.bytes==44u && u32(m.data+12)==12u);
    assert(u32(m.data+28)==768u && u32(m.data+32)==65u);

    assert(p360_ipc3_build_dai_new(&m,&ids,1u)==0);
    assert(m.bytes==80u && u32(m.data+12)==2u);
    assert(u32(m.data+48)==1u);
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
    assert(m.bytes==112u && u32(m.data+4)==0x80010000u);
    assert(u32(m.data+8)==1u && u32(m.data+12)==1u);
    assert(m.data[16]==0x01u && m.data[17]==0x40u);
    assert(u32(m.data+64)==48000u);
    assert(u32(m.data+68)==3072000u);
    assert(u32(m.data+72)==2u && u32(m.data+76)==3u);
    assert(u32(m.data+80)==3u && u32(m.data+84)==24u);
    assert(m.data[88]==32u && m.data[89]==0u);

    assert(p360_ipc3_build_stream_trigger(&m,100u,1)==0);
    assert(m.bytes==12u && u32(m.data+4)==0x60040000u);
    assert(u32(m.data+8)==100u);
    assert(p360_ipc3_build_stream_trigger(&m,100u,0)==0);
    assert(u32(m.data+4)==0x60050000u);

    ssp.bclk_rate=1536000u;
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
