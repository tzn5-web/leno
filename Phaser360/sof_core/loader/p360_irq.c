/* SPDX-License-Identifier: BSD-3-Clause */
#include "p360_irq.h"
void p360_irq_init(struct p360_irq *q) {struct p360_irq zero={0};if(q) *q=zero;}
void p360_irq_close(struct p360_irq *q)
{if(q) {q->accepting=0;q->head=0;q->count=0;}}
void p360_irq_poison(struct p360_irq *q)
{if(q) {p360_irq_close(q);q->poisoned=1;}}
int p360_irq_bind_boot(struct p360_irq *q,uint64_t epoch)
{
    if(!q || !epoch || epoch<=q->epoch || q->accepting || q->count || q->poisoned) return 1;
    q->epoch=epoch;q->sequence=0;q->head=0;q->accepting=1;return 0;
}
int p360_irq_capture(struct p360_irq *q,uint32_t adspis,uint32_t hipci,
    uint32_t hipcie,uint32_t hipct,uint32_t hipcte)
{
    struct p360_irq_event e;uint32_t causes=0;
    if(!q || !q->accepting) return q && q->poisoned?-1:0;
    if(adspis==UINT32_MAX) {p360_irq_poison(q);return -1;}
    if(!(adspis&1u)) return 0;
    if(hipci==UINT32_MAX || hipcie==UINT32_MAX || hipct==UINT32_MAX || hipcte==UINT32_MAX) {
        p360_irq_poison(q);return -1;
    }
    if(hipcie&0x40000000u) causes|=1u;
    if(hipct&0x80000000u) causes|=2u;
    if(!causes || q->count==P360_IRQ_DEPTH || q->sequence==UINT64_MAX) {
        p360_irq_poison(q);return -1;
    }
    e.epoch=q->epoch;e.sequence=++q->sequence;e.hipci=hipci;e.hipcie=hipcie;
    e.hipct=hipct;e.hipcte=hipcte;e.causes=causes;
    q->pending[(q->head+q->count)%P360_IRQ_DEPTH]=e;q->count++;return 1;
}
int p360_irq_take(struct p360_irq *q,uint64_t epoch,struct p360_irq_event *out)
{
    struct p360_irq_event zero={0};
    if(!out) return -1;
    *out=zero;
    if(!q) return -1;
    if(q->poisoned || epoch!=q->epoch) return -1;
    if(!q->accepting || !q->count) return 0;
    *out=q->pending[q->head];q->head=(q->head+1u)%P360_IRQ_DEPTH;q->count--;return 1;
}
