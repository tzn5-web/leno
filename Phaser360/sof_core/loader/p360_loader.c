/* SPDX-License-Identifier: BSD-3-Clause
 * APL/GLK IPC3 ROM sequencer. Composite adapter compiled; audit FDO activation absent.
 */
#include "p360_loader.h"

#define ADSPCS 0x04u
#define HIPCT 0x40u
#define HIPCTE 0x44u
#define HIPCI 0x48u
#define HIPCIE 0x4cu
#define HIPCCTL 0x50u
#define ROM_STATUS 0x80000u
#define ROM_ERROR 0x80004u
#define BUSY 0x80000000u
#define DONE 0x40000000u
#define CORES_RESET 0x00000003u
#define CORES_STALL 0x00000300u
#define CORES_SPA 0x00030000u
#define CORES_CPA 0x03000000u
#define CONTROL_MASK (CORES_RESET | CORES_STALL | CORES_SPA)
#define POLL_US 500u

struct execution {
    const struct p360_loader_ops *ops;
    void *context;
    struct p360_loader_result *result;
    int cleaning;
};
static int read32(struct execution *e,uint32_t offset,uint32_t *v)
{
    if (!e->cleaning && e->ops->cancelled(e->context)) return P360_L_CANCEL;
    if (e->ops->read32(e->context,offset,v) || *v==UINT32_MAX) return P360_L_IO;
    return 0;
}
static int write32(struct execution *e,uint32_t offset,uint32_t v)
{
    if (!e->cleaning && e->ops->cancelled(e->context)) return P360_L_CANCEL;
    return e->ops->write32(e->context,offset,v) ? P360_L_IO : 0;
}
static int update(struct execution *e,uint32_t offset,uint32_t mask,uint32_t bits)
{
    uint32_t v;
    int rc=read32(e,offset,&v);
    return rc ? rc : write32(e,offset,(v&~mask)|(bits&mask));
}
static int acknowledge(struct execution *e,uint32_t offset,uint32_t bit)
{
    uint32_t v;
    int rc=read32(e,offset,&v);
    /* W1C registers: preserve message fields, force only the known ACK bit. */
    return rc ? rc : write32(e,offset,v|bit);
}
static int poll(struct execution *e,uint32_t offset,uint32_t mask,uint32_t want,
    uint32_t timeout_us,int check_rom_error)
{
    uint64_t start=e->ops->now_us(e->context),last=start,now,deadline;
    uint32_t v,n;
    int rc;
    if (start>UINT64_MAX-timeout_us) return P360_L_TIMEOUT;
    deadline=start+timeout_us;
    /* Time deadline plus sample budget protects against a broken/frozen clock. */
    for (n=0;n<timeout_us/POLL_US+2u;++n) {
        now=e->ops->now_us(e->context);
        if (now<last || now>=deadline) return P360_L_TIMEOUT;
        last=now;
        rc=read32(e,offset,&v);
        if (rc) return rc;
        if (offset==ADSPCS) e->result->adspcs=v;
        if (offset==ROM_STATUS) e->result->rom_status=v;
        if (check_rom_error) {
            rc=read32(e,ROM_ERROR,&e->result->rom_error);
            if (rc) return rc;
            if (e->result->rom_error) return P360_L_ROM_ERROR;
        }
        now=e->ops->now_us(e->context);
        if (now<last || now>=deadline) return P360_L_TIMEOUT;
        last=now;
        if ((v&mask)==want) return 0;
        e->ops->wait_us(e->context,POLL_US);
    }
    return P360_L_TIMEOUT;
}
static int power_down(struct execution *e)
{
    int rc=update(e,ADSPCS,CORES_STALL,CORES_STALL);
    if (!rc) rc=update(e,ADSPCS,CORES_RESET,CORES_RESET);
    if (!rc) rc=poll(e,ADSPCS,CORES_RESET,CORES_RESET,50000u,0);
    if (!rc) rc=update(e,ADSPCS,CORES_SPA,0);
    if (!rc) rc=poll(e,ADSPCS,CORES_CPA,0,50000u,0);
    return rc;
}

