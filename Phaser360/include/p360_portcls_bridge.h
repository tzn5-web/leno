#pragma once

#include <ntddk.h>
#include <wdf.h>

/*
 * PortCls owns PnP/power for the final audio adapter.  The WDF miniport handle
 * created here is only a framework view of the PortCls FDO; it is used by the
 * existing Phaser360 host modules for WdfFdoQueryForInterface and as a parent
 * for non-PnP framework objects.
 */
#ifdef __cplusplus
extern "C" {
#endif

NTSTATUS
p360_portcls_create_wdf_miniport(
    _In_ PDEVICE_OBJECT PortClsFdo,
    _In_opt_ PWDF_OBJECT_ATTRIBUTES Attributes,
    _Out_ WDFDEVICE *Device
    );

VOID
p360_portcls_delete_wdf_miniport(
    _Inout_ WDFDEVICE *Device
    );

#ifdef __cplusplus
}
#endif
