#include "../include/p360_cs_bus.h"
#include "../include/p360_telemetry.h"

static void p360_cs_zero(P360_CS_BUS *bus)
{
    if (bus) RtlZeroMemory(bus, sizeof(*bus));
}

static ULONG p360_cs_abi_detail(const P360_CS_ADSP_BUS_INTERFACE *i)
{
    ULONG d=0;
    if (!i) return MAXULONG;
    if (i->Size!=sizeof(*i)) d|=P360_PREP_ABI_SIZE;
    if (i->Version!=P360_CS_ADSP_INTERFACE_VERSION) d|=P360_PREP_ABI_VERSION;
    if (i->CtlrDevId!=P360_CS_GLK_DEVICE_ID) d|=P360_PREP_ABI_DEVICE_ID;
    if (!i->Context) d|=P360_PREP_ABI_CONTEXT;
    if (!i->GetResources) d|=P360_PREP_ABI_GET_RESOURCES;
    if (!i->SetDSPPowerState) d|=P360_PREP_ABI_SET_POWER;
    if (!i->RegisterInterrupt) d|=P360_PREP_ABI_REGISTER_IRQ;
    if (!i->UnregisterInterrupt) d|=P360_PREP_ABI_UNREGISTER_IRQ;
    if (!i->GetRenderStream) d|=P360_PREP_ABI_GET_RENDER;
    if (!i->FreeStream) d|=P360_PREP_ABI_FREE_STREAM;
    if (!i->PrepareDSP) d|=P360_PREP_ABI_PREPARE_DSP;
    if (!i->CleanupDSP) d|=P360_PREP_ABI_CLEANUP_DSP;
    if (!i->TriggerDSP) d|=P360_PREP_ABI_TRIGGER_DSP;
    if (!i->StreamPosition) d|=P360_PREP_ABI_STREAM_POSITION;
    return d;
}

static ULONG p360_cs_resource_detail(const P360_CS_BUS *bus)
{
    ULONG d=0;
    if (!bus) return MAXULONG;
    if (!bus->hda.Base.Base) d|=P360_PREP_RES_HDA_BASE;
    if (bus->hda.Len<0x4000u) d|=P360_PREP_RES_HDA_LEN;
    if (!bus->dsp.Base.Base) d|=P360_PREP_RES_DSP_BASE;
    if (bus->dsp.Len<0xA2000u) d|=P360_PREP_RES_DSP_LEN;
    if (!bus->ppcap) d|=P360_PREP_RES_PPCAP;
    if (!bus->nhlt.nhlt) d|=P360_PREP_RES_NHLT_PTR;
    if (bus->nhlt.nhltSz<36u || bus->nhlt.nhltSz>0x10000u) d|=P360_PREP_RES_NHLT_SIZE;
    if (!bus->pci.GetBusData) d|=P360_PREP_RES_PCI_GET;
    if (!bus->pci.SetBusData) d|=P360_PREP_RES_PCI_SET;
    return d;
}

