/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef P360_LOADER_H
#define P360_LOADER_H
#include <stddef.h>
#include <stdint.h>
#define P360_LOADER_API_VERSION 3u

#define P360_FW_FILE_BYTES 246528u
#define P360_FW_MANIFEST_BYTES 768u
#define P360_FW_PAYLOAD_BYTES 245760u
#define P360_FW_READY_BYTES 108u
#define P360_BDL_MAX 256u
#define P360_ROM_STATUS_MASK 0x00ffffffu
#define P360_ROM_FW_ENTERED 5u

enum p360_loader_error {
    P360_L_OK = 0, P360_L_ARGUMENT = -1, P360_L_IMAGE = -2,
    P360_L_BUSY = -3, P360_L_IO = -4, P360_L_TIMEOUT = -5,
    P360_L_CANCEL = -6, P360_L_ROM_ERROR = -7,
    P360_L_READY = -8, P360_L_QUARANTINE = -9
};
enum p360_loader_phase {
    P360_L_VALIDATE, P360_L_ACQUIRE, P360_L_DMA_PREPARE,
    P360_L_RESET, P360_L_POWER_UP, P360_L_PURGE,
    P360_L_ROM_INIT, P360_L_TRANSFER, P360_L_FW_READY,
    P360_L_CLEANUP, P360_L_COMPLETE
};
struct p360_fw_view { const uint8_t *payload; uint32_t bytes; };
/* Image bytes must be a private resident immutable copy throughout run().
 * Only the already-built diagnostic v2 image is admitted, by full-file SHA256.
 * This is an identity check, not a replacement for DSP ROM signature validation.
 */
int p360_fw_validate(const uint8_t *image, size_t bytes, struct p360_fw_view *view);
int p360_fw_ready_validate(const uint8_t *first, const uint8_t *second, size_t bytes);

struct p360_dma_span { uint64_t address; uint32_t bytes; };
/* Little-endian wire BDL; build() writes bytes explicitly, not native structs. */
int p360_bdl_build(const struct p360_dma_span *spans, size_t span_count,
    uint64_t bdl_address, uint32_t payload_bytes, int dma64,
    uint8_t *bdl, size_t bdl_bytes, uint16_t *entry_count);

/* Hardware adapter contract, NOT IMPLEMENTED by the current read-only FDO.
 * Caller serializes the engine at PASSIVE_LEVEL and holds D0/removal exclusion.
 * All callbacks must finish within their own bounded hardware deadlines.
 * acquire() must validate the PCI identity and hold the parent controller in D0.
 * Once this child driver owns the ADSP PDO, a stale powered-core state is
 * normalized with the Linux HDA/SOF stall -> reset -> power-down sequence and
 * must prove CPA=0 before DMA preparation. No second ADSP child owner is allowed.
 * prepare() uses independently owned WDM common buffers, copies ONLY view.payload, builds BDL,
 * programs HDA stream + SPIB in DSP-decoupled mode, with link RUN never set.
 * No codec verbs, topology, SSP writes or speaker commands are permitted.
 * A failed acquire()/prepare() may be partial: cleanup is still mandatory.
 * stop() returning 0 MUST prove DMA stopped and all memory references detached;
 * otherwise do NOT free common buffers or restore the platform/gating lease.
 * release_dma() returns 0 only after safe allocation release; a failure retains
 * the buffers and must quarantine the engine. release_platform() must
 * restore journaled bits with read/merge/write, preserve unrelated changes,
 * and retain the lease on failure. success=1 must verify the restored gating
 * leaves core 0 alive/FW_ENTERED with no ROM error, transfer live-DSP ownership
 * to the caller, and leave IPC interrupts masked for the pending dispatcher.
 * Cleanup callbacks must ignore cancellation; common buffers stay resident
 * while DMA quiescence is unproved. A retained lease needs a live context.
 * No public adapter or boot IOCTL exists in this package.
 */
struct p360_loader_ops {
    int (*acquire)(void *context);
    int (*release_platform)(void *context, int success);
    int (*prepare)(void *context, const struct p360_fw_view *view, uint8_t *stream_tag);
    int (*start)(void *context);
    int (*stop)(void *context);
    int (*release_dma)(void *context);
    int (*read32)(void *context, uint32_t dsp_offset, uint32_t *value);
    int (*write32)(void *context, uint32_t dsp_offset, uint32_t value);
    int (*read_ready)(void *context, uint8_t out[P360_FW_READY_BYTES]);
    uint64_t (*now_us)(void *context); /* monotonic; no wall-clock */
    void (*wait_us)(void *context, uint32_t microseconds);
    int (*cancelled)(void *context);
};
struct p360_loader {
    uint64_t last_attempt_epoch;
    int active, quarantined;
};
struct p360_loader_result {
    enum p360_loader_phase phase;
    int error, cleanup_error;
    uint32_t rom_status, rom_error, adspcs;
    uint32_t entry_adspcs, normalized_adspcs;
    uint64_t boot_epoch;
    int ready_proved, resources_retained;
};
void p360_loader_init(struct p360_loader *loader);
/* One attempt, no automatic retries. Epoch increases even if an attempt fails.
 * This engine performs real sequencing only when backed by a real adapter.
 * CPU simulation PASS is not a hardware boot proof and must never enable IPC.
 * init() must not be used to clear a quarantine while resources are retained.
 */
int p360_loader_run(struct p360_loader *loader, const struct p360_loader_ops *ops,
    void *context, const uint8_t *image, size_t bytes, uint64_t boot_epoch,
    struct p360_loader_result *result);
#endif
