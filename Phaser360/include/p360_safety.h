#pragma once
#include "p360_state.h"

#define P360_ENABLE_INTERNAL_SPEAKER 0

typedef struct P360_SAFETY_POLICY {
    unsigned require_exact_pci_identity : 1;
    unsigned require_valid_nhlt : 1;
    unsigned require_fw_ready : 1;
    unsigned require_ipc_ready : 1;
    unsigned require_topology_ready : 1;
    unsigned require_audio_core_before_speaker : 1;
    unsigned internal_speaker_compile_enabled : 1;
} P360_SAFETY_POLICY;

extern const P360_SAFETY_POLICY g_p360_default_safety_policy;

int p360_safety_can_start_headphone(const P360_STATE_MACHINE *sm);
int p360_safety_can_start_speaker(const P360_STATE_MACHINE *sm);