NTSTATUS p360_cs_bus_open(P360_CS_BUS *bus, WDFDEVICE device)
{
    NTSTATUS status;

    if (!bus || !device)
        return STATUS_INVALID_PARAMETER;

    p360_cs_zero(bus);
    bus->device = device;

    (void)p360_telemetry_prepare(P360_PREP_STEP_BUS_QUERY_INTERFACE,0,STATUS_PENDING);
    status = WdfFdoQueryForInterface(
        device,
        &P360_GUID_ADSP_BUS_INTERFACE,
        (PINTERFACE)&bus->iface,
        sizeof(bus->iface),
        P360_CS_ADSP_INTERFACE_VERSION,
        NULL);

    (void)p360_telemetry_prepare(P360_PREP_STEP_BUS_QUERY_INTERFACE,0,status);
    if (!NT_SUCCESS(status))
        return status;

    /*
     * WdfFdoQueryForInterface has completed the query-interface lifetime
     * handshake. Track that independently from our stricter ABI validation.
     */
    bus->interface_acquired = TRUE;

    /*
     * Speaker-only runtime requires the render half of the CoolStar v1
     * interface. Capture is intentionally not a startup prerequisite until a
     * microphone/headset-capture endpoint is implemented.
     */
    (void)p360_telemetry_prepare(P360_PREP_STEP_BUS_ABI_VALIDATE,0,STATUS_PENDING);
    if (bus->iface.Size != sizeof(bus->iface) ||
        bus->iface.Version != P360_CS_ADSP_INTERFACE_VERSION ||
        bus->iface.CtlrDevId != P360_CS_GLK_DEVICE_ID ||
        !bus->iface.Context ||
        !bus->iface.GetResources ||
        !bus->iface.RegisterInterrupt ||
        !bus->iface.UnregisterInterrupt ||
        !bus->iface.GetRenderStream ||
        !bus->iface.FreeStream ||
        !bus->iface.PrepareDSP ||
        !bus->iface.CleanupDSP ||
        !bus->iface.TriggerDSP ||
        !bus->iface.StreamPosition) {
        status=STATUS_REVISION_MISMATCH;
        (void)p360_telemetry_prepare(P360_PREP_STEP_BUS_ABI_VALIDATE,p360_cs_abi_detail(&bus->iface),status);
        p360_cs_bus_close(bus);
        return status;
    }

    (void)p360_telemetry_prepare(P360_PREP_STEP_BUS_ABI_VALIDATE,0,STATUS_SUCCESS);
    bus->interface_valid = TRUE;

    (void)p360_telemetry_prepare(P360_PREP_STEP_BUS_GET_RESOURCES,0,STATUS_PENDING);
    status = bus->iface.GetResources(
        bus->iface.Context,
        &bus->hda,
        &bus->dsp,
        &bus->ppcap,
        &bus->nhlt,
        &bus->pci);

    (void)p360_telemetry_prepare(P360_PREP_STEP_BUS_GET_RESOURCES,0,status);
    if (!NT_SUCCESS(status)) {
        p360_cs_bus_close(bus);
        return status;
    }

    (void)p360_telemetry_prepare(P360_PREP_STEP_BUS_VALIDATE,0,STATUS_PENDING);
    status = p360_cs_bus_validate_resources(bus);
    (void)p360_telemetry_prepare(P360_PREP_STEP_BUS_VALIDATE,NT_SUCCESS(status) ? 0 : p360_cs_resource_detail(bus),status);
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

        if (got!=sizeof(ULONG)) {
            (void)p360_telemetry_prepare(
                P360_PREP_STEP_PCI_IDENTITY,
                P360_PREP_ID_READ | offset,
                STATUS_DEVICE_DATA_ERROR);
            return STATUS_DEVICE_DATA_ERROR;
        }
    }

    {
        int rc=p360_pci_validate(config,sizeof(config),identity);
        if (rc!=0) {
            (void)p360_telemetry_prepare(
                P360_PREP_STEP_PCI_IDENTITY,
                P360_PREP_ID_VALIDATE | ((ULONG)(-rc) & 0xffffu),
                STATUS_DEVICE_CONFIGURATION_ERROR);
            return STATUS_DEVICE_CONFIGURATION_ERROR;
        }
    }

    /*
     * B4 additionally requires bus mastering before any firmware DMA.
     * Do not alter PCI COMMAND here; fail closed if firmware/BIOS/bus did not
     * leave both Memory Space and Bus Master enabled.
     */
    if ((identity->command & 6u)!=6u) {
        (void)p360_telemetry_prepare(
            P360_PREP_STEP_PCI_IDENTITY,
            P360_PREP_ID_COMMAND | (ULONG)identity->command,
            STATUS_DEVICE_CONFIGURATION_ERROR);
        return STATUS_DEVICE_CONFIGURATION_ERROR;
    }

    (void)p360_telemetry_prepare(
        P360_PREP_STEP_PCI_IDENTITY,
        (ULONG)identity->command,
        STATUS_SUCCESS);
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
    if (bus->interface_acquired &&
        bus->iface.InterfaceDereference) {
        bus->iface.InterfaceDereference(bus->iface.Context);
    }

    p360_cs_zero(bus);
}
