/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef P360_IPC3_TX_H
#define P360_IPC3_TX_H

#include <stddef.h>
#include <stdint.h>
#include "p360_dispatch.h"
#include "../adapter/p360_irq_arm_adapter.h"

#define P360_IPC3_MAX_MESSAGE_BYTES 384u
#define P360_IPC3_PROOF_COMMAND     0xe0000000u
#define P360_IPC3_PROOF_ERROR       (-22)

enum p360_ipc3_tx_status {
    P360_IPC3_TX_OK = 0,
    P360_IPC3_TX_ARGUMENT = -1,
    P360_IPC3_TX_STATE = -2,
    P360_IPC3_TX_PENDING = -3,
    P360_IPC3_TX_EXPECT = -4,
    P360_IPC3_TX_MAILBOX = -5,
    P360_IPC3_TX_DOORBELL = -6
};

struct p360_ipc3_tx_io {
    int (*read32)(void *context, uint32_t offset, uint32_t *value);
    int (*write32)(void *context, uint32_t offset, uint32_t value);
    int (*write_box)(void *context, uint32_t offset, const uint8_t *data, uint32_t bytes);
    uint64_t (*now)(void *context);
    void (*barrier)(void *context);
};

struct p360_ipc3_tx_result {
    int status;
    int mailbox_written;
    int doorbell_written;
    int poison_required;
    uint64_t generation;
    uint32_t hipci_before;
    uint32_t hipcie_before;
    uint32_t hipct_before;
};

int p360_ipc3_build_proof(uint8_t message[8]);

/*
 * Serialized by the caller with the same lock as p360_dispatch_process().
 * The function records the expected reply BEFORE publishing mailbox data and
 * ringing HIPCI.BUSY. Once the doorbell write is attempted, any error requires
 * a fresh DSP boot; Intel IPC3 carries no host generation token on the wire.
 */
int p360_ipc3_tx_begin(
    struct p360_dispatch *dispatch,
    const struct p360_ipc3_tx_io *io,
    void *context,
    const uint8_t *message,
    uint32_t bytes,
    uint32_t timeout_ms,
    struct p360_ipc3_tx_result *result);

#endif
