/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef P360_IRQ_H
#define P360_IRQ_H
#include <stdint.h>
#define P360_IRQ_DEPTH 8u
struct p360_irq_event {
    uint64_t epoch,sequence;
    uint32_t hipci,hipcie,hipct,hipcte,causes;
};
struct p360_irq {
    struct p360_irq_event pending[P360_IRQ_DEPTH];
    uint64_t epoch,sequence;
    unsigned head,count;
    int accepting,poisoned;
};
/* All operations require caller's interrupt lock; init only for a NEW object.
 * An epoch tags HOST state, not a token carried by Intel IPC3 firmware.
 */
void p360_irq_init(struct p360_irq *q);
int p360_irq_bind_boot(struct p360_irq *q,uint64_t epoch);
/* 1=queued, 0=unrelated/closed, -1=poisoned. No register writes or ACK here. */
int p360_irq_capture(struct p360_irq *q,uint32_t adspis,uint32_t hipci,
    uint32_t hipcie,uint32_t hipct,uint32_t hipcte);
int p360_irq_take(struct p360_irq *q,uint64_t epoch,struct p360_irq_event *out);
void p360_irq_close(struct p360_irq *q);
void p360_irq_poison(struct p360_irq *q);
#endif
