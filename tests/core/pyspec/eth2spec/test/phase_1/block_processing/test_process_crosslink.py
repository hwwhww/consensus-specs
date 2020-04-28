from eth2spec.test.context import (
    with_all_phases_except,
    spec_state_test,
    always_bls,
)
from eth2spec.test.helpers.attestations import (
    get_valid_on_time_attestation,
)
from eth2spec.test.helpers.crosslinks import (
    run_crosslinks_processing,
)
from eth2spec.test.helpers.shard_block import build_shard_block
from eth2spec.test.helpers.state import next_epoch, next_slot, next_slots


@with_all_phases_except(['phase0'])
@spec_state_test
@always_bls
def test_basic_crosslinks(spec, state):
    next_epoch(spec, state)
    next_epoch(spec, state)
    state = spec.upgrade_to_phase1(state)
    next_slot(spec, state)

    committee_index = spec.CommitteeIndex(0)
    shard = spec.compute_shard_from_committee_index(state, committee_index, state.slot)
    body = b'\x56' * spec.MAX_SHARD_BLOCK_SIZE
    shard_block = build_shard_block(spec, state, shard, body=body, slot=state.slot, signed=True)
    shard_blocks = [shard_block]

    next_slot(spec, state)

    shard_transition = spec.get_shard_transition(state, shard, shard_blocks)
    shard_transitions = [spec.ShardTransition()] * len(state.shard_states)
    shard_transitions[shard] = shard_transition

    attestation = get_valid_on_time_attestation(
        spec,
        state,
        slot=state.slot,
        index=committee_index,
        shard_transition=shard_transition,
        signed=True,
    )
    attestations = [attestation]

    pre_gasprice = state.shard_states[shard].gasprice
    offset_slots = spec.get_offset_slots(state, shard)
    assert len(offset_slots) == 1

    yield from run_crosslinks_processing(spec, state, shard_transitions, attestations)

    shard_state = state.shard_states[shard]
    assert shard_state.slot == offset_slots[-1]
    assert shard_state.latest_block_root == shard_block.message.hash_tree_root()
    assert shard_state == shard_transition.shard_states[len(shard_transition.shard_states) - 1]
    assert shard_state.gasprice > pre_gasprice


@with_all_phases_except(['phase0'])
@spec_state_test
@always_bls
def test_multiple_offset_slots(spec, state):
    next_epoch(spec, state)
    next_epoch(spec, state)
    state = spec.upgrade_to_phase1(state)
    next_slot(spec, state)

    committee_index = spec.CommitteeIndex(0)
    shard = spec.compute_shard_from_committee_index(state, committee_index, state.slot)
    body = b'\x56' * spec.MAX_SHARD_BLOCK_SIZE
    shard_block = build_shard_block(spec, state, shard, body=body, slot=state.slot, signed=True)
    shard_blocks = [shard_block]

    next_slots(spec, state, 3)

    shard_transition = spec.get_shard_transition(state, shard, shard_blocks)
    shard_transitions = [spec.ShardTransition()] * len(state.shard_states)
    shard_transitions[shard] = shard_transition

    attestation = get_valid_on_time_attestation(
        spec,
        state,
        slot=state.slot,
        index=committee_index,
        shard_transition=shard_transition,
        signed=True,
    )
    attestations = [attestation]

    pre_gasprice = state.shard_states[shard].gasprice
    offset_slots = spec.get_offset_slots(state, shard)
    assert len(offset_slots) == 3

    yield from run_crosslinks_processing(spec, state, shard_transitions, attestations)

    shard_state = state.shard_states[shard]
    assert shard_state.slot == offset_slots[-1]
    assert shard_state.latest_block_root == shard_block.message.hash_tree_root()
    assert shard_state == shard_transition.shard_states[len(shard_transition.shard_states) - 1]
    assert shard_state.gasprice > pre_gasprice
