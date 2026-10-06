#include <assert.h>
#include <stdio.h>
#include "../include/p360_state.h"
#include "../include/p360_board.h"
#include "../include/p360_safety.h"

static void test_board(void)
{
    P360_NHLT_FACTS ok = {3684u, 1, 1, 1, 1, 1};
    P360_NHLT_FACTS bad = ok;

    assert(p360_board_validate_identity(0x8086u, 0x3198u));
    assert(!p360_board_validate_identity(0x8086u, 0x1234u));
    assert(p360_board_validate_nhlt(&ok));

    bad.ssp2_capture = 0;
    assert(!p360_board_validate_nhlt(&bad));
}

static void test_state_machine(void)
{
    P360_STATE_MACHINE sm;
    p360_state_init(&sm);

    assert(sm.state == P360_STATE_DISCOVER);
    assert(!p360_state_advance(&sm, P360_STATE_SOF_READY));

    sm.hardware_identity_ok = 1;
    sm.nhlt_ok = 1;

    assert(p360_state_advance(&sm, P360_STATE_RESOURCES_OK));
    assert(p360_state_advance(&sm, P360_STATE_SOF_BOOTING));

    sm.fw_ready = 1;
    assert(p360_state_advance(&sm, P360_STATE_SOF_READY));

    sm.ipc_ready = 1;
    assert(p360_state_advance(&sm, P360_STATE_IPC_READY));

    sm.topology_ready = 1;
    assert(p360_state_advance(&sm, P360_STATE_TOPOLOGY_READY));

    sm.audio_core_ready = 1;
    assert(p360_state_advance(&sm, P360_STATE_AUDIO_CORE_READY));
    assert(p360_safety_can_start_headphone(&sm));

    sm.headphone_ready = 1;
    assert(p360_state_advance(&sm, P360_STATE_HEADPHONE_READY));

    /* Runtime proof may only be discarded after the caller proves quiescence. */
    assert(!p360_state_runtime_reset(&sm, 0));
    assert(sm.state == P360_STATE_HEADPHONE_READY);
    assert(p360_state_runtime_reset(&sm, 1));
    assert(sm.state == P360_STATE_RESOURCES_OK);
    assert(sm.hardware_identity_ok && sm.nhlt_ok);
    assert(!sm.fw_ready && !sm.ipc_ready && !sm.topology_ready &&
           !sm.audio_core_ready && !sm.headphone_ready &&
           !sm.speaker_runtime_armed);

    /* Rebuild the proven chain for the speaker fail-closed assertion. */
    assert(p360_state_advance(&sm, P360_STATE_SOF_BOOTING));
    sm.fw_ready = 1;
    assert(p360_state_advance(&sm, P360_STATE_SOF_READY));
    sm.ipc_ready = 1;
    assert(p360_state_advance(&sm, P360_STATE_IPC_READY));
    sm.topology_ready = 1;
    assert(p360_state_advance(&sm, P360_STATE_TOPOLOGY_READY));
    sm.audio_core_ready = 1;
    assert(p360_state_advance(&sm, P360_STATE_AUDIO_CORE_READY));
    sm.headphone_ready = 1;
    assert(p360_state_advance(&sm, P360_STATE_HEADPHONE_READY));

    /* Initial builds must never allow internal speaker start. */
    sm.speaker_policy_enabled = 1;
    assert(!p360_safety_can_start_speaker(&sm));

    p360_state_fail(&sm, P360_FAIL_STREAM);
    assert(sm.state == P360_STATE_FAILED);
    assert(sm.failure == P360_FAIL_STREAM);
    assert(!sm.speaker_runtime_armed);
}

int main(void)
{
    test_board();
    test_state_machine();
    puts("P360 core smoke: PASS");
    return 0;
}
