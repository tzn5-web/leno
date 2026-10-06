/* SPDX-License-Identifier: BSD-3-Clause */
#include "p360_irq.h"
#define BUSY 0x80000000u
#define DONE 0x40000000u
void p360_irq_init(struct p360_irq *irq)
{
    if(irq){irq->boot_epoch=0;irq->sequence=0;irq->admitted=0;irq->poisoned=0;}
}
int p360_irq_bind(struct p360_irq *irq,uint64_t epoch)
{
    if(!irq||!epoch||irq->admitted||irq->poisoned||epoch<=irq->boot_epoch)return -1;
    irq->boot_epoch=epoch;irq->sequence=0;irq->admitted=1;return 0;
}
int p360_irq_capture(struct p360_irq *irq,uint32_t adspis,uint32_t hipct,uint32_t hipcte,uint32_t hipcie,struct p360_irq_event *out)
{
    uint32_t causes=0;
    if(!irq||!out||!irq->admitted||irq->poisoned||!irq->boot_epoch)return 0;
    if((adspis&1u) && (hipct&BUSY))causes|=P360_IRQ_IPC_TARGET;
    if((adspis&1u) && (hipcie&DONE))causes|=P360_IRQ_IPC_INITIATOR;
    if(!causes)return 0;
    out->boot_epoch=irq->boot_epoch;out->sequence=++irq->sequence;out->causes=causes;
    out->hipct=hipct;out->hipcte=hipcte;out->hipcie=hipcie;return 1;
}
void p360_irq_poison(struct p360_irq *irq){if(irq){irq->poisoned=1;irq->admitted=0;}}
void p360_irq_stop(struct p360_irq *irq){if(irq){irq->admitted=0;irq->boot_epoch=0;}}
