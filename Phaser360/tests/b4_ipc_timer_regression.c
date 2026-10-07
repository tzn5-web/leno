#include <assert.h>
#include <stdio.h>
#include "../sof_core/loader/p360_ipc_timer.h"

static void pending(struct p360_ipc *ipc,uint64_t epoch,uint64_t now,uint32_t ms)
{
    uint64_t gen;
    p360_ipc_init(ipc);
    assert(!p360_ipc_new_proved_boot(ipc,epoch));
    assert(!p360_ipc_begin(ipc,now,ms,&gen));
    assert(gen==1);
}

int main(void)
{
    struct p360_ipc ipc,newipc;
    struct p360_ipc_timer t;
    uint64_t old_epoch,old_gen,g;

    p360_ipc_timer_init(&t);
    pending(&ipc,3,100,10);
    assert(!p360_ipc_timer_arm(&t,&ipc));
    assert(t.state==P360_T_ARMED && t.epoch==3 && t.generation==1 &&
           t.deadline_100ns==100100);
    assert(!p360_ipc_timer_fire(&t,&ipc,100099));
    assert(p360_ipc_timer_fire(&t,&ipc,100100)==1);
    assert(ipc.state==P360_IPC_POISONED && t.state==P360_T_FIRED);

    p360_ipc_timer_init(&t);
    pending(&ipc,4,0,1);
    assert(!p360_ipc_timer_arm(&t,&ipc));
    old_epoch=t.epoch; old_gen=t.generation;
    assert(p360_ipc_timer_cancel(&t,old_epoch,old_gen+1)==1);
    assert(!p360_ipc_timer_cancel(&t,old_epoch,old_gen));
    assert(t.state==P360_T_CANCELLED);

    p360_ipc_timer_init(&t);
    pending(&ipc,5,0,1);
    assert(!p360_ipc_timer_arm(&t,&ipc));
    newipc=ipc;
    p360_ipc_stop(&newipc);
    assert(!p360_ipc_new_proved_boot(&newipc,6));
    assert(!p360_ipc_begin(&newipc,0,2,&g));
    assert(p360_ipc_timer_fire(&t,&newipc,10000)==2);
    assert(newipc.state==P360_IPC_PENDING && newipc.boot_epoch==6);

    puts("B4 IPC timer regression: PASS");
    return 0;
}
