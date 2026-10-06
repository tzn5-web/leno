#pragma once

#include <ntddk.h>
#include <wdf.h>

#include "../include/p360_state.h"
#include "../include/p360_board.h"
#include "../include/p360_nhlt.h"
#include "../include/p360_cs_bus.h"
#include "../include/p360_cs_boot.h"
#include "../include/p360_cs_runtime.h"
#include "../sof_core/loader/p360_loader.h"

/*
 * Same final driver, staged safely. This switch controls only whether D0Entry
 * starts the already-integrated SOF loader; it does not select a probe driver.
 */
#define P360_RUNTIME_BOOT_ENABLED 0

typedef struct _P360_DEVICE_CONTEXT {
    P360_STATE_MACHINE State;
    P360_NHLT_FACTS Nhlt;
    struct p360_pci_identity Identity;

    P360_CS_BUS Bus;
    P360_CS_BOOT_ADAPTER Boot;
    P360_CS_RUNTIME Runtime;
    struct p360_loader Loader;

    BOOLEAN BusOpen;
    BOOLEAN BootInitialized;
    BOOLEAN RuntimeInitialized;
    BOOLEAN Prepared;
    volatile LONG Removing;
} P360_DEVICE_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(P360_DEVICE_CONTEXT,P360GetContext)

DRIVER_INITIALIZE DriverEntry;
EVT_WDF_DRIVER_DEVICE_ADD P360EvtDeviceAdd;
EVT_WDF_DEVICE_PREPARE_HARDWARE P360EvtPrepareHardware;
EVT_WDF_DEVICE_RELEASE_HARDWARE P360EvtReleaseHardware;
EVT_WDF_DEVICE_D0_ENTRY P360EvtD0Entry;
EVT_WDF_DEVICE_D0_EXIT P360EvtD0Exit;
