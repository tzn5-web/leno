/* SPDX-License-Identifier: BSD-3-Clause
 * Bounded PCI parser and serialized IPC lifecycle; no hardware operations.
 */
#include "p360_transport_core.h"
static uint32_t p360_u32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
        ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
int p360_range_valid(uint64_t base, uint64_t length, uint64_t required)
{
    return base != 0 && (base & 0xfffu) == 0 && length >= required &&
        length <= 0x1000000u && base <= UINT64_MAX - length;
}
int p360_pci_validate(const uint8_t *c, size_t bytes, struct p360_pci_identity *out)
{
    uint32_t b0, b4;
    if (!out) return -1;
    out->hda_bar = out->dsp_bar = 0; out->command = 0;
    if (!c || bytes != 256) return -1;
    /* Exact identity supplied by the user's existing case, including class. */
    if (p360_u32(c) != 0x31988086u || c[8] != 6 || c[9] != 0 ||
        c[10] != 1 || c[11] != 4 || (c[14] & 0x7fu) != 0 || p360_u32(c + 0x2c) != 0)
        return -2;
    out->command = (uint16_t)((uint16_t)c[4] | ((uint16_t)c[5] << 8));
    if (!(out->command & 2u)) return -3; /* Memory space must already be enabled. */
    b0 = p360_u32(c + 0x10); b4 = p360_u32(c + 0x20);
    /* BAR0 and BAR4 must be non-prefetchable 64-bit memory BARs. No sizing writes. */
    if ((b0 & 0xfu) != 4u || (b4 & 0xfu) != 4u) return -4;
    out->hda_bar = ((uint64_t)p360_u32(c + 0x14) << 32) | (b0 & ~0xfu);
    out->dsp_bar = ((uint64_t)p360_u32(c + 0x24) << 32) | (b4 & ~0xfu);
    if (!out->hda_bar || !out->dsp_bar || out->hda_bar == out->dsp_bar ||
        (out->hda_bar & 0xfffu) || (out->dsp_bar & 0xfffu)) return -4;
    return 0;
}
void p360_ipc_init(struct p360_ipc *ipc)
{
    if (!ipc) return;
    ipc->state = P360_IPC_OFFLINE; ipc->boot_epoch = 0; ipc->generation = 0;
    ipc->deadline_100ns = 0; ipc->firmware_error = 0; ipc->reply_bytes = 0;
}
int p360_ipc_new_proved_boot(struct p360_ipc *ipc, uint64_t epoch)
{
    if (!ipc || !epoch || epoch <= ipc->boot_epoch || ipc->state == P360_IPC_PENDING)
        return -1;
    /* Hardware caller must first quiesce ISR/DPC/DMA and prove a fresh boot.
     * Merely calling this function is not a hardware reset or boot proof.
     */
    ipc->boot_epoch = epoch; ipc->generation = 0;
    ipc->deadline_100ns = 0; ipc->firmware_error = 0; ipc->reply_bytes = 0;
    ipc->state = P360_IPC_IDLE;
    return 0;
}
int p360_ipc_begin(struct p360_ipc *ipc, uint64_t now, uint32_t timeout_ms, uint64_t *gen)
{
    uint64_t duration;
    if (gen) *gen = 0;
    if (!ipc || !gen || ipc->state != P360_IPC_IDLE || !timeout_ms || timeout_ms > 400)
        return -1;
    duration = (uint64_t)timeout_ms * 10000u;
    if (now > UINT64_MAX - duration || ipc->generation == UINT64_MAX) {
        ipc->state = P360_IPC_POISONED; return -2;
    }
    ipc->deadline_100ns = now + duration;
    ipc->firmware_error = 0; ipc->reply_bytes = 0;
    *gen = ++ipc->generation; ipc->state = P360_IPC_PENDING;
    return 0;
}
int p360_ipc_expire(struct p360_ipc *ipc, uint64_t now)
{
    if (!ipc || ipc->state != P360_IPC_PENDING) return 0;
    if (now < ipc->deadline_100ns) return 0;
    ipc->state = P360_IPC_POISONED; return 1;
}
int p360_ipc_complete(struct p360_ipc *ipc, uint64_t epoch, uint64_t gen,
    uint64_t now, const uint8_t *reply, size_t bytes)
{
    uint32_t header_size, command, error;
    if (!ipc || ipc->state != P360_IPC_PENDING || epoch != ipc->boot_epoch ||
        gen != ipc->generation) return -1;
    if (p360_ipc_expire(ipc, now)) return -2;
    if (!reply || bytes < 12 || bytes > 384) {
        ipc->state = P360_IPC_POISONED; return -3;
    }
    header_size = p360_u32(reply); command = p360_u32(reply + 4);
    /* SOF IPC3 generic reply. Other reply formats require explicit future support. */
    if (header_size != bytes || command != 0x10000000u) {
        ipc->state = P360_IPC_POISONED; return -3;
    }
    error = p360_u32(reply + 8);
    /* Bit-preserving signed conversion, without implementation-defined cast. */
    ipc->firmware_error = error <= INT32_MAX ? (int32_t)error :
        -1 - (int32_t)(UINT32_MAX - error);
    ipc->reply_bytes = (uint32_t)bytes; ipc->state = P360_IPC_COMPLETE;
    return 0;
}
int p360_ipc_consume(struct p360_ipc *ipc, int32_t *error, uint32_t *bytes)
{
    if (!ipc || !error || !bytes || ipc->state != P360_IPC_COMPLETE) return -1;
    *error = ipc->firmware_error; *bytes = ipc->reply_bytes;
    ipc->state = P360_IPC_IDLE;
    return 0;
}
void p360_ipc_stop(struct p360_ipc *ipc)
{
    if (!ipc) return;
    ipc->state = P360_IPC_OFFLINE; ipc->deadline_100ns = 0;
    /* Preserve the epoch, preventing stale callbacks from being accepted after restart. */
}
