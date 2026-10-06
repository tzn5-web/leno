/* SPDX-License-Identifier: BSD-3-Clause */
#include "p360_ipc3_tx.h"

static uint32_t get32(const uint8_t *p)
{
    return (uint32_t)p[0] |
        ((uint32_t)p[1] << 8) |
        ((uint32_t)p[2] << 16) |
        ((uint32_t)p[3] << 24);
}

static void put32(uint8_t *p, uint32_t v)
{
    p[0]=(uint8_t)v;
    p[1]=(uint8_t)(v >> 8);
    p[2]=(uint8_t)(v >> 16);
    p[3]=(uint8_t)(v >> 24);
}

int p360_ipc3_build_proof(uint8_t message[8])
{
    if (!message)
        return P360_IPC3_TX_ARGUMENT;

    put32(message,8u);
    /*
     * The pinned SOF 1.9.3 ipc3 handler has no global type 0xe. Its default
     * path performs no topology/PM/DAI operation and returns the standard
     * 12-byte SOF_IPC_GLB_REPLY with -EINVAL. That makes this an intentional
     * side-effect-free transport proof, not an audio command.
     */
    put32(message + 4,P360_IPC3_PROOF_COMMAND);
    return P360_IPC3_TX_OK;
}

int p360_ipc3_tx_begin(
    struct p360_dispatch *d,
    const struct p360_ipc3_tx_io *io,
    void *context,
    const uint8_t *message,
    uint32_t bytes,
    uint32_t timeout_ms,
    struct p360_ipc3_tx_result *result)
{
    struct p360_ipc3_tx_result zero = {0};
    uint32_t hipci, hipcie, hipct;

    if (result)
        *result=zero;

    if (!d || !io || !result || !message ||
        !io->read32 || !io->write32 || !io->write_box ||
        !io->now || !io->barrier ||
        bytes < 8u || bytes > P360_IPC3_MAX_MESSAGE_BYTES ||
        (bytes & 3u) || get32(message) != bytes)
        return P360_IPC3_TX_ARGUMENT;

    if (!d->active || d->poisoned || d->ipc.state != P360_IPC_IDLE)
        return P360_IPC3_TX_STATE;

    if (io->read32(context,P360_DSP_HIPCI,&hipci) ||
        io->read32(context,P360_DSP_HIPCIE,&hipcie) ||
        io->read32(context,P360_DSP_HIPCT,&hipct) ||
        hipci == UINT32_MAX || hipcie == UINT32_MAX || hipct == UINT32_MAX)
        return P360_IPC3_TX_STATE;

    result->hipci_before=hipci;
    result->hipcie_before=hipcie;
    result->hipct_before=hipct;

    if ((hipci & P360_HIPCI_BUSY) ||
        (hipcie & P360_HIPCIE_DONE) ||
        (hipct & P360_HIPCT_BUSY))
        return P360_IPC3_TX_PENDING;

    if (p360_dispatch_expect(d,io->now(context),timeout_ms) != 0) {
        result->status=P360_IPC3_TX_EXPECT;
        return result->status;
    }

    result->generation=d->ipc.generation;

    if (io->write_box(context,P360_HOST_DOWNBOX,message,bytes) != 0) {
        p360_dispatch_stop(d);
        result->status=P360_IPC3_TX_MAILBOX;
        return result->status;
    }

    result->mailbox_written=1;
    io->barrier(context);

    /*
     * cAVS 1.5 / APL-GLK IPC3: the command itself lives in the host mailbox.
     * HIPCI carries only BUSY for this path. Do not require BUSY read-back:
     * firmware may consume and clear it before the host can sample it.
     */
    result->doorbell_written=1;
    result->poison_required=1;
    if (io->write32(context,P360_DSP_HIPCI,P360_HIPCI_BUSY) != 0) {
        result->status=P360_IPC3_TX_DOORBELL;
        return result->status;
    }

    io->barrier(context);
    result->poison_required=0;
    result->status=P360_IPC3_TX_OK;
    return result->status;
}
