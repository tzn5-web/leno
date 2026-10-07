#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../sof_core/p360_transport_core.h"

static void put32(uint8_t *p, uint32_t v)
{
    p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8);
    p[2]=(uint8_t)(v>>16); p[3]=(uint8_t)(v>>24);
}

int main(void)
{
    uint8_t cfg[256]={0};
    uint8_t reply[12]={0};
    struct p360_pci_identity id;
    struct p360_ipc ipc;
    uint64_t gen=0;
    int32_t error=0;
    uint32_t bytes=0;

    put32(cfg+0x00,0x31988086u);
    cfg[4]=6; /* memory + bus master */
    cfg[8]=6; cfg[9]=0; cfg[10]=1; cfg[11]=4;
    cfg[14]=0;
    put32(cfg+0x10,0x00100004u);
    put32(cfg+0x14,0);
    put32(cfg+0x20,0x00200004u);
    put32(cfg+0x24,0);
    put32(cfg+0x2c,0);

    assert(p360_pci_validate(cfg,sizeof(cfg),&id)==0);
    assert(id.hda_bar==0x00100000u);
    assert(id.dsp_bar==0x00200000u);
    assert(id.command==6);
    assert(p360_range_valid(id.hda_bar,0x4000u,0x4000u));
    assert(p360_range_valid(id.dsp_bar,0x100000u,0xA2000u));

    cfg[11]=3;
    assert(p360_pci_validate(cfg,sizeof(cfg),&id)!=0);
    cfg[11]=4;

    p360_ipc_init(&ipc);
    assert(ipc.state==P360_IPC_OFFLINE);
    assert(p360_ipc_new_proved_boot(&ipc,1)==0);
    assert(p360_ipc_begin(&ipc,100,10,&gen)==0 && gen==1);

    put32(reply+0,12);
    put32(reply+4,0x10000000u);
    put32(reply+8,0xfffffffbu);
    assert(p360_ipc_complete(&ipc,1,gen,1000,reply,sizeof(reply))==0);
    assert(p360_ipc_consume(&ipc,&error,&bytes)==0);
    assert(error==-5 && bytes==12 && ipc.state==P360_IPC_IDLE);

    assert(p360_ipc_begin(&ipc,2000,1,&gen)==0);
    assert(p360_ipc_expire(&ipc,12000)==1);
    assert(ipc.state==P360_IPC_POISONED);

    p360_ipc_stop(&ipc);
    assert(ipc.state==P360_IPC_OFFLINE);
    assert(p360_ipc_new_proved_boot(&ipc,2)==0);

    puts("B4 transport regression: PASS");
    return 0;
}
