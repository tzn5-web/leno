/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef P360_TRANSPORT_CORE_H
#define P360_TRANSPORT_CORE_H
#include <stddef.h>
#include <stdint.h>
struct p360_pci_identity { uint16_t vendor,device; uint8_t revision,hda_bar,dsp_bar; };
int p360_range_valid(uint64_t base,uint64_t length,uint64_t required);
int p360_pci_validate(const uint8_t *config,size_t bytes,struct p360_pci_identity *out);

enum p360_ipc_state { P360_IPC_OFFLINE,P360_IPC_IDLE,P360_IPC_PENDING,P360_IPC_COMPLETE,P360_IPC_POISONED };
struct p360_ipc {
    enum p360_ipc_state state;
    uint64_t boot_epoch,generation,pending_generation,deadline_100ns;
    int32_t reply_error;
    uint32_t reply_bytes;
};
void p360_ipc_init(struct p360_ipc *ipc);
int p360_ipc_new_proved_boot(struct p360_ipc *ipc,uint64_t epoch);
int p360_ipc_begin(struct p360_ipc *ipc,uint64_t now,uint32_t timeout_ms,uint64_t *gen);
int p360_ipc_expire(struct p360_ipc *ipc,uint64_t now);
int p360_ipc_complete(struct p360_ipc *ipc,uint64_t epoch,uint64_t gen,const uint8_t *reply,size_t bytes);
int p360_ipc_consume(struct p360_ipc *ipc,int32_t *error,uint32_t *bytes);
void p360_ipc_stop(struct p360_ipc *ipc);
#endif
