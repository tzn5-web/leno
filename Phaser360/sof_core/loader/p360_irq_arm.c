/* SPDX-License-Identifier: BSD-3-Clause */
#include "p360_irq_arm.h"

static int bad32(uint32_t value)
{
    return value == UINT32_MAX;
}

static int pending(const struct p360_irq_arm_snapshot *s)
{
    return !!(s->adspis & P360_ADSPIS_IPC) ||
           !!(s->hipci & P360_HIPCI_BUSY) ||
           !!(s->hipcie & P360_HIPCIE_DONE) ||
           !!(s->hipct & P360_HIPCT_BUSY);
}

int p360_irq_arm_prepare(
    const struct p360_irq_arm_snapshot *s,
    uint64_t epoch,
    int accepting,
    unsigned queued,
    int poisoned,
    int fault,
    int mask_confirmed,
    struct p360_irq_arm_plan *p)
{
    struct p360_irq_arm_plan zero = {0};

    if (p)
        *p = zero;

    if (!s || !p || !epoch || !accepting || queued ||
        poisoned || fault || !mask_confirmed)
        return -1;

    if (bad32(s->adspis) || bad32(s->hipci) ||
        bad32(s->hipcie) || bad32(s->hipct) ||
        bad32(s->hipcte) || bad32(s->hipcctl) ||
        bad32(s->adspic))
        return -1;

    if ((s->hipcctl & (P360_HIPCCTL_BUSY | P360_HIPCCTL_DONE)) ||
        (s->adspic & P360_ADSPIC_IPC) ||
        pending(s))
        return -1;

    p->hipcctl_before = s->hipcctl;
    p->hipcctl_after =
        s->hipcctl | P360_HIPCCTL_BUSY | P360_HIPCCTL_DONE;

    p->adspic_before = s->adspic;
    p->adspic_after = s->adspic | P360_ADSPIC_IPC;

    return 0;
}

int p360_irq_arm_verify(
    const struct p360_irq_arm_snapshot *s,
    const struct p360_irq_arm_plan *p)
{
    if (!s || !p ||
        bad32(s->adspis) || bad32(s->hipci) ||
        bad32(s->hipcie) || bad32(s->hipct) ||
        bad32(s->hipcte) || bad32(s->hipcctl) ||
        bad32(s->adspic))
        return -1;

    if (s->hipcctl != p->hipcctl_after ||
        s->adspic != p->adspic_after ||
        pending(s))
        return -1;

    return 0;
}
