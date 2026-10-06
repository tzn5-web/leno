/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef P360_TRANSPORT_CORE_H
#define P360_TRANSPORT_CORE_H
#include <stdint.h>
#include <stddef.h>

struct p360_pci_identity {
    uint64_t hda_bar, dsp_bar;
    uint16_t command;
};
int p360_pci_validate(const uint8_t *config, size_t bytes, struct p360_pci_identity *out);
int p360_range_valid(uint64_t base, uint64_t length, uint64_t required);

/* Caller serializes all state transitions (interrupt lock in hardware driver).
 * The generation is host-local. Intel IPC3 replies do not carry this token.
 * A timeout poisons the channel; no reuse before an independently proved new boot.
 */
enum p360_ipc_state { P360_IPC_OFFLINE, P360_IPC_IDLE, P360_IPC_PENDING,
    P360_IPC_COMPLETE, P360_IPC_POISONED };
struct p360_ipc {
    enum p360_ipc_state state;
    uint64_t boot_epoch, generation, deadline_100ns;
    int32_t firmware_error;
    uint32_t reply_bytes;
};
void p360_ipc_init(struct p360_ipc *ipc);
int p360_ipc_new_proved_boot(struct p360_ipc *ipc, uint64_t boot_epoch);
int p360_ipc_begin(struct p360_ipc *ipc, uint64_t now_100ns, uint32_t timeout_ms,
    uint64_t *generation);
int p360_ipc_expire(struct p360_ipc *ipc, uint64_t now_100ns);
int p360_ipc_complete(struct p360_ipc *ipc, uint64_t captured_boot_epoch,
    uint64_t captured_generation, uint64_t now_100ns,
    const uint8_t *reply, size_t bytes);
int p360_ipc_consume(struct p360_ipc *ipc, int32_t *firmware_error, uint32_t *reply_bytes);
void p360_ipc_stop(struct p360_ipc *ipc);
#endif
