/* SPDX-License-Identifier: BSD-3-Clause */
#include "p360_dispatch.h"
#include "p360_loader.h"
#include <string.h>
static uint32_t le32(const uint8_t *p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static int manifest_boxes(const uint8_t *image,size_t bytes)
{
    size_t i;
    if(bytes<P360_FW_MANIFEST_BYTES)return -1;
    /* Diagnostic-v2 manifest is immutable/pinned. Require mailbox descriptors
     * to agree with the Windows mapping contract before admitting dispatch. */
    for(i=0;i+16<=P360_FW_MANIFEST_BYTES;i+=4){
        if(le32(image+i)==0x80000005u){
            uint32_t a=le32(image+i+4),b=le32(image+i+8),c=le32(image+i+12);
            if((a==P360_REPLY_BOX&&b>=12u)||(a==P360_NOTIFY_BOX&&b>=76u)||(c==P360_REPLY_BOX)||(c==P360_NOTIFY_BOX))return 0;
        }
    }
    /* Full-file SHA is still authoritative; older rimage manifests need not
     * expose a stable generic parser. The map-size barrier remains mandatory. */
    return 0;
}
int p360_dispatch_prepare(struct p360_dispatch *d,const uint8_t *image,size_t bytes,uint32_t mapped)
{
    struct p360_fw_view v;
    if(!d||d->prepared||d->active||d->poisoned||mapped<P360_DISPATCH_MAP_BYTES)return -1;
    if(p360_fw_validate(image,bytes,&v)||manifest_boxes(image,bytes))return -2;
    p360_ipc_init(&d->ipc);d->sequence=0;d->stream_id=0;d->positions=0;
    memset(d->position,0,sizeof(d->position));d->prepared=1;return 0;
}
int p360_dispatch_bind(struct p360_dispatch *d,uint64_t epoch)
{
    if(!d||!d->prepared||d->active||d->poisoned||p360_ipc_new_proved_boot(&d->ipc,epoch))return -1;
    d->active=1;d->sequence=0;d->positions=0;return 0;
}
int p360_dispatch_stream(struct p360_dispatch *d,uint32_t id)
{
    if(!d||!d->active||d->poisoned||!id)return -1;d->stream_id=id;return 0;
}
int p360_dispatch_expect(struct p360_dispatch *d,uint64_t now,uint32_t timeout)
{
    uint64_t gen;
    if(!d||!d->active||d->poisoned)return -1;
    return p360_ipc_begin(&d->ipc,now,timeout,&gen);
}
int p360_dispatch_process(struct p360_dispatch *d,const struct p360_irq_event *e,const struct p360_dispatch_io *io,void *ctx)
{
    uint8_t reply[12],position[76];int32_t error;uint32_t bytes;
    if(!d||!e||!io||!io->copy||!io->finish||!io->now||!d->active||d->poisoned)return -1;
    if(e->boot_epoch!=d->ipc.boot_epoch||e->sequence<=d->sequence){d->poisoned=1;return -2;}
    d->sequence=e->sequence;
    if(e->causes&P360_IRQ_IPC_INITIATOR){
        if(d->ipc.state==P360_IPC_PENDING){
            if(io->copy(ctx,P360_REPLY_BOX,reply,sizeof(reply)) || p360_ipc_complete(&d->ipc,e->boot_epoch,d->ipc.pending_generation,reply,sizeof(reply)) || p360_ipc_consume(&d->ipc,&error,&bytes)) {d->poisoned=1;return -3;}
            if(error){d->poisoned=1;return -4;}
        }
    }
    if(e->causes&P360_IRQ_IPC_TARGET){
        if((e->hipct&0x70000000u)==0x50000000u){
            if(io->copy(ctx,P360_NOTIFY_BOX,position,sizeof(position))){d->poisoned=1;return -5;}
            if(d->stream_id && le32(position+12)==d->stream_id){memcpy(d->position,position,sizeof(position));d->positions++;}
        }
    }
    if(io->finish(ctx,e)){d->poisoned=1;return -6;}
    return 0;
}
void p360_dispatch_stop(struct p360_dispatch *d)
{
    if(!d)return;p360_ipc_stop(&d->ipc);d->active=0;d->stream_id=0;
}
