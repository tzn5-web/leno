#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../sof_core/adapter/p360_irq_arm_adapter.h"

struct hw {
    uint32_t r[0x54/4];
    int op, fail_at, deny_at, barriers, writes;
};

static int permit(void *c)
{
    struct hw *h = c;
    return !h->deny_at || h->op < h->deny_at;
}

static int read32(void *c, uint32_t o, uint32_t *v)
{
    struct hw *h = c;
    ++h->op;
    if (h->fail_at == h->op)
        return -1;
    if ((o % 4) || o >= 0x54)
        return -1;
    *v = h->r[o/4];
    return 0;
}

static int write32(void *c, uint32_t o, uint32_t v)
{
    struct hw *h = c;
    ++h->op;
    if (h->fail_at == h->op)
        return -1;
    if ((o % 4) || o >= 0x54)
        return -1;
    h->r[o/4] = v;
    ++h->writes;
    return 0;
}

static void barrier(void *c)
{
    ((struct hw *)c)->barriers++;
}

static const struct p360_irq_arm_adapter_io io = {
    permit, read32, write32, barrier
};

static void clean(struct hw *h)
{
    memset(h, 0, sizeof(*h));
    h->r[P360_DSP_HIPCCTL/4] = 0x100;
    h->r[P360_DSP_ADSPIC/4] = 0x20;
}

int main(void)
{
    struct hw h;
    struct p360_irq_arm_adapter_result r;
    int rc, i, cases = 0;

    clean(&h);
    rc = p360_irq_arm_adapter_run(&io, &h, 9, 1, 0, 0, 0, 1, &r);
    assert(rc == 0);
    assert(h.r[P360_DSP_HIPCCTL/4] == 0x103);
    assert(h.r[P360_DSP_ADSPIC/4] == 0x21);
    assert(h.writes == 2 && r.rollback_attempted == 0);
    cases++;

    clean(&h);
    h.r[P360_DSP_HIPCI/4] = P360_HIPCI_BUSY;
    assert(p360_irq_arm_adapter_run(
        &io, &h, 9, 1, 0, 0, 0, 1, &r) ==
        P360_IRQ_ADAPTER_POLICY);
    assert(h.writes == 0);
    cases++;

    clean(&h);
    assert(p360_irq_arm_adapter_run(
        &io, &h, 0, 1, 0, 0, 0, 1, &r) ==
        P360_IRQ_ADAPTER_POLICY);
    cases++;

    clean(&h);
    assert(p360_irq_arm_adapter_run(
        &io, &h, 9, 0, 0, 0, 0, 1, &r) ==
        P360_IRQ_ADAPTER_POLICY);
    cases++;

    clean(&h);
    assert(p360_irq_arm_adapter_run(
        &io, &h, 9, 1, 1, 0, 0, 1, &r) ==
        P360_IRQ_ADAPTER_POLICY);
    cases++;

    clean(&h);
    assert(p360_irq_arm_adapter_run(
        &io, &h, 9, 1, 0, 1, 0, 1, &r) ==
        P360_IRQ_ADAPTER_POLICY);
    cases++;

    clean(&h);
    assert(p360_irq_arm_adapter_run(
        &io, &h, 9, 1, 0, 0, 1, 1, &r) ==
        P360_IRQ_ADAPTER_POLICY);
    cases++;

    clean(&h);
    assert(p360_irq_arm_adapter_run(
        &io, &h, 9, 1, 0, 0, 0, 0, &r) ==
        P360_IRQ_ADAPTER_POLICY);
    cases++;

    for (i = 1; i <= 7; ++i) {
        clean(&h);
        h.fail_at = i;
        rc = p360_irq_arm_adapter_run(
            &io, &h, 9, 1, 0, 0, 0, 1, &r);
        assert(rc == P360_IRQ_ADAPTER_SNAPSHOT);
        assert(h.writes == 0);
        cases++;
    }

    for (i = 8; i <= 17; ++i) {
        clean(&h);
        h.fail_at = i;
        rc = p360_irq_arm_adapter_run(
            &io, &h, 9, 1, 0, 0, 0, 1, &r);
        assert(rc != 0);
        if (r.writes_started)
            assert(r.poison_required);
        cases++;
    }

    clean(&h);
    h.deny_at = -1;
    assert(p360_irq_arm_adapter_run(
        &io, &h, 9, 1, 0, 0, 0, 1, &r) ==
        P360_IRQ_ADAPTER_ACCESS);
    assert(h.writes == 0);
    cases++;

    for (i = 8; i <= 16; ++i) {
        clean(&h);
        h.deny_at = i;
        rc = p360_irq_arm_adapter_run(
            &io, &h, 9, 1, 0, 0, 0, 1, &r);
        assert(rc != 0);
        assert(r.poison_required);
        cases++;
    }

    printf("PASS: %d IRQ arm adapter cases.\n", cases);
    return 0;
}
