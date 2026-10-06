/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef P360_IPC_TIMER_H
#define P360_IPC_TIMER_H
#include <stdint.h>
#include "p360_transport_core.h"
struct p360_ipc_timer {
    struct p360_ipc *ipc;
    uint64_t armed_generation;
    uint64_t armed_epoch;
    int armed,poisoned;
};
void p360_ipc_timer_init(struct p360_ipc_timer *t,struct p360_ipc *ipc);
int p360_ipc_timer_arm(struct p360_ipc_timer *t,uint64_t epoch,uint64_t generation);
int p360_ipc_timer_fire(struct p360_ipc_timer *t,uint64_t now);
int p360_ipc_timer_cancel(struct p360_ipc_timer *t,uint64_t epoch,uint64_t generation);
void p360_ipc_timer_stop(struct p360_ipc_timer *t);
#endif
