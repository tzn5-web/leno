/* SPDX-License-Identifier: BSD-3-Clause */
#include "p360_ipc_timer.h"
void p360_ipc_timer_init(struct p360_ipc_timer *t)
{
    struct p360_ipc_timer z = {0};
    if (t) *t = z;
}
int p360_ipc_timer_arm(struct p360_ipc_timer *t, const struct p360_ipc *ipc)
{
    if (!t || !ipc || t->state == P360_T_ARMED || ipc->state != P360_IPC_PENDING ||
        !ipc->boot_epoch || !ipc->generation || !ipc->deadline_100ns) return -1;
    t->epoch = ipc->boot_epoch; t->generation = ipc->generation;
    t->deadline_100ns = ipc->deadline_100ns; t->state = P360_T_ARMED; return 0;
}
int p360_ipc_timer_cancel(struct p360_ipc_timer *t, uint64_t epoch, uint64_t generation)
{
    if (!t || t->state != P360_T_ARMED) return -1;
    if (t->epoch != epoch || t->generation != generation) return 1;
    t->state = P360_T_CANCELLED; return 0;
}
int p360_ipc_timer_fire(struct p360_ipc_timer *t, struct p360_ipc *ipc, uint64_t now)
{
    if (!t || !ipc) return -1;
    if (t->state != P360_T_ARMED) return 0;
    if (ipc->state != P360_IPC_PENDING || ipc->boot_epoch != t->epoch ||
        ipc->generation != t->generation || ipc->deadline_100ns != t->deadline_100ns) {
        t->state = P360_T_CANCELLED; return 2;
    }
    if (now < t->deadline_100ns) return 0;
    if (!p360_ipc_expire(ipc, now) || ipc->state != P360_IPC_POISONED) return -1;
    t->state = P360_T_FIRED; return 1;
}
