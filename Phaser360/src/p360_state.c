#include "../include/p360_state.h"

void p360_state_init(P360_STATE_MACHINE *sm)
{
    if (!sm) return;
    *sm = (P360_STATE_MACHINE){0};
    sm->state = P360_STATE_DISCOVER;
}

static int p360_transition_allowed(P360_RUNTIME_STATE from, P360_RUNTIME_STATE to)
{
    if (to == P360_STATE_FAILED) return 1;
    return (int)to == ((int)from + 1);
}

int p360_state_advance(P360_STATE_MACHINE *sm, P360_RUNTIME_STATE next)
{
    if (!sm) return 0;
    if (!p360_transition_allowed(sm->state, next)) return 0;
    sm->state = next;
    sm->generation++;
    return 1;
}

void p360_state_fail(P360_STATE_MACHINE *sm, P360_FAILURE_REASON why)
{
    if (!sm) return;
    sm->speaker_runtime_armed = 0;
    sm->failure = why;
    sm->state = P360_STATE_FAILED;
    sm->generation++;
}

int p360_speaker_may_arm(const P360_STATE_MACHINE *sm)
{
    if (!sm) return 0;
    return
        sm->state == P360_STATE_HEADPHONE_READY &&
        sm->hardware_identity_ok &&
        sm->nhlt_ok &&
        sm->fw_ready &&
        sm->ipc_ready &&
        sm->topology_ready &&
        sm->audio_core_ready &&
        sm->headphone_ready &&
        sm->speaker_policy_enabled;
}

int p360_state_runtime_reset(P360_STATE_MACHINE *sm, int quiesced)
{
    if (!sm || !quiesced ||
        !sm->hardware_identity_ok ||
        !sm->nhlt_ok)
        return 0;

    sm->fw_ready = 0;
    sm->ipc_ready = 0;
    sm->topology_ready = 0;
    sm->audio_core_ready = 0;
    sm->headphone_ready = 0;
    sm->speaker_runtime_armed = 0;
    sm->failure = P360_FAIL_NONE;
    sm->state = P360_STATE_RESOURCES_OK;
    sm->generation++;
    return 1;
}
