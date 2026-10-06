/* SPDX-License-Identifier: BSD-3-Clause */
#include "p360_irq_arm_adapter.h"

static int permit(const struct p360_irq_arm_adapter_io *io, void *context)
{
    return io && io->permit && io->permit(context);
}

static int rd(
    const struct p360_irq_arm_adapter_io *io,
    void *context,
    uint32_t offset,
    uint32_t *value)
{
    if (!permit(io, context) || !io->read32 || !value)
        return -1;

    return io->read32(context, offset, value);
}

static int wr(
    const struct p360_irq_arm_adapter_io *io,
    void *context,
    uint32_t offset,
    uint32_t value)
{
    if (!permit(io, context) || !io->write32)
        return -1;

    if (io->write32(context, offset, value))
        return -1;

    if (io->barrier)
        io->barrier(context);

    return 0;
}

static int snapshot(
    const struct p360_irq_arm_adapter_io *io,
    void *context,
    struct p360_irq_arm_snapshot *s)
{
    if (!s)
        return -1;

    return
        rd(io, context, P360_DSP_ADSPIS, &s->adspis) ||
        rd(io, context, P360_DSP_HIPCI, &s->hipci) ||
        rd(io, context, P360_DSP_HIPCIE, &s->hipcie) ||
        rd(io, context, P360_DSP_HIPCT, &s->hipct) ||
        rd(io, context, P360_DSP_HIPCTE, &s->hipcte) ||
        rd(io, context, P360_DSP_HIPCCTL, &s->hipcctl) ||
        rd(io, context, P360_DSP_ADSPIC, &s->adspic);
}

static int remask(
    const struct p360_irq_arm_adapter_io *io,
    void *context)
{
    uint32_t value;

    if (rd(io, context, P360_DSP_ADSPIC, &value) ||
        wr(io, context, P360_DSP_ADSPIC,
           value & ~P360_ADSPIC_IPC))
        return -1;

    if (rd(io, context, P360_DSP_HIPCCTL, &value) ||
        wr(io, context, P360_DSP_HIPCCTL,
           value & ~(P360_HIPCCTL_BUSY | P360_HIPCCTL_DONE)))
        return -1;

    if (rd(io, context, P360_DSP_ADSPIC, &value) ||
        (value & P360_ADSPIC_IPC))
        return -1;

    if (rd(io, context, P360_DSP_HIPCCTL, &value) ||
        (value & (P360_HIPCCTL_BUSY | P360_HIPCCTL_DONE)))
        return -1;

    return 0;
}

int p360_irq_arm_adapter_run(
    const struct p360_irq_arm_adapter_io *io,
    void *context,
    uint64_t epoch,
    int accepting,
    unsigned queued,
    int poisoned,
    int fault,
    int mask_confirmed,
    struct p360_irq_arm_adapter_result *r)
{
    int status = P360_IRQ_ADAPTER_ARGUMENT;

    if (r) {
        struct p360_irq_arm_adapter_result zero = {0};
        *r = zero;
    }

    if (!io || !io->permit || !io->read32 ||
        !io->write32 || !r)
        return status;

    if (!permit(io, context)) {
        r->status = P360_IRQ_ADAPTER_ACCESS;
        return r->status;
    }

    if (snapshot(io, context, &r->before)) {
        r->status = P360_IRQ_ADAPTER_SNAPSHOT;
        return r->status;
    }

    if (p360_irq_arm_prepare(
            &r->before,
            epoch,
            accepting,
            queued,
            poisoned,
            fault,
            mask_confirmed,
            &r->plan)) {
        r->status = P360_IRQ_ADAPTER_POLICY;
        return r->status;
    }

    r->writes_started = 1;

    if (wr(io, context, P360_DSP_HIPCCTL,
           r->plan.hipcctl_after)) {
        status = P360_IRQ_ADAPTER_WRITE;
        goto fail;
    }

    {
        uint32_t value;

        if (rd(io, context, P360_DSP_HIPCCTL, &value) ||
            value != r->plan.hipcctl_after) {
            status = P360_IRQ_ADAPTER_VERIFY;
            goto fail;
        }
    }

    if (wr(io, context, P360_DSP_ADSPIC,
           r->plan.adspic_after)) {
        status = P360_IRQ_ADAPTER_WRITE;
        goto fail;
    }

    if (snapshot(io, context, &r->after) ||
        p360_irq_arm_verify(&r->after, &r->plan)) {
        status = P360_IRQ_ADAPTER_VERIFY;
        goto fail;
    }

    r->status = P360_IRQ_ADAPTER_OK;
    return 0;

fail:
    r->poison_required = 1;
    r->rollback_attempted = 1;
    r->rollback_proved = remask(io, context) == 0;

    r->status = r->rollback_proved ?
        status :
        P360_IRQ_ADAPTER_ROLLBACK_UNPROVED;

    return r->status;
}
