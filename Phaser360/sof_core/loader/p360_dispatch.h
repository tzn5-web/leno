/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef P360_DISPATCH_H
#define P360_DISPATCH_H
#include "p360_irq.h"
#include "../p360_transport_core.h"
#define P360_DSP_UPBOX           0x81000u
#define P360_HOST_DOWNBOX        0xa0000u
#define P360_STREAM_BOX          0xc1000u
#define P360_DISPATCH_MAP_BYTES  0xc2000u
struct p360_dispatch_io {
    int (*copy)(void *context,uint32_t offset,uint8_t *out,uint32_t bytes);
    /* Serialize with ISR; recheck admission, epoch and captured doorbells.
     * ACK only validated causes; verify W1C, then HIPCCTL -> ADSPIC unmask.
     * Failure must leave sources masked or latch the owner's hardware fault.
     */
    int (*finish)(void *context,const struct p360_irq_event *event);
    uint64_t (*now)(void *context);
};
struct p360_dispatch {
    struct p360_ipc ipc;
    uint64_t sequence;
    uint32_t stream_id;
    uint8_t position[76];
    unsigned positions;
    uint32_t expected_reply_bytes;
    uint32_t expected_reply_cmd;
    uint32_t expected_comp_id;
    int expected_generic;
    int prepared,active,poisoned;
};
/* NEW zeroed object only; immutable resident pinned full image, no hardware IO.
 * Verifies image identity AND the actual manifest UPBOX/DOWNBOX descriptors.
 * A read-only audit prefix (0x82000) is deliberately insufficient.
 */
int p360_dispatch_prepare(struct p360_dispatch *d,const uint8_t *image,
    size_t bytes,uint32_t mapped_bytes);
/* Serialized by dispatcher lock, after real independently proved FW_READY.
 * No bind/reinit recovery after poison; current FDO has no bind/send call site.
 */
int p360_dispatch_bind(struct p360_dispatch *d,uint64_t epoch);
int p360_dispatch_stream(struct p360_dispatch *d,uint32_t id);
/* Metadata only, BEFORE an allowed command send. No hardware send here.
 * Most IPC3 commands use the 12-byte generic reply. STREAM_PCM_PARAMS is the
 * one explicitly supported structured reply (20 bytes) and is correlated by
 * request command + component id. No timeout retry: IPC3 has no wire generation.
 */
int p360_dispatch_expect(struct p360_dispatch *d,uint64_t now,uint32_t timeout_ms);
int p360_dispatch_expect_message(struct p360_dispatch *d,uint64_t now,
    uint32_t timeout_ms,const uint8_t *message,uint32_t bytes);
int p360_dispatch_process(struct p360_dispatch *d,const struct p360_irq_event *event,
    const struct p360_dispatch_io *io,void *context);
void p360_dispatch_stop(struct p360_dispatch *d);
#endif
