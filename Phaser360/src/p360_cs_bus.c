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
     * The B4 IPC dispatcher uses the reply mailbox at 0xA0000 and validates
     * a mapping of at least 0xA2000 bytes.
     */
    if (!bus->hda.Base.Base || bus->hda.Len < 0x4000u)
        return STATUS_DEVICE_CONFIGURATION_ERROR;

    if (!bus->dsp.Base.Base || bus->dsp.Len < 0xA2000u)
        return STATUS_DEVICE_CONFIGURATION_ERROR;

    /*
     * Pinned CoolStar GetRenderStream() accesses PPCTL through ppcap.
     * Treat a missing PP capability as a hard configuration failure rather
     * than allowing a later NULL MMIO dereference.
     */
    if (!bus->ppcap)
        return STATUS_DEVICE_CONFIGURATION_ERROR;

    if (!bus->nhlt.nhlt || bus->nhlt.nhltSz < 36u || bus->nhlt.nhltSz > 0x10000u)
        return STATUS_DEVICE_CONFIGURATION_ERROR;

    if (!bus->pci.GetBusData || !bus->pci.SetBusData)
        return STATUS_DEVICE_CONFIGURATION_ERROR;

    return STATUS_SUCCESS;
}

NTSTATUS p360_cs_bus_read_identity(
    P360_CS_BUS *bus,
    struct p360_pci_identity *identity)
{
    UCHAR config[256];
    ULONG offset;

    if (!bus || !identity || !bus->resources_valid ||
        !bus->pci.GetBusData)
        return STATUS_INVALID_DEVICE_STATE;

    RtlZeroMemory(config,sizeof(config));
    RtlZeroMemory(identity,sizeof(*identity));

    for (offset=0;offset<sizeof(config);offset+=sizeof(ULONG)) {
        ULONG got=bus->pci.GetBusData(
            bus->pci.Context,
            PCI_WHICHSPACE_CONFIG,
            config+offset,
            offset,
            sizeof(ULONG));

        if (got!=sizeof(ULONG))
            return STATUS_DEVICE_DATA_ERROR;
    }

    if (p360_pci_validate(config,sizeof(config),identity)!=0)
        return STATUS_DEVICE_CONFIGURATION_ERROR;

    /*
     * B4 additionally requires bus mastering before any firmware DMA.
     * Do not alter PCI COMMAND here; fail closed if firmware/BIOS/bus did not
     * leave both Memory Space and Bus Master enabled.
     */
    if ((identity->command & 6u)!=6u)
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
