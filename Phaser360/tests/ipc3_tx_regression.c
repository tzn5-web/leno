/* SPDX-License-Identifier: BSD-3-Clause */
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "../sof_core/loader/p360_ipc3_tx.h"

struct mock {
    uint32_t hipci, hipcie, hipct;
    uint64_t now;
    unsigned reads, box_writes, reg_writes, barriers;
    uint32_t box_offset, box_bytes, reg_offset, reg_value;
    uint8_t box[384];
    int fail_box, fail_reg;
    char order[32];
    unsigned order_len;
};

static void mark(struct mock *m,char c)
{
    assert(m->order_len + 1u < sizeof(m->order));
    m->order[m->order_len++]=c;
    m->order[m->order_len]=0;
}

static int rd(void *ctx,uint32_t off,uint32_t *v)
{
    struct mock *m=(struct mock *)ctx;
    mark(m,'r');
    ++m->reads;
    if(off==P360_DSP_HIPCI)*v=m->hipci;
    else if(off==P360_DSP_HIPCIE)*v=m->hipcie;
    else if(off==P360_DSP_HIPCT)*v=m->hipct;
    else return -1;
    return 0;
}

static int wr(void *ctx,uint32_t off,uint32_t v)
{
    struct mock *m=(struct mock *)ctx;
    mark(m,'d');
    ++m->reg_writes;
    m->reg_offset=off;
    m->reg_value=v;
    return m->fail_reg ? -1 : 0;
}

static int box(void *ctx,uint32_t off,const uint8_t *data,uint32_t bytes)
{
    struct mock *m=(struct mock *)ctx;
    mark(m,'m');
    ++m->box_writes;
    m->box_offset=off;
    m->box_bytes=bytes;
    if(bytes>sizeof(m->box))
        return -1;
    memcpy(m->box,data,bytes);
    return m->fail_box ? -1 : 0;
}

static uint64_t get_now(void *ctx)
{
    struct mock *m=(struct mock *)ctx;
    mark(m,'n');
    return m->now;
}

static void barrier(void *ctx)
{
    struct mock *m=(struct mock *)ctx;
    mark(m,'b');
    ++m->barriers;
}

static const struct p360_ipc3_tx_io io={
    rd,wr,box,get_now,barrier
};

static void ready(struct p360_dispatch *d)
{
    memset(d,0,sizeof(*d));
    p360_ipc_init(&d->ipc);
    assert(p360_ipc_new_proved_boot(&d->ipc,9)==0);
    d->active=1;
}

int main(void)
{
    struct p360_dispatch d;
    struct p360_ipc3_tx_result out;
    struct mock m;
    uint8_t msg[8];

    assert(p360_ipc3_build_proof(msg)==P360_IPC3_TX_OK);
    assert(msg[0]==8 && msg[1]==0 && msg[2]==0 && msg[3]==0);
    assert(msg[4]==0 && msg[5]==0 && msg[6]==0 && msg[7]==0xe0);

    memset(&m,0,sizeof(m));
    m.now=1000;
    ready(&d);
    assert(p360_ipc3_tx_begin(&d,&io,&m,msg,sizeof(msg),100,&out)==P360_IPC3_TX_OK);
    assert(out.generation==1);
    assert(out.mailbox_written && out.doorbell_written && !out.poison_required);
    assert(d.ipc.state==P360_IPC_PENDING);
    assert(m.box_offset==P360_REPLY_BOX && m.box_bytes==sizeof(msg));
    assert(memcmp(m.box,msg,sizeof(msg))==0);
    assert(m.reg_offset==P360_DSP_HIPCI && m.reg_value==P360_HIPCI_BUSY);
    assert(strcmp(m.order,"rrrnmbdb")==0);
    assert(m.reads==3 && m.box_writes==1 && m.reg_writes==1 && m.barriers==2);

    memset(&m,0,sizeof(m));
    m.hipci=P360_HIPCI_BUSY;
    ready(&d);
    assert(p360_ipc3_tx_begin(&d,&io,&m,msg,sizeof(msg),100,&out)==P360_IPC3_TX_PENDING);
    assert(d.ipc.state==P360_IPC_IDLE);
    assert(m.box_writes==0 && m.reg_writes==0);

    memset(&m,0,sizeof(m));
    m.now=2000;
    m.fail_box=1;
    ready(&d);
    assert(p360_ipc3_tx_begin(&d,&io,&m,msg,sizeof(msg),100,&out)==P360_IPC3_TX_MAILBOX);
    assert(d.ipc.state==P360_IPC_OFFLINE);
    assert(out.mailbox_written==0 && out.doorbell_written==0);

    memset(&m,0,sizeof(m));
    m.now=3000;
    m.fail_reg=1;
    ready(&d);
    assert(p360_ipc3_tx_begin(&d,&io,&m,msg,sizeof(msg),100,&out)==P360_IPC3_TX_DOORBELL);
    assert(d.ipc.state==P360_IPC_PENDING);
    assert(out.mailbox_written && out.doorbell_written && out.poison_required);

    memset(&m,0,sizeof(m));
    ready(&d);
    assert(p360_ipc3_tx_begin(&d,&io,&m,msg,4,100,&out)==P360_IPC3_TX_ARGUMENT);
    assert(d.ipc.state==P360_IPC_IDLE);

    return 0;
}
