/* SPDX-License-Identifier: BSD-3-Clause
 * Bounded PCI parser and serialized IPC lifecycle; no hardware operations.
 */
#include "p360_transport_core.h"
static uint32_t p360_u32(const uint8_t *p)
{
    return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);
}
int p360_range_valid(uint64_t base,uint64_t length,uint64_t required)
{
    return base && length>=required && base<=UINT64_MAX-length;
}
int p360_pci_validate(const uint8_t *c,size_t bytes,struct p360_pci_identity *out)
{
    uint32_t classrev;
    if (!c || !out || bytes<0x28) return -1;
    out->vendor=(uint16_t)(c[0]|((uint16_t)c[1]<<8));
    out->device=(uint16_t)(c[2]|((uint16_t)c[3]<<8));
    classrev=p360_u32(c+8);out->revision=(uint8_t)(classrev&0xffu);
    if(out->vendor!=0x8086u || out->device!=0x3198u || ((classrev>>8)&0xffffffu)!=0x040100u)
        return -2;
    /* Gemini Lake HDA BAR0 and DSP BAR4 are 64-bit memory BARs. */
    if((p360_u32(c+0x10)&0x7u)!=0x4u || (p360_u32(c+0x20)&0x7u)!=0x4u) return -3;
    out->hda_bar=0;out->dsp_bar=4;return 0;
}
void p360_ipc_init(struct p360_ipc *ipc)
{
    if(!ipc) return;
    ipc->state=P360_IPC_OFFLINE; ipc->boot_epoch=0; ipc->generation=0;
    ipc->pending_generation=0;ipc->deadline_100ns=0;ipc->reply_error=0;ipc->reply_bytes=0;
}
int p360_ipc_new_proved_boot(struct p360_ipc *ipc,uint64_t epoch)
{
    if(!ipc || !epoch || epoch<=ipc->boot_epoch || ipc->state==P360_IPC_PENDING)
        return -1;
    /* Hardware caller must first quiesce ISR/DPC/DMA and prove a fresh boot.
     * No recovery/rebind is permitted after poison. */
    if(ipc->state==P360_IPC_POISONED) return -2;
    ipc->boot_epoch=epoch;ipc->pending_generation=0;ipc->deadline_100ns=0;
    ipc->reply_error=0;ipc->reply_bytes=0;ipc->state=P360_IPC_IDLE;
    return 0;
}
int p360_ipc_begin(struct p360_ipc *ipc,uint64_t now,uint32_t timeout_ms,uint64_t *gen)
{
    uint64_t delta;
    if(!ipc || !gen || ipc->state!=P360_IPC_IDLE || !timeout_ms || timeout_ms>400)
        return -1;
    delta=(uint64_t)timeout_ms*10000u;
    if(now>UINT64_MAX-delta) {
        ipc->state=P360_IPC_POISONED; return -2;
    }
    ipc->reply_error=0;ipc->reply_bytes=0;
    ipc->pending_generation=++ipc->generation;ipc->deadline_100ns=now+delta;
    *gen=ipc->generation;ipc->state=P360_IPC_PENDING;
    return 0;
}
int p360_ipc_expire(struct p360_ipc *ipc,uint64_t now)
{
    if(!ipc || ipc->state!=P360_IPC_PENDING) return 0;
    if(now<ipc->deadline_100ns) return 0;
    ipc->state=P360_IPC_POISONED; return 1;
}
int p360_ipc_complete(struct p360_ipc *ipc,uint64_t epoch,uint64_t gen,
    const uint8_t *reply,size_t bytes)
{
    uint32_t word;
    if(!ipc || ipc->state!=P360_IPC_PENDING || epoch!=ipc->boot_epoch ||
        gen!=ipc->pending_generation || !reply || bytes!=12u)
        return -1;
    word=p360_u32(reply);
    if((word&0xc0000000u)!=0xc0000000u) {
        ipc->state=P360_IPC_POISONED; return -3;
    }
    /* SOF IPC3 generic reply. Other reply formats require explicit future support. */
    if((p360_u32(reply+4)&0xffff0000u)!=0) {
        ipc->state=P360_IPC_POISONED; return -3;
    }
    ipc->reply_error=(int32_t)p360_u32(reply+8);
    ipc->reply_bytes=(uint32_t)bytes;ipc->state=P360_IPC_COMPLETE;
    return 0;
}
int p360_ipc_consume(struct p360_ipc *ipc,int32_t *error,uint32_t *bytes)
{
    if(!ipc || !error || !bytes || ipc->state!=P360_IPC_COMPLETE) return -1;
    *error=ipc->reply_error;*bytes=ipc->reply_bytes;
    ipc->reply_error=0;ipc->reply_bytes=0;ipc->deadline_100ns=0;
    ipc->state=P360_IPC_IDLE;
    return 0;
}
void p360_ipc_stop(struct p360_ipc *ipc)
{
    if(!ipc) return;
    ipc->state=P360_IPC_OFFLINE;ipc->deadline_100ns=0;
    ipc->pending_generation=0;ipc->reply_error=0;ipc->reply_bytes=0;
}
