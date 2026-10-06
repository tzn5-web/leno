/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef P360_IPC_TIMER_H
#define P360_IPC_TIMER_H
#include <stdint.h>
#include "../p360_transport_core.h"

enum p360_ipc_timer_state { P360_T_OFF, P360_T_ARMED, P360_T_FIRED, P360_T_CANCELLED };
struct p360_ipc_timer {
    enum p360_ipc_timer_state state;
    uint64_t epoch, generation, deadline_100ns;
};
void p360_ipc_timer_init(struct p360_ipc_timer *timer);
/* Snapshot a PENDING IPC token. No OS timer is created here. */
int p360_ipc_timer_arm(struct p360_ipc_timer *timer, const struct p360_ipc *ipc);
/* Exact-token cancellation only. Stale cancellation cannot cancel a new IPC. */
int p360_ipc_timer_cancel(struct p360_ipc_timer *timer, uint64_t epoch, uint64_t generation);
/* 1=expired current IPC and poisoned it, 0=early/off, 2=stale callback retired,
 * -1=inconsistent current-token state. No callback can expire a newer generation.
 */
int p360_ipc_timer_fire(struct p360_ipc_timer *timer, struct p360_ipc *ipc, uint64_t now_100ns);
#endif
