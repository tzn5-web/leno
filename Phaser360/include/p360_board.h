#pragma once
#include <stdint.h>
#include <stddef.h>

#define P360_INTEL_VENDOR_ID 0x8086u
#define P360_GLK_AUDIO_DEVICE_ID 0x3198u
#define P360_SAMPLE_RATE 48000u
#define P360_SPEAKER_CHANNELS 2u
#define P360_SPEAKER_CONTAINER_BITS 32u
#define P360_SPEAKER_PCM_VALID_BITS 16u
/*
 * Windows/CoolStar keeps a forced 32-bit output container, but the pinned
 * GLK SOF topology explicitly overrides the SSP1 backend to s16le.
 */
#define P360_SPEAKER_DAI_VALID_BITS 16u
#define P360_SPEAKER_DAI_SLOT_BITS 16u
#define P360_SPEAKER_SSP1_BCLK_HZ 1536000u
#define P360_SPEAKER_SSP1_MCLK_HZ 19200000u
#define P360_SPEAKER_SSP1_MCLK_ID 1u

typedef enum P360_ENDPOINT {
    P360_ENDPOINT_HEADPHONE = 0,
    P360_ENDPOINT_HEADSET_MIC,
    P360_ENDPOINT_SPEAKER,
    P360_ENDPOINT_DMIC
} P360_ENDPOINT;

typedef struct P360_BOARD_PROFILE {
    uint16_t pci_vendor;
    uint16_t pci_device;
    uint8_t ssp_amp;
    uint8_t ssp_codec;
    uint8_t dmic_index;
    uint32_t sample_rate;
    uint8_t speaker_channels;
    uint8_t speaker_container_bits;
    uint8_t speaker_pcm_valid_bits;
    uint8_t speaker_dai_valid_bits;
    uint8_t speaker_enabled_by_default;
} P360_BOARD_PROFILE;

typedef struct P360_NHLT_FACTS {
    uint32_t table_length;
    uint8_t checksum_ok;
    uint8_t ssp1_render;
    uint8_t ssp2_render;
    uint8_t ssp2_capture;
    uint8_t dmic_capture;
} P360_NHLT_FACTS;

extern const P360_BOARD_PROFILE g_p360_phaser360_profile;

int p360_board_validate_identity(uint16_t vendor, uint16_t device);
int p360_board_validate_nhlt(const P360_NHLT_FACTS *facts);
