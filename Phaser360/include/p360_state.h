#pragma once
#include <stdint.h>

typedef enum P360_RUNTIME_STATE {
    P360_STATE_DISCOVER = 0,
    P360_STATE_RESOURCES_OK,
    P360_STATE_SOF_BOOTING,
    P360_STATE_SOF_READY,
    P360_STATE_IPC_READY,
    P360_STATE_TOPOLOGY_READY,
    P360_STATE_AUDIO_CORE_READY,
    P360_STATE_HEADPHONE_READY,
    P360_STATE_SPEAKER_ARMED,
    P360_STATE_FAILED
} P360_RUNTIME_STATE;

typedef enum P360_FAILURE_REASON {
    P360_FAIL_NONE = 0,
    P360_FAIL_IDENTITY,
    P360_FAIL_RESOURCES,
    P360_FAIL_NHLT,
    P360_FAIL_FIRMWARE,
    P360_FAIL_FW_READY,
    P360_FAIL_IRQ,
    P360_FAIL_IPC,
    P360_FAIL_TOPOLOGY,
    P360_FAIL_STREAM,
    P360_FAIL_CODEC,
    P360_FAIL_SPEAKER_GUARD
} P360_FAILURE_REASON;

typedef struct P360_STATE_MACHINE {
    P360_RUNTIME_STATE state;
    P360_FAILURE_REASON failure;
    uint32_t generation;
    uint8_t hardware_identity_ok;
    uint8_t nhlt_ok;
    uint8_t fw_ready;
    uint8_t ipc_ready;
    uint8_t topology_ready;
    uint8_t audio_core_ready;
    uint8_t headphone_ready;
    uint8_t speaker_policy_enabled;
    uint8_t speaker_runtime_armed;
} P360_STATE_MACHINE;

void p360_state_init(P360_STATE_MACHINE *sm);
int p360_state_advance(P360_STATE_MACHINE *sm, P360_RUNTIME_STATE next);
void p360_state_fail(P360_STATE_MACHINE *sm, P360_FAILURE_REASON why);
int p360_speaker_may_arm(const P360_STATE_MACHINE *sm);