void p360_loader_init(struct p360_loader *loader)
{
    if (loader) { loader->last_attempt_epoch=0;loader->active=0;loader->quarantined=0; }
}
int p360_loader_run(struct p360_loader *loader,const struct p360_loader_ops *ops,
    void *context,const uint8_t *image,size_t bytes,uint64_t boot_epoch,
    struct p360_loader_result *result)
{
    struct p360_fw_view view;
    struct execution e;
    uint8_t tag=0,first[P360_FW_READY_BYTES],second[P360_FW_READY_BYTES];
    uint32_t baseline=0,v;
    int acquired=0,dma_attempted=0,touched=0,rc=0,cleanup=0,stopped=1,release_failed=0;
    enum p360_loader_phase failed_phase;
    if (!result) return P360_L_ARGUMENT;
    result->phase=P360_L_VALIDATE;result->error=0;result->cleanup_error=0;
    result->rom_status=0;result->rom_error=0;result->adspcs=0;
    result->entry_adspcs=0;result->normalized_adspcs=0;
    result->boot_epoch=0;result->ready_proved=0;result->resources_retained=0;
    if (!loader || !ops || !ops->acquire || !ops->release_platform || !ops->prepare ||
        !ops->start || !ops->stop || !ops->release_dma || !ops->read32 || !ops->write32 ||
        !ops->read_ready || !ops->now_us || !ops->wait_us || !ops->cancelled || !boot_epoch) {
        result->error=P360_L_ARGUMENT;return result->error;
    }
    if (loader->active || loader->quarantined || boot_epoch<=loader->last_attempt_epoch) {
        if (loader->quarantined) {
            result->resources_retained=1;result->cleanup_error=P360_L_QUARANTINE;
        }
        result->error=P360_L_BUSY;return result->error;
    }
    rc=p360_fw_validate(image,bytes,&view);
    if (rc) {result->error=rc;return rc;}
    loader->last_attempt_epoch=boot_epoch;loader->active=1;
    e.ops=ops;e.context=context;e.result=result;e.cleaning=0;
    result->phase=P360_L_ACQUIRE;
    if (ops->cancelled(context)) { rc=P360_L_CANCEL;goto finish; }
    acquired=1; /* Cleanup even if acquire reports a partial failure. */
    if (ops->acquire(context)) { rc=P360_L_BUSY;goto finish; }
    rc=read32(&e,ADSPCS,&baseline);
    if (rc) goto finish;
    result->entry_adspcs=baseline;

    /*
     * Linux Intel HDA/SOF does not require ADSPCS to be cold on entry.
     * The ADSP PDO is exclusively bound to this driver at this point, so a
     * stale powered-core state is normalized before any HDA DMA allocation:
     * stall -> reset -> prove reset -> clear SPA -> prove CPA=0.
     *
     * This is deliberately stricter than merely clearing the old BUSY guard:
     * if hardware cannot prove OFF, boot aborts without preparing DMA.
     * The pre-normalization state is diagnostic only and is never restored as
     * unknown firmware state during cleanup.
     */
    if (baseline&(CORES_SPA|CORES_CPA)) {
        touched=1;
        rc=power_down(&e);
        if (rc) goto finish;

        rc=read32(&e,ADSPCS,&baseline);
        if (rc) goto finish;
        if (baseline&(CORES_SPA|CORES_CPA)) {
            rc=P360_L_BUSY;
            goto finish;
        }
    }
    result->normalized_adspcs=baseline;

