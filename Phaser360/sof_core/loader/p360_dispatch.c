/* SPDX-License-Identifier: BSD-3-Clause */
#include "p360_dispatch.h"
#include "p360_loader.h"
static uint32_t U32(const uint8_t *p)
{return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static int Fail(struct p360_dispatch *d)
{d->poisoned=1;d->active=0;d->ipc.state=P360_IPC_POISONED;return -1;}
static int TopologyNewCommand(uint32_t command)
{
    return command==0x30010000u || /* COMP_NEW */
        command==0x30100000u ||    /* PIPE_NEW */
        command==0x30200000u;      /* BUFFER_NEW */
}
int p360_dispatch_prepare(struct p360_dispatch *d,const uint8_t *image,
    size_t bytes,uint32_t mapped_bytes)
{
    struct p360_fw_view view;const uint8_t *up,*down,*stream;
    if(!d || d->prepared || d->active || d->poisoned || d->ipc.boot_epoch ||
        mapped_bytes<P360_DISPATCH_MAP_BYTES || p360_fw_validate(image,bytes,&view)) return -1;
    /* Pinned XMan element type1 at0x10; ext window type1, fixed7 descriptors.
     * sof_ipc_window_elem.hdr.size is zero in this image (not sizeof(elem)). */
    if(U32(image+0x10)!=1 || U32(image+0x14)!=0x1a0 ||
       U32(image+0x18)!=0x190 || U32(image+0x1c)!=0x70000000 ||
       U32(image+0x20)!=1 || U32(image+0x24)!=7) return -1;
    up=image+0x40;down=image+0x58;stream=image+0xa0;
    if(U32(up)!=0 || U32(up+4)!=1 || U32(up+8)!=0 || U32(up+12)!=0 ||
       U32(up+16)!=0x1000 || U32(up+20)!=0x1000 ||
       U32(down)!=0 || U32(down+4)!=0 || U32(down+8)!=1 || U32(down+12)!=0 ||
       U32(down+16)!=0x2000 || U32(down+20)!=0 ||
       U32(stream)!=0 || U32(stream+4)!=4 || U32(stream+8)!=2 || U32(stream+12)!=0 ||
       U32(stream+16)!=0x1000 || U32(stream+20)!=0x1000) return -1;
    p360_ipc_init(&d->ipc);d->prepared=1;return 0;
}
int p360_dispatch_bind(struct p360_dispatch *d,uint64_t epoch)
{
    if(!d || !d->prepared || d->active || d->poisoned ||
        p360_ipc_new_proved_boot(&d->ipc,epoch)) return -1;
    d->sequence=0;d->stream_id=0;d->positions=0;
    d->expected_reply_bytes=0;d->expected_reply_cmd=0;
    d->expected_comp_id=0;d->expected_generic=0;
    d->active=1;return 0;
}
int p360_dispatch_stream(struct p360_dispatch *d,uint32_t id)
{
    if(!d || !d->active || d->poisoned || d->ipc.state!=P360_IPC_IDLE ||
       d->stream_id || !id || id>0xffff) return -1;
    d->stream_id=id;return 0;
}
int p360_dispatch_expect(struct p360_dispatch *d,uint64_t now,uint32_t timeout_ms)
{
    uint64_t generation;
    if(!d || !d->active || d->poisoned) return -1;
    d->expected_reply_bytes=12u;
    d->expected_reply_cmd=0x10000000u;
    d->expected_comp_id=0;
    d->expected_generic=1;
    {int rc=p360_ipc_begin(&d->ipc,now,timeout_ms,&generation);
     if(rc) {
        d->expected_reply_bytes=0;d->expected_reply_cmd=0;
        d->expected_comp_id=0;d->expected_generic=0;
     }
     if(d->ipc.state==P360_IPC_POISONED) return Fail(d);
     return rc;}
}
int p360_dispatch_expect_message(struct p360_dispatch *d,uint64_t now,
    uint32_t timeout_ms,const uint8_t *message,uint32_t bytes)
{
    uint32_t command,comp_id=0;
    uint64_t generation;
    int rc;

    if(!d || !d->active || d->poisoned || !message ||
       bytes<8u || (bytes&3u) || U32(message)!=bytes)
        return -1;

    command=U32(message+4);
    if(command==0x60010000u || TopologyNewCommand(command)) {
        if(bytes<12u) return -1;
        comp_id=U32(message+8);
        if(!comp_id) return -1;
        d->expected_reply_bytes=20u;
        d->expected_reply_cmd=command;
        /* SOF 1.9.3 topology handlers zero-initialize id/offset in their
         * sof_ipc_comp_reply. PCM_PARAMS instead echoes comp_id. */
        d->expected_comp_id=command==0x60010000u ? comp_id : 0u;
        d->expected_generic=0;
    } else {
        d->expected_reply_bytes=12u;
        d->expected_reply_cmd=0x10000000u;
        d->expected_comp_id=0;
        d->expected_generic=1;
    }

    rc=p360_ipc_begin(&d->ipc,now,timeout_ms,&generation);
    if(rc) {
        d->expected_reply_bytes=0;d->expected_reply_cmd=0;
        d->expected_comp_id=0;d->expected_generic=0;
    }
    if(d->ipc.state==P360_IPC_POISONED) return Fail(d);
    return rc;
}
static int Stable(const struct p360_dispatch_io *io,void *ctx,uint32_t offset,
    uint8_t *out,uint32_t size)
{
    uint8_t other[76];uint32_t i;
    if(io->copy(ctx,offset,out,size) || io->copy(ctx,offset,other,size)) return -1;
    for(i=0;i<size;++i) if(out[i]!=other[i]) return -1;
    return U32(out)==size?0:-1;
}
static int ReadReply(const struct p360_dispatch_io *io,void *ctx,
    uint8_t reply[20],uint32_t *bytes)
{
    uint8_t header[12],other[12];uint32_t i,size;
    /* SOF 1.9.3 writes command replies back into the host request mailbox.
     * DSP_UPBOX contains FW_READY and unsolicited DSP messages instead. */
    if(io->copy(ctx,P360_HOST_DOWNBOX,header,sizeof(header)) ||
       io->copy(ctx,P360_HOST_DOWNBOX,other,sizeof(other))) return -1;
    for(i=0;i<sizeof(header);++i) if(header[i]!=other[i]) return -1;
    size=U32(header);
    if(size!=12u && size!=20u) return -1;
    if(Stable(io,ctx,P360_HOST_DOWNBOX,reply,size)) return -1;
    for(i=0;i<sizeof(header);++i) if(header[i]!=reply[i]) return -1;
    *bytes=size;return 0;
}
static int32_t Signed32(uint32_t value)
{
    return value<=INT32_MAX ? (int32_t)value :
        -1-(int32_t)(UINT32_MAX-value);
}
static int CompleteStructured(struct p360_ipc *ipc,const uint8_t *reply,
    uint32_t bytes)
{
    if(!ipc || !reply || ipc->state!=P360_IPC_PENDING ||
       bytes<12u || bytes>384u || U32(reply)!=bytes)
        return -1;
    ipc->firmware_error=Signed32(U32(reply+8));
    ipc->reply_bytes=bytes;
    ipc->state=P360_IPC_COMPLETE;
    return 0;
}
int p360_dispatch_process(struct p360_dispatch *d,const struct p360_irq_event *e,
    const struct p360_dispatch_io *io,void *ctx)
{
    uint8_t reply[20],position[76];struct p360_ipc next;uint64_t now;uint32_t i;
    struct p360_irq_event captured;uint32_t causes,reply_bytes=0;
    uint64_t sequence;int generic_reply=0;
    if(!d || !e || !io || !io->copy || !io->finish || !io->now) return -1;
    if(!d->active || d->poisoned) return -1;
    /* Keep validated event metadata stable across external callbacks. In
     * particular Finish cannot introduce a cause whose buffer was not read. */
    captured=*e;e=&captured;causes=e->causes;sequence=e->sequence;
    if(e->epoch!=d->ipc.boot_epoch || !e->sequence || e->sequence<=d->sequence ||
       !e->causes || e->causes>3 || e->hipci==UINT32_MAX || e->hipcie==UINT32_MAX ||
       e->hipct==UINT32_MAX || e->hipcte==UINT32_MAX ||
       !!(e->causes&1)!=!!(e->hipcie&0x40000000u) ||
       !!(e->causes&2)!=!!(e->hipct&0x80000000u)) return Fail(d);
    if(d->ipc.state==P360_IPC_POISONED) return Fail(d);
    now=io->now(ctx);next=d->ipc;
    if(p360_ipc_expire(&next,now)) return Fail(d);
    if(causes&1) {
        if(next.state!=P360_IPC_PENDING ||
           (d->expected_reply_bytes!=12u && d->expected_reply_bytes!=20u) ||
           !d->expected_reply_cmd || ReadReply(io,ctx,reply,&reply_bytes))
            return Fail(d);

        generic_reply=reply_bytes==12u && U32(reply+4)==0x10000000u;
        if(generic_reply) {
            /* Structured commands still return a generic negative reply on
             * firmware failure. A generic success cannot replace payload. */
            if(!d->expected_generic && Signed32(U32(reply+8))>=0)
                return Fail(d);
        } else {
            if(d->expected_generic || reply_bytes!=20u ||
               d->expected_reply_bytes!=20u ||
               U32(reply+4)!=d->expected_reply_cmd ||
               (d->expected_reply_cmd!=0x60010000u &&
                !TopologyNewCommand(d->expected_reply_cmd)) ||
               U32(reply+8)!=0 || U32(reply+12)!=d->expected_comp_id)
                return Fail(d);
            if(TopologyNewCommand(d->expected_reply_cmd) && U32(reply+16)!=0)
                return Fail(d);
        }
    }
    if(causes&2) {
        if(!d->stream_id || d->positions==UINT32_MAX || e->hipcte!=0 ||
           (e->hipct&0x7fffffffu)!=(0x600a0000u|d->stream_id) ||
           Stable(io,ctx,P360_STREAM_BOX,position,76) ||
           U32(position+4)!=(0x600a0000u|d->stream_id) ||
           U32(position+8)!=0 || U32(position+12)!=d->stream_id ||
           (U32(position+16)&~0x000f0f0fu) || U32(position+68)!=0 || U32(position+72)!=0)
            return Fail(d);
    }
    /* Validate both causes before ANY ACK. Recheck deadline after SRAM copies.
     * Generation is pending HOST metadata, not inferred firmware correlation. */
    now=io->now(ctx);
    if(p360_ipc_expire(&next,now)) return Fail(d);
    if(causes&1) {
        if(generic_reply) {
            if(p360_ipc_complete(&next,e->epoch,next.generation,now,
                    reply,reply_bytes))
                return Fail(d);
        } else {
            if(CompleteStructured(&next,reply,reply_bytes))
                return Fail(d);
        }
    }
    if(io->finish(ctx,e)) return Fail(d);
    d->ipc=next;d->sequence=sequence;
    if(causes&1) {
        d->expected_reply_bytes=0;d->expected_reply_cmd=0;
        d->expected_comp_id=0;d->expected_generic=0;
    }
    if(causes&2) {for(i=0;i<76;++i) d->position[i]=position[i];++d->positions;}
    return 0;
}
void p360_dispatch_stop(struct p360_dispatch *d)
{if(d) {d->active=0;p360_ipc_stop(&d->ipc);}}
