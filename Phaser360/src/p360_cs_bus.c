#include "../include/p360_cs_bus.h"

static void p360_cs_zero(P360_CS_BUS *bus)
{
    if (bus) RtlZeroMemory(bus, sizeof(*bus));
}

NTSTATUS p360_cs_bus_open(P360_CS_BUS *bus, WDFDEVICE device)
{
    NTSTATUS status;

    if (!bus || !device)
        return STATUS_INVALID_PARAMETER;

    p360_cs_zero(bus);
    bus->device = device;

    status = WdfFdoQueryForInterface(
        device,
        &P360_GUID_ADSP_BUS_INTERFACE,
        (PINTERFACE)&bus->iface,
        sizeof(bus->iface),
        P360_CS_ADSP_INTERFACE_VERSION,
        NULL);

    if (!NT_SUCCESS(status))
        return status;

    if (bus->iface.Size != sizeof(bus->iface) ||
        bus->iface.Version != P360_CS_ADSP_INTERFACE_VERSION ||
        bus->iface.CtlrDevId != P360_CS_GLK_DEVICE_ID ||
        !bus->iface.Context ||
        !bus->iface.GetResources ||
        !bus->iface.RegisterInterrupt ||
        !bus->iface.UnregisterInterrupt ||
        !bus->iface.GetRenderStream ||
        !bus->iface.GetCaptureStream ||
        !bus->iface.FreeStream ||
        !bus->iface.PrepareDSP ||
        !bus->iface.CleanupDSP ||
        !bus->iface.TriggerDSP ||
        !bus->iface.StreamPosition) {
        p360_cs_bus_close(bus);
        return STATUS_REVISION_MISMATCH;
    }

    bus->interface_valid = TRUE;

    status = bus->iface.GetResources(
        bus->iface.Context,
        &bus->hda,
        &bus->dsp,
        &bus->ppcap,
        &bus->nhlt,
        &bus->pci);

    if (!NT_SUCCESS(status)) {
        p360_cs_bus_close(bus);
        return status;
    }

    status = p360_cs_bus_validate_resources(bus);
    if (!NT_SUCCESS(status)) {
        p360_cs_bus_close(bus);
        return status;
    }

    bus->resources_valid = TRUE;
    return STATUS_SUCCESS;
}

NTSTATUS p360_cs_bus_validate_resources(P360_CS_BUS *bus)
{
    if (!bus || !bus->interface_valid)
        return STATUS_INVALID_DEVICE_STATE;

    /*
     * B4 proved that 4 KiB was insufficient for the GLK HDA extended
     * capability chain; require at least 16 KiB before using the HDA BAR.
     * The DSP BAR must cover ROM status/mailbox addresses used by APL/GLK SOF.
     */
    if (!bus->hda.Base.Base || bus->hda.Len < 0x4000u)
        return STATUS_DEVICE_CONFIGURATION_ERROR;

    if (!bus->dsp.Base.Base || bus->dsp.Len < 0x90000u)
        return STATUS_DEVICE_CONFIGURATION_ERROR;

    if (!bus->nhlt.nhlt || bus->nhlt.nhltSz < 36u || bus->nhlt.nhltSz > 0x10000u)
        return STATUS_DEVICE_CONFIGURATION_ERROR;

    if (!bus->pci.GetBusData || !bus->pci.SetBusData)
        return STATUS_DEVICE_CONFIGURATION_ERROR;

    return STATUS_SUCCESS;
}

void p360_cs_bus_close(P360_CS_BUS *bus)
{
    if (!bus)
        return;

    /*
     * Current audited CoolStar v1 exposes no-op interface reference handlers,
     * but honor the standard INTERFACE lifetime contract anyway.
     */
    if (bus->interface_valid &&
        bus->iface.InterfaceDereference &&
        bus->iface.Context) {
        bus->iface.InterfaceDereference(bus->iface.Context);
    }

    p360_cs_zero(bus);
}
