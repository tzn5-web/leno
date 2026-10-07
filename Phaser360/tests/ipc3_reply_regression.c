/* SPDX-License-Identifier: BSD-3-Clause */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../sof_core/loader/p360_dispatch.h"
#include "../sof_core/loader/p360_ipc3_tx.h"
#include "../sof_core/loader/p360_ipc3_topology.h"
#include "../include/p360_board.h"

struct mock {
    uint8_t reply[216];
    uint32_t reply_bytes;
    uint64_t now;
    unsigned finishes;
};

static void put32(uint8_t *p,uint32_t v)
{
    p[0]=(uint8_t)v;
    p[1]=(uint8_t)(v>>8);
    p[2]=(uint8_t)(v>>16);
    p[3]=(uint8_t)(v>>24);
}

static int cp(void *ctx,uint32_t off,uint8_t *out,uint32_t bytes)
{
    struct mock *m=(struct mock *)ctx;
    if(off!=P360_DSP_UPBOX || bytes!=m->reply_bytes)
        return -1;
    memcpy(out,m->reply,bytes);
    return 0;
}

static int finish(void *ctx,const struct p360_irq_event *event)
{
    struct mock *m=(struct mock *)ctx;
    assert(event->causes==1u);
    ++m->finishes;
    return 0;
}

static uint64_t now(void *ctx)
{
    return ((struct mock *)ctx)->now;
}

static const struct p360_dispatch_io io={cp,finish,now};

static void ready(struct p360_dispatch *d)
{
    memset(d,0,sizeof(*d));
    p360_ipc_init(&d->ipc);
    assert(p360_ipc_new_proved_boot(&d->ipc,9u)==0);
    d->prepared=1;
    d->active=1;
}

static struct p360_irq_event reply_event(uint64_t sequence)
{
    struct p360_irq_event e;
    memset(&e,0,sizeof(e));
    e.epoch=9u;
    e.sequence=sequence;
    e.causes=1u;
    e.hipcie=0x40000000u;
    return e;
}

int main(void)
{
    struct p360_dispatch d;
    struct p360_irq_event e;
    const struct p360_ipc3_speaker_ids ids={1u,100u,101u,102u,103u};
    struct p360_ipc3_message pcm;
    struct p360_ipc3_message tone;
    struct p360_ipc3_message tone_control;
    struct mock m;
    uint8_t proof[8];
    int32_t error;
    uint32_t bytes;

    memset(&m,0,sizeof(m));
    m.now=200u;
    ready(&d);
    assert(p360_ipc3_build_proof(proof)==0);
    assert(p360_dispatch_expect_message(
        &d,100u,100u,proof,sizeof(proof))==0);
    assert(d.expected_generic==1);
    assert(d.expected_reply_bytes==12u);
    assert(d.expected_reply_cmd==0x10000000u);

    m.reply_bytes=12u;
    put32(m.reply,12u);
    put32(m.reply+4,0x10000000u);
    put32(m.reply+8,0u);
    e=reply_event(1u);
    assert(p360_dispatch_process(&d,&e,&io,&m)==0);
    assert(m.finishes==1u);
    assert(p360_ipc_consume(&d.ipc,&error,&bytes)==0);
    assert(error==0 && bytes==12u);
    assert(d.expected_reply_bytes==0u);

    memset(&m,0,sizeof(m));
    m.now=250u;
    ready(&d);
    assert(p360_ipc3_build_tone_new(&tone,&ids,P360_SAMPLE_RATE)==0);
    assert(p360_dispatch_expect_message(
        &d,150u,100u,tone.data,tone.bytes)==0);
    assert(d.expected_generic==0);
    assert(d.expected_reply_bytes==20u);
    assert(d.expected_reply_cmd==0x30010000u);
    assert(d.expected_comp_id==ids.tone_id);
    m.reply_bytes=20u;
    put32(m.reply,20u);
    put32(m.reply+4,0x30010000u);
    put32(m.reply+8,0u);
    put32(m.reply+12,ids.tone_id);
    put32(m.reply+16,0u);
    e=reply_event(1u);
    assert(p360_dispatch_process(&d,&e,&io,&m)==0);
    assert(p360_ipc_consume(&d.ipc,&error,&bytes)==0);
    assert(error==0 && bytes==20u);

    memset(&m,0,sizeof(m));
    m.now=275u;
    ready(&d);
    assert(p360_ipc3_build_tone_amplitude_control(
        &tone_control,ids.tone_id,0x01000000)==0);
    assert(p360_dispatch_expect_message(
        &d,175u,100u,tone_control.data,tone_control.bytes)==0);
    assert(d.expected_generic==0);
    assert(d.expected_reply_bytes==140u);
    assert(d.expected_reply_cmd==0x50030000u);
    assert(d.expected_comp_id==ids.tone_id);

    m.reply_bytes=140u;
    memcpy(m.reply,tone_control.data,tone_control.bytes);
    put32(m.reply+8,0u);
    e=reply_event(1u);
    assert(p360_dispatch_process(&d,&e,&io,&m)==0);
    assert(p360_ipc_consume(&d.ipc,&error,&bytes)==0);
    assert(error==0 && bytes==140u);

    memset(&m,0,sizeof(m));
    m.now=300u;
    ready(&d);
    assert(p360_ipc3_build_pcm_params(
        &pcm,100u,P360_SAMPLE_RATE,P360_SPEAKER_CHANNELS)==0);
    assert(p360_dispatch_expect_message(
        &d,200u,100u,pcm.data,pcm.bytes)==0);
    assert(d.expected_generic==0);
    assert(d.expected_reply_bytes==20u);
    assert(d.expected_reply_cmd==0x60010000u);
    assert(d.expected_comp_id==100u);

    m.reply_bytes=20u;
    put32(m.reply,20u);
    put32(m.reply+4,0x60010000u);
    put32(m.reply+8,0u);
    put32(m.reply+12,100u);
    put32(m.reply+16,0x1234u);
    e=reply_event(1u);
    assert(p360_dispatch_process(&d,&e,&io,&m)==0);
    assert(p360_ipc_consume(&d.ipc,&error,&bytes)==0);
    assert(error==0 && bytes==20u);

    memset(&m,0,sizeof(m));
    m.now=400u;
    ready(&d);
    assert(p360_dispatch_expect_message(
        &d,300u,100u,pcm.data,pcm.bytes)==0);
    m.reply_bytes=20u;
    put32(m.reply,20u);
    put32(m.reply+4,0x60010000u);
    put32(m.reply+8,0u);
    put32(m.reply+12,101u); /* wrong component */
    put32(m.reply+16,0u);
    e=reply_event(1u);
    assert(p360_dispatch_process(&d,&e,&io,&m)!=0);
    assert(d.poisoned && d.ipc.state==P360_IPC_POISONED);

    puts("IPC3 reply dispatcher regression: PASS");
    return 0;
}
