#pragma once

#include <ntddk.h>

#ifdef __cplusplus
extern "C" {
#endif

NTSTATUS
p360_speaker_endpoint_install(
    _In_ PDEVICE_OBJECT DeviceObject,
    _In_opt_ PIRP Irp,
    _In_ PRESOURCELIST ResourceList,
    _Outptr_result_maybenull_ PVOID *TopologyPort,
    _Outptr_result_maybenull_ PVOID *WavePort
    );

NTSTATUS
p360_speaker_endpoint_uninstall(
    _In_ PDEVICE_OBJECT DeviceObject,
    _Inout_ PVOID *TopologyPort,
    _Inout_ PVOID *WavePort
    );

#ifdef __cplusplus
}
#endif
