#pragma once

#include <ntddk.h>
#include <wdf.h>

#include "../include/p360_state.h"
#include "../include/p360_board.h"
#include "../include/p360_nhlt.h"
#include "../include/p360_cs_bus.h"
#include "../include/p360_cs_boot.h"
#include "../include/p360_cs_runtime.h"
#include "../include/p360_firmware.h"
#include "../sof_core/loader/p360_loader.h"

/*
 * Same final driver, staged safely. This switch controls only whether D0Entry
 * starts the already-integrated SOF loader; it does not select a probe driver.
 */
#ifndef P360_RUNTIME_BOOT_ENABLED
#define P360_RUNTIME_BOOT_ENABLED 0
#endif

/*
 * Final endpoint shell gate. PortCls bridge code is compiled and audited, but
 * the active DriverEntry remains the current KMDF host until the PortCls
 * adapter lifecycle is complete.
 */
#ifndef P360_PORTCLS_SHELL_ENABLED
#define P360_PORTCLS_SHELL_ENABLED 0
#endif

#ifndef P360_IPC_PROBE_ENABLED
#define P360_IPC_PROBE_ENABLED 0
#endif


typedef struct _P360_DEVICE_CONTEXT {
    P360_STATE_MACHINE State;
    P360_NHLT_FACTS Nhlt;
    struct p360_pci_identity Identity;

    P360_CS_BUS Bus;
    P360_CS_BOOT_ADAPTER Boot;
    P360_CS_RUNTIME Runtime;
    struct p360_loader Loader;
    ULONGLONG BootEpoch;

    WDFDEVICE FrameworkDevice;
    PDEVICE_OBJECT PortClsFdo;

    BOOLEAN BusOpen;
    BOOLEAN BootInitialized;
    BOOLEAN RuntimeInitialized;
    BOOLEAN Prepared;
    volatile LONG Removing;
} P360_DEVICE_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(P360_DEVICE_CONTEXT,P360GetContext)

#ifdef __cplusplus
extern "C" {
#endif

NTSTATUS p360_host_prepare(
    _Inout_ P360_DEVICE_CONTEXT *ctx,
    _In_ WDFDEVICE Device);
NTSTATUS p360_host_release(
    _Inout_ P360_DEVICE_CONTEXT *ctx);
NTSTATUS p360_host_d0_entry(
    _Inout_ P360_DEVICE_CONTEXT *ctx);
NTSTATUS p360_host_d0_exit(
    _Inout_ P360_DEVICE_CONTEXT *ctx);

NTSTATUS p360_portcls_driver_initialize(
    _In_ PDRIVER_OBJECT DriverObject,
    _In_ PUNICODE_STRING RegistryPath);

DRIVER_INITIALIZE DriverEntry;
EVT_WDF_DRIVER_DEVICE_ADD P360EvtDeviceAdd;
EVT_WDF_DEVICE_PREPARE_HARDWARE P360EvtPrepareHardware;
EVT_WDF_DEVICE_RELEASE_HARDWARE P360EvtReleaseHardware;
EVT_WDF_DEVICE_D0_ENTRY P360EvtD0Entry;
EVT_WDF_DEVICE_D0_EXIT P360EvtD0Exit;

#ifdef __cplusplus
}
#endif
