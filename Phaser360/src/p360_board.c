#include "../include/p360_board.h"

const P360_BOARD_PROFILE g_p360_phaser360_profile = {
    P360_INTEL_VENDOR_ID,
    P360_GLK_AUDIO_DEVICE_ID,
    1, /* SSP1 -> MAX98357A */
    2, /* SSP2 -> DA7219 */
    0, /* DMIC0 */
    P360_SAMPLE_RATE,
    0  /* speaker disabled by default */
};

int p360_board_validate_identity(uint16_t vendor, uint16_t device)
{
    return vendor == g_p360_phaser360_profile.pci_vendor &&
           device == g_p360_phaser360_profile.pci_device;
}

int p360_board_validate_nhlt(const P360_NHLT_FACTS *facts)
{
    if (!facts) return 0;
    return facts->checksum_ok &&
           facts->table_length >= 36 &&
           facts->ssp1_render &&
           facts->ssp2_render &&
           facts->ssp2_capture &&
           facts->dmic_capture;
}
