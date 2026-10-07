#include "../include/p360_board.h"

const P360_BOARD_PROFILE g_p360_phaser360_profile = {
    P360_INTEL_VENDOR_ID,
    P360_GLK_AUDIO_DEVICE_ID,
    1, /* SSP1 -> MAX98357A */
    2, /* SSP2 -> DA7219 */
    0, /* DMIC0 */
    P360_SAMPLE_RATE,
    P360_SPEAKER_CHANNELS,
    P360_SPEAKER_CONTAINER_BITS,
    P360_SPEAKER_PCM_VALID_BITS,
    P360_SPEAKER_DAI_VALID_BITS,
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

    /*
     * The current Windows package exposes only the internal-speaker render
     * path.  Do not make unrelated future endpoints (SSP2 headset/codec or
     * DMIC capture) prerequisites for bringing up SSP1 -> MAX98357A.
     *
     * We still require a structurally valid/checksummed NHLT table and the
     * exact SSP1 render descriptor used to validate the speaker wiring.
     */
    return facts->checksum_ok &&
           facts->table_length >= 36 &&
           facts->ssp1_render;
}