    result->phase=P360_L_DMA_PREPARE;
    dma_attempted=1;stopped=0;
    if (ops->prepare(context,&view,&tag)) {rc=P360_L_IO;goto finish;}
    if (tag<1u || tag>15u) {rc=P360_L_ARGUMENT;goto finish;}
    result->phase=P360_L_RESET;touched=1;
    rc=update(&e,ADSPCS,CORES_STALL,CORES_STALL);
    if (!rc) rc=update(&e,ADSPCS,CORES_RESET,CORES_RESET);
    if (!rc) rc=poll(&e,ADSPCS,CORES_RESET,CORES_RESET,50000u,0);
    if (!rc) rc=update(&e,HIPCCTL,3u,0); /* Polling boot: no ISR/DPC enabled here. */
    if (!rc) rc=acknowledge(&e,HIPCIE,DONE);
    if (!rc) rc=acknowledge(&e,HIPCT,BUSY);
    if (!rc) rc=write32(&e,HIPCI,0);
    if (!rc) rc=poll(&e,HIPCIE,DONE,0,50000u,0);
    if (!rc) rc=poll(&e,HIPCT,BUSY,0,50000u,0);
    if (rc) goto finish;
    result->phase=P360_L_POWER_UP;
    rc=update(&e,ADSPCS,CORES_SPA,CORES_SPA);
    if (!rc) rc=poll(&e,ADSPCS,CORES_CPA,CORES_CPA,50000u,0);
    if (rc) goto finish;
    /* Core 1 participates in first ROM boot but remains reset/stalled. */
    result->phase=P360_L_PURGE;
    rc=write32(&e,HIPCI,BUSY|0x01004000u|((uint32_t)(tag-1u)<<9));
    if (!rc) rc=update(&e,ADSPCS,1u,0);
    if (!rc) rc=poll(&e,ADSPCS,1u,0,50000u,0);
    if (!rc) rc=update(&e,ADSPCS,0x100u,0);
    if (!rc) rc=poll(&e,ADSPCS,0x01010101u,0x01010000u,50000u,0);
    if (!rc) rc=poll(&e,HIPCIE,DONE,DONE,500000u,0);
    if (!rc) rc=acknowledge(&e,HIPCIE,DONE);
    if (!rc) rc=poll(&e,HIPCIE,DONE,0,50000u,0);
    if (!rc) rc=poll(&e,HIPCI,BUSY,0,50000u,0);
    if (!rc) rc=update(&e,ADSPCS,0x00020000u,0);
    if (!rc) rc=poll(&e,ADSPCS,0x02000000u,0,50000u,0);
    if (rc) goto finish;
    result->phase=P360_L_ROM_INIT;
    rc=poll(&e,ROM_STATUS,P360_ROM_STATUS_MASK,1u,150000u,1);
    if (rc) goto finish;
    result->phase=P360_L_TRANSFER;
    if (ops->cancelled(context)) {rc=P360_L_CANCEL;goto finish;}
    if (ops->start(context)) {rc=P360_L_IO;goto finish;}
    rc=poll(&e,ROM_STATUS,P360_ROM_STATUS_MASK,P360_ROM_FW_ENTERED,3000000u,1);
    if (rc) goto finish;
    /* Stop and detach bus-master memory references before any buffer is freed. */
    if (ops->stop(context)) {rc=P360_L_QUARANTINE;goto finish;}
    stopped=1;
    result->phase=P360_L_FW_READY;
    rc=poll(&e,HIPCT,BUSY,BUSY,3000000u,1);
    if (!rc) rc=read32(&e,HIPCT,&v);
    if (!rc && v!=(BUSY|0x70000000u)) rc=P360_L_READY;
    if (!rc) rc=read32(&e,HIPCTE,&v);
    if (!rc && (v&0x7fffffffu)!=0x80u) rc=P360_L_READY;
    if (!rc && ops->read_ready(context,first)) rc=P360_L_IO;
    if (!rc && ops->read_ready(context,second)) rc=P360_L_IO;
    if (!rc) rc=p360_fw_ready_validate(first,second,sizeof(first));
    if (!rc) rc=read32(&e,HIPCT,&v);
    if (!rc && v!=(BUSY|0x70000000u)) rc=P360_L_READY;
    if (!rc) rc=acknowledge(&e,HIPCT,BUSY);
    if (!rc) rc=poll(&e,HIPCT,BUSY,0,50000u,0);
    if (!rc) rc=poll(&e,HIPCIE,DONE,0,50000u,0);
    if (!rc) rc=poll(&e,HIPCI,BUSY,0,50000u,0);
    if (!rc) rc=poll(&e,ADSPCS,0x03030303u,0x01010202u,50000u,0);
    if (rc) goto finish;
    result->phase=P360_L_CLEANUP;
    if (ops->release_dma(context)) {
        release_failed=1;rc=P360_L_QUARANTINE;goto finish;
    }
    dma_attempted=0;
    if (ops->release_platform(context,1)) {rc=P360_L_QUARANTINE;goto finish;}
    result->phase=P360_L_COMPLETE;result->boot_epoch=boot_epoch;result->ready_proved=1;
    loader->active=0;return 0;
finish:
    failed_phase=result->phase;e.cleaning=1;
    /* Cleanup ignores cancellation. Failed stop retains all DMA allocations. */
    if (dma_attempted && !stopped) {
        if (ops->stop(context)) cleanup=P360_L_QUARANTINE;
        else stopped=1;
    }
    if (touched) {
        int down=power_down(&e);
        if (down && !cleanup) cleanup=down;
        if (!down) {
            /*
             * baseline is the proved post-normalization OFF state, never the
             * unknown powered state observed when the ADSP PDO was attached.
             */
            int restore=update(&e,ADSPCS,CONTROL_MASK,baseline&CONTROL_MASK);
            if (restore && !cleanup) cleanup=restore;
        }
    }
    /* Even if cores stopped, an unproved DMA stop must not release memory. */
    if (dma_attempted && stopped) {
        if (release_failed || ops->release_dma(context)) cleanup=P360_L_QUARANTINE;
        else dma_attempted=0;
    }
    if (acquired && !cleanup && (!dma_attempted || stopped)) {
        if (ops->release_platform(context,0)) cleanup=P360_L_QUARANTINE;
        else acquired=0;
    }
    if (cleanup || dma_attempted || acquired) {
        loader->quarantined=1;result->resources_retained=1;
        if (!cleanup) cleanup=P360_L_QUARANTINE;
    }
    loader->active=0;result->phase=failed_phase;
    result->error=rc;result->cleanup_error=cleanup;
    return cleanup ? P360_L_QUARANTINE : rc;
}
