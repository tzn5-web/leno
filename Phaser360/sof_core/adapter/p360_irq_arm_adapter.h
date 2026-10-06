/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef P360_IRQ_ARM_ADAPTER_H
#define P360_IRQ_ARM_ADAPTER_H
#include <stdint.h>
#include "../loader/p360_irq_arm.h"

#define P360_DSP_ADSPIC   0x08u
#define P360_DSP_ADSPIS   0x0cu
#define P360_DSP_HIPCT    0x40u
#define P360_DSP_HIPCTE   0x44u
#define P360_DSP_HIPCI    0x48u
#define P360_DSP_HIPCIE   0x4cu
#define P360_DSP_HIPCCTL  0x50u

enum p360_irq_arm_adapter_status {
    P360_IRQ_ADAPTER_OK = 0,
    P360_IRQ_ADAPTER_ARGUMENT = -1,
    P360_IRQ_ADAPTER_ACCESS = -2,
    P360_IRQ_ADAPTER_SNAPSHOT = -3,
    P360_IRQ_ADAPTER_POLICY = -4,
    P360_IRQ_ADAPTER_WRITE = -5,
    P360_IRQ_ADAPTER_VERIFY = -6,
    P360_IRQ_ADAPTER_ROLLBACK_UNPROVED = -7
};

struct p360_irq_arm_adapter_io {
    int (*permit)(void *context);
    int (*read32)(void *context, uint32_t offset, uint32_t *value);
    int (*write32)(void *context, uint32_t offset, uint32_t value);
    void (*barrier)(void *context);
};

struct p360_irq_arm_adapter_result {
    int status;
    int writes_started;
    int rollback_attempted;
    int rollback_proved;
    int poison_required;
    struct p360_irq_arm_snapshot before;
    struct p360_irq_arm_snapshot after;
    struct p360_irq_arm_plan plan;
};

int p360_irq_arm_adapter_run(
    const struct p360_irq_arm_adapter_io *io,
    void *context,
    uint64_t epoch,
    int accepting,
    unsigned queued,
    int poisoned,
    int fault,
    int mask_confirmed,
    struct p360_irq_arm_adapter_result *result);

#endif
