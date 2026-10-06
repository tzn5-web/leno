#include "../include/p360_portcls_bridge.h"

#include <portcls.h>
#include <wdfminiport.h>

NTSTATUS
p360_portcls_create_wdf_miniport(
    _In_ PDEVICE_OBJECT PortClsFdo,
    _Out_ WDFDEVICE *Device
    )
{
    PDEVICE_OBJECT pdo=NULL;
    PDEVICE_OBJECT lower=NULL;
    NTSTATUS status;

    if (!PortClsFdo || !Device ||
        KeGetCurrentIrql()!=PASSIVE_LEVEL) {
        return STATUS_INVALID_PARAMETER;
    }

    *Device=NULL;

    status=PcGetPhysicalDeviceObject(
        PortClsFdo,
        &pdo);
    if (!NT_SUCCESS(status) || !pdo)
        return NT_SUCCESS(status) ? STATUS_NO_SUCH_DEVICE : status;

    /*
     * WdfDeviceMiniportCreate accepts the existing port-driver FDO. Supplying
     * the next-lower device and PDO makes the lower edge explicit; this WDF
     * miniport is then permitted to call WdfFdoQueryForInterface.
     */
    lower=IoGetLowerDeviceObject(PortClsFdo);
    if (!lower)
        return STATUS_NO_SUCH_DEVICE;

    status=WdfDeviceMiniportCreate(
        WdfGetDriver(),
        WDF_NO_OBJECT_ATTRIBUTES,
        PortClsFdo,
        lower,
        pdo,
        Device);

    ObDereferenceObject(lower);

    if (!NT_SUCCESS(status))
        *Device=NULL;

    return status;
}

VOID
p360_portcls_delete_wdf_miniport(
    _Inout_ WDFDEVICE *Device
    )
{
    if (!Device || !*Device)
        return;

    WdfObjectDelete(*Device);
    *Device=NULL;
}
