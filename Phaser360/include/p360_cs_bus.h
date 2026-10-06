#pragma once
#include "p360_coolstar_adsp.h"
#include "p360_board.h"

typedef struct P360_CS_BUS {
    WDFDEVICE device;
    P360_CS_ADSP_BUS_INTERFACE iface;
    P360_CS_PCI_BAR hda;
    P360_CS_PCI_BAR dsp;
    PVOID ppcap;
    P360_CS_NHLT_INFO nhlt;
    BUS_INTERFACE_STANDARD pci;
    BOOLEAN interface_valid;
    BOOLEAN resources_valid;
} P360_CS_BUS;

NTSTATUS p360_cs_bus_open(P360_CS_BUS *bus, WDFDEVICE device);
void p360_cs_bus_close(P360_CS_BUS *bus);
NTSTATUS p360_cs_bus_validate_resources(P360_CS_BUS *bus);
