#include "../include/p360_safety.h"

const P360_SAFETY_POLICY g_p360_default_safety_policy = {
    1, 1, 1, 1, 1, 1, P360_ENABLE_INTERNAL_SPEAKER
};

int p360_safety_can_start_headphone(const P360_STATE_MACHINE *sm)
{
    if (!sm) return 0;
    return sm->state == P360_STATE_AUDIO_CORE_READY &&
           sm->hardware_identity_ok &&
           sm->nhlt_ok &&
           sm->fw_ready &&
           sm->ipc_ready &&
           sm->topology_ready &&
           sm->audio_core_ready &&
           !sm->headphone_ready &&
           !sm->speaker_runtime_armed;
}

int p360_safety_can_start_speaker(const P360_STATE_MACHINE *sm)
{
#if P360_ENABLE_INTERNAL_SPEAKER
    return p360_speaker_may_arm(sm);
#else
    (void)sm;
    return 0;
#endif
}
