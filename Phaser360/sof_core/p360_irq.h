/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef P360_IRQ_H
#define P360_IRQ_H
#include <stdint.h>
#define P360_IRQ_IPC_TARGET 1u
#define P360_IRQ_IPC_INITIATOR 2u
struct p360_irq_event { uint64_t boot_epoch,sequence; uint32_t causes,hipct,hipcte,hipcie; };
struct p360_irq {
    uint64_t boot_epoch,sequence;
    uint32_t admitted,poisoned;
};
void p360_irq_init(struct p360_irq *irq);
int p360_irq_bind(struct p360_irq *irq,uint64_t epoch);
int p360_irq_capture(struct p360_irq *irq,uint32_t adspis,uint32_t hipct,uint32_t hipcte,uint32_t hipcie,struct p360_irq_event *out);
void p360_irq_poison(struct p360_irq *irq);
void p360_irq_stop(struct p360_irq *irq);
#endif
