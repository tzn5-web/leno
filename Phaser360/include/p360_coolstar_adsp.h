#pragma once
/*
 * ABI compatibility definition for CoolStar sklhdaudbus ADSP interface.
 * Pinned reference:
 *   coolstar/sklhdaudbus
 *   commit 5477b93a3b68c474819abf2094a49d0e2d8d9799
 *   sklhdaudbus/adsp.h
 *
 * This file intentionally contains only the ABI needed by Phaser360.
 */
#include <ntddk.h>
#include <wdf.h>
#include <hdaudio.h>

#define P360_CS_ADSP_INTERFACE_VERSION 1u
#define P360_CS_GLK_DEVICE_ID 0x3198u

/* {752A2CAE-3455-4D18-A184-8B34B22632CE} */
static const GUID P360_GUID_ADSP_BUS_INTERFACE =
{ 0x752a2cae, 0x3455, 0x4d18, { 0xa1, 0x84, 0x8b, 0x34, 0xb2, 0x26, 0x32, 0xce } };

typedef union P360_CS_BASEADDR {
    PVOID Base;
    UINT8 *baseptr;
} P360_CS_BASEADDR;

typedef struct P360_CS_PCI_BAR {
    P360_CS_BASEADDR Base;
    ULONG Len;
} P360_CS_PCI_BAR;

typedef struct P360_CS_NHLT_INFO {
    PVOID nhlt;
    UINT64 nhltSz;
} P360_CS_NHLT_INFO;

typedef NTSTATUS (*P360_CS_GET_RESOURCES)(
    PVOID context,
    P360_CS_PCI_BAR *hdaBar,
    P360_CS_PCI_BAR *adspBar,
    PVOID *ppcap,
    P360_CS_NHLT_INFO *nhltInfo,
    BUS_INTERFACE_STANDARD *pciConfig);

typedef NTSTATUS (*P360_CS_SET_POWER_STATE)(PVOID context, DEVICE_POWER_STATE state);
typedef LONG P360_CS_BOOL;
typedef P360_CS_BOOL (*P360_CS_INTERRUPT_CALLBACK)(PVOID context);
typedef NTSTATUS (*P360_CS_REGISTER_INTERRUPT)(PVOID context, P360_CS_INTERRUPT_CALLBACK callback, PVOID callbackContext);
typedef NTSTATUS (*P360_CS_UNREGISTER_INTERRUPT)(PVOID context);
typedef NTSTATUS (*P360_CS_GET_STREAM)(PVOID context, HDAUDIO_STREAM_FORMAT format, PHANDLE handle, UINT8 *streamTag);
typedef NTSTATUS (*P360_CS_FREE_STREAM)(PVOID context, HANDLE handle);
typedef NTSTATUS (*P360_CS_PREPARE_STREAM)(PVOID context, HANDLE handle, unsigned int byteSize, int fragments, PVOID *bdlBuf);
typedef NTSTATUS (*P360_CS_CLEANUP_STREAM)(PVOID context, HANDLE handle);
typedef void (*P360_CS_TRIGGER_STREAM)(PVOID context, HANDLE handle, P360_CS_BOOL startStop);
typedef UINT32 (*P360_CS_STREAM_POSITION)(PVOID context, HANDLE handle);
typedef void (*P360_CS_ENABLE_SPIB)(PVOID context, HANDLE handle, UINT32 value);
typedef void (*P360_CS_DISABLE_SPIB)(PVOID context, HANDLE handle);

typedef struct P360_CS_ADSP_BUS_INTERFACE {
    USHORT Size;
    USHORT Version;
    PVOID Context;
    PINTERFACE_REFERENCE InterfaceReference;
    PINTERFACE_DEREFERENCE InterfaceDereference;

    UINT16 CtlrDevId;
    P360_CS_GET_RESOURCES GetResources;
    P360_CS_SET_POWER_STATE SetDSPPowerState;
    P360_CS_REGISTER_INTERRUPT RegisterInterrupt;
    P360_CS_UNREGISTER_INTERRUPT UnregisterInterrupt;
    P360_CS_GET_STREAM GetRenderStream;
    P360_CS_GET_STREAM GetCaptureStream;
    P360_CS_FREE_STREAM FreeStream;
    P360_CS_PREPARE_STREAM PrepareDSP;
    P360_CS_CLEANUP_STREAM CleanupDSP;
    P360_CS_TRIGGER_STREAM TriggerDSP;
    P360_CS_STREAM_POSITION StreamPosition;
    P360_CS_ENABLE_SPIB DSPEnableSPIB;
    P360_CS_DISABLE_SPIB DSPDisableSPIB;
} P360_CS_ADSP_BUS_INTERFACE;

#if defined(_WIN64)
C_ASSERT(sizeof(P360_CS_BOOL) == 4);
C_ASSERT(sizeof(P360_CS_BASEADDR) == 8);
C_ASSERT(sizeof(P360_CS_PCI_BAR) == 16);
C_ASSERT(FIELD_OFFSET(P360_CS_PCI_BAR, Base) == 0);
C_ASSERT(FIELD_OFFSET(P360_CS_PCI_BAR, Len) == 8);
C_ASSERT(sizeof(P360_CS_NHLT_INFO) == 16);
C_ASSERT(sizeof(P360_CS_ADSP_BUS_INTERFACE) == 144);
C_ASSERT(FIELD_OFFSET(P360_CS_ADSP_BUS_INTERFACE, GetResources) == 40);
C_ASSERT(FIELD_OFFSET(P360_CS_ADSP_BUS_INTERFACE, RegisterInterrupt) == 56);
C_ASSERT(FIELD_OFFSET(P360_CS_ADSP_BUS_INTERFACE, GetRenderStream) == 72);
C_ASSERT(FIELD_OFFSET(P360_CS_ADSP_BUS_INTERFACE, PrepareDSP) == 96);
C_ASSERT(FIELD_OFFSET(P360_CS_ADSP_BUS_INTERFACE, StreamPosition) == 120);
#endif
