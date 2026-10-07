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
    uint8_t reply[20];
    uint32_t reply_bytes;
    uint64_t now;
    unsigned finishes;
    unsigned copies;
    unsigned unstable_copy;
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
    if(off!=P360_HOST_DOWNBOX || bytes>m->reply_bytes || bytes>sizeof(m->reply))
        return -1;
    memcpy(out,m->reply,bytes);
    ++m->copies;
    if(m->unstable_copy==m->copies)
        out[8]^=1u;
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

static void reply(struct mock *m,uint32_t bytes,uint32_t command,
    uint32_t error,uint32_t id,uint32_t offset)
{
    memset(m,0,sizeof(*m));
    m->now=300u;
    m->reply_bytes=bytes;
    put32(m->reply,bytes);
    put32(m->reply+4,command);
    put32(m->reply+8,error);
    put32(m->reply+12,id);
    put32(m->reply+16,offset);
}

static void rejected(struct p360_dispatch *d,struct mock *m)
{
    struct p360_irq_event e=reply_event(1u);
    assert(p360_dispatch_process(d,&e,&io,m)!=0);
    assert(d->poisoned && d->ipc.state==P360_IPC_POISONED);
    assert(m->finishes==0u); /* malformed data must never be acknowledged */
}

int main(void)
{
    struct p360_dispatch d;
    struct p360_irq_event e;
    struct p360_ipc3_message pcm;
    struct p360_ipc3_message topology[4];
    const struct p360_ipc3_speaker_ids ids={1u,100u,101u,102u,103u};
    const uint32_t commands[4]={0x30010000u,0x30010000u,
        0x30200000u,0x30100000u};
    struct mock m;
    uint8_t proof[8];
    int32_t error;
    uint32_t bytes;
    unsigned i;

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
    assert(m.finishes==0u);

    assert(p360_ipc3_build_tone_new(&topology[0],&ids,48000u)==0);
    assert(p360_ipc3_build_dai_new(&topology[1],&ids,1u)==0);
    assert(p360_ipc3_build_buffer_new(&topology[2],&ids,768u)==0);
    assert(p360_ipc3_build_pipe_new(&topology[3],&ids,1000u,48u)==0);
    for(i=0;i<4u;++i) {
        ready(&d);
        assert(p360_dispatch_expect_message(&d,200u,100u,
            topology[i].data,topology[i].bytes)==0);
        assert(!d.expected_generic && d.expected_reply_bytes==20u);
        assert(d.expected_reply_cmd==commands[i]);
        assert(d.expected_comp_id==0u); /* pinned handler leaves this zero */
        reply(&m,20u,commands[i],0u,0u,0u);
        e=reply_event(1u);
        assert(p360_dispatch_process(&d,&e,&io,&m)==0);
        assert(m.finishes==1u);
        assert(p360_ipc_consume(&d.ipc,&error,&bytes)==0);
        assert(error==0 && bytes==20u && !d.poisoned);

        /* Failed NEW operations use the generic negative reply instead. */
        ready(&d);
        assert(p360_dispatch_expect_message(&d,200u,100u,
            topology[i].data,topology[i].bytes)==0);
        reply(&m,12u,0x10000000u,0xffffffedu,0u,0u); /* -ENODEV */
        assert(p360_dispatch_process(&d,&e,&io,&m)==0);
        assert(p360_ipc_consume(&d.ipc,&error,&bytes)==0);
        assert(error==-19 && bytes==12u && !d.poisoned);

        ready(&d);
        assert(p360_dispatch_expect_message(&d,200u,100u,
            topology[i].data,topology[i].bytes)==0);
        reply(&m,12u,0x10000000u,0u,0u,0u); /* lost structured payload */
        rejected(&d,&m);

        ready(&d);
        assert(p360_dispatch_expect_message(&d,200u,100u,
            topology[i].data,topology[i].bytes)==0);
        reply(&m,20u,0x60010000u,0u,0u,0u); /* unrelated reply */
        rejected(&d,&m);
    }

    ready(&d);
    assert(p360_dispatch_expect_message(&d,200u,100u,pcm.data,pcm.bytes)==0);
    reply(&m,12u,0x10000000u,0xffffffea,0u,0u); /* failed PCM_PARAMS */
    e=reply_event(1u);
    assert(p360_dispatch_process(&d,&e,&io,&m)==0);
    assert(p360_ipc_consume(&d.ipc,&error,&bytes)==0);
    assert(error==-22 && bytes==12u);

    ready(&d);
    assert(p360_dispatch_expect_message(&d,200u,100u,
        topology[0].data,topology[0].bytes)==0);
    reply(&m,20u,commands[0],0u,100u,0u); /* not pinned topology ABI */
    rejected(&d,&m);

    ready(&d);
    assert(p360_dispatch_expect_message(&d,200u,100u,
        topology[0].data,topology[0].bytes)==0);
    reply(&m,20u,commands[0],0u,0u,4u); /* reserved offset is nonzero */
    rejected(&d,&m);

    ready(&d);
    assert(p360_dispatch_expect_message(&d,200u,100u,pcm.data,pcm.bytes)==0);
    reply(&m,20u,0x60010000u,0u,100u,0u);
    put32(m.reply,24u); /* declared size cannot exceed the reply buffer */
    rejected(&d,&m);
    assert(m.copies==2u); /* only bounded headers read */

    ready(&d);
    assert(p360_dispatch_expect_message(&d,200u,100u,pcm.data,pcm.bytes)==0);
    reply(&m,20u,0x60010000u,0u,100u,0u);
    m.unstable_copy=2u;
    rejected(&d,&m);

    ready(&d);
    assert(p360_dispatch_expect_message(&d,200u,100u,pcm.data,pcm.bytes)==0);
    reply(&m,20u,0x60010000u,0u,100u,0u);
    m.unstable_copy=4u;
    rejected(&d,&m);

    puts("IPC3 reply dispatcher regression: PASS");
    return 0;
}
