/* SPDX-License-Identifier: BSD-3-Clause */
#include "p360_ipc_timer.h"
void p360_ipc_timer_init(struct p360_ipc_timer *t,struct p360_ipc *ipc)
{
    if(t){t->ipc=ipc;t->armed_generation=0;t->armed_epoch=0;t->armed=0;t->poisoned=0;}
}
int p360_ipc_timer_arm(struct p360_ipc_timer *t,uint64_t epoch,uint64_t gen)
{
    if(!t||!t->ipc||t->armed||t->poisoned||t->ipc->state!=P360_IPC_PENDING||
       epoch!=t->ipc->boot_epoch||gen!=t->ipc->pending_generation)return -1;
    t->armed_epoch=epoch;t->armed_generation=gen;t->armed=1;return 0;
}
int p360_ipc_timer_fire(struct p360_ipc_timer *t,uint64_t now)
{
    int expired;
    if(!t||!t->ipc||!t->armed||t->poisoned)return 0;
    if(t->armed_epoch!=t->ipc->boot_epoch||t->armed_generation!=t->ipc->pending_generation){t->poisoned=1;t->armed=0;return -1;}
    expired=p360_ipc_expire(t->ipc,now);
    if(expired){t->armed=0;t->poisoned=1;return 1;}
    return 0;
}
int p360_ipc_timer_cancel(struct p360_ipc_timer *t,uint64_t epoch,uint64_t gen)
{
    if(!t||!t->ipc||!t->armed)return 0;
    if(t->armed_epoch!=epoch||t->armed_generation!=gen){t->poisoned=1;return -1;}
    t->armed=0;t->armed_epoch=0;t->armed_generation=0;return 0;
}
void p360_ipc_timer_stop(struct p360_ipc_timer *t)
{
    if(!t)return;t->armed=0;t->armed_epoch=0;t->armed_generation=0;
}
