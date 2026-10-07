#include <assert.h>
#include <stdio.h>
#include "../sof_core/loader/p360_irq.h"

int main(void)
{
    struct p360_irq q;
    struct p360_irq_event e;
    unsigned i,j,script,actions=0;

    p360_irq_init(&q);
    assert(!p360_irq_capture(&q,1,0,0x40000000u,0,0));
    assert(p360_irq_bind_boot(&q,0));
    assert(!p360_irq_bind_boot(&q,10));
    assert(p360_irq_bind_boot(&q,11));
    assert(!p360_irq_capture(&q,2,UINT32_MAX,UINT32_MAX,UINT32_MAX,UINT32_MAX));
    assert(!q.count && !q.poisoned);

    assert(p360_irq_capture(&q,1,0x12,0x40000034u,0x80000056u,0x78)==1);
    assert(p360_irq_take(&q,9,&e)==-1 && !e.epoch && q.count==1);
    assert(p360_irq_take(&q,10,&e)==1);
    assert(e.epoch==10 && e.sequence==1 && e.causes==3 &&
           e.hipci==0x12 && e.hipcie==0x40000034u &&
           e.hipct==0x80000056u && e.hipcte==0x78);

    for(j=0;j<20;j++) {
        for(i=0;i<P360_IRQ_DEPTH;i++)
            assert(p360_irq_capture(&q,1,i,0x40000000u,0,0)==1);
        for(i=0;i<P360_IRQ_DEPTH;i++) {
            assert(p360_irq_take(&q,10,&e)==1);
            assert(e.hipci==i && e.causes==1);
        }
    }

    for(i=0;i<P360_IRQ_DEPTH;i++)
        assert(p360_irq_capture(&q,1,i,0x40000000u,0,0)==1);
    assert(p360_irq_capture(&q,1,9,0x40000000u,0,0)==-1);
    assert(q.poisoned && !q.accepting && !q.count);

    for(script=0;script<1024;script++) {
        unsigned bits=script;
        uint64_t delivered=0;
        p360_irq_init(&q);
        assert(!p360_irq_bind_boot(&q,1));
        for(i=0;i<5;i++,bits>>=2) {
            switch(bits&3u) {
            case 0:
                (void)p360_irq_capture(&q,1,0,0x40000000u,0,0);
                break;
            case 1:
                if(p360_irq_take(&q,q.epoch,&e)==1) {
                    assert(e.epoch==q.epoch && e.sequence>delivered);
                    delivered=e.sequence;
                }
                break;
            case 2:
                p360_irq_close(&q);
                assert(!q.count && !q.accepting);
                break;
            default:
                if(!p360_irq_bind_boot(&q,q.epoch+1))
                    delivered=0;
                break;
            }
            assert(q.count<=P360_IRQ_DEPTH);
            actions++;
        }
        p360_irq_close(&q);
        assert(!p360_irq_take(&q,q.epoch,&e));
    }

    printf("B4 IRQ regression: PASS (%u interleaving actions)\n",actions);
    return 0;
}
