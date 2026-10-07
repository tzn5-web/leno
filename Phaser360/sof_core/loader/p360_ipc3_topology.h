/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef P360_IPC3_TOPOLOGY_H
#define P360_IPC3_TOPOLOGY_H

#include <stddef.h>
#include <stdint.h>

#define P360_IPC3_TOPOLOGY_MAX_MESSAGE 216u

#define P360_IPC3_SPEAKER_PIPELINE_ID 1u
#define P360_IPC3_SPEAKER_TONE_ID     100u
#define P360_IPC3_SPEAKER_BUFFER_ID   101u
#define P360_IPC3_SPEAKER_DAI_ID      102u
#define P360_IPC3_SPEAKER_SCHED_ID    103u
#define P360_IPC3_TONE_NEW_BYTES       100u
#define P360_IPC3_BUFFER_NEW_BYTES      44u
#define P360_IPC3_DAI_NEW_BYTES         80u
#define P360_IPC3_PIPE_NEW_BYTES        48u
#define P360_IPC3_CONNECT_BYTES         16u
#define P360_IPC3_PIPE_READY_BYTES      12u
#define P360_IPC3_STREAM_BYTES          12u
#define P360_IPC3_DAI_CONFIG_BYTES     216u
#define P360_IPC3_PCM_PARAMS_BYTES     108u
#define P360_IPC3_TONE_CONTROL_BYTES   140u

#define P360_IPC3_GLB_TPLG_MSG   0x30000000u
#define P360_IPC3_GLB_STREAM_MSG 0x60000000u
#define P360_IPC3_GLB_DAI_MSG    0x80000000u
#define P360_IPC3_GLB_COMP_MSG   0x50000000u
#define P360_IPC3_TPLG_COMP_NEW  0x00010000u
#define P360_IPC3_TPLG_CONNECT   0x00030000u
#define P360_IPC3_TPLG_PIPE_NEW  0x00100000u
#define P360_IPC3_TPLG_PIPE_DONE 0x00130000u
#define P360_IPC3_TPLG_BUFFER_NEW 0x00200000u
#define P360_IPC3_STREAM_PCM_PARAMS 0x00010000u
#define P360_IPC3_STREAM_START   0x00040000u
#define P360_IPC3_STREAM_STOP    0x00050000u
#define P360_IPC3_DAI_CONFIG     0x00010000u
#define P360_IPC3_COMP_SET_DATA  0x00030000u

#define P360_IPC3_COMP_DAI    2u
#define P360_IPC3_COMP_TONE  10u
#define P360_IPC3_COMP_BUFFER 12u

#define P360_IPC3_FRAME_S16_LE  0u
#define P360_IPC3_FRAME_S24_4LE 1u
#define P360_IPC3_FRAME_S32_LE  2u

#define P360_IPC3_STREAM_PLAYBACK 0u
#define P360_IPC3_DAI_INTEL_SSP   1u
#define P360_IPC3_TIME_DMA         0u
#define P360_IPC3_TIME_TIMER       1u
#define P360_IPC3_BUFFER_INTERLEAVED 0u
#define P360_IPC3_MCLK_CODEC_INPUT 1u
#define P360_IPC3_CHMAP_UNKNOWN 0u
#define P360_IPC3_CHMAP_FL 3u
#define P360_IPC3_CHMAP_FR 4u


#define P360_IPC3_DAI_FMT_I2S      0x0001u
#define P360_IPC3_DAI_FMT_CONT     0x0010u
#define P360_IPC3_DAI_FMT_NB_NF    0x0000u
#define P360_IPC3_DAI_FMT_CBC_CFC  0x4000u

#define P360_IPC3_MEM_RAM   (1u << 0)
#define P360_IPC3_MEM_HP    (1u << 4)
#define P360_IPC3_MEM_DMA   (1u << 5)
#define P360_IPC3_MEM_CACHE (1u << 6)

enum p360_ipc3_topology_status {
    P360_IPC3_TOPOLOGY_OK = 0,
    P360_IPC3_TOPOLOGY_ARGUMENT = -1,
    P360_IPC3_TOPOLOGY_RANGE = -2,
    P360_IPC3_TOPOLOGY_PROFILE = -3
};

struct p360_ipc3_speaker_ids {
    uint32_t pipeline_id;
    uint32_t tone_id;
    uint32_t buffer_id;
    uint32_t dai_id;
    uint32_t pipe_comp_id;
};

struct p360_ipc3_ssp1_profile {
    uint16_t format;
    uint16_t mclk_id;
    uint32_t mclk_rate;
    uint32_t fsync_rate;
    uint32_t bclk_rate;
    uint32_t tdm_slots;
    uint32_t rx_slots;
    uint32_t tx_slots;
    uint32_t sample_valid_bits;
    uint16_t tdm_slot_width;
    uint32_t mclk_direction;
    uint16_t frame_pulse_width;
    uint16_t tdm_per_slot_padding_flag;
    uint32_t clks_control;
    uint32_t quirks;
    uint32_t bclk_delay;
    uint8_t group_id;
    uint8_t flags;
};

struct p360_ipc3_message {
    uint32_t bytes;
    uint8_t data[P360_IPC3_TOPOLOGY_MAX_MESSAGE];
};

int p360_ipc3_speaker_ids_validate(const struct p360_ipc3_speaker_ids *ids);
int p360_ipc3_ssp1_profile_validate(const struct p360_ipc3_ssp1_profile *profile);

int p360_ipc3_build_tone_new(struct p360_ipc3_message *out,
    const struct p360_ipc3_speaker_ids *ids, uint32_t sample_rate);
int p360_ipc3_build_buffer_new(struct p360_ipc3_message *out,
    const struct p360_ipc3_speaker_ids *ids, uint32_t bytes);
int p360_ipc3_build_dai_new(struct p360_ipc3_message *out,
    const struct p360_ipc3_speaker_ids *ids, uint32_t dai_index);
int p360_ipc3_build_pipe_new(struct p360_ipc3_message *out,
    const struct p360_ipc3_speaker_ids *ids, uint32_t period_us,
    uint32_t frames_per_sched);
int p360_ipc3_build_connect(struct p360_ipc3_message *out,
    uint32_t source_id, uint32_t sink_id);
int p360_ipc3_build_pipe_complete(struct p360_ipc3_message *out,
    const struct p360_ipc3_speaker_ids *ids);
int p360_ipc3_build_pcm_params(struct p360_ipc3_message *out,
    uint32_t comp_id, uint32_t sample_rate, uint16_t channels);
int p360_ipc3_build_tone_amplitude_control(struct p360_ipc3_message *out,
    uint32_t comp_id, int32_t amplitude_q1_31);
int p360_ipc3_build_tone_length_control(struct p360_ipc3_message *out,
    uint32_t comp_id, uint32_t blocks_125us);
int p360_ipc3_build_stream_trigger(struct p360_ipc3_message *out,
    uint32_t comp_id, int start);
int p360_ipc3_build_ssp1_config(struct p360_ipc3_message *out,
    uint32_t dai_index, const struct p360_ipc3_ssp1_profile *profile);

#endif
